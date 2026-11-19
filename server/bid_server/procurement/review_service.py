"""MVP-02 read-only review projection; no eligibility/AI/win-probability claim."""
import re

from django.db.models import OuterRef, Subquery, F
from django.utils import timezone

from .extractor_service import scoped_document_versions
from .models import (
    Chunk, DeadlineStatus, DocumentFreshness, DocumentVersion, ExtractionRun, ExtractionState,
)
from .serializers import document_source_url, notice_source_url

# Candidate signals only; existing legacy taxonomy is broader and independently evaluated.
CHECKS = (
    ("qualification", "참가자격·업종·면허", r"참가\s*자격|업종\s*제한|면허|직접생산확인|소프트웨어사업자|공동\s*수급"),
    ("experience", "수행실적", r"수행\s*실적|유사\s*(?:사업|용역)|실적\s*증명"),
    ("technology", "과업·기술요건", r"과업\s*(?:내용|범위)|요구사항|Java|Python|Spring|FastAPI|LLM|RAG|API|데이터베이스|시스템\s*구축|인공지능"),
    ("staffing", "인력·필요 MM", r"투입\s*인력|인력\s*(?:투입|구성)|상주|인월|(?<![A-Za-z])M/M(?![A-Za-z])"),
    ("schedule", "수행기간·제출", r"사업\s*기간|수행\s*기간|계약\s*기간|제출\s*(?:기한|서류)|납품\s*기한"),
)
MAX_DOCUMENTS = 8
MAX_CHUNKS = 160
MAX_PER_CHECK = 3
MAX_TEXT = 500
LOCATOR_KEYS = ("line", "section", "p_index", "table_index", "row", "col", "footnote_index", "footnote_num")


def review_projection(notice, actor, *, now=None):
    """Current notice/version only, never use stale/inaccessible document evidence.

    Existing document ACLs apply unchanged. A matched excerpt is not a verified requirement,
    source authenticity, completeness, company capacity, or a human determination.
    """
    now = now or timezone.now()
    version = notice.current_version
    checks = [{"key": key, "label": label, "state": "UNVERIFIED", "evidence": []}
              for key, label, _ in CHECKS]
    result = {
        "notice_version_id": str(version.pk) if version else None,
        "source_revision": version.source_revision if version else None,
        "state": "HOLD", "reason": "CURRENT_VERSION_UNVERIFIED",
        "evaluation": "NOT_EVALUATED", "coverage": "NOT_VERIFIED",
        "checks": checks, "truncated": False, "mode": "RULE_BASED_READ_ONLY",
    }
    if version is None or version.notice_id != notice.pk:
        return result
    if version.cancellation:
        result["reason"] = "CANCELLED"
        return result
    if version.deadline_at is None or version.deadline_status not in (DeadlineStatus.PARSED, DeadlineStatus.EXPIRED):
        result["reason"] = "DEADLINE_UNVERIFIED"
        return result
    if version.deadline_at <= now or version.deadline_status == DeadlineStatus.EXPIRED:
        result["reason"] = "CLOSED"
        return result
    if version.correction:
        result["reason"] = "CORRECTION_REVIEW_REQUIRED"
        return result
    if notice.source != "G2B_OFFICIAL_API" or not notice_source_url(notice):
        result["reason"] = "OFFICIAL_SOURCE_UNVERIFIED"
        return result
    if not isinstance(version.department_categories, list) or not any(
        value in ("AI", "DATA", "SW", "SECURITY") for value in version.department_categories
    ):
        result["reason"] = "CATEGORY_REVIEW_REQUIRED"
        return result

    latest_doc = DocumentVersion.objects.filter(document_id=OuterRef("document_id")).order_by("-version_seq")
    documents = list(scoped_document_versions(actor).filter(
        document__notice_id=notice.pk, notice_version_id=version.pk, freshness=DocumentFreshness.CURRENT,
        size_bytes__gt=0, pk=Subquery(latest_doc.values("pk")[:1]),
    ).order_by("pk")[:MAX_DOCUMENTS + 1])
    result["truncated"] = len(documents) > MAX_DOCUMENTS
    # Only the latest run may contribute; a later failed run must not resurrect old excerpts.
    eligible = [d for d in documents[:MAX_DOCUMENTS]
                if re.fullmatch(r"[0-9a-fA-F]{64}", d.sha256 or "") and document_source_url(d)]
    remaining = MAX_CHUNKS
    for doc in eligible:
        run = ExtractionRun.objects.filter(document_version=doc).order_by("-created_at", "-pk").first()
        if run is None or run.state != ExtractionState.PARSED:
            continue
        rows = list(Chunk.objects.filter(
            extraction_run=run,
            extraction_run__document_version__in=scoped_document_versions(actor),
            extraction_run__document_version__freshness=DocumentFreshness.CURRENT,
            extraction_run__document_version__notice_version_id=version.pk,
            extraction_run__document_version__document__notice__current_version_id=version.pk,
        ).order_by("ordinal")[:remaining + 1])
        if len(rows) > remaining:
            result["truncated"] = True
        for chunk in rows[:remaining]:
            for check, (_, _, pattern) in zip(checks, CHECKS):
                if len(check["evidence"]) >= MAX_PER_CHECK:
                    continue
                match = re.search(pattern, chunk.text[:10000], re.IGNORECASE)
                if match is None:
                    continue
                start = max(0, match.start() - 120)
                excerpt = chunk.text[start:start + MAX_TEXT]
                locator = {k: val for k, val in (chunk.locator.items() if isinstance(chunk.locator, dict) else [])
                           if k in LOCATOR_KEYS and type(val) is int and 0 <= val <= 1000000}
                check["evidence"].append({
                    "document_version_id": str(doc.pk), "document_version_seq": doc.version_seq,
                    "source_sha256": doc.sha256, "source_url": document_source_url(doc),
                    "extraction_run_id": str(run.pk), "chunk_id": str(chunk.pk),
                    "ordinal": chunk.ordinal, "locator": locator, "excerpt": excerpt,
                    "verification": "UNVERIFIED",
                })
        remaining -= min(remaining, len(rows))
        if remaining == 0:
            result["truncated"] = True
            break
    if any(check["evidence"] for check in checks):
        result.update(state="DETAIL_REVIEW_REQUIRED", reason="EXTRACTED_CANDIDATES")
    else:
        result.update(state="HOLD", reason="RFP_EVIDENCE_UNAVAILABLE")
    return result
