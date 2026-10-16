"""부서 역량·입찰 요건 증빙 준비도 읽기 전용 게이트.
입력: 공고 메타데이터, 별도 로컬 운영자료의 기록 상태 요약.
출력: 비식별 검증 필요 항목. 법적 적격/사업이익/추천 결정은 판정하지 않는다.
신뢰 경계: 사용자 'reviewed'는 실제 법적 등록 확인이 아니라 주장된 확인 상태.
부작용: 파일/AI/외부 API I/O 없음. 운영자료 요약문·직원정보/원가 미반환.
불변: 공고 취소/STALE/기한 이슈는 명시적 보류. 모든 자격 게이트 UNVERIFIED.
관련: D-02,D-06,D-07,D-17, operations.py, test_bid_readiness.py.
"""
from notice_lifecycle import is_cancel_kind
from procurement_filter import bid_window

REQUIRED=("registrations","past_performance","utilization","finance","pipeline","risks")
NAMES={
 "registrations":"사업자 등록·업종·면허 증빙",
 "past_performance":"유사 과업 수행실적 증빙",
 "utilization":"투입 인력·가용 MM",
 "finance":"예산·원가·현금흐름",
 "pipeline":"제안 일정·제출 서류",
 "risks":"계약·보안·품질 위험",
}

def assess(notice, operations):
    if not isinstance(notice,dict) or not isinstance(operations,dict):
        raise ValueError("준비도 조회 입력 형식 오류")
    registers=operations.get("registers")
    if not isinstance(registers,dict):
        raise ValueError("운영자료 확인표 없음")
    checks=[]
    for key in REQUIRED:
        source=registers.get(key)
        status=source.get("status") if isinstance(source,dict) else None
        if status not in ("reviewed","needs_refresh","not_collected"):
            status="not_collected"
        checks.append({"code":key,"label":NAMES[key],
                       "status":"USER_REVIEWED_UNVERIFIED" if status=="reviewed" else
                       "STALE_OR_REFRESH_NEEDED" if status=="needs_refresh" else "NOT_COLLECTED"})
    blocked=(notice.get("notice_lifecycle") in ("CANCELLED","SUPERSEDED","REVIEW") or
             is_cancel_kind(notice.get("notice_kind")) or
             notice.get("rfp_review_status")=="STALE")
    window=bid_window(notice.get("end"),notice.get("notice_kind",""),
                      notice.get("qualification_deadline",""))
    return {
        "mode":"RULE_BASED_EVIDENCE_READINESS_ONLY",
        "status":"BLOCKED_LIFECYCLE" if blocked else
                 "DEADLINE_NOT_OPEN" if window not in ("OPEN","REGISTRATION_REVIEW") else
                 "HOLD_FOR_EVIDENCE_REVIEW",
        "checks":checks,
        "rfp_extraction":"STORED_EXCERPT_UNVERIFIED" if notice.get("document_status")=="EXTRACTED"
                          else "ORIGINAL_EXTRACTION_REQUIRED",
        "legal_eligibility":"UNVERIFIED",
        "technical_fit":"UNVERIFIED",
        "staffing_fit":"UNVERIFIED",
        "profitability":"UNVERIFIED",
        "automated_bid_recommendation":"NOT_AVAILABLE",
        "human_decision_unchanged":True,
    }
