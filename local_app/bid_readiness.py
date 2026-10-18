"""부서 역량·입찰 요건 증빙 준비도 읽기 전용 게이트.
입력: 공고 메타데이터, 별도 로컬 운영자료의 기록 상태 요약.
출력: 비식별 검증 필요 항목. 법적 적격/사업이익/추천 결정은 판정하지 않는다.
신뢰 경계: 사용자 'reviewed'는 실제 법적 등록 확인이 아니라 주장된 확인 상태.
부작용: 파일/AI/외부 API I/O 없음. 운영자료 요약문·직원정보/원가 미반환.
불변: 공고 취소/STALE/기한 이슈는 명시적 보류. 모든 자격 게이트 UNVERIFIED.
관련: D-02,D-06,D-07,D-17, operations.py, test_bid_readiness.py.
추가 계약: 출처·요약·확인일은 존재/형식만 검사하며 원문 검증으로 승격하지 않는다.
가용공수/단가는 운영자료의 준비도만 검사하고 공고별 요구와의 일치/이익은 계산하지 않는다.
실패: 잘못된 자료는 고정 누락 사유로 보류; 입력 불변, 자동 재시도 없음.
"""
from datetime import date
import re

from notice_lifecycle import is_cancel_kind
from operations import clean_profile
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
REVIEW_GUIDANCE={
 "registrations":["공고의 등록 업종·지역 조건과 공식 등록 증빙 대조",
                  "면허 종류·유효기간·명의 및 공동수급 적용 범위 별도 대조"],
 "past_performance":["공고의 인정 기간·유사 과업·금액·완료 조건과 실적증명 대조"],
 "utilization":["직무·등급 증빙과 사업기간별 배치·겸임·가용 MM 대조"],
 "finance":["총원가 단가·간접비·법정부담금·외주·직접경비·현금흐름 근거 대조"],
 "pipeline":["등록·제안·제출 기한과 필수 서류 준비 상태 대조"],
 "risks":["계약·보안·품질 조건과 예외·충돌 근거 검토"],
}


def _evidence_gaps(source, today):
    """비공개 필드 내용은 반환하지 않고 고정 코드만 반환한다."""
    gaps=[]
    for field,code,maximum in (("summary","SUMMARY_MISSING_OR_INVALID",600),
                               ("source","SOURCE_MISSING_OR_INVALID",120)):
        value=source.get(field)
        if not isinstance(value,str) or not value.strip() or len(value)>maximum:
            gaps.append(code)
    reviewed_on=source.get("reviewed_on")
    if not isinstance(reviewed_on,str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}",reviewed_on):
        gaps.append("REVIEW_DATE_MISSING_OR_INVALID")
    else:
        try:
            if date.fromisoformat(reviewed_on)>today:gaps.append("REVIEW_DATE_IN_FUTURE")
        except ValueError:
            gaps.append("REVIEW_DATE_MISSING_OR_INVALID")
    return gaps


def _operational_gaps(operations):
    """기존 프로필 수치 계약을 재사용; 직무명/공수/단가 값은 응답에서 제외."""
    try:
        profile=clean_profile(operations)
    except (ValueError,TypeError,KeyError,AttributeError):
        return ["OPERATIONS_PROFILE_INVALID"],["OPERATIONS_PROFILE_INVALID"]
    staffing=[];cost=[]
    roles=profile["roles"]
    if not roles:
        staffing.append("ROLE_CAPACITY_NOT_RECORDED")
        cost.append("ROLE_COST_NOT_RECORDED")
    if any(r["available_mm"] is None for r in roles):
        staffing.append("AVAILABLE_MM_UNKNOWN")
    if roles and all(r["available_mm"]==0 for r in roles):
        staffing.append("NO_RECORDED_AVAILABLE_MM")
    if any(r["cost_per_mm_krw"]==0 for r in roles):
        cost.append("ZERO_ROLE_COST_REQUIRES_REVIEW")
    if profile["cost_basis"]!="FULLY_LOADED":cost.append("FULL_COST_BASIS_NOT_RECORDED")
    return staffing,cost

def assess(notice, operations, *, today=None):
    if not isinstance(notice,dict) or not isinstance(operations,dict):
        raise ValueError("준비도 조회 입력 형식 오류")
    registers=operations.get("registers")
    if not isinstance(registers,dict):
        raise ValueError("운영자료 확인표 없음")
    today=date.today() if today is None else today
    if type(today) is not date:raise ValueError("준비도 기준일 형식 오류")
    staffing_gaps,cost_gaps=_operational_gaps(operations)
    checks=[]
    for key in REQUIRED:
        source=registers.get(key)
        status=source.get("status") if isinstance(source,dict) else None
        if status not in ("reviewed","needs_refresh","not_collected"):
            status="not_collected"
        gaps=_evidence_gaps(source if isinstance(source,dict) else {},today)
        state=("EVIDENCE_RECORD_INCOMPLETE" if gaps else "USER_REVIEWED_UNVERIFIED")
        if status!="reviewed":
            state="STALE_OR_REFRESH_NEEDED" if status=="needs_refresh" else "NOT_COLLECTED"
        checks.append({"code":key,"label":NAMES[key],"status":state,
                       "evidence_gaps":gaps,
                       "data_gaps":staffing_gaps if key=="utilization" else cost_gaps if key=="finance" else [],
                       "required_review":list(REVIEW_GUIDANCE[key]),
                       "requirement_comparison":"NOT_PERFORMED",
                       "evidence_verification":"UNVERIFIED"})
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
