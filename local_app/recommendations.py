"""공식 입찰공고의 읽기 전용 상세검토 우선순위.

입력/출력: 현행 공식 대시보드 및 부서분야 -> 근거 라벨/검토 순위.
신뢰 경계: 수집 필드와 문서 텍스트를 비신뢰 입력으로 처리. 공식 메타/추출증거 재분류.
부작용: 없음. JSON 저장·유료 LLM·원격 모델·회사정보 전송 없음.
실패: 필드 누락·불확실성은 상세검토 필요. 입찰 가능/수익성/가용인력 확정 금지.
불변: 기존 사람 판단 원문 비노출, RFP 본문 미반환, 후보 재순위 외 상태변경 없음.
검증: test_recommendations.py / docs/design/RFP_RECOMMENDATION_SLICE_2026-10-12.md.
"""
from __future__ import annotations

import hashlib
import re

from procurement_documents import official_url
from procurement_filter import bid_window, classify
from procurement_discovery import evaluate as discovery_evaluate

CATEGORIES = frozenset(("AI", "SW", "DATA", "SECURITY"))
VALID_WINDOWS = frozenset(("OPEN", "REGISTRATION_REVIEW"))
MAX_RESULTS = 100
CHECKS = ("업체 입찰 등록·면허·지역·실적 확인", "공식 RFP 원문·정정 여부 확인",
          "부서 실제 기술·가용 인력·공수 검증", "투입 원가·수행기간·사업성 검증")
DECISIONS = frozenset(("bid", "hold", "no_bid", "human_bid", "human_hold", "human_no_bid"))
EXCLUDED_DECISIONS = frozenset(("no_bid", "human_no_bid", "closed", "cancelled", "rejected"))


def _safe(value, limit=180):
    return value[:limit] if isinstance(value, str) else ""


def _extracted_passages(notice):
    """검증된 저장 형식과 추출 상태가 있는 발췌만 분야 탐지 입력으로 사용."""
    if notice.get("document_status") != "EXTRACTED":
        return ""
    attachments=notice.get("attachments")
    if not isinstance(attachments,list):
        attachments=[]
    known_ids=set()
    for f in attachments[:120]:
        if not isinstance(f,dict):
            continue
        name,url=f.get("name"),f.get("url")
        if isinstance(name,str) and official_url(url):
            known_ids.add(hashlib.sha256((url+"\\n"+name).encode()).hexdigest())
    full_text=notice.get("rfp_text")
    if not isinstance(full_text,str):
        return ""
    passages=[]
    items=notice.get("document_evidence")
    if not isinstance(items,list):
        return ""
    for item in items[:2]:
        if not isinstance(item, dict) or item.get("status") != "EXTRACTED":
            continue
        excerpt=item.get("excerpt")
        sha=item.get("sha256")
        identity=item.get("identity")
        if (not isinstance(excerpt,str) or not excerpt.strip()
                or not isinstance(sha,str)
                or re.fullmatch(r"[a-fA-F0-9]{64}", sha) is None
                or not isinstance(identity,str) or identity not in known_ids
                or excerpt[:6000] not in full_text):
            continue
        passages.append(excerpt[:6000])
    return "\n".join(passages)[:12000]


def _metadata_and_document_evidence(notice, selected):
    attached=notice.get("attachments")
    if not isinstance(attached,list):
        attached=[]
    names=[_safe(x.get("name"),180) for x in attached[:20]
           if isinstance(x,dict)]
    excerpt=_extracted_passages(notice)
    detection=classify(title=_safe(notice.get("title"),250),
                       procurement=_safe(notice.get("procurement_classification"),250),
                       filenames=names,rfp_text=excerpt,
                       info_biz=_safe(notice.get("information_business"),5))
    sources=[]
    for e in detection["category_evidence"]:
        if e["category"] not in selected:
            continue
        for label in e["sources"]:
            if label in ("공공조달분류", "공고명", "첨부파일명", "RFP 추출본문"):
                sources.append({"category":e["category"],"source":label})
    return detection["department_categories"],sources[:16],bool(excerpt)


def evaluate(notice, profile):
    """공식 분류/유효 발췌가 있는 현재 공고만 상세검토 순위를 계산."""
    if not isinstance(notice,dict) or not isinstance(profile,dict):
        return None
    raw_selected=profile.get("categories")
    if not isinstance(raw_selected,list):
        return None
    selected=set(x for x in raw_selected if isinstance(x,str)) & CATEGORIES
    if not selected:
        return None
    ident=notice.get("id")
    no,order=notice.get("bid_no"),notice.get("bid_order")
    if (not isinstance(ident,str) or not isinstance(no,str)
            or not isinstance(order,str) or ident!="G2B-"+no+"-"+order
            or not re.fullmatch(r"[0-9A-Za-z-]{4,32}",no)
            or not re.fullmatch(r"[0-9]{1,5}",order)
            or notice.get("source")!="G2B_OFFICIAL_API"):
        return None
    # 정정/취소 공고 및 과거 RFP는 법적 적격과 무관하게 추천 대상에서 제외.
    if notice.get("notice_lifecycle") in ("CANCELLED", "SUPERSEDED", "REVIEW"):
        return None
    if notice.get("rfp_review_status") == "STALE":
        return None
    human_raw=_safe(notice.get("final"),50).strip().casefold()
    if human_raw in EXCLUDED_DECISIONS:
        return None
    official_kind=_safe(notice.get("notice_kind"),80)
    if any(phrase in official_kind for phrase in ("취소", "유찰", "종료")):
        return None
    if notice.get("window_status") == "CANCELLED":
        return None
    raw_status=_safe(notice.get("status"),40).upper()
    if raw_status in ("CANCELLED","CLOSED","EXPIRED","CANCELED"):
        return None
    window=bid_window(notice.get("end"),official_kind,
                      notice.get("qualification_deadline", ""))
    if window not in VALID_WINDOWS:
        return None
    detected_categories,sources,has_verified_excerpt=_metadata_and_document_evidence(
        notice,selected)
    categories=set(detected_categories) & selected
    if not categories:
        # REVIEW 공고의 원본은 다른 발견 패널과 dashboard에 그대로 남는다.
        return None
    saved_status=notice.get("department_status")
    discovery=discovery_evaluate(notice) if saved_status == "REVIEW" else None
    if saved_status == "REVIEW" and discovery is None:
        return None
    rfp_source=any(s["source"]=="RFP 추출본문" for s in sources)
    has_legacy_text=(notice.get("document_status")=="EXTRACTED"
                     and isinstance(notice.get("rfp_text"),str)
                     and bool(notice["rfp_text"].strip()))
    if rfp_source and has_verified_excerpt:
        tier,basis=3,"저장된 RFP 발췌에서 부서 관심분야 표현 탐지(원문 의미 미검증)"
    elif has_legacy_text or has_verified_excerpt:
        tier,basis=2,"RFP 본문 확보 상태, 요구조건·기술 적합성 확인 필요"
    elif saved_status == "REVIEW":
        tier,basis=0,"REVIEW 공고 중 조달 분류 및 관심분야 신호 추가 발굴"
    else:
        tier,basis=1,"공식 분류·공고명·첨부 메타데이터 기반 검토 후보"
    status=notice.get("document_status")
    safe_status=status if status in ("EXTRACTED","FAILED","PENDING","NOT_AVAILABLE") else "UNKNOWN"
    return {
        "id":ident,"title":_safe(notice.get("title"),250),
        "org":_safe(notice.get("org"),120),
        "end":_safe(notice.get("end"),45),"window_status":window,
        "categories":sorted(categories),"priority_tier":tier,
        "priority_label":("RFP 근거 우선 검토","RFP 추출 후 검토",
                          "공고 메타데이터 검토","검토대기 재발굴")[3-tier],
        "basis":basis,"evidence":sources,
        "document_status":safe_status,
        "rfp_text_available":bool(has_legacy_text or has_verified_excerpt),
        "legal_eligibility":"UNVERIFIED",
        "technical_fit":"UNVERIFIED",
        "staffing_fit":"UNVERIFIED","profitability":"UNVERIFIED",
        "recommendation_state":"DETAIL_REVIEW_REQUIRED",
        "required_checks":list(CHECKS),
        "human_decision":human_raw if human_raw in DECISIONS else None,
        "_sort":(window=="OPEN",tier,len(sources)),
    }


def shortlist(notices,profile,limit=30):
    """10,000건 내 공식 공고의 마감 전 검토순위를 반환; 원본 불변."""
    if type(limit) is not int or not 1<=limit<=MAX_RESULTS:
        raise ValueError("검토 순위 반환 제한 오류")
    if not isinstance(notices,list) or len(notices)>10000:
        raise ValueError("공고 목록 형식 오류")
    if not isinstance(profile,dict):
        raise ValueError("부서 설정 형식 오류")
    found=[v for n in notices if (v:=evaluate(n,profile)) is not None]
    found.sort(key=lambda r:(-int(r["_sort"][0]),-r["priority_tier"],
                              -r["_sort"][2],r["id"]))
    public=[]
    for i,r in enumerate(found[:limit],1):
        out={k:v for k,v in r.items() if k!="_sort"}
        out["review_rank"]=i
        public.append(out)
    return {"total_notices":len(notices),"review_priority_count":len(found),
            "rfp_evidence_count":sum(x["priority_tier"]>=2 for x in found),
            "metadata_only_count":sum(x["priority_tier"]<2 for x in found),
            "profile_categories":[x for x in profile.get("categories",[])
                if x in CATEGORIES] if isinstance(profile.get("categories"),list) else [],
            "results":public,
            "basis":"공식 공고 분류·유효 RFP 발췌를 통한 상세검토 순위. 참가자격·기술수행 가능성·원가·실제 AI 분석은 미검증",
            "analysis_mode":"RULE_BASED_READ_ONLY",
            "legal_eligibility":"UNVERIFIED"}
