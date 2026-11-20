"""Provider metadata + session IDs only. No OAuth tokens, passwords or transcripts."""
import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


class ProviderName(models.TextChoices):
    CODEX = "CODEX", "Codex"
    CLAUDE = "CLAUDE", "Claude Code"


class AuthState(models.TextChoices):
    UNKNOWN = "UNKNOWN", "Unknown"
    AUTH_REQUIRED = "AUTH_REQUIRED", "Sign in required"
    AUTHENTICATED = "AUTHENTICATED", "Authenticated"


class ProviderProfile(models.Model):
    """Created/verified by an authorized worker, not by a public registration API."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="ai_provider_profiles")
    provider = models.CharField(max_length=10, choices=ProviderName.choices)
    enabled = models.BooleanField(default=False)
    auth_state = models.CharField(max_length=16, choices=AuthState.choices,
                                  default=AuthState.UNKNOWN)
    policy_approved = models.BooleanField(default=False)
    runtime_isolated = models.BooleanField(default=False)
    data_export_approved = models.BooleanField(default=False)
    quota_available = models.BooleanField(default=False)
    verified_auth_epoch = models.PositiveBigIntegerField(default=0)
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "provider"], name="agw_user_provider_unique"),
        ]


class SessionPurpose(models.TextChoices):
    ANALYSIS = "ANALYSIS", "Independent first pass"
    ISSUE_REVIEW = "ISSUE_REVIEW", "Disagreement review"


class SessionState(models.TextChoices):
    NEW = "NEW", "New"
    PAUSED = "PAUSED", "Ready to resume"
    RECOVERABLE = "RECOVERABLE", "Recoverable"
    RESET_REQUIRED = "RESET_REQUIRED", "Reset required"
    ARCHIVED = "ARCHIVED", "Historical"


class SessionBinding(models.Model):
    """Never return provider_session_id or OS workspace path through provider APIs."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(ProviderProfile, on_delete=models.PROTECT,
                                related_name="session_bindings")
    notice = models.ForeignKey("procurement.Notice", on_delete=models.PROTECT,
                               related_name="ai_session_bindings")
    purpose = models.CharField(max_length=16, choices=SessionPurpose.choices,
                               default=SessionPurpose.ANALYSIS)
    issue_key = models.CharField(max_length=64, blank=True, default="")
    provider_session_id = models.UUIDField(null=True, blank=True)
    last_notice_version = models.ForeignKey("procurement.NoticeVersion",
                                            on_delete=models.PROTECT, null=True,
                                            blank=True, related_name="+")
    state = models.CharField(max_length=20, choices=SessionState.choices,
                             default=SessionState.NEW)
    is_current = models.BooleanField(default=True)
    lease_owner = models.CharField(max_length=80, blank=True, default="")
    lease_epoch = models.PositiveBigIntegerField(default=1)
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["profile", "notice", "purpose", "issue_key"],
                condition=models.Q(is_current=True),
                name="agw_one_current_session_per_context",
            ),
            models.CheckConstraint(
                condition=(models.Q(purpose="ANALYSIS", issue_key="")
                           | (models.Q(purpose="ISSUE_REVIEW") & ~models.Q(issue_key=""))),
                name="agw_issue_key_matches_purpose",
            ),
            models.CheckConstraint(
                condition=models.Q(lease_epoch__gte=1),
                name="agw_session_lease_epoch_positive",
            ),
        ]
