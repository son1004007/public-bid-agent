"""부서의 현재 입찰 검토 대상: 로컬 공고·관심분야·운영자료 단일 스냅샷.

목적: 현재 부서 역량 또는 합법적 보완을 통해 수익을 낼 수 있을 가능성을
       검토할 작업 큐만 보여 준다. 실제 입찰 가능/이익을 자동 확정하지 않는다.
입력: 공식 저장 공고 리스트, 분야 프로필, 로컬 운영자료, 고정 KST 시각.
출력: 공개 공고 ID 및 *고정 분류·증빙 누락 코드*로 구성된 제한된 목록/집계.
신뢰 경계: 직원명/인원/단가/원가/부서 증빙 원문/입찰 제목/첨부 URL 미반환.
부작용: 읽기만 수행. 원본/판정/인력자료 파일 쓰기, 외부 네트워크 없음.
"""
from collections import Counter
from datetime import datetime
import re

from bid_now_triage import classify
from bid_readiness import assess
from procurement_filter import KST

MAX_NOTICE_COUNT=10000
MAX_PER_BUCKET=30
SCOPE_ACTIVE=frozenset(("PRIORITY_REVIEW","NEEDS_OFFICIAL_DOCUMENT",
    "NEEDS_EXTRACTION_REVIEW"))
CAPABILITY_BUCKET="CAPABILITY_GAP_MARGIN_REVIEW"
REGISTRATION_BUCKET="REVIEW_REGISTRATION"
HOLD=frozenset(("HOLD_OFFICIAL_STATUS","HOLD_STALE_DOCUMENT","HOLD_DEADLINE",
    "REVIEW_UNKNOWN_DEADLINE"))
VALID_ID=re.compile(r"G2B-([A-Za-z0-9-]{4,32})-([0-9]{1,5})\Z")

def _safe_readiness(notice,operations,at):
    report=assess(notice,operations,today=at.date())
    return {
        "overall_status":report["status"],
        "checks":[{
            "code":c["code"],"status":c["status"],
            "evidence_gaps":c["evidence_gaps"],
            "data_gaps":c["data_gaps"],
            "evidence_verification":"UNVERIFIED",
        } for c in report["checks"]],
        "legal_eligibility":"UNVERIFIED",
        "staffing_fit":"UNVERIFIED",
        "profitability":"UNVERIFIED"
    }

def build(notices,profile,operations,*,at=None,limit=20):
    if not isinstance(notices,list) or len(notices)>MAX_NOTICE_COUNT:
        raise ValueError("공식 공고 목록 범위 오류")
    if not isinstance(profile,dict) or not isinstance(operations,dict):
        raise ValueError("부서 설정·운영자료 미확인")
    if type(limit) is not int or not 1<=limit<=MAX_PER_BUCKET:
        raise ValueError("큐 표시 개수 오류")
    if at is not None and (not isinstance(at,datetime) or at.tzinfo is None):
        raise ValueError("기준시각 형식 오류")
    stamp=at or datetime.now(KST)
    seen=set()
    totals=Counter()
    categories={"matching":[],"augmentation":[],"registration":[]}
    for notice in notices:
        if not isinstance(notice,dict):
            raise ValueError("공고 원본 데이터 형식 오류")
        code=notice.get("id")
        ident=VALID_ID.fullmatch(code) if isinstance(code,str) else None
        if (ident is None or notice.get("bid_no")!=ident.group(1)
                or str(notice.get("bid_order"))!=ident.group(2)):
            totals["INVALID_ID_HELD"]+=1
            continue
        if code in seen:
            raise ValueError("중복 공고 식별자: 확인 전 분류 불가")
        seen.add(code)
        triage=classify(notice,profile,at=stamp)
        state=triage["status"]
        totals[state]+=1
        if state in SCOPE_ACTIVE: group="matching"
        elif state==CAPABILITY_BUCKET:group="augmentation"
        elif state==REGISTRATION_BUCKET:group="registration"
        else:continue
        categories[group].append((code,triage,notice))
    def rows(values):
        selected=sorted(values,key=lambda rec:(
            {"PRIORITY_REVIEW":0,"NEEDS_EXTRACTION_REVIEW":1,
             "NEEDS_OFFICIAL_DOCUMENT":2,"CAPABILITY_GAP_MARGIN_REVIEW":3,
             "REVIEW_REGISTRATION":4}.get(rec[1]["status"],9),rec[0]))[:limit]
        output=[]
        for code,triage,n in selected:
            output.append({
                "id":code,
                "status":triage["status"],
                "reason_codes":triage["reason_codes"],
                "document_state":triage["document_state"],
                "document_quality_flags":triage["document_quality_flags"],
                "bidding_window":triage["bidding_window"],
                "department_category_match":triage["department_category_match"],
                "legal_eligibility":"UNVERIFIED",
                "profit_after_augmentation_cost":"UNVERIFIED",
                "augmentation_feasibility":"UNVERIFIED",
                "required_readiness":_safe_readiness(n,operations,stamp),
                "bid_decision":"HUMAN_ONLY",
            })
        return output
    return {
        "mode":"READ_ONLY_BID_OPPORTUNITY_REVIEW_NOT_ELIGIBILITY",
        "snapshot_time":stamp.isoformat(),
        "total_notices":len(notices),
        "status_counts":dict(sorted(totals.items())),
        "matching_total":len(categories["matching"]),
        "augmentation_review_total":len(categories["augmentation"]),
        "registration_review_total":len(categories["registration"]),
        "matching_results":rows(categories["matching"]),
        "augmentation_review_results":rows(categories["augmentation"]),
        "registration_review_results":rows(categories["registration"]),
        "per_bucket_limit":limit,
        "legal_eligibility":"UNVERIFIED",
        "profitability":"UNVERIFIED",
        "human_review_required":True,
        "automatic_bid_submittal":False,
        "private_operations_data_included":False,
        "interpretation":"관심분야 불일치는 고이익 기회의 제외 근거가 아닙니다. 실제 원문·법적 자격·보완 비용·이익은 별도로 검증해야 합니다."
    }
