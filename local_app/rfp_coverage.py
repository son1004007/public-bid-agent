"""RFP 본문 확보 상태를 집계하는 읽기 전용 진단.

목적: 부서 관심 후보에서 공식 첨부 링크/포맷/추출 실패의 병목을 구분한다.
입력: 기존 공식 공고와 검증된 관심분야 설정. 네트워크·모델·파일 갱신 없음.
출력: 개별 공고명/주소/원문/오류 텍스트를 제외한 비식별 집계와 처리 순서.
불변: 추출됨은 전체 문서 정확도나 업체 적격·입찰 추천을 의미하지 않는다.
"""

from pathlib import PurePath

from procurement_documents import SUPPORTED, official_url
from procurement_filter import bid_window
from notice_lifecycle import is_cancel_kind

STATES = (
    "EXTRACTED_TEXT", "FAILED_ATTEMPT", "READY_TO_FETCH",
    "UNSUPPORTED_FORMAT", "MISSING_OFFICIAL_LINK", "INVALID_ATTACHMENTS"
)
ACTIVE = {"OPEN", "REGISTRATION_REVIEW"}

# 각 수치는 공고 건수이며 서로 중첩될 수 있다. 원문 캐시를 열어 검증하지 않는다.
MAX_EVIDENCE_SCAN = 120
QUALITY_FLAGS = (
    "STALE_RFP",
    "LIFECYCLE_REVIEW",
    "CANCELLED_OR_SUPERSEDED",
    "FULLTEXT_REFERENCE_UNVERIFIED",
    "EXCERPT_OR_LEGACY_ONLY",
    "EXTRACTED_WITHOUT_PROVENANCE",
    "PARSER_TRUNCATION_REPORTED",
    "PARSER_WARNING_REPORTED",
    "EXTRACTED_EVIDENCE_OVER_TWO",
    "ATTACHMENT_SCAN_OVER_LIMIT",
    "EVIDENCE_SCAN_OVER_LIMIT",
    "MALFORMED_EVIDENCE",
)


def _quality_flags(notice):
    """비신뢰 메타데이터에서 집계 표시만 생성. 원문·링크·파일명은 읽거나 반환하지 않는다."""
    flags = set()
    if notice.get("rfp_review_status") == "STALE":
        flags.add("STALE_RFP")
    if (notice.get("notice_lifecycle") in ("CANCELLED", "SUPERSEDED")
            or is_cancel_kind(notice.get("notice_kind"))):
        flags.add("CANCELLED_OR_SUPERSEDED")
    if notice.get("notice_lifecycle") == "REVIEW":
        flags.add("LIFECYCLE_REVIEW")
    attachments = notice.get("attachments", [])
    if isinstance(attachments, list) and len(attachments) > 400:
        flags.add("ATTACHMENT_SCAN_OVER_LIMIT")
    evidence = notice.get("document_evidence", [])
    if not isinstance(evidence, list):
        flags.add("MALFORMED_EVIDENCE")
        evidence = []
    if len(evidence) > MAX_EVIDENCE_SCAN:
        flags.add("EVIDENCE_SCAN_OVER_LIMIT")
    # 상한을 넘는 비신뢰 메타데이터는 이후 어떤 품질 플래그에도 영향을 주지 않는다.
    scanned = evidence[:MAX_EVIDENCE_SCAN]
    if any(not isinstance(e, dict) for e in scanned):
        flags.add("MALFORMED_EVIDENCE")
    extracted = [e for e in scanned if isinstance(e, dict) and e.get("status") == "EXTRACTED"]
    if len(extracted) > 2:
        flags.add("EXTRACTED_EVIDENCE_OVER_TWO")
    if notice.get("document_status") == "EXTRACTED":
        refs = [e for e in extracted if isinstance(e.get("fulltext_ref"), str)
                and len(e["fulltext_ref"]) == 64
                and all(c in "0123456789abcdef" for c in e["fulltext_ref"])]
        if refs:
            flags.add("FULLTEXT_REFERENCE_UNVERIFIED")
        if extracted and len(refs) < len(extracted):
            flags.add("EXCERPT_OR_LEGACY_ONLY")
        if not extracted:
            flags.add("EXTRACTED_WITHOUT_PROVENANCE")
    if any(e.get("fulltext_truncated") is True for e in extracted):
        flags.add("PARSER_TRUNCATION_REPORTED")
    if any(isinstance(e.get("warnings"), list) and bool(e["warnings"]) for e in extracted):
        flags.add("PARSER_WARNING_REPORTED")
    return flags


def _status(notice):
    if (notice.get("document_status") == "EXTRACTED"
            and isinstance(notice.get("rfp_text"), str)
            and notice["rfp_text"].strip()):
        return "EXTRACTED_TEXT"
    if notice.get("document_status") == "FAILED":
        return "FAILED_ATTEMPT"
    files = notice.get("attachments", [])
    if not isinstance(files, list):
        return "INVALID_ATTACHMENTS"
    official_links = []
    for item in files[:120]:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        link = item.get("url")
        if isinstance(name, str) and official_url(link):
            official_links.append(name)
    if any(PurePath(name).suffix.lower() in SUPPORTED for name in official_links):
        return "READY_TO_FETCH"
    if official_links:
        return "UNSUPPORTED_FORMAT"
    return "MISSING_OFFICIAL_LINK"


def summarize(notices, profile):
    """전체 공고를 보존하면서 후보/현재 진행중 후보의 추출 병목만 집계한다."""
    if not isinstance(notices, list) or len(notices) > 10000:
        raise ValueError("공식 공고 목록 형식 오류")
    categories = profile.get("categories")
    if not isinstance(categories, list):
        raise ValueError("부서 분야 설정 오류")
    selected = set(categories)
    total = {key: 0 for key in STATES}
    active = {key: 0 for key in STATES}
    quality_all = {key: 0 for key in QUALITY_FLAGS}
    quality_active = {key: 0 for key in QUALITY_FLAGS}
    reviewed = 0
    active_count = 0
    for n in notices:
        if not isinstance(n, dict):
            raise ValueError("공고 항목 형식 오류")
        if n.get("department_status") != "CANDIDATE":
            continue
        found = n.get("department_categories", [])
        if not isinstance(found, list):
            continue
        if not selected.intersection(x for x in found if isinstance(x, str)):
            continue
        status = _status(n)
        flags = _quality_flags(n)
        total[status] += 1
        for flag in flags:
            quality_all[flag] += 1
        reviewed += 1
        if (not flags.intersection(("CANCELLED_OR_SUPERSEDED", "LIFECYCLE_REVIEW"))
                and bid_window(n.get("end"), n.get("notice_kind", ""),
                               n.get("qualification_deadline", "")) in ACTIVE):
            active_count += 1
            active[status] += 1
            for flag in flags:
                quality_active[flag] += 1
    return {
        "candidate_count": reviewed,
        "active_candidate_count": active_count,
        "by_state_all": total,
        "by_state_active": active,
        "by_quality_all": quality_all,
        "by_quality_active": quality_active,
        "quality_mode": "UNVERIFIED_STORED_METADATA_ONLY",
        "quality_interpretation": (
            "품질 위험별 공고 건수는 중복 가능. 캐시 SHA/원문 페이지/누락률은 검증하지 않음"
        ),
        "unprocessed_active": active["READY_TO_FETCH"] + active["UNSUPPORTED_FORMAT"]
                              + active["MISSING_OFFICIAL_LINK"]
                              + active["INVALID_ATTACHMENTS"],
        "failed_active": active["FAILED_ATTEMPT"],
        "ready_active": active["READY_TO_FETCH"],
        "needs_related_lookup_active": active["MISSING_OFFICIAL_LINK"],
        "mode": "READ_ONLY_DOCUMENT_COVERAGE",
        "scope": "현재 선택한 부서 관심분야의 CANDIDATE 공고, 실시간 재계산 마감상태",
        "interpretation": "추출 여부는 첨부 전체 파악·원문 정확도·실제 입찰 적격성이 아님",
        "next_steps": [
            "READY_TO_FETCH: 공식 문서 순차 배치로 추출",
            "FAILED_ATTEMPT: 다운로드/파서 실패 원인 세분화 및 재시도",
            "UNSUPPORTED_FORMAT: 파일 형식·추출기 적용 가능성 검토",
            "MISSING_OFFICIAL_LINK: 공식 상세/e발주 첨부 목록 추가 조회"
        ]
    }
