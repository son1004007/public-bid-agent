"""공개 조달정보 MCP 조회 서비스.

목적/책임: 기존 Django 조달 모델에서 검증된 공식 공고 메타데이터만 조회한다.
입력/출력: 검증된 검색어/공고번호 -> 고정된 공개 필드만 가진 제한된 dict.
신뢰 경계: 인증된 원본과 동일 법인/사업부 자료는 구조적으로 질의하지 않는다.
상태 변경/부작용: DB SELECT만; 읽기 전용 DB 계정 요구.
실패/타임아웃/재시도: 오류 상세를 MCP 결과에 노출하지 않고 BACKEND_UNAVAILABLE.
핵심 불변조건: source=G2B_OFFICIAL_API, 현재 차수 일치, 10건 이하, 원문/개인자료 미노출.
관련: docs/server-migration/14-bid-mcp-interface.md, procurement/models.py.
"""
from .scope import (PUBLIC_SOURCE, approved_public_rfp_enabled, require_enabled,
                    validate_limit, validate_notice_number, validate_query)


def _public_queryset():
    from django.db.models import F
    from bid_server.procurement.models import Notice

    # current_version belongs to the same Notice: reject stale/corrupt foreign key links.
    return Notice.objects.select_related("current_version").filter(
        source=PUBLIC_SOURCE,
        current_version__isnull=False,
        current_version__notice_id=F("pk"),
    )


def _project(notice):
    v = notice.current_version
    return {
        "notice_number": notice.notice_number,
        "version_id": str(v.id),
        "title": v.title[:500],
        "buyer": v.buyer[:300],
        "deadline_status": v.deadline_status,
        "deadline_at": v.deadline_at.isoformat() if v.deadline_at else None,
        "cancelled": bool(v.cancellation),
        "budget_krw": v.budget_amount,
        "source": PUBLIC_SOURCE,
        "evidence_state": "PUBLIC_NOTICE_METADATA_ONLY",
    }


def search_public_notices(query: str, limit: int = 5) -> dict:
    require_enabled()
    query = validate_query(query)
    limit = validate_limit(limit)
    from django.db.models import Q
    qs = _public_queryset().filter(
        Q(notice_number__icontains=query)
        | Q(current_version__title__icontains=query)
        | Q(current_version__buyer__icontains=query)
    ).order_by("-current_version__observed_at", "notice_number")[:limit]
    return {"status": "OK", "source": PUBLIC_SOURCE, "items": [_project(n) for n in qs]}


def get_public_notice(notice_number: str) -> dict:
    require_enabled()
    notice_number = validate_notice_number(notice_number)
    n = _public_queryset().filter(notice_number=notice_number).first()
    if n is None:
        return {"status": "NOT_FOUND", "notice_number": notice_number}
    return {"status": "OK", "item": _project(n)}


def search_public_rfp_passages(notice_number: str, query: str, limit: int = 5) -> dict:
    """공식 자료여도 소유·공유·현재 원문·추출 검증이 모두 충족돼야 한다."""
    require_enabled()
    notice_number = validate_notice_number(notice_number)
    query = validate_query(query)
    limit = validate_limit(limit)
    if not _public_queryset().filter(notice_number=notice_number).exists():
        return {"status": "NOT_FOUND", "notice_number": notice_number}
    if not approved_public_rfp_enabled():
        return {"status": "NOT_ENABLED", "reason": "PUBLIC_RFP_REVIEW_REQUIRED", "items": []}
    from django.db.models import F, OuterRef, Subquery
    from bid_server.procurement.models import Chunk, ExtractionRun

    latest_runs = ExtractionRun.objects.filter(
        document_version_id=OuterRef("extraction_run__document_version_id"),
    ).order_by("-created_at", "-id").values("id")[:1]
    qs = Chunk.objects.filter(
        extraction_run__document_version__document__notice__source=PUBLIC_SOURCE,
        extraction_run__document_version__document__notice__notice_number=notice_number,
        extraction_run__document_version__document__notice__current_version__isnull=False,
        extraction_run__document_version__notice_version_id=F(
            "extraction_run__document_version__document__notice__current_version_id"
        ),
        extraction_run__document_version__owner_user__isnull=True,
        extraction_run__document_version__shared_read_approved=True,
        extraction_run__document_version__freshness="CURRENT",
        extraction_run__state="PARSED",
        extraction_run_id=Subquery(latest_runs),
        text__icontains=query,
    ).select_related("extraction_run__document_version").order_by(
        "extraction_run__document_version_id", "ordinal"
    )[:limit]
    items = []
    for c in qs:
        d = c.extraction_run.document_version
        items.append({
            "evidence_id": str(c.id),
            "document_version_id": str(d.id),
            "document_sha256": d.sha256,
            "ordinal": c.ordinal,
            "text_excerpt": c.text[:1000],
            "coverage": "EXCERPT_ONLY",
        })
    return {"status": "OK", "notice_number": notice_number, "items": items}
