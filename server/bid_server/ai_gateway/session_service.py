"""AGW-04: persist and fence provider sessions; no CLI calls or credentials.

Only a trusted backend worker may call these functions. Authentication, notice scope,
approved evidence classification and job-owner permission must be checked by the
calling workflow; this service also checks user identity, provider readiness and
current NoticeVersion. Expired external calls are UNCERTAIN, never auto-retried.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import ProviderProfile, SessionBinding, SessionPurpose, SessionState
from .service import _to_core_profile


class SessionLeaseError(Exception):
    """Stable code only. Never place provider session IDs in log/error messages."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class AcquiredSession:
    binding_id: uuid.UUID
    fence: int
    provider: str
    notice_version_id: uuid.UUID
    provider_session_id: uuid.UUID | None = field(default=None, repr=False)


def _owner_and_ready(*, actor, profile, now):
    if (
        actor is None or not getattr(actor, "is_authenticated", False)
        or not actor.is_active or actor.must_change_password
        or (actor.locked_until is not None and actor.locked_until > now)
        or profile.user_id != actor.pk
    ):
        raise SessionLeaseError("UNAUTHORIZED_OWNER")
    if not _to_core_profile(profile, actor, now).ready:
        raise SessionLeaseError("PROVIDER_NOT_READY")


def _validate_context(purpose, issue_key, worker_id=None):
    if purpose not in SessionPurpose.values:
        raise SessionLeaseError("INVALID_PURPOSE")
    if purpose == SessionPurpose.ANALYSIS and issue_key:
        raise SessionLeaseError("INVALID_ISSUE_CONTEXT")
    if purpose == SessionPurpose.ISSUE_REVIEW and not re.fullmatch(
        r"[a-zA-Z0-9_.-]{1,64}", issue_key
    ):
        raise SessionLeaseError("INVALID_ISSUE_CONTEXT")
    if worker_id is not None and not re.fullmatch(r"[a-zA-Z0-9_.-]{1,64}", worker_id):
        raise SessionLeaseError("INVALID_WORKER_ID")


def acquire_session(
    *,
    actor,
    profile_id,
    notice,
    notice_version_id,
    worker_id: str,
    purpose: str = SessionPurpose.ANALYSIS,
    issue_key: str = "",
    lease_seconds: int = 240,
) -> AcquiredSession:
    """Acquire exactly one session lease. Never create a new session on CLI failure."""
    _validate_context(purpose, issue_key, worker_id)
    if type(lease_seconds) is not int or not 30 <= lease_seconds <= 600:
        raise SessionLeaseError("INVALID_LEASE_DURATION")
    if not getattr(notice, "pk", None) or not notice_version_id:
        raise SessionLeaseError("INVALID_NOTICE")
    try:
        requested_version = uuid.UUID(str(notice_version_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise SessionLeaseError("INVALID_NOTICE_VERSION") from exc

    expired = False
    result = None
    with transaction.atomic():
        now = timezone.now()
        profile = ProviderProfile.objects.select_for_update().get(pk=profile_id)
        _owner_and_ready(actor=actor, profile=profile, now=now)
        # Latest notice version is authoritative, not caller-supplied model state.
        from bid_server.procurement.models import Notice
        db_notice = Notice.objects.select_for_update().get(pk=notice.pk)
        if db_notice.current_version_id is None or db_notice.current_version_id != requested_version:
            raise SessionLeaseError("STALE_NOTICE_VERSION")
        binding, _ = SessionBinding.objects.select_for_update().get_or_create(
            profile=profile, notice=db_notice, purpose=purpose, issue_key=issue_key,
            is_current=True,
        )
        if binding.state in (SessionState.RESET_REQUIRED, SessionState.ARCHIVED):
            raise SessionLeaseError("SESSION_RESET_REQUIRES_REVIEW")
        if binding.state == SessionState.RECOVERABLE:
            raise SessionLeaseError("SESSION_RECOVERY_REQUIRES_REVIEW")
        if binding.lease_owner:
            if binding.lease_expires_at is not None and binding.lease_expires_at > now:
                raise SessionLeaseError("SESSION_IN_USE")
            # Previous CLI invocation may have consumed tokens and advanced session;
            # revoke its fence, block new calls until a separately audited recovery.
            binding.lease_epoch += 1
            binding.lease_owner = ""
            binding.lease_expires_at = None
            binding.state = SessionState.RECOVERABLE
            binding.save(update_fields=[
                "lease_epoch", "lease_owner", "lease_expires_at", "state"
            ])
            expired = True
        else:
            binding.lease_epoch += 1
            binding.lease_owner = worker_id
            binding.lease_expires_at = now + timedelta(seconds=lease_seconds)
            binding.last_notice_version_id = requested_version
            binding.save(update_fields=[
                "lease_epoch", "lease_owner", "lease_expires_at", "last_notice_version"
            ])
            result = AcquiredSession(
                binding_id=binding.pk, fence=binding.lease_epoch,
                provider=profile.provider, notice_version_id=requested_version,
                provider_session_id=binding.provider_session_id,
            )
    if expired:
        raise SessionLeaseError("EXPIRED_EXTERNAL_CALL_UNCERTAIN")
    return result


def _locked_owned_lease(*, actor, binding_id, fence, worker_id, now):
    binding = (
        SessionBinding.objects.select_for_update()
        .select_related("profile", "notice")
        .get(pk=binding_id)
    )
    if binding.profile.user_id != getattr(actor, "pk", None):
        raise SessionLeaseError("UNAUTHORIZED_OWNER")
    if (
        type(fence) is not int or binding.lease_epoch != fence
        or binding.lease_owner != worker_id or not binding.is_current
        or binding.lease_expires_at is None or binding.lease_expires_at <= now
    ):
        raise SessionLeaseError("STALE_SESSION_FENCE")
    _owner_and_ready(actor=actor, profile=binding.profile, now=now)
    return binding


def finish_session(
    *,
    actor,
    lease: AcquiredSession,
    worker_id: str,
    observed_session_id,
) -> None:
    """Save a verified provider thread id and release lease; never reset silently."""
    _validate_context(SessionPurpose.ANALYSIS, "", worker_id)
    try:
        observed = uuid.UUID(str(observed_session_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise SessionLeaseError("INVALID_SESSION_ID") from exc
    failure = None
    with transaction.atomic():
        now = timezone.now()
        binding = _locked_owned_lease(
            actor=actor, binding_id=lease.binding_id,
            fence=lease.fence, worker_id=worker_id, now=now,
        )
        if (
            binding.profile.provider != lease.provider
            or binding.last_notice_version_id != lease.notice_version_id
        ):
            raise SessionLeaseError("SESSION_CONTEXT_MISMATCH")
        if binding.provider_session_id is not None and binding.provider_session_id != observed:
            binding.state = SessionState.RESET_REQUIRED
            failure = "PROVIDER_SESSION_MISMATCH"
        elif binding.notice.current_version_id != lease.notice_version_id:
            binding.state = SessionState.RECOVERABLE
            failure = "STALE_NOTICE_VERSION"
        else:
            binding.provider_session_id = observed
            binding.state = SessionState.PAUSED
            binding.last_success_at = now
        binding.lease_owner = ""
        binding.lease_expires_at = None
        binding.lease_epoch += 1
        binding.save(update_fields=[
            "provider_session_id", "state", "last_success_at",
            "lease_owner", "lease_expires_at", "lease_epoch",
        ])
    if failure:
        raise SessionLeaseError(failure)


def fail_session(
    *,
    actor,
    lease: AcquiredSession,
    worker_id: str,
    error_code: str,
) -> None:
    """Preserve original session ID; provider timeouts never auto-create a new one."""
    _validate_context(SessionPurpose.ANALYSIS, "", worker_id)
    if error_code not in {
        "CODEX_TIMEOUT", "CODEX_PROCESS_FAILED", "CODEX_TURN_FAILED",
        "AUTH_REQUIRED", "QUOTA_LIMITED", "SESSION_MISSING",
        "INVALID_RESULT_JSON", "UNAVAILABLE", "SESSION_CONTAMINATED",
    }:
        raise SessionLeaseError("INVALID_FAILURE_CODE")
    with transaction.atomic():
        binding = _locked_owned_lease(
            actor=actor, binding_id=lease.binding_id,
            fence=lease.fence, worker_id=worker_id, now=timezone.now(),
        )
        binding.state = (
            SessionState.RESET_REQUIRED if error_code in {
                "SESSION_MISSING", "SESSION_CONTAMINATED"
            } else SessionState.RECOVERABLE
        )
        binding.lease_owner = ""
        binding.lease_expires_at = None
        binding.lease_epoch += 1
        binding.save(update_fields=[
            "state", "lease_owner", "lease_expires_at", "lease_epoch"
        ])


def approve_recovery(*, actor, binding_id, reviewed_safe_to_resume: bool) -> None:
    """Trusted recovery action, NOT exposed to a generic user request/HTTP API."""
    if reviewed_safe_to_resume is not True:
        raise SessionLeaseError("REVIEW_REQUIRED")
    with transaction.atomic():
        binding = SessionBinding.objects.select_for_update().select_related("profile").get(
            pk=binding_id
        )
        now = timezone.now()
        _owner_and_ready(actor=actor, profile=binding.profile, now=now)
        if binding.state != SessionState.RECOVERABLE or binding.lease_owner:
            raise SessionLeaseError("NOT_RECOVERABLE")
        binding.state = (
            SessionState.PAUSED if binding.provider_session_id else SessionState.NEW
        )
        binding.save(update_fields=["state"])
