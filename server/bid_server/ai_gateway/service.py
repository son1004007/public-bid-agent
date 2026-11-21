"""Fail-closed provider status. Read-only queries; no CLI or model invocation."""
from datetime import timedelta
from django.utils import timezone

from ai_gateway_core.planning import Provider, Profile, select_plan
from .models import AuthState, ProviderProfile

READINESS_TTL_SECONDS = 300
MAX_CLOCK_SKEW_SECONDS = 30


def _to_core_profile(record, user, now):
    if record is None:
        return None
    verified_recently = (
        record.verified_at is not None
        and now - timedelta(seconds=READINESS_TTL_SECONDS) <= record.verified_at
        <= now + timedelta(seconds=MAX_CLOCK_SKEW_SECONDS)
        and record.verified_auth_epoch == user.auth_epoch
    )
    return Profile(
        provider=Provider(record.provider),
        registered=True,
        enabled=record.enabled,
        authenticated=record.auth_state == AuthState.AUTHENTICATED and verified_recently,
        execution_contract_approved=record.policy_approved,
        runtime_isolated=record.runtime_isolated,
        data_export_approved=record.data_export_approved,
        quota_available=record.quota_available,
    )


def provider_status_for_user(user):
    """Only the authenticated Django user; never return session IDs or secrets."""
    if user is None or not user.is_authenticated or user.must_change_password:
        raise PermissionError("USER_NOT_AUTHORIZED")
    records = {r.provider: r for r in ProviderProfile.objects.filter(user=user)}
    now = timezone.now()
    statuses = []
    profiles = []
    for provider in Provider:
        record = records.get(provider.value)
        if record is None:
            statuses.append({
                "provider": provider.value, "registered": False, "enabled": False,
                "availability_state": "NOT_REGISTERED", "checked_at": None,
            })
            continue
        core = _to_core_profile(record, user, now)
        profiles.append(core)
        if not record.enabled:
            state = "DISABLED"
        elif not record.policy_approved or not record.data_export_approved:
            state = "POLICY_BLOCKED"
        elif not record.runtime_isolated:
            state = "RUNTIME_UNAVAILABLE"
        elif core.authenticated is False:
            state = "AUTH_REQUIRED"
        elif not record.quota_available:
            state = "QUOTA_LIMITED"
        else:
            state = "READY"
        statuses.append({
            "provider": provider.value, "registered": True, "enabled": record.enabled,
            "availability_state": state,
            "checked_at": record.verified_at.isoformat() if record.verified_at else None,
        })
    plan = select_plan(profiles)
    return {
        "plan_mode": plan.mode.value,
        "providers": statuses,
        "execution_requires_explicit_request": plan.requires_explicit_run_request,
    }
