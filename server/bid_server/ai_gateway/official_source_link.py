"""P0-02 offline, append-only verified official raw source <-> legacy DB link.

This operation NEVER makes a document PUBLIC, alters a historical NoticeVersion
digest, fetches the network, changes ACL, or invokes a provider. Call only from
a trusted staff-only workflow after reading exact bytes from approved private
storage (with filesystem read-only validation performed by the caller).
The permanent link preserves BOTH official response byte SHA and the existing
legacy-importer canonical metadata SHA. Postgres has an additional DB trigger.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile

from django.db import transaction
from django.utils import timezone

from ai_gateway_core.official_g2b_capture import (
    API_URL, CAPTURE_DIR, MAX_BYTES, CaptureError, _no_duplicate_keys,
    _official_attachment, _official_response,
)
from bid_server.procurement.models import (
    DocumentFreshness, DocumentVersion, Notice, NoticeVersion,
)
from .models import OfficialSourceLink
from .public_source import official_source_url


class SourceLinkError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


_HEX64 = re.compile(r"[a-f0-9]{64}\Z")
_SOURCE_KEYS = frozenset({
    "status", "notice_number", "source_revision",
    "notice_sha256", "notice_size_bytes",
    "document_sha256", "document_size_bytes", "document_type",
    "official_api_operation", "capture_id",
    "notice_storage_key", "document_storage_key",
    "document_storage_scope", "document_bytes_copied",
    "document_reference_validation", "attestation_state",
})


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _staff(actor) -> bool:
    now = timezone.now()
    locked_until = getattr(actor, "locked_until", None)
    return bool(
        actor is not None
        and getattr(actor, "is_authenticated", False)
        and actor.is_active and actor.is_staff
        and not getattr(actor, "must_change_password", True)
        and (locked_until is None or locked_until <= now)
    )


def _manifest(
    *,
    manifest_bytes: bytes,
    raw_notice_payload_bytes: bytes,
    raw_document_bytes: bytes,
) -> dict:
    if (
        type(manifest_bytes) is not bytes or not 1 <= len(manifest_bytes) <= 8192
        or type(raw_notice_payload_bytes) is not bytes
        or type(raw_document_bytes) is not bytes
        or not 1 <= len(raw_notice_payload_bytes) <= MAX_BYTES
        or not 1 <= len(raw_document_bytes) <= MAX_BYTES
    ):
        raise SourceLinkError("INVALID_SOURCE_BYTES")
    try:
        doc = json.loads(
            manifest_bytes.decode("utf-8"), object_pairs_hook=_no_duplicate_keys,
        )
    except (ValueError, TypeError, UnicodeError, CaptureError):
        raise SourceLinkError("INVALID_CAPTURE_MANIFEST") from None
    if type(doc) is not dict or set(doc) != _SOURCE_KEYS:
        raise SourceLinkError("INVALID_CAPTURE_MANIFEST")
    n_sha = _sha(raw_notice_payload_bytes)
    d_sha = _sha(raw_document_bytes)
    rev = doc["source_revision"]
    number = doc["notice_number"]
    if (
        type(number) is not str or not re.fullmatch(r"[A-Za-z0-9-]{4,32}", number)
        or type(rev) is not str or not re.fullmatch(r"[0-9]{1,5}", rev)
        or type(doc["notice_sha256"]) is not str
        or type(doc["document_sha256"]) is not str
        or not _HEX64.fullmatch(doc["notice_sha256"])
        or not _HEX64.fullmatch(doc["document_sha256"])
        or doc["notice_sha256"] != n_sha
        or doc["document_sha256"] != d_sha
        or type(doc["notice_size_bytes"]) is not int
        or type(doc["document_size_bytes"]) is not int
        or doc["notice_size_bytes"] != len(raw_notice_payload_bytes)
        or doc["document_size_bytes"] != len(raw_document_bytes)
        or doc["status"] != "UNATTESTED_RAW_CAPTURE"
        or doc["document_type"] != "HWPX"
        or doc["official_api_operation"] != "getBidPblancListInfoServc02"
        or doc["document_storage_scope"] != "EXISTING_PRIVATE_MEDIA"
        or doc["document_reference_validation"] != "HASH_AND_KEY_ONLY"
        or doc["document_bytes_copied"] is not False
        or doc["attestation_state"] != "UNREVIEWED"
        or not zipfile.is_zipfile(io.BytesIO(raw_document_bytes))
    ):
        raise SourceLinkError("CAPTURE_INTEGRITY_MISMATCH")

    capture_id = _sha(f"{n_sha}:{d_sha}:{number}:{rev}".encode("utf-8"))
    expected_notice_key = f"{CAPTURE_DIR}/{capture_id}.notice.raw.json"
    expected_manifest_key = f"{CAPTURE_DIR}/{capture_id}.existing.manifest.json"
    if (
        doc["capture_id"] != capture_id
        or doc["notice_storage_key"] != expected_notice_key
        or doc["document_storage_key"] != f"public-rfp/{d_sha}.hwpx"
    ):
        raise SourceLinkError("CAPTURE_IDENTITY_MISMATCH")
    # Do not accept user-supplied paths. Derive the manifest filename from
    # a validated content-addressed capture ID rather than trusting a URL.
    doc["_validated_manifest_key"] = expected_manifest_key
    return doc


def _validate_current_link(
    *, notice_version, document_version, manifest, raw_notice_payload_bytes,
):
    current = notice_version.notice
    rev = manifest["source_revision"]
    if (
        current.source != "G2B_OFFICIAL_API"
        or current.current_version_id != notice_version.pk
        or notice_version.cancellation or notice_version.correction
        or not isinstance(notice_version.source_revision, str)
        or not notice_version.source_revision.isdecimal()
        or int(notice_version.source_revision) != int(rev)
        or document_version.notice_version_id != notice_version.pk
        or document_version.document.notice_id != current.pk
        or document_version.freshness != DocumentFreshness.CURRENT
        or document_version.owner_user_id is None
        or document_version.sha256 != manifest["document_sha256"]
        or document_version.size_bytes != manifest["document_size_bytes"]
        or document_version.storage_key != manifest["document_storage_key"]
        or current.notice_number != manifest["notice_number"]
        or not official_source_url(notice_version.source_url)
        or not _official_attachment(
            document_version.source_url, current.notice_number, rev,
        )
        or type(notice_version.source_payload_digest) is not str
        or not _HEX64.fullmatch(notice_version.source_payload_digest)
    ):
        raise SourceLinkError("SOURCE_VERSION_STALE_OR_UNVERIFIED")
    try:
        title = _official_response(
            raw_notice_payload_bytes, current.notice_number, rev,
        )
    except CaptureError:
        raise SourceLinkError("INVALID_OFFICIAL_NOTICE") from None
    # Fail closed on a same-revision different title rather than blessing
    # metadata drift as a verified source. No legacy digest is overwritten.
    if title.strip() != notice_version.title.strip():
        raise SourceLinkError("SAME_REVISION_METADATA_CONFLICT")


def _fields_for_link(*, doc, notice_version, manifest):
    return {
        "capture_id": manifest["capture_id"],
        "official_revision": manifest["source_revision"],
        "metadata_canonical_sha256": notice_version.source_payload_digest,
        "raw_notice_sha256": manifest["notice_sha256"],
        "raw_notice_size_bytes": manifest["notice_size_bytes"],
        "raw_notice_storage_key": manifest["notice_storage_key"],
        "manifest_storage_key": manifest["_validated_manifest_key"],
        "document_sha256": manifest["document_sha256"],
        "document_size_bytes": manifest["document_size_bytes"],
        "existing_document_storage_key": doc.storage_key,
    }


def _reconcile_locked(
    *, actor, notice_version_id, document_version_id,
    raw_notice_payload_bytes, raw_document_bytes, manifest_bytes, apply,
):
    if not _staff(actor):
        raise SourceLinkError("LINK_OPERATOR_NOT_AUTHORIZED")
    if type(apply) is not bool:
        raise SourceLinkError("INVALID_APPLY_MODE")
    manifest = _manifest(
        manifest_bytes=manifest_bytes,
        raw_notice_payload_bytes=raw_notice_payload_bytes,
        raw_document_bytes=raw_document_bytes,
    )
    with transaction.atomic():
        try:
            # The importer locks Notice before advancing current_version. Take
            # the same lock order for writes, then re-read and validate current.
            # Dry runs do not acquire write locks and can run on a read-only DB.
            initial_version = NoticeVersion.objects.only("notice_id").get(
                pk=notice_version_id,
            )
            if apply:
                Notice.objects.select_for_update().get(pk=initial_version.notice_id)
            version_query = NoticeVersion.objects.select_related("notice")
            doc_query = DocumentVersion.objects.select_related(
                "document", "notice_version", "owner_user",
            )
            if apply:
                version_query = version_query.select_for_update(of=("self",))
                # Only lock the concrete DocumentVersion row; owner_user is a
                # nullable LEFT OUTER JOIN and PostgreSQL forbids locking it.
                doc_query = doc_query.select_for_update(of=("self",))
            notice_version = version_query.get(pk=notice_version_id)
            doc = doc_query.get(pk=document_version_id)
        except (Notice.DoesNotExist, NoticeVersion.DoesNotExist,
                DocumentVersion.DoesNotExist):
            raise SourceLinkError("UNKNOWN_SOURCE_VERSION") from None
        _validate_current_link(
            notice_version=notice_version, document_version=doc,
            manifest=manifest, raw_notice_payload_bytes=raw_notice_payload_bytes,
        )
        fields = _fields_for_link(
            doc=doc, notice_version=notice_version, manifest=manifest,
        )
        old = OfficialSourceLink.objects.filter(document_version=doc).first()
        if old is not None:
            if old.notice_version_id != notice_version.pk or any(
                getattr(old, field) != value for field, value in fields.items()
            ):
                raise SourceLinkError("SOURCE_CAPTURE_CONFLICT")
            return old  # Idempotent replay; no write.
        if OfficialSourceLink.objects.filter(capture_id=manifest["capture_id"]).exists():
            raise SourceLinkError("SOURCE_CAPTURE_CONFLICT")
        if not apply:
            return None  # Full DB+byte validation, no persistent write.
        return OfficialSourceLink.objects.create(
            notice_version=notice_version,
            document_version=doc,
            linked_by=actor,
            **fields,
        )


def reconcile_official_source_capture(
    *,
    actor, notice_version_id, document_version_id,
    raw_notice_payload_bytes: bytes, raw_document_bytes: bytes,
    manifest_bytes: bytes, apply: bool = False,
) -> OfficialSourceLink | None:
    """Trusted offline operator: verify source/versions and optionally insert.

    By default this is read-only. A staff operator must explicitly set
    apply=True; this is NOT a PUBLIC packet approval or model export approval.
    Network I/O, filesystem operations and secret extraction are out of scope.
    """
    return _reconcile_locked(
        actor=actor, notice_version_id=notice_version_id,
        document_version_id=document_version_id,
        raw_notice_payload_bytes=raw_notice_payload_bytes,
        raw_document_bytes=raw_document_bytes,
        manifest_bytes=manifest_bytes, apply=apply,
    )


def verify_official_source_link(
    *,
    actor, document_version_id,
    raw_notice_payload_bytes: bytes, raw_document_bytes: bytes,
    manifest_bytes: bytes,
) -> OfficialSourceLink:
    """Revalidate stored immutable mapping against current data/bytes.

    This does not grant PUBLIC access, export, or automatic model execution.
    """
    try:
        link = OfficialSourceLink.objects.select_related(
            "document_version", "notice_version",
        ).get(document_version_id=document_version_id)
    except OfficialSourceLink.DoesNotExist:
        raise SourceLinkError("SOURCE_LINK_MISSING") from None
    result = _reconcile_locked(
        actor=actor, notice_version_id=link.notice_version_id,
        document_version_id=link.document_version_id,
        raw_notice_payload_bytes=raw_notice_payload_bytes,
        raw_document_bytes=raw_document_bytes,
        manifest_bytes=manifest_bytes, apply=False,
    )
    if result is None or result.pk != link.pk:
        raise SourceLinkError("SOURCE_LINK_MISSING")
    return result
