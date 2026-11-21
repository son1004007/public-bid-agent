"""실제 PostgreSQL 잠금 검증. SQLite 결과로 동시성을 주장하지 않는다.
경계: 합성 계정/임시 DB만 사용. thread별 연결 종료, 제한 시간 내 완료.
관련: 문서29. 암호 변경 1회 commit 및 비활성화/로그인 경합 검증.
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from unittest import skipUnless
from unittest.mock import patch
from django.db import connection, connections, transaction
from django.test import TransactionTestCase, override_settings
from rest_framework.test import APIClient
from bid_server.accounts.models import User, AuthEvent
from bid_server.accounts import views
from .test_auth import OLD, NEW

@skipUnless(connection.vendor == "postgresql", "requires isolated PostgreSQL")
@override_settings(ROOT_URLCONF="tests.auth_urls")
class PostgreSQLConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="concurrency-fixture", password=OLD)

    def client_token(self, authenticated=True):
        client = APIClient(enforce_csrf_checks=True)
        token = client.get("/api/v1/auth/csrf", secure=True).json()["data"]["csrf_token"]
        if authenticated:
            response = client.post("/api/v1/auth/login", {"username": self.user.username, "password": OLD}, format="json", secure=True, HTTP_X_CSRFTOKEN=token, HTTP_ORIGIN="https://testserver")
            self.assertEqual(response.status_code, 200)
            token = client.get("/api/v1/auth/csrf", secure=True).json()["data"]["csrf_token"]
        return client, token

    def test_concurrent_password_change_has_one_commit(self):
        clients = [self.client_token() for _ in range(2)]
        barrier = Barrier(2, timeout=10)
        original = views.parse
        def synchronized_parse(cls, request):
            data = original(cls, request)
            if cls is views.PasswordInput:
                barrier.wait()
            return data
        def change(pair):
            client, token = pair
            try:
                response = client.post("/api/v1/auth/change-password", {"current_password": OLD, "new_password": NEW, "expected_auth_epoch": 1}, format="json", secure=True, HTTP_X_CSRFTOKEN=token, HTTP_ORIGIN="https://testserver")
                return response.status_code
            finally:
                connections.close_all()
        with patch.object(views, "parse", synchronized_parse), ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(change, clients))
        self.assertEqual(sorted(results), [204, 409])
        self.user.refresh_from_db()
        self.assertEqual(self.user.auth_epoch, 2)
        self.assertEqual(AuthEvent.objects.filter(kind="password_changed").count(), 1)

    def test_login_waits_for_disable_commit(self):
        client, token = self.client_token(authenticated=False)
        started = Event()
        def attempt():
            try:
                started.set()
                return client.post("/api/v1/auth/login", {"username": self.user.username, "password": OLD}, format="json", secure=True, HTTP_X_CSRFTOKEN=token, HTTP_ORIGIN="https://testserver").status_code
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                user = User.objects.select_for_update().get(pk=self.user.pk)
                future = pool.submit(attempt)
                self.assertTrue(started.wait(5))
                user.is_active = False
                user.save(update_fields=["is_active"])
            self.assertEqual(future.result(timeout=15), 401)
        self.assertEqual(AuthEvent.objects.filter(kind="login").count(), 0)
