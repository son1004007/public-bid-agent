"""AGW-05 trusted, *offline* review of public RFP provenance.

No downloads, provider calls, key handling or user-facing approval API.
Trusted reviewer supplies exact raw bytes already acquired through an approved
ingestion route; this service binds their SHA-256 to immutable document/notice
versions. Approval is not a provider execution or account/egress authorization.
"""
from __future__ import annotations

import hashlib
from urllib.parse import parse_qsl, urlsplit

from django.db import transaction
from django.utils import timezone

from bid_server.procurement.models import DocumentFreshness, DocumentVersion
from .models import PublicRfpAttestation

# Official government/G2B endpoints verified in procurement agency open API docs.
# Exact host comparison prevents attacker.example.g2b.go.kr.evil.test confusion.
OFFICIAL_HOSTS = frozenset({
    "www.g2b.go.kr", "g2b.go.kr", "data.g2b.go.kr",
    "apis.data.go.kr", "www.data.go.kr",
})
_SECRET_PARAMS = frozenset({
    "servicekey", "apikey", "api_key", "access_token",
    "token", "authorization", "secret",
})


class PublicSourceError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def official_source_url(value: str) -> bool:
    if type(value) is not str or len(value) > 2048 or any(
        x in value for x in ("\x00", "\n", "\r", "\\")
    ):
        return False
    try:
        url = urlsplit(value)
        if (
            url.scheme != "https" or url.hostname not in OFFICIAL_HOSTS
            or url.username is not None or url.password is not None
            or url.port not in (None, 443) or url.fragment
        ):
            return False
        if any(k.lower() in _SECRET_PARAMS for k, _ in
               parse_qsl(url.query, keep_blank_values=True)):
            return False
        return bool(url.path and url.path.startswith("/"))
    except (ValueError, TypeError):
        return False


def approve_official_public_document(
    *,
    reviewer,
    document_version_id,
    raw_document_bytes: bytes,
    raw_notice_payload_bytes: bytes,
    provider_export_approved: bool = False,
) -> PublicRfpAttestation:
    """Explicit staff-only approval after actual bytes-to-DB digest match.

    This operation creates an attestation record but never triggers a paid call.
    Revocations intentionally cannot silently be reversed on the same
    DocumentVersion. A newly reviewed, immutable version is required.
    """
    if (
        reviewer is None or not getattr(reviewer, "is_authenticated", False)
        or not reviewer.is_active or not reviewer.is_staff
        or getattr(reviewer, "must_change_password", True)
    ):
        raise PublicSourceError("REVIEWER_NOT_AUTHORIZED")
    if type(provider_export_approved) is not bool:
        raise PublicSourceError("INVALID_EXPORT_APPROVAL")
    if (
        type(raw_document_bytes) is not bytes
        or type(raw_notice_payload_bytes) is not bytes
        or not 1 <= len(raw_document_bytes) <= 20 * 1024 * 1024
        or not 1 <= len(raw_notice_payload_bytes) <= 8 * 1024 * 1024
    ):
        raise PublicSourceError("INVALID_SOURCE_BYTES")
    with transaction.atomic():
        try:
            doc = (
                DocumentVersion.objects.select_related(
                    "document", "notice_version", "notice_version__notice",
                ).select_for_update().get(pk=document_version_id)
            )
        except DocumentVersion.DoesNotExist as exc:
            raise PublicSourceError("UNKNOWN_DOCUMENT_VERSION") from exc
        notice_version = doc.notice_version
        notice = notice_version.notice
        if (
            notice.source != "G2B_OFFICIAL_API"
            or notice.current_version_id != notice_version.pk
            or notice_version.cancellation
            or doc.document.notice_id != notice.pk
            or doc.freshness != DocumentFreshness.CURRENT
            or not doc.shared_read_approved
            or doc.size_bytes != len(raw_document_bytes)
            or not official_source_url(doc.source_url)
            or not official_source_url(notice_version.source_url)
        ):
            raise PublicSourceError("PUBLIC_SOURCE_NOT_VERIFIED")
        doc_digest = hashlib.sha256(raw_document_bytes).hexdigest()
        notice_digest = hashlib.sha256(raw_notice_payload_bytes).hexdigest()
        if doc.sha256 != doc_digest or notice_version.source_payload_digest != notice_digest:
            raise PublicSourceError("PUBLIC_SOURCE_BYTES_MISMATCH")
        if PublicRfpAttestation.objects.filter(document_version=doc).exists():
            raise PublicSourceError("ATTESTATION_ALREADY_EXISTS")
        return PublicRfpAttestation.objects.create(
            document_version=doc, approved_by=reviewer,
            notice_source_sha256=notice_digest,
            document_sha256=doc_digest,
            source_url=doc.source_url,
            packet_approved=True,
            provider_export_approved=provider_export_approved,
            revoked=False, reviewed_at=timezone.now(),
        )
