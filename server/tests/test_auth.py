"""SM03 합성 보안 통합 계약.
목적: A01 강제변경, A02 역할, CSRF/세션/실패/원자성/보존 검증.
경계: 임시 테스트 DB와 합성 사용자만 사용. 실제 운영 계정/자료를 읽지 않는다.
관련: 문서29. PostgreSQL 동시성은 test_auth_concurrency로 분리한다.
"""
import time
from datetime import timedelta
from unittest.mock import patch
from django.conf import settings
from django.contrib.auth import SESSION_KEY
from django.contrib.sessions.models import Session
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from bid_server.accounts.models import User, AuthEvent, LoginBucket

OLD = "Synthetic!Initial39Blue"
NEW = "Changed!Independent74Green"

@override_settings(ROOT_URLCONF="tests.auth_urls")
class AuthenticationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="synthetic-reviewer", password=OLD)
        self.client = self.client_for()

    def client_for(self):
        return APIClient(enforce_csrf_checks=True)

    def csrf(self, client=None):
        client = client or self.client
        response = client.get("/api/v1/auth/csrf", secure=True)
        self.assertEqual(response.status_code, 200)
        return response.json()["data"]["csrf_token"]

    def post(self, path, data, client=None):
        client = client or self.client
        token = self.csrf(client)
        return client.post(path, data, format="json", secure=True, HTTP_X_CSRFTOKEN=token, HTTP_ORIGIN="https://testserver")

    def login(self, client=None, password=OLD, username="synthetic-reviewer"):
        return self.post("/api/v1/auth/login", {"username": username, "password": password}, client)

    def change(self, **kwargs):
        self.user.refresh_from_db()
        data = {"current_password": OLD, "new_password": NEW, "expected_auth_epoch": self.user.auth_epoch}
        data.update(kwargs)
        return self.post("/api/v1/auth/change-password", data)

    def full(self, role="lead"):
        self.user.must_change_password = False
        self.user.role = role
        self.user.save()
        self.assertEqual(self.login().status_code, 200)

    def contain(self, mode, answers, passwords=()):
        from io import StringIO
        from django.core.management import call_command
        output = StringIO()
        with patch("sys.stdin.isatty", return_value=True), patch("sys.stderr.isatty", return_value=True), \
                patch("builtins.input", side_effect=answers), patch("getpass.getpass", side_effect=passwords):
            call_command("contain_account", mode, stdout=output)
        self.assertNotIn(OLD, output.getvalue())
        self.assertNotIn(NEW, output.getvalue())

    def test_operator_rotation_revokes_old_sessions_and_requires_new_password_change(self):
        self.full()
        other = self.client_for()
        self.assertEqual(self.login(other).status_code, 200)
        self.user.refresh_from_db()
        epoch = self.user.auth_epoch
        self.contain("--rotate", [self.user.username, "ROTATE"], [NEW, NEW])
        self.user.refresh_from_db()
        self.assertEqual(self.user.auth_epoch, epoch + 1)
        self.assertTrue(self.user.must_change_password)
        self.assertTrue(self.user.check_password(NEW))
        self.assertFalse(self.user.check_password(OLD))
        self.assertIsNotNone(self.user.password_changed_at)
        self.assertGreater(self.user.temporary_expires_at, timezone.now())
        for client in (self.client, other):
            self.assertEqual(client.get("/api/v1/auth/session", secure=True).status_code, 401)
        self.assertEqual(self.login(password=OLD).status_code, 401)
        response = self.login(password=NEW)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["access"], "PASSWORD_CHANGE_REQUIRED")
        self.assertTrue(AuthEvent.objects.filter(kind="operator_password_reset", actor=None).exists())

    def test_operator_disable_revokes_session_and_cannot_enable_by_rotation(self):
        from django.core.management.base import CommandError
        self.full()
        other = User.objects.create_user(username="unrelated-fixture", password=OLD)
        self.user.refresh_from_db()
        epoch = self.user.auth_epoch
        self.contain("--disable", [self.user.username, "DISABLE"])
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertFalse(self.user.has_usable_password())
        self.assertEqual(self.user.auth_epoch, epoch + 1)
        self.assertEqual(self.client.get("/api/v1/auth/session", secure=True).status_code, 401)
        with self.assertRaises(CommandError):
            self.contain("--rotate", [self.user.username, "ROTATE"], [NEW, NEW])
        self.user.refresh_from_db()
        other.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertTrue(other.is_active)
        self.assertTrue(other.check_password(OLD))

    def test_operator_command_cancel_reuse_and_noninteractive_fail_closed(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError
        original = self.user.auth_epoch
        with patch("sys.stdin.isatty", return_value=False), self.assertRaises(CommandError):
            call_command("contain_account", "--disable")
        for answers, passwords in (([self.user.username, "CANCEL"], []),
                                   ([self.user.username, "ROTATE"], [OLD, OLD]),
                                   ([self.user.username, "ROTATE"], [NEW, OLD])):
            with self.subTest(answers=answers), self.assertRaises(CommandError):
                self.contain("--rotate", answers, passwords)
        self.user.refresh_from_db()
        self.assertEqual(self.user.auth_epoch, original)
        self.assertTrue(self.user.check_password(OLD))
        self.assertTrue(self.user.is_active)
        self.assertFalse(AuthEvent.objects.filter(kind__startswith="operator_").exists())

    def test_defaults_first_migration_and_hash(self):
        self.assertTrue(self.user.must_change_password)
        self.assertEqual(self.user.role, "lead")
        self.assertEqual(self.user.auth_epoch, 1)
        self.assertNotEqual(self.user.password, OLD)
        self.assertTrue(self.user.check_password(OLD))
        self.assertGreater(self.user.temporary_expires_at, timezone.now())
        self.assertEqual(settings.AUTH_USER_MODEL, "accounts.User")

    def test_role_and_epoch_database_constraints(self):
        for values in ({"role": "owner"}, {"auth_epoch": 0}):
            with self.subTest(values=values), self.assertRaises(IntegrityError), transaction.atomic():
                User.objects.filter(pk=self.user.pk).update(**values)

    def test_login_limited_response_no_secrets(self):
        response = self.login()
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["access"], "PASSWORD_CHANGE_REQUIRED")
        self.assertEqual(data["user"]["capabilities"], [])
        for value in (OLD, self.user.password, "temporary_expires_at"):
            self.assertNotIn(value, response.content.decode())

    def test_a01_exact_allowlist_blocks_all_other_paths(self):
        self.login()
        for path in ("/api/v1/health", "/fixture/business", "/fixture/decision", "/admin/", "/api/v1/missing", "/api/v1/auth/session/", "/api/v1/auth/login"):
            with self.subTest(path=path):
                response = self.client.get(path, secure=True)
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json()["error"]["code"], "PASSWORD_CHANGE_REQUIRED")
        self.assertEqual(self.client.get("/api/v1/auth/session", secure=True).status_code, 200)
        self.assertEqual(self.post("/api/v1/auth/logout", {}).status_code, 204)

    def test_limited_and_expired_session_can_reopen_auth_shell_only(self):
        self.assertEqual(self.login().status_code, 200)
        for path in ("/", "/workspace"):
            page = self.client.get(path, secure=True)
            self.assertEqual(page.status_code, 200)
            self.assertContains(page, 'id="passwordForm"')
            self.assertEqual(page["Cache-Control"], "no-store")
            self.assertEqual(self.client.get("/api/v1/notices", secure=True).status_code, 403)
        self.assertEqual(self.post("/workspace", {}).status_code, 403)
        self.assertEqual(self.client.get("/api/v1/auth/session", secure=True).json()["data"]["access"],
                         "PASSWORD_CHANGE_REQUIRED")

        session = self.client.session
        session["login_at"] = time.time() - 901
        session["last_seen"] = time.time()
        session.save()
        self.assertEqual(self.client.get("/workspace", secure=True).status_code, 200)
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertEqual(self.client.get("/api/v1/auth/session", secure=True).status_code, 401)
        self.assertEqual(self.client.get("/api/v1/notices", secure=True).status_code, 401)

    def test_workspace_script_hash_and_no_inline_handlers(self):
        import base64
        import hashlib
        import re
        page = self.client.get("/workspace", secure=True)
        self.assertEqual(page.status_code, 200)
        text = page.content.decode("utf-8")
        scripts = re.findall(r"<script>(.*?)</script>", text, flags=re.S)
        self.assertEqual(len(scripts), 1)
        digest = base64.b64encode(hashlib.sha256(scripts[0].encode("utf-8")).digest()).decode("ascii")
        policy = page["Content-Security-Policy"]
        self.assertIn("script-src 'sha256-" + digest + "'", policy)
        self.assertIn("script-src-attr 'none'", policy)
        self.assertIn("connect-src 'self'", policy)
        self.assertIn("frame-ancestors 'none'", policy)
        self.assertEqual(page["Referrer-Policy"], "no-referrer")
        self.assertNotRegex(text.split("<script>", 1)[0], r"\son[a-z]+\s*=")

    def test_a01_superuser_has_no_gate_exemption(self):
        self.user.is_superuser = True
        self.user.is_staff = True
        self.user.save()
        self.login()
        self.assertEqual(self.client.get("/fixture/decision", secure=True).status_code, 403)

    def test_a02_lead_cannot_decide_manage_users_or_secrets(self):
        self.full()
        self.assertEqual(self.client.get("/fixture/business", secure=True).status_code, 200)
        for path in ("decision", "accounts", "secrets"):
            self.assertEqual(self.post("/fixture/" + path, {"role": "director", "actor": str(self.user.pk)}).status_code, 403)

    def test_a02_director_can_access_role_fixture(self):
        self.full("director")
        self.assertEqual(self.client.get("/fixture/decision", secure=True).status_code, 200)

    def test_a02_technical_superuser_is_not_director(self):
        self.user.is_superuser = True
        self.user.save()
        self.full()
        self.assertEqual(self.client.get("/fixture/decision", secure=True).status_code, 403)

    def test_anonymous_session_and_business_denied(self):
        for path in ("/api/v1/auth/session", "/fixture/business"):
            self.assertEqual(self.client.get(path, secure=True).status_code, 401)

    def test_login_csrf_missing_wrong_and_foreign_origin(self):
        data = {"username": self.user.username, "password": OLD}
        self.assertEqual(self.client.post("/api/v1/auth/login", data, format="json", secure=True).status_code, 403)
        token = self.csrf()
        self.assertEqual(self.client.post("/api/v1/auth/login", data, format="json", secure=True, HTTP_X_CSRFTOKEN="x"*32).status_code, 403)
        self.assertEqual(self.client.post("/api/v1/auth/login", data, format="json", secure=True, HTTP_X_CSRFTOKEN=token, HTTP_ORIGIN="https://foreign.invalid").status_code, 403)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_change_and_logout_require_csrf(self):
        self.login()
        for path in ("change-password", "logout"):
            self.assertEqual(self.client.post("/api/v1/auth/"+path, {}, format="json", secure=True).status_code, 403)
        self.assertEqual(AuthEvent.objects.filter(kind="password_changed").count(), 0)

    def test_csrf_rotation_and_session_fixation(self):
        before = self.csrf()
        session = self.client.session
        session["untrusted"] = "fixture"
        session.save()
        old_key = session.session_key
        self.login()
        self.assertNotEqual(self.client.session.session_key, old_key)
        self.assertNotIn("untrusted", self.client.session)
        self.assertFalse(Session.objects.filter(session_key=old_key).exists())
        self.assertEqual(self.client.post("/api/v1/auth/logout", {}, format="json", secure=True, HTTP_X_CSRFTOKEN=before).status_code, 403)
        self.assertTrue(self.client.cookies["sessionid"]["httponly"])
        self.assertTrue(self.client.cookies["sessionid"]["secure"])
        self.assertEqual(self.client.cookies["sessionid"]["samesite"], "Lax")

    def test_change_atomic_success_and_forced_relogin(self):
        self.login()
        self.assertEqual(self.change().status_code, 204)
        self.user.refresh_from_db()
        self.assertFalse(self.user.must_change_password)
        self.assertIsNone(self.user.temporary_expires_at)
        self.assertIsNotNone(self.user.password_changed_at)
        self.assertEqual(self.user.auth_epoch, 2)
        self.assertTrue(self.user.check_password(NEW))
        self.assertEqual(AuthEvent.objects.filter(kind="password_changed").count(), 1)
        self.assertEqual(self.client.get("/api/v1/auth/session", secure=True).status_code, 401)
        self.assertEqual(self.login(password=NEW).json()["data"]["access"], "FULL")

    def test_other_session_revoked_after_password_change(self):
        other = self.client_for()
        self.login(other)
        self.login()
        self.change()
        self.assertEqual(other.get("/api/v1/auth/session", secure=True).status_code, 401)
        self.assertNotIn(SESSION_KEY, other.session)

    def test_password_change_stale_epoch(self):
        self.login()
        self.assertEqual(self.change(expected_auth_epoch=99).status_code, 409)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(OLD))

    def test_wrong_current_password_no_change(self):
        self.login()
        self.assertEqual(self.change(current_password="wrong").status_code, 422)
        self.user.refresh_from_db()
        self.assertEqual(self.user.auth_epoch, 1)

    def test_password_policy_reuse_short_numeric_common_similar_long(self):
        self.login()
        for password in (OLD, "Short!x", "123456789012345", "password123456", "synthetic-reviewer123", "X!"*65):
            with self.subTest(password_case=len(password)):
                self.assertEqual(self.change(new_password=password).status_code, 422)
        self.assertEqual(AuthEvent.objects.filter(kind="password_changed").count(), 0)

    def test_unknown_fields_cannot_override_identity_or_gate(self):
        response = self.post("/api/v1/auth/login", {"username": self.user.username, "password": OLD, "role": "director"})
        self.assertEqual(response.status_code, 422)
        self.login()
        self.assertEqual(self.change(must_change_password=False).status_code, 422)

    def test_change_audit_failure_rolls_back_and_keeps_session(self):
        self.login()
        self.client.raise_request_exception = False
        with patch("bid_server.accounts.views.AuthEvent.objects.create", side_effect=RuntimeError("PRIVATE_FIXTURE")):
            response = self.change()
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("PRIVATE_FIXTURE", response.content.decode())
        self.user.refresh_from_db()
        self.assertEqual(self.user.auth_epoch, 1)
        self.assertTrue(self.user.must_change_password)
        self.assertTrue(self.user.check_password(OLD))
        self.assertEqual(self.client.get("/api/v1/auth/session", secure=True).status_code, 200)

    def test_expired_temporary_password_login_rejected(self):
        self.user.temporary_expires_at = timezone.now()-timedelta(seconds=1)
        self.user.save()
        self.assertEqual(self.login().status_code, 401)

    def test_inactive_and_unknown_login_have_same_error(self):
        self.user.is_active = False
        self.user.save()
        one = self.login().json()["error"]
        two = self.login(username="missing-user").json()["error"]
        self.assertEqual(one, two)

    def test_lock_rejects_valid_password(self):
        self.user.locked_until = timezone.now()+timedelta(minutes=1)
        self.user.save()
        self.assertEqual(self.login().status_code, 401)

    def test_pair_rate_limit_persists_and_has_no_raw_identifiers(self):
        for _ in range(5):
            self.assertEqual(self.login(password="wrong").status_code, 401)
        response = self.login()
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response["Retry-After"], "900")
        for bucket in LoginBucket.objects.all():
            self.assertNotIn(self.user.username, bucket.key)
            self.assertNotIn("127.0.0.1", bucket.key)

    @override_settings(AUTH_IP_FAILURES=2)
    def test_ip_rate_limit_across_usernames(self):
        self.assertEqual(self.login(username="unknown-one").status_code, 401)
        self.assertEqual(self.login(username="unknown-two").status_code, 401)
        self.assertEqual(self.login(username="unknown-three").status_code, 429)

    def test_rate_limit_expires(self):
        for _ in range(5):
            self.login(password="wrong")
        LoginBucket.objects.update(started_at=timezone.now()-timedelta(minutes=20), locked_until=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.login().status_code, 200)

    def test_security_field_changes_increment_epoch(self):
        self.full()
        self.user.role = "director"
        self.user.save(update_fields=["role"])
        self.assertEqual(self.client.get("/api/v1/auth/session", secure=True).status_code, 401)

    def test_inactive_residual_session_flushed(self):
        self.login()
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        self.assertEqual(self.client.get("/api/v1/auth/session", secure=True).status_code, 401)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_stale_model_save_cannot_restore_security_state(self):
        stale = User.objects.get(pk=self.user.pk)
        self.user.role = "director"
        self.user.save()
        stale.last_login = timezone.now()
        with self.assertRaises(ValueError):
            stale.save(update_fields=["last_login"])
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, "director")

    def test_nonsecurity_update_does_not_bump_epoch(self):
        self.user.display_name = "Synthetic Display"
        self.user.save(update_fields=["display_name"])
        self.user.refresh_from_db()
        self.assertEqual(self.user.auth_epoch, 1)

    def test_session_expiry_idle_absolute_and_limited(self):
        for key, age in (("last_seen", 1801), ("login_at", 28801), ("login_at", 901)):
            with self.subTest(key=key, age=age):
                self.assertEqual(self.login().status_code, 200)
                session = self.client.session
                session[key] = time.time()-age
                session.save()
                self.assertEqual(self.client.get("/api/v1/auth/session", secure=True).status_code, 401)

    def test_session_missing_epoch_and_future_time_rejected(self):
        for mode in ("missing", "future"):
            self.login()
            session = self.client.session
            if mode == "missing":
                session.pop("auth_epoch")
            else:
                session["login_at"] = time.time()+60
            session.save()
            self.assertEqual(self.client.get("/api/v1/auth/session", secure=True).status_code, 401)

    def test_corrupted_session_fields_fail_closed(self):
        for key, value in (
            ("auth_epoch", True), ("login_at", float("nan")),
            ("last_seen", float("inf")), ("last_seen", True),
            ("login_at", 10 ** 400), ("last_seen", 0),
        ):
            with self.subTest(key=key, value=str(value)[:20]):
                self.login()
                session = self.client.session
                session[key] = value
                session.save()
                self.assertEqual(self.client.get("/api/v1/auth/session", secure=True).status_code, 401)

    def test_logout_csrf_and_idempotent_empty_response(self):
        self.login()
        for _ in range(2):
            response = self.post("/api/v1/auth/logout", {})
            self.assertEqual(response.status_code, 204)
            self.assertEqual(response.content, b"")

    def test_create_superuser_is_limited_lead(self):
        admin = User.objects.create_superuser(username="technical-only", password=OLD)
        self.assertEqual(admin.role, "lead")
        self.assertTrue(admin.must_change_password)

    @override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.PBKDF2PasswordHasher"])
    def test_production_hash_path_and_password_change(self):
        self.user.set_password(OLD)
        self.user.save(update_fields=["password"])
        self.assertTrue(self.user.password.startswith("pbkdf2_sha256$"))
        self.assertEqual(self.login().status_code, 200)
        self.assertEqual(self.change().status_code, 204)
        self.user.refresh_from_db()
        self.assertTrue(self.user.password.startswith("pbkdf2_sha256$"))
        self.assertTrue(self.user.check_password(NEW))

    def test_login_audit_failure_does_not_create_usable_session(self):
        self.client.raise_request_exception = False
        with patch("bid_server.accounts.views.AuthEvent.objects.create", side_effect=RuntimeError("PRIVATE_FIXTURE")):
            response = self.login()
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("PRIVATE_FIXTURE", response.content.decode())
        self.assertEqual(self.client.get("/api/v1/auth/session", secure=True).status_code, 401)

    def test_relogin_rotates_full_session(self):
        self.full()
        old = self.client.session.session_key
        self.assertEqual(self.login().status_code, 200)
        self.assertNotEqual(old, self.client.session.session_key)
        self.assertFalse(Session.objects.filter(session_key=old).exists())

    def test_auth_response_openapi_schemas(self):
        import json
        from pathlib import Path
        from jsonschema import Draft202012Validator, FormatChecker
        spec = json.loads((Path(__file__).resolve().parents[1] / "openapi.json").read_text(encoding="utf-8"))
        for response, name in ((self.client.get("/api/v1/auth/csrf", secure=True), "CsrfResponse"),
                               (self.login(), "SessionResponse"),
                               (self.client.get("/api/v1/auth/session", secure=True), "SessionResponse")):
            self.assertEqual(response.status_code, 200)
            Draft202012Validator({"$ref": "#/components/schemas/" + name, "components": spec["components"]}, format_checker=FormatChecker()).validate(response.json())

    def test_password_cannot_match_display_name(self):
        self.user.display_name = "SyntheticDisplayName"
        self.user.save(update_fields=["display_name"])
        self.login()
        self.assertEqual(self.change(new_password="SyntheticDisplayName123").status_code, 422)

    def test_array_inputs_rejected_as_validation_errors(self):
        self.assertEqual(self.post("/api/v1/auth/login", []).status_code, 422)
        self.assertEqual(self.post("/api/v1/auth/logout", []).status_code, 422)

    def test_temporary_expiry_between_requests_flushes_session(self):
        self.login()
        # 합성 DB에서만 epoch 변경 없이 시각 경과를 재현한다.
        User.objects.filter(pk=self.user.pk).update(temporary_expires_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.client.get("/api/v1/auth/session", secure=True).status_code, 401)
        self.assertNotIn(SESSION_KEY, self.client.session)
