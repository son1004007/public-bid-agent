"""AGW-05/09: authorized synthetic RFP snapshot and append-only result operations.

No model invocation, no customer/private RFP export, no public HTTP endpoint.
Only a trusted backend workflow may call these functions. First release
intentionally supports SYNTHETIC_FIXTURE documents only until corporate export
classification, ACL and provider terms are independently implemented.
"""
from __future__ import annotations

import hashlib
import uuid
from django.db import transaction
from django.utils import timezone

from ai_gateway_core.snapshot import (
    EvidenceSnapshot, SnapshotError, build_snapshot, canonical_json,
    payload_hash, verify_snapshot,
)
from ai_gateway_core.result_contract import (
    ResultContractError, validate_raw_result,
)
from bid_server.procurement.models import (
    Chunk, ChunkCategory, DocumentFreshness, ExtractionState,
    NoticeVersion,
)
from .models import AnalysisRun, AnalysisRevision, ProviderName, PublicRfpAttestation
from .public_source import official_source_url


class AnalysisServiceError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _uuid(value, code):
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise AnalysisServiceError(code) from exc


def _authorized_actor(actor):
    now = timezone.now()
    if (
        actor is None or not getattr(actor, "is_authenticated", False)
        or not actor.is_active or actor.must_change_password
        or (actor.locked_until is not None and actor.locked_until > now)
    ):
        raise AnalysisServiceError("UNAUTHORIZED_USER")


def _chunk_text(chunk):
    # Silent truncation hides later requirements and defeats full-source integrity.
    # Explicit chunking must happen in the trusted extraction pipeline instead.
    if type(chunk.text) is not str:
        raise AnalysisServiceError("INVALID_SOURCE_SPAN")
    full_bytes = chunk.text.encode("utf-8")
    if len(full_bytes) > 1800:
        raise AnalysisServiceError("SOURCE_CHUNK_TOO_LARGE")
    if not chunk.text.strip() or "\x00" in chunk.text:
        raise AnalysisServiceError("EMPTY_SOURCE_SPAN")
    return chunk.text


def _trusted_chunks(*, chunk_ids, expected_version, actor, source_mode="SYNTHETIC"):
    chunks = list(
        Chunk.objects.select_related(
            "extraction_run", "extraction_run__document_version",
            "extraction_run__document_version__document",
        ).filter(id__in=chunk_ids)
    )
    if len(chunks) != len(chunk_ids):
        raise AnalysisServiceError("UNKNOWN_SOURCE_CHUNK")
    by_id = {c.id: c for c in chunks}
    if set(by_id) != set(chunk_ids):
        raise AnalysisServiceError("UNKNOWN_SOURCE_CHUNK")
    for chunk in chunks:
        extraction = chunk.extraction_run
        doc = extraction.document_version
        if (
            extraction.state != ExtractionState.PARSED
            or doc.freshness != DocumentFreshness.CURRENT
            or doc.notice_version_id != expected_version.pk
            or doc.document.notice_id != expected_version.notice_id
            or not (doc.owner_user_id == actor.pk or doc.shared_read_approved)
        ):
            raise AnalysisServiceError("UNAPPROVED_OR_STALE_SOURCE")
        if source_mode == "PUBLIC":
            if (
                not doc.shared_read_approved
                or extraction.coverage.get("complete") is not True
                or extraction.warnings
                or doc.size_bytes <= 0
                or not official_source_url(doc.source_url)
                or not official_source_url(expected_version.source_url)
            ):
                raise AnalysisServiceError("PUBLIC_SOURCE_NOT_APPROVED")
            try:
                attestation = PublicRfpAttestation.objects.select_related(
                    "approved_by"
                ).get(document_version=doc)
            except PublicRfpAttestation.DoesNotExist as exc:
                raise AnalysisServiceError("PUBLIC_SOURCE_NOT_APPROVED") from exc
            if (
                attestation.revoked
                or not attestation.packet_approved
                or not attestation.provider_export_approved
                or not attestation.approved_by.is_active
                or not attestation.approved_by.is_staff
                or attestation.source_url != doc.source_url
                or attestation.document_sha256 != doc.sha256
                or attestation.notice_source_sha256 != expected_version.source_payload_digest
            ):
                raise AnalysisServiceError("PUBLIC_SOURCE_NOT_APPROVED")
        elif source_mode != "SYNTHETIC":
            raise AnalysisServiceError("INVALID_SOURCE_MODE")
    return by_id


def _verify_stored_provenance(*, packet, actor, version):
    """Re-read current database ACL/extraction and the exact chunk bytes."""
    if packet["notice_source_digest"] != version.source_payload_digest:
        raise AnalysisServiceError("STALE_NOTICE_SOURCE_DIGEST")
    rows = packet["requirements"] + packet["evidence"]
    ids = {_uuid(row["source_span_id"], "INVALID_SOURCE_SPAN") for row in rows}
    classes = packet["policy"]["classification_allowlist"]
    if classes == ["PUBLIC"] and version.notice.source == "G2B_OFFICIAL_API":
        source_mode = "PUBLIC"
    elif classes == ["SYNTHETIC"] and version.notice.source == "SYNTHETIC_FIXTURE":
        source_mode = "SYNTHETIC"
    else:
        raise AnalysisServiceError("SOURCE_CLASSIFICATION_MISMATCH")
    chunks = _trusted_chunks(
        chunk_ids=ids, expected_version=version, actor=actor, source_mode=source_mode,
    )
    for row in rows:
        chunk = chunks[_uuid(row["source_span_id"], "INVALID_SOURCE_SPAN")]
        doc = chunk.extraction_run.document_version
        excerpt = _chunk_text(chunk)
        expected_kind = (
            "QUALIFICATION" if chunk.category == ChunkCategory.QUALIFICATION
            else "TECHNICAL" if chunk.category == ChunkCategory.REQUIREMENT
            else None
        )
        if (
            row["source_document_id"] != str(doc.pk)
            or row["source_version"] != str(doc.pk)
            or row["document_sha256"] != doc.sha256
            or row["extraction_run_id"] != str(chunk.extraction_run_id)
            or (
                "required_kind" in row
                and row["required_kind"] != expected_kind
            )
            or row["excerpt"] != excerpt
            or row["source_hash"] != hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
        ):
            raise AnalysisServiceError("STALE_OR_TAMPERED_SOURCE")


def _input_digest(*, actor_id, notice_version_id, requirement_chunk_ids, evidence_chunk_ids,
                  request_key, prompt_version, source_mode):
    return payload_hash({
        "actor_id": str(actor_id), "notice_version_id": str(notice_version_id),
        "requirement_chunk_ids": sorted(str(x) for x in requirement_chunk_ids),
        "evidence_chunk_ids": sorted(str(x) for x in evidence_chunk_ids),
        "request_key": str(request_key), "prompt_version": prompt_version,
        "source_mode": source_mode,
    })


def _create_analysis_run(
    *,
    actor,
    notice_version_id,
    request_key,
    requirement_chunk_ids,
    evidence_chunk_ids,
    prompt_version="agw-v1",
    source_mode="SYNTHETIC",
):
    """Trusted service, NOT HTTP: immutable packet from reviewed source rows."""
    _authorized_actor(actor)
    version_id = _uuid(notice_version_id, "INVALID_NOTICE_VERSION")
    replay_key = _uuid(request_key, "INVALID_REQUEST_KEY")
    if (
        type(requirement_chunk_ids) not in (list, tuple)
        or type(evidence_chunk_ids) not in (list, tuple)
        or not 1 <= len(requirement_chunk_ids) <= 200
        or not 1 <= len(evidence_chunk_ids) <= 400
    ):
        raise AnalysisServiceError("INVALID_SOURCE_COUNT")
    req_ids = [_uuid(x, "INVALID_CHUNK_ID") for x in requirement_chunk_ids]
    evidence_ids = [_uuid(x, "INVALID_CHUNK_ID") for x in evidence_chunk_ids]
    if len(set(req_ids)) != len(req_ids) or len(set(evidence_ids)) != len(evidence_ids):
        raise AnalysisServiceError("DUPLICATE_SOURCE_CHUNK")
    digest = _input_digest(
        actor_id=actor.pk, notice_version_id=version_id,
        requirement_chunk_ids=req_ids, evidence_chunk_ids=evidence_ids,
        request_key=replay_key, prompt_version=prompt_version,
        source_mode=source_mode,
    )
    with transaction.atomic():
        try:
            version = NoticeVersion.objects.select_related("notice").get(pk=version_id)
        except NoticeVersion.DoesNotExist as exc:
            raise AnalysisServiceError("UNKNOWN_NOTICE_VERSION") from exc
        # Serialize against current-version changes and reject cancelled notices.
        from bid_server.procurement.models import Notice
        notice = Notice.objects.select_for_update().get(pk=version.notice_id)
        if (
            notice.current_version_id != version.pk or version.cancellation
            or (
                (source_mode == "SYNTHETIC" and notice.source != "SYNTHETIC_FIXTURE")
                or (source_mode == "PUBLIC" and notice.source != "G2B_OFFICIAL_API")
                or source_mode not in {"SYNTHETIC", "PUBLIC"}
            )
        ):
            raise AnalysisServiceError("STALE_OR_UNAPPROVED_NOTICE")
        existing = AnalysisRun.objects.filter(
            owner=actor, notice_version=version, request_key=replay_key
        ).first()
        if existing:
            if existing.input_digest != digest:
                raise AnalysisServiceError("REQUEST_KEY_REUSED_WITH_DIFFERENT_INPUT")
            verify_snapshot(
                EvidenceSnapshot(existing.snapshot_payload, existing.snapshot_sha256),
                expected_sha256=existing.snapshot_sha256,
            )
            _verify_stored_provenance(
                packet=existing.snapshot_payload, actor=actor, version=version
            )
            return existing
        chunks = _trusted_chunks(
            chunk_ids=set(req_ids + evidence_ids), expected_version=version,
            actor=actor, source_mode=source_mode,
        )
        requirements = []
        for c_id in req_ids:
            c = chunks[c_id]
            if c.category not in (ChunkCategory.QUALIFICATION, ChunkCategory.REQUIREMENT):
                raise AnalysisServiceError("NOT_REQUIREMENT_CHUNK")
            doc = c.extraction_run.document_version
            excerpt = _chunk_text(c)
            requirements.append({
                "requirement_id": "R-" + str(c.pk),
                "source_document_id": str(doc.pk),
                "source_version": str(doc.pk),
                "source_span_id": str(c.pk),
                "source_hash": hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
                "document_sha256": doc.sha256,
                "extraction_run_id": str(c.extraction_run_id),
                "required_kind": ("QUALIFICATION" if c.category == ChunkCategory.QUALIFICATION
                                  else "TECHNICAL"),
                "excerpt": excerpt, "extraction_state": "PARSED",
            })
        evidence = []
        for c_id in evidence_ids:
            c = chunks[c_id]
            doc = c.extraction_run.document_version
            excerpt = _chunk_text(c)
            evidence.append({
                "evidence_id": "E-" + str(c.pk), "evidence_type": "RFP",
                "source_document_id": str(doc.pk),
                "source_version": str(doc.pk), "source_span_id": str(c.pk),
                "source_hash": hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
                "document_sha256": doc.sha256,
                "extraction_run_id": str(c.extraction_run_id),
                "excerpt": excerpt, "classification": source_mode,
                "approved_for_provider": True,
                "requirement_ids": ["R-" + str(x) for x in req_ids],
            })
        run_id = uuid.uuid4()
        corpus_id = uuid.uuid4()
        packet = build_snapshot(
            run_id=str(run_id), notice_version_id=str(version.pk),
            notice_source_digest=version.source_payload_digest,
            corpus_snapshot_id=str(corpus_id), prompt_version=prompt_version,
            requirements=requirements, evidence=evidence,
            approved_document_ids=frozenset({
                str(c.extraction_run.document_version_id) for c in chunks.values()
            }),
            allowed_classifications=frozenset({source_mode}),
        )
        return AnalysisRun.objects.create(
            id=run_id, owner=actor, notice_version=version,
            corpus_snapshot_id=corpus_id, request_key=replay_key,
            input_digest=digest, prompt_version=prompt_version,
            snapshot_sha256=packet.sha256, snapshot_payload=packet.payload,
        )


def create_synthetic_analysis_run(
    *,
    actor,
    notice_version_id,
    request_key,
    requirement_chunk_ids,
    evidence_chunk_ids,
    prompt_version="agw-v1",
):
    """Existing synthetic-only entrypoint; no data egress or model calls."""
    return _create_analysis_run(
        actor=actor, notice_version_id=notice_version_id,
        request_key=request_key, requirement_chunk_ids=requirement_chunk_ids,
        evidence_chunk_ids=evidence_chunk_ids, prompt_version=prompt_version,
        source_mode="SYNTHETIC",
    )


def create_attested_public_analysis_run(
    *,
    actor,
    notice_version_id,
    request_key,
    requirement_chunk_ids,
    evidence_chunk_ids,
    prompt_version="agw-v1",
):
    """Trusted backend-only construction from reviewed official bytes/ACL.

    No public API, CLI, model or external network call is triggered here.
    All document versions must have a current staff byte-hash attestation.
    """
    return _create_analysis_run(
        actor=actor, notice_version_id=notice_version_id,
        request_key=request_key, requirement_chunk_ids=requirement_chunk_ids,
        evidence_chunk_ids=evidence_chunk_ids, prompt_version=prompt_version,
        source_mode="PUBLIC",
    )


def append_validated_result(
    *, actor, run_id, provider: str, raw_json: str,
    authorize_additional_revision=False,
) -> AnalysisRevision:
    """Idempotent append. New divergent revision needs explicit backend approval."""
    _authorized_actor(actor)
    if provider not in ProviderName.values:
        raise AnalysisServiceError("INVALID_PROVIDER")
    if authorize_additional_revision is not False and authorize_additional_revision is not True:
        raise AnalysisServiceError("INVALID_REVISION_AUTHORIZATION")
    with transaction.atomic():
        try:
            run = AnalysisRun.objects.select_for_update().select_related(
                "notice_version", "notice_version__notice"
            ).get(pk=_uuid(run_id, "INVALID_RUN_ID"))
        except AnalysisRun.DoesNotExist as exc:
            raise AnalysisServiceError("UNKNOWN_RUN") from exc
        if run.owner_id != actor.pk:
            raise AnalysisServiceError("UNAUTHORIZED_USER")
        if (
            run.notice_version.notice.current_version_id != run.notice_version_id
            or run.notice_version.cancellation
        ):
            raise AnalysisServiceError("STALE_NOTICE_VERSION")
        packet = EvidenceSnapshot(run.snapshot_payload, run.snapshot_sha256)
        try:
            verify_snapshot(packet, expected_sha256=run.snapshot_sha256)
            _verify_stored_provenance(
                packet=run.snapshot_payload, actor=actor, version=run.notice_version
            )
            validated = validate_raw_result(
                raw_json=raw_json, snapshot=packet, expected_provider=provider
            )
        except (ResultContractError, SnapshotError) as exc:
            raise AnalysisServiceError("RESULT_NOT_VALIDATED") from exc
        prior = list(
            AnalysisRevision.objects.filter(run=run, provider=provider)
            .order_by("revision_seq")
        )
        for revision in prior:
            if revision.result_sha256 == validated.sha256:
                if revision.validated_payload != validated.payload:
                    raise AnalysisServiceError("RESULT_DIGEST_COLLISION")
                return revision
        if prior and not authorize_additional_revision:
            raise AnalysisServiceError("REVISION_APPROVAL_REQUIRED")
        return AnalysisRevision.objects.create(
            run=run, provider=provider, revision_seq=len(prior) + 1,
            result_sha256=validated.sha256, validated_payload=validated.payload,
        )
