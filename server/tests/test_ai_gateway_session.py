"""AGW-04 synthetic Django/PostgreSQL session binding and fencing acceptance."""
import uuid
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from bid_server.accounts.models import User
from bid_server.procurement.models import Notice, NoticeVersion
from bid_server.ai_gateway.models import (
    AuthState, ProviderName, ProviderProfile,
    SessionBinding, SessionState, SessionPurpose,
)
from bid_server.ai_gateway.session_service import (
    SessionLeaseError, acquire_session, finish_session,
    fail_session, approve_recovery,
)

SESSION_A = uuid.UUID("11111111-2222-4333-8444-555555555555")
SESSION_B = uuid.UUID("22222222-3333-4444-8555-666666666666")


class SessionLeaseTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_user(
            username="agw-lease-owner", password="Synthetic!Only5512", must_change_password=False
        )
        self.other = User.objects.create_user(
            username="agw-lease-other", password="Synthetic!Only5512", must_change_password=False
        )
        self.notice = Notice.objects.create(source="SYNTHETIC_FIXTURE", notice_number="AGW-LEASE-1")
        self.version = self.new_version(1)
        self.notice.current_version = self.version
        self.notice.save(update_fields=["current_version"])
        self.profile = self.profile_for(self.actor, ProviderName.CODEX)
        self.worker = "test-worker-01"

    def new_version(self, seq):
        return NoticeVersion.objects.create(
            notice=self.notice, version_seq=seq, observed_at=timezone.now(),
            title=f"Synthetic project {seq}", buyer="Synthetic Public Office",
            source_payload_digest="a" * 64,
        )

    def profile_for(self, user, provider):
        return ProviderProfile.objects.create(
            user=user, provider=provider, enabled=True,
            auth_state=AuthState.AUTHENTICATED, policy_approved=True,
            runtime_isolated=True, data_export_approved=True, quota_available=True,
            verified_auth_epoch=user.auth_epoch, verified_at=timezone.now(),
        )

    def acquire(self, **override):
        fields = dict(actor=self.actor, profile_id=self.profile.pk, notice=self.notice,
                      notice_version_id=self.version.pk, worker_id=self.worker)
        fields.update(override)
        return acquire_session(**fields)

    def complete(self, lease, session_id=SESSION_A, **override):
        fields = dict(actor=self.actor, lease=lease, worker_id=self.worker,
                      observed_session_id=session_id)
        fields.update(override)
        return finish_session(**fields)

    def test_new_then_resume_same_persistent_uuid(self):
        first = self.acquire()
        self.assertIsNone(first.provider_session_id)
        self.complete(first)
        second = self.acquire()
        self.assertEqual(second.binding_id, first.binding_id)
        self.assertEqual(second.provider_session_id, SESSION_A)
        self.complete(second)
        self.assertEqual(SessionBinding.objects.count(), 1)

    def test_same_session_double_acquire_blocked(self):
        first = self.acquire()
        with self.assertRaisesRegex(SessionLeaseError, "SESSION_IN_USE"):
            self.acquire(worker_id="worker-02")
        self.complete(first)

    def test_provider_owner_must_match_actor(self):
        with self.assertRaisesRegex(SessionLeaseError, "UNAUTHORIZED_OWNER"):
            self.acquire(actor=self.other)
        self.assertFalse(SessionBinding.objects.exists())

    def test_profile_disabled_blocks_new_session(self):
        self.profile.enabled = False
        self.profile.save(update_fields=["enabled"])
        with self.assertRaisesRegex(SessionLeaseError, "PROVIDER_NOT_READY"):
            self.acquire()
        self.assertFalse(SessionBinding.objects.exists())

    def test_auth_epoch_change_blocks_session_resume(self):
        self.actor.auth_epoch += 1
        self.actor.save(update_fields=["auth_epoch"])
        with self.assertRaisesRegex(SessionLeaseError, "PROVIDER_NOT_READY"):
            self.acquire()

    def test_stale_notice_version_cannot_start(self):
        stale = self.new_version(2)
        with self.assertRaisesRegex(SessionLeaseError, "STALE_NOTICE_VERSION"):
            self.acquire(notice_version_id=stale.pk)

    def test_claude_and_codex_sessions_are_independent(self):
        claude = self.profile_for(self.actor, ProviderName.CLAUDE)
        codex = self.acquire()
        other = self.acquire(profile_id=claude.pk, worker_id="claude-worker")
        self.assertNotEqual(codex.binding_id, other.binding_id)
        self.complete(codex)
        finish_session(actor=self.actor, lease=other, worker_id="claude-worker",
                       observed_session_id=SESSION_B)

    def test_analysis_and_issue_session_are_separate(self):
        analysis = self.acquire()
        issue = self.acquire(purpose=SessionPurpose.ISSUE_REVIEW,
                             issue_key="R1-eligibility", worker_id="review-worker")
        self.assertNotEqual(analysis.binding_id, issue.binding_id)
        with self.assertRaisesRegex(SessionLeaseError, "INVALID_ISSUE_CONTEXT"):
            self.acquire(purpose=SessionPurpose.ISSUE_REVIEW, issue_key="")

    def test_external_timeout_preserves_id_until_review(self):
        first = self.acquire()
        self.complete(first)
        followup = self.acquire()
        fail_session(actor=self.actor, lease=followup, worker_id=self.worker,
                     error_code="CODEX_TIMEOUT")
        binding = SessionBinding.objects.get(pk=first.binding_id)
        self.assertEqual(binding.provider_session_id, SESSION_A)
        self.assertEqual(binding.state, SessionState.RECOVERABLE)
        with self.assertRaisesRegex(SessionLeaseError, "RECOVERY_REQUIRES_REVIEW"):
            self.acquire()
        with self.assertRaisesRegex(SessionLeaseError, "REVIEW_REQUIRED"):
            approve_recovery(actor=self.actor, binding_id=binding.pk,
                             reviewed_safe_to_resume=False)
        approve_recovery(actor=self.actor, binding_id=binding.pk,
                         reviewed_safe_to_resume=True)
        renewed = self.acquire()
        self.assertEqual(renewed.provider_session_id, SESSION_A)

    def test_expired_lease_is_not_auto_retried(self):
        first = self.acquire()
        SessionBinding.objects.filter(pk=first.binding_id).update(
            lease_expires_at=timezone.now() - timedelta(seconds=1)
        )
        with self.assertRaisesRegex(SessionLeaseError, "EXPIRED_EXTERNAL_CALL_UNCERTAIN"):
            self.acquire(worker_id="new-worker")
        binding = SessionBinding.objects.get(pk=first.binding_id)
        self.assertEqual(binding.state, SessionState.RECOVERABLE)
        self.assertEqual(binding.lease_owner, "")
        with self.assertRaisesRegex(SessionLeaseError, "RECOVERY_REQUIRES_REVIEW"):
            self.acquire()
        with self.assertRaisesRegex(SessionLeaseError, "STALE_SESSION_FENCE"):
            self.complete(first)

    def test_old_worker_fence_cannot_publish(self):
        first = self.acquire()
        self.complete(first)
        with self.assertRaisesRegex(SessionLeaseError, "STALE_SESSION_FENCE"):
            self.complete(first)

    def test_provider_session_id_change_requires_reset(self):
        first = self.acquire()
        self.complete(first)
        renewed = self.acquire()
        with self.assertRaisesRegex(SessionLeaseError, "PROVIDER_SESSION_MISMATCH"):
            self.complete(renewed, SESSION_B)
        binding = SessionBinding.objects.get(pk=first.binding_id)
        self.assertEqual(binding.state, SessionState.RESET_REQUIRED)
        self.assertEqual(binding.provider_session_id, SESSION_A)
        with self.assertRaisesRegex(SessionLeaseError, "SESSION_RESET_REQUIRES_REVIEW"):
            self.acquire()

    def test_notice_correction_during_call_blocks_publication(self):
        first = self.acquire()
        newer = self.new_version(2)
        self.notice.current_version = newer
        self.notice.save(update_fields=["current_version"])
        with self.assertRaisesRegex(SessionLeaseError, "STALE_NOTICE_VERSION"):
            self.complete(first)
        binding = SessionBinding.objects.get(pk=first.binding_id)
        self.assertEqual(binding.state, SessionState.RECOVERABLE)

    def test_other_user_cannot_finish_lease(self):
        first = self.acquire()
        with self.assertRaisesRegex(SessionLeaseError, "UNAUTHORIZED_OWNER"):
            self.complete(first, actor=self.other)
        self.complete(first)

    def test_first_call_invalid_session_id_is_rejected(self):
        first = self.acquire()
        with self.assertRaisesRegex(SessionLeaseError, "INVALID_SESSION_ID"):
            self.complete(first, session_id="--fake-session")

    def test_failure_does_not_reset_first_session(self):
        first = self.acquire()
        fail_session(actor=self.actor, lease=first, worker_id=self.worker,
                     error_code="CODEX_PROCESS_FAILED")
        row = SessionBinding.objects.get(pk=first.binding_id)
        self.assertIsNone(row.provider_session_id)
        self.assertEqual(row.state, SessionState.RECOVERABLE)
