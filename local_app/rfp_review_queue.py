"""RFP 추출 품질 위험 기반 사람 검토 큐. 비공개 원문·첨부주소 미반환.
검토 우선순위만 표시, RFP 원본/캐시 SHA 확인·자동 입찰적격 판정 불가.
입력: 공식 저장 공고 및 관심분야 프로필. 출력: 식별자/고정 위험 플래그/건수.
부작용: 없음. 네트워크/데이터 갱신·유료 AI 호출 금지.
출력 계약: 각 행에 원본 페이지·표·각주·OCR 수동 검토 항목을 제공한다.
저장 메타데이터만으로 실제 페이지 위치나 구조 진단 결과를 만들어내지 않는다.
"""
import re
from rfp_coverage import _quality_flags, _status
from procurement_filter import bid_window

WEIGHTS={
 "STALE_RFP":100,"PARSER_TRUNCATION_REPORTED":60,
 "PARSER_WARNING_REPORTED":45,"EXCERPT_OR_LEGACY_ONLY":35,
 "EXTRACTED_WITHOUT_PROVENANCE":35,"MALFORMED_EVIDENCE":30,
 "EVIDENCE_SCAN_OVER_LIMIT":25,"ATTACHMENT_SCAN_OVER_LIMIT":25,
 "EXTRACTED_EVIDENCE_OVER_TWO":20,
 "FULLTEXT_REFERENCE_UNVERIFIED":10,
}
BLOCKED=frozenset(("CANCELLED_OR_SUPERSEDED","LIFECYCLE_REVIEW"))
MAX_ITEMS=100

def build(notices,profile,limit=30):
    if not isinstance(notices,list) or len(notices)>10000 or not isinstance(profile,dict):
        raise ValueError("검토 큐 입력 형식 오류")
    categories=profile.get("categories")
    if not isinstance(categories,list) or type(limit) is not int or not 1<=limit<=MAX_ITEMS:
        raise ValueError("검토 큐 필터 오류")
    chosen=set(x for x in categories if isinstance(x,str))
    rows=[]
    for n in notices:
        if not isinstance(n,dict):raise ValueError("공고 형식 오류")
        if n.get("department_status")!="CANDIDATE":continue
        cats=n.get("department_categories")
        if not isinstance(cats,list) or not chosen.intersection(x for x in cats if isinstance(x,str)):continue
        ident=n.get("id")
        if not isinstance(ident,str) or not re.fullmatch(r"G2B-[A-Za-z0-9-]{4,100}",ident):continue
        flags=_quality_flags(n)
        if flags & BLOCKED:
            continue
        window=bid_window(n.get("end"),n.get("notice_kind",""),n.get("qualification_deadline",""))
        if window not in ("OPEN","REGISTRATION_REVIEW"):continue
        state=_status(n)
        if state=="FAILED_ATTEMPT":flags.add("EXTRACTION_FAILED")
        if state!="EXTRACTED_TEXT":flags.add("ORIGINAL_TEXT_NOT_AVAILABLE")
        if not flags:
            continue
        priority=max([WEIGHTS.get(f,15) for f in flags])
        rows.append({"id":ident,"priority":priority,"document_state":state,
                     "flags":sorted(flags),"status":"MANUAL_REVIEW_REQUIRED",
                     "required_review":[
                         "공식 최신 원본과 페이지별 추출 범위·잘림 대조",
                         "표의 행·열·병합 셀 및 읽기 순서 확인",
                         "각주·단서·예외조항과 본문 연결 확인",
                         "스캔·이미지와 OCR의 숫자·날짜·자격 표현 육안 대조"],
                     "structural_diagnostic":"NOT_PERFORMED_BY_QUEUE",
                     "legal_eligibility":"UNVERIFIED"})
    rows.sort(key=lambda x:(-x["priority"],x["id"]))
    return {"mode":"STORED_METADATA_TRIAGE_ONLY","total":len(rows),
            "results":rows[:limit],"omitted_count":max(0,len(rows)-limit),
            "original_page_recall":"NOT_VERIFIED","human_review_required":True}
