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


class ImmutableAnalysisQuerySet(models.QuerySet):
    """Block ordinary ORM update/delete of signed analysis history."""

    def update(self, **kwargs):
        raise ValueError("IMMUTABLE_ANALYSIS_HISTORY")

    def delete(self):
        raise ValueError("IMMUTABLE_ANALYSIS_HISTORY")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValueError("IMMUTABLE_ANALYSIS_HISTORY")


class ImmutableAnalysisManager(models.Manager.from_queryset(ImmutableAnalysisQuerySet)):
    pass


class AnalysisRun(models.Model):
    """One access-checked RFP snapshot reused unchanged for both providers.

    Model/ORM update and delete are forbidden. DB privileged raw SQL and direct
    bulk migrations remain outside this Python guard; production DB role grants
    and database-level immutability controls are still an AGW-13 gate.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                              related_name="ai_analysis_runs")
    notice_version = models.ForeignKey(
        "procurement.NoticeVersion", on_delete=models.PROTECT,
        related_name="ai_analysis_runs"
    )
    corpus_snapshot_id = models.UUIDField()
    request_key = models.UUIDField()
    input_digest = models.CharField(max_length=64)
    prompt_version = models.CharField(max_length=64)
    snapshot_sha256 = models.CharField(max_length=64)
    snapshot_payload = models.JSONField()
    created_at = models.DateTimeField(default=timezone.now)

    objects = ImmutableAnalysisManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "notice_version", "request_key"],
                name="agw_one_run_per_request_key",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("IMMUTABLE_ANALYSIS_HISTORY")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("IMMUTABLE_ANALYSIS_HISTORY")


class AnalysisRevision(models.Model):
    """Append-only, canonicalized evidence-bound model result; not a bid decision."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(AnalysisRun, on_delete=models.PROTECT,
                            related_name="revisions")
    provider = models.CharField(max_length=10, choices=ProviderName.choices)
    revision_seq = models.PositiveIntegerField()
    result_sha256 = models.CharField(max_length=64)
    validated_payload = models.JSONField()
    created_at = models.DateTimeField(default=timezone.now)

    objects = ImmutableAnalysisManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["run", "provider", "result_sha256"],
                name="agw_unique_result_digest",
            ),
            models.UniqueConstraint(
                fields=["run", "provider", "revision_seq"],
                name="agw_unique_result_revision",
            ),
            models.CheckConstraint(
                condition=models.Q(revision_seq__gte=1),
                name="agw_revision_seq_positive",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("IMMUTABLE_ANALYSIS_HISTORY")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("IMMUTABLE_ANALYSIS_HISTORY")


class PublicRfpAttestation(models.Model):
    """Explicit staff review of independently hashed official public bytes.

    Merely setting DocumentVersion.shared_read_approved or pointing at an
    official-looking URL does NOT establish public provenance or provider
    transmission permission. The trusted ingestion/review service must hash
    both raw notice metadata and attachment bytes before recording approval.
    This model does not grant permission to invoke a provider.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document_version = models.OneToOneField(
        "procurement.DocumentVersion", on_delete=models.PROTECT,
        related_name="public_rfp_attestation",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="public_rfp_attestations",
    )
    notice_source_sha256 = models.CharField(max_length=64)
    document_sha256 = models.CharField(max_length=64)
    source_url = models.TextField()
    packet_approved = models.BooleanField(default=False)
    provider_export_approved = models.BooleanField(default=False)
    revoked = models.BooleanField(default=False)
    reviewed_at = models.DateTimeField(default=timezone.now)


class ImmutableSourceLinkQuerySet(models.QuerySet):
    """No ordinary ORM mutation of previously captured official byte identities."""

    def update(self, **kwargs):
        raise ValueError("IMMUTABLE_OFFICIAL_SOURCE_LINK")

    def delete(self):
        raise ValueError("IMMUTABLE_OFFICIAL_SOURCE_LINK")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValueError("IMMUTABLE_OFFICIAL_SOURCE_LINK")


class ImmutableSourceLinkManager(models.Manager.from_queryset(ImmutableSourceLinkQuerySet)):
    pass


class OfficialSourceLink(models.Model):
    """P0-02: append-only cross-reference, not an approval or exported source.

    NoticeVersion.source_payload_digest is the historical canonical metadata
    digest and MUST NOT be changed to the raw official HTTP response digest.
    Raw bytes remain in a private, off-repository store; the database records
    independently checked sizes, digests, storage keys and exact FK identities.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notice_version = models.ForeignKey(
        "procurement.NoticeVersion", on_delete=models.PROTECT,
        related_name="official_source_links",
    )
    document_version = models.OneToOneField(
        "procurement.DocumentVersion", on_delete=models.PROTECT,
        related_name="official_source_link",
    )
    linked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="official_source_links",
    )
    capture_id = models.CharField(max_length=64, unique=True)
    official_revision = models.CharField(max_length=5)
    metadata_canonical_sha256 = models.CharField(max_length=64)
    raw_notice_sha256 = models.CharField(max_length=64)
    raw_notice_size_bytes = models.PositiveIntegerField()
    raw_notice_storage_key = models.CharField(max_length=160)
    manifest_storage_key = models.CharField(max_length=180)
    document_sha256 = models.CharField(max_length=64)
    document_size_bytes = models.PositiveIntegerField()
    existing_document_storage_key = models.CharField(max_length=180)
    linked_at = models.DateTimeField(default=timezone.now)

    objects = ImmutableSourceLinkManager()

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("IMMUTABLE_OFFICIAL_SOURCE_LINK")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("IMMUTABLE_OFFICIAL_SOURCE_LINK")

