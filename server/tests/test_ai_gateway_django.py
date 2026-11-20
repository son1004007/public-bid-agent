"""AGW-01 Django integration: account isolation, no token transport, no model egress."""
from datetime import timedelta
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from bid_server.accounts.models import User
from bid_server.ai_gateway.models import (
    AuthState, ProviderName, ProviderProfile, SessionBinding, SessionPurpose,
)
from bid_server.procurement.models import Notice


PASSWORD = "Synthetic!SecureProfile50"


class ProviderStatusAPITests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="agw-owner", password=PASSWORD, must_change_password=False
        )
        self.other = User.objects.create_user(
            username="agw-other", password=PASSWORD, must_change_password=False
        )
        self.client = APIClient(enforce_csrf_checks=True)

    def login_as(self, username):
        client = APIClient(enforce_csrf_checks=True)
        csrf = client.get("/api/v1/auth/csrf", secure=True)
        self.assertEqual(csrf.status_code, 200)
        token = csrf.json()["data"]["csrf_token"]
        result = client.post(
            "/api/v1/auth/login",
            {"username": username, "password": PASSWORD},
            secure=True, format="json",
            HTTP_X_CSRFTOKEN=token, HTTP_ORIGIN="https://testserver",
        )
        self.assertEqual(result.status_code, 200)
        return client

    def add_provider(self, user, provider=ProviderName.CODEX, **overrides):
        fields = dict(enabled=True, auth_state=AuthState.AUTHENTICATED,
                      policy_approved=True, runtime_isolated=True,
                      data_export_approved=True, quota_available=True,
                      verified_auth_epoch=user.auth_epoch,
                      verified_at=timezone.now())
        fields.update(overrides)
        return ProviderProfile.objects.create(user=user, provider=provider, **fields)

    def test_unauthenticated_cannot_get_provider_list(self):
        self.assertEqual(self.client.get("/api/v1/ai/providers", secure=True).status_code, 401)

    def test_no_provider_registration_fails_closed(self):
        client = self.login_as(self.owner.username)
        result = client.get("/api/v1/ai/providers", secure=True)
        self.assertEqual(result.status_code, 200)
        data = result.json()["data"]
        self.assertEqual(data["plan_mode"], "NO_AI")
        self.assertEqual([p["availability_state"] for p in data["providers"]],
                         ["NOT_REGISTERED", "NOT_REGISTERED"])
        self.assertEqual(result["Cache-Control"], "no-store")
        self.assertTrue(data["execution_requires_explicit_request"])

    def test_single_ready(self):
        self.add_provider(self.owner)
        client = self.login_as(self.owner.username)
        data = client.get("/api/v1/ai/providers", secure=True).json()["data"]
        self.assertEqual(data["plan_mode"], "SINGLE_CODEX")
        self.assertEqual(data["providers"][0]["availability_state"], "READY")

    def test_two_ready(self):
        self.add_provider(self.owner)
        self.add_provider(self.owner, ProviderName.CLAUDE)
        data = self.login_as(self.owner.username).get(
            "/api/v1/ai/providers", secure=True
        ).json()["data"]
        self.assertEqual(data["plan_mode"], "DUAL_INDEPENDENT")

    def test_user_b_cannot_see_user_a(self):
        self.add_provider(self.owner)
        data = self.login_as(self.other.username).get(
            "/api/v1/ai/providers", secure=True
        ).json()["data"]
        self.assertEqual(data["plan_mode"], "NO_AI")

    def test_registered_but_disabled_not_ready(self):
        self.add_provider(self.owner, enabled=False)
        data = self.login_as(self.owner.username).get(
            "/api/v1/ai/providers", secure=True
        ).json()["data"]
        self.assertEqual(data["plan_mode"], "NO_AI")
        self.assertEqual(data["providers"][0]["availability_state"], "DISABLED")

    def test_policy_unknown_prevents_execution(self):
        self.add_provider(self.owner, policy_approved=False)
        data = self.login_as(self.owner.username).get(
            "/api/v1/ai/providers", secure=True
        ).json()["data"]
        self.assertEqual(data["plan_mode"], "NO_AI")
        self.assertEqual(data["providers"][0]["availability_state"], "POLICY_BLOCKED")

    def test_login_status_stale_blocks_execution(self):
        self.add_provider(self.owner, verified_at=timezone.now() - timedelta(hours=1))
        data = self.login_as(self.owner.username).get(
            "/api/v1/ai/providers", secure=True
        ).json()["data"]
        self.assertEqual(data["plan_mode"], "NO_AI")
        self.assertEqual(data["providers"][0]["availability_state"], "AUTH_REQUIRED")

    def test_auth_epoch_change_invalidates_provider_ready(self):
        self.add_provider(self.owner, verified_auth_epoch=self.owner.auth_epoch + 1)
        data = self.login_as(self.owner.username).get(
            "/api/v1/ai/providers", secure=True
        ).json()["data"]
        self.assertEqual(data["plan_mode"], "NO_AI")

    def test_post_cannot_register_or_force_ready(self):
        client = self.login_as(self.owner.username)
        result = client.post("/api/v1/ai/providers",
                             {"provider": "CODEX", "enabled": True},
                             format="json", secure=True)
        self.assertEqual(result.status_code, 405)
        self.assertFalse(ProviderProfile.objects.exists())

    def test_session_id_never_exposed_in_provider_list(self):
        p = self.add_provider(self.owner)
        notice = Notice.objects.create(source="SYNTHETIC_FIXTURE",
                                       notice_number="AGW-NOTICE-00001")
        session = SessionBinding.objects.create(
            profile=p, notice=notice,
            provider_session_id="01a1f6a7-9dd4-7843-99bb-bca6bf1d73ca",
        )
        response = self.login_as(self.owner.username).get(
            "/api/v1/ai/providers", secure=True
        )
        self.assertNotIn(str(session.provider_session_id), response.content.decode())
        self.assertNotIn("provider_session_id", response.content.decode())


class ProviderPersistenceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="agw-db", password=PASSWORD, must_change_password=False
        )
        self.profile = ProviderProfile.objects.create(user=self.owner, provider=ProviderName.CODEX)
        self.notice = Notice.objects.create(source="SYNTHETIC_FIXTURE",
                                            notice_number="AGW-PERSIST-00001")

    def test_only_one_profile_per_user_provider(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ProviderProfile.objects.create(user=self.owner, provider=ProviderName.CODEX)

    def test_same_analysis_session_cannot_be_recreated_while_current(self):
        first = SessionBinding.objects.create(profile=self.profile, notice=self.notice)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SessionBinding.objects.create(profile=self.profile, notice=self.notice)
        first.is_current = False
        first.save(update_fields=["is_current"])
        second = SessionBinding.objects.create(profile=self.profile, notice=self.notice)
        self.assertNotEqual(first.pk, second.pk)

    def test_issue_review_requires_separate_issue_key(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SessionBinding.objects.create(
                    profile=self.profile, notice=self.notice,
                    purpose=SessionPurpose.ISSUE_REVIEW, issue_key=""
                )
        SessionBinding.objects.create(
            profile=self.profile, notice=self.notice,
            purpose=SessionPurpose.ISSUE_REVIEW, issue_key="CASE-1"
        )
        SessionBinding.objects.create(profile=self.profile, notice=self.notice)
        self.assertEqual(SessionBinding.objects.count(), 2)
