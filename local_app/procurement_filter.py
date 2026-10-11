"""공개 용역 메타데이터·RFP 텍스트를 이용한 부서 관심분야 후보 분류.

입력: 나라장터 공개 API 필드 및 선택적으로 추출된 공식 첨부문서 텍스트.
출력: 마감/취소 상태, 분야 후보, 출처별 근거. 실제 회사 참가자격 적격 여부는 항상 미검증.
신뢰 경계: 필드는 비신뢰 문자열로 취급, 동적 코드/LLM/외부 전송 없음.
부작용: 없음. 모든 분야 판단은 재계산 가능.
실패: 기한 파싱 실패나 분류 미확정은 REVIEW/UNKNOWN으로 보존, 데이터 삭제 금지.
"""
from datetime import datetime, timezone, timedelta
import re

KST = timezone(timedelta(hours=9))
CATEGORIES = {
    "AI": "AI 서비스·LLM",
    "SW": "SW·업무시스템 개발",
    "DATA": "데이터 수집·분석·플랫폼",
    "SECURITY": "보안·인증·감사 지원 SW",
}
TAXONOMY = {
    "AI": ("인공지능", "AI서비스", "인공지능기반", "지능형소프트웨어"),
    "SW": ("정보시스템개발", "소프트웨어개발", "응용소프트웨어", "소프트웨어엔지니어링",
           "시스템통합", "정보시스템구축", "전산업무개발", "정보화시스템"),
    "DATA": ("데이터처리", "데이터분석", "빅데이터", "데이터베이스", "데이터구축",
             "데이터품질", "데이터수집", "데이터통합", "데이터플랫폼"),
    "SECURITY": ("정보보안", "보안소프트웨어", "정보시스템감리", "정보보호", "정보보안컨설팅"),
}
TEXT_TERMS = {
    "AI": ("AI 서비스", "AI 플랫폼", "AI 데이터", "생성형 AI", "LLM", "RAG", "인공지능 서비스", "AI 기반 시스템",
           "인공지능 활용 시스템", "AI 에이전트", "AI Agent", "AI 시스템", "머신러닝 서비스"),
    "SW": ("정보시스템 개발", "정보시스템 구축", "정보시스템 고도화", "소프트웨어 개발",
           "업무시스템 개발", "업무시스템 구축", "시스템 개발", "시스템 구축",
           "시스템 고도화", "시스템통합", "서비스 구현", "플랫폼 구축",
           "플랫폼 개발", "앱 개발", "웹 개발", "웹 서비스", "애플리케이션 개발",
           "백엔드", "프론트엔드", "API 개발", "홈페이지 구축", "전자정부"),
    "DATA": ("데이터 수집", "데이터 처리", "데이터 정제", "데이터 분석", "DB 구축",
             "데이터베이스 구축", "데이터 연계", "ETL", "데이터 파이프라인",
             "빅데이터 플랫폼", "데이터 품질", "빅데이터 분석"),
    "SECURITY": ("정보보안 시스템", "보안 솔루션", "정보보호 관리체계", "ISMS", "GRC",
                 "감사 자동화", "인증 심사 시스템", "보안관제 시스템", "감리 지원"),
}
# 제목만으로 자동 제외하지 않는다. 분류 근거 우선순위를 낮추는 보조 신호.
NON_DEVELOPMENT = ("행사 대행", "행사운영", "포럼 운영", "교육 운영", "해외연수", "여행 용역",
                   "홍보 대행", "광고대행", "콘텐츠 제작", "시설 관리", "경비 용역")
CLOSED = ("취소공고", "취소", "공고취소")


def timestamp(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00")).replace(
            tzinfo=KST) if ("+" not in value and "Z" not in value) else datetime.fromisoformat(
                value.strip().replace("Z", "+00:00")).astimezone(KST)
    except ValueError:
        return None


def bid_window(closing, kind="", qualification_cutoff="", at=None):
    now = at or datetime.now(KST)
    if any(k in str(kind) for k in CLOSED):
        return "CANCELLED"
    due = timestamp(closing)
    if due is None:
        return "UNKNOWN"
    if due <= now:
        return "CLOSED"
    # 등록기한이 지났어도 이미 입찰등록된 업체는 참여할 수 있음. 단정 금지.
    q = timestamp(qualification_cutoff)
    return "REGISTRATION_REVIEW" if q and q <= now else "OPEN"


def classify(title="", procurement="", filenames=None, rfp_text="", info_biz=""):
    title = str(title or "")[:500]
    procurement = str(procurement or "")[:300]
    filenames = [str(x)[:180] for x in (filenames or [])[:10]]
    rfp_text = str(rfp_text or "")[:12000]
    output = []
    evidence = []
    for category in CATEGORIES:
        sources = []
        if any(term.casefold() in procurement.casefold() for term in TAXONOMY[category]):
            sources.append("공공조달분류")
        # 정보화사업 여부는 단독으로 개발 확정 근거가 아님. 검토대기로 남긴다.
        if any(term.casefold() in title.casefold() for term in TEXT_TERMS[category]):
            sources.append("공고명")
        if any(term.casefold() in " ".join(filenames).casefold() for term in TEXT_TERMS[category]):
            sources.append("첨부파일명")
        if any(term.casefold() in rfp_text.casefold() for term in TEXT_TERMS[category]):
            sources.append("RFP 추출본문")
        if sources:
            output.append(category)
            evidence.append({"category": category, "sources": sources})
    contains_non_dev = any(x.casefold() in title.casefold() for x in NON_DEVELOPMENT)
    if output:
        status = "REVIEW" if contains_non_dev and not any(
            "공공조달분류" in item["sources"] or "RFP 추출본문" in item["sources"] for item in evidence) else "CANDIDATE"
    else:
        status = "REVIEW" if info_biz == "Y" or filenames or not rfp_text else "OUT_OF_SCOPE"
    return {"department_categories": output, "department_status": status,
            "category_evidence": evidence, "needs_document": not bool(rfp_text.strip()),
            "classification_version": 1}


def apply(notice, at=None):
    notice.update(classify(notice.get("title", ""), notice.get("procurement_classification", ""),
                           [x.get("name", "") for x in notice.get("attachments", [])],
                           notice.get("rfp_text", ""), notice.get("information_business", "")))
    notice["window_status"] = bid_window(notice.get("end"), notice.get("notice_kind", ""),
                                           notice.get("qualification_deadline", ""), at=at)
    notice["legal_eligibility"] = "UNVERIFIED"
    return notice
