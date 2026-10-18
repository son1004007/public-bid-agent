"""현재 시점 입찰 기회 보수적 읽기 전용 사전 분류 (D-20).

입력: 공식 공고 1건/사용자 선택 분야/고정 기준시각.
출력: 고정 코드와 문서 상태만. 공고 본문, 제목, URL, 회사·인력·금액은 제외.
의사결정 경계: 자격/수익·가용 인력의 실제 검증은 다른 사람 승인 게이트.
기술역량 부족/분야 미일치로 고수익 가능성을 자동 삭제하지 않는다.
부작용: 없음. 네트워크, 파일/모델 호출, 자동 제출 없음.
"""
from datetime import datetime
from procurement_filter import CATEGORIES, KST, bid_window, timestamp
from notice_lifecycle import is_cancel_kind
from rfp_coverage import _quality_flags, _status

RISK_FLAGS=frozenset({
    "STALE_RFP","PARSER_TRUNCATION_REPORTED","PARSER_WARNING_REPORTED",
    "FULLTEXT_REFERENCE_UNVERIFIED","EXCERPT_OR_LEGACY_ONLY",
    "EXTRACTED_WITHOUT_PROVENANCE","MALFORMED_EVIDENCE",
    "EVIDENCE_SCAN_OVER_LIMIT","ATTACHMENT_SCAN_OVER_LIMIT",
    "EXTRACTED_EVIDENCE_OVER_TWO",
})
LEGAL_UNKNOWN="UNVERIFIED"
MARGIN_UNKNOWN="UNVERIFIED"
CAPABILITY_UNKNOWN="UNVERIFIED"


def _safe_timestamp(value):
    try:
        return timestamp(value)
    except (OverflowError,TypeError,ValueError):
        return None


def classify(notice, profile, *, at=None):
    if not isinstance(notice,dict) or not isinstance(profile,dict):
        raise ValueError("공지/부서 설정 객체 필요")
    cats=profile.get("categories")
    if not isinstance(cats,list) or any(type(x) is not str or x not in CATEGORIES for x in cats):
        raise ValueError("부서 분야 설정 오류")
    if at is not None and (not isinstance(at,datetime) or at.tzinfo is None):
        raise ValueError("기준시각은 시간대 포함 datetime")
    when=at or datetime.now(KST)
    lifecycle=notice.get("notice_lifecycle")
    kind=notice.get("notice_kind","")
    flags=_quality_flags(notice)
    document=_status(notice)
    try:
        window=bid_window(notice.get("end"), kind,
                          notice.get("qualification_deadline",""),at=when)
    except (OverflowError,TypeError,ValueError):
        window="UNKNOWN"
    matching=(notice.get("department_status")=="CANDIDATE"
              and isinstance(notice.get("department_categories"),list)
              and bool(set(x for x in notice["department_categories"]
                           if type(x) is str)&set(cats)))
    reason=[]
    if lifecycle != "CURRENT" or is_cancel_kind(kind):
        status="HOLD_OFFICIAL_STATUS"
        reason.append("OFFICIAL_LIFECYCLE_NOT_CURRENT")
    elif notice.get("rfp_review_status")=="STALE":
        status="HOLD_STALE_DOCUMENT"
        reason.append("SOURCE_REVISION_STALE")
    elif window in ("CANCELLED","CLOSED"):
        status="HOLD_DEADLINE"
        reason.append("NOT_OPEN_FOR_BIDDING")
    elif window=="UNKNOWN":
        status="REVIEW_UNKNOWN_DEADLINE"
        reason.append("DEADLINE_NOT_VERIFIED")
    elif ("qualification_deadline" in notice
          and (not isinstance(notice["qualification_deadline"],str)
               or not notice["qualification_deadline"].strip()
               or _safe_timestamp(notice["qualification_deadline"]) is None)):
        # Present-but-unparseable preregistration deadline is not proof of no restriction.
        status="REVIEW_REGISTRATION"
        reason.append("QUALIFICATION_DEADLINE_INVALID_OR_UNVERIFIED")
    elif window=="REGISTRATION_REVIEW":
        status="REVIEW_REGISTRATION"
        reason.append("QUALIFICATION_REGISTRATION_DEADLINE_PASSED")
    elif not matching:
        status="CAPABILITY_GAP_MARGIN_REVIEW"
        reason.append("DEPARTMENT_CATEGORY_OR_CAPABILITY_NOT_PROVEN")
    elif document!="EXTRACTED_TEXT":
        status="NEEDS_OFFICIAL_DOCUMENT"
        reason.append("FULL_ORIGINAL_TEXT_NOT_AVAILABLE")
    elif flags & RISK_FLAGS:
        status="NEEDS_EXTRACTION_REVIEW"
        reason.append("STORED_EXTRACTION_QUALITY_UNVERIFIED")
    else:
        status="PRIORITY_REVIEW"
        reason.append("OFFICIAL_REQUIREMENTS_AND_ELIGIBILITY_NOT_VERIFIED")
    return {
        "mode":"LOCAL_DETERMINISTIC_TRIAGE_ONLY",
        "status":status,"reason_codes":reason,
        "bidding_window":window,
        "document_state":document,
        "document_quality_flags":sorted(flags & RISK_FLAGS),
        "department_category_match":matching,
        "current_capacity_fit":CAPABILITY_UNKNOWN,
        "capacity_augmentation_possible":"UNVERIFIED",
        "subcontract_or_consortium_permitted":"UNVERIFIED",
        "legal_eligibility":LEGAL_UNKNOWN,
        "estimated_profit":MARGIN_UNKNOWN,
        "profit_after_augmentation_cost":MARGIN_UNKNOWN,
        "bid_decision":"HUMAN_ONLY",
        "automatic_bid_submittal":False,
        "cannot_auto_discard_on_capability_gap":True,
        "confidential_fields_returned":False,
    }
