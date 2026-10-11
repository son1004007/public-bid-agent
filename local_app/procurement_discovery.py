"""제목 기반 선별에서 누락될 수 있는 REVIEW 용역의 메타데이터 우선순위.

목적: 전체 원본은 보존하고 정보화사업·공공조달분류·공식 첨부로 상세검토 후보만 제시.
입력: 이미 수집한 공식 나라장터 공고; 출력: 출처가 기록된 미확인 검토 순위.
신뢰경계: 메타데이터만 읽으며 원격 조회, 모델 요청, 임의 명령 실행 없음.
상태 변경: 없음. 법적 적격성·실제 부서 수행가능성을 자동 확정하지 않음.
실패: 확인되지 않은 정보는 점수에 반영하지 않고 수동 RFP 확인을 안내.
검증: local_app/test_procurement_discovery.py.
"""
import re

POSITIVE = ("개발", "고도화", "구축", "신규", "개선", "재구축", "전환", "서비스")
TAXONOMY = ("소프트웨어", "정보시스템", "정보화", "데이터", "전산", "인공지능",
            "웹", "디지털", "정보보안", "시스템개발", "정보통신")
OPERATIONS = ("유지관리", "유지보수", "운영", "장비", "임대", "시설", "행사", "용역대행")
DOC_TERMS = ("제안요청", "과업지시", "과업내용")
BROAD = ("정보시스템", "데이터", "소프트웨어", "플랫폼", "인공지능", "디지털")


def evaluate(notice):
    if not isinstance(notice, dict) or notice.get("department_status") != "REVIEW":
        return None
    title = str(notice.get("title") or "")[:250]
    taxonomy = str(notice.get("procurement_classification") or "")[:220]
    attachments = [f for f in notice.get("attachments", []) if isinstance(f, dict)]
    names = " ".join(str(f.get("name") or "")[:150] for f in attachments[:40])
    score, evidence = 0, []
    if notice.get("information_business") == "Y":
        evidence.append({"source":"나라장터 정보화사업 여부","value":"Y","weight":5})
        score += 5
    matching = [term for term in TAXONOMY if term.lower() in taxonomy.lower()]
    if matching:
        term = matching[0]
        evidence.append({"source":"나라장터 공공조달분류","value":taxonomy,"weight":4})
        score += 4
    if any(term in names for term in DOC_TERMS):
        evidence.append({"source":"공식 첨부 파일명","value":"제안요청/과업 관련 첨부 존재","weight":2})
        score += 2
    if any(term in title for term in BROAD):
        evidence.append({"source":"공고명","value":title,"weight":2})
        score += 2
    if any(term in title for term in POSITIVE):
        evidence.append({"source":"공고명 개발/구축 신호","value":title,"weight":3})
        score += 3
    if any(term in title for term in OPERATIONS):
        score -= 4
        evidence.append({"source":"공고명 운영/물품 위험","value":title,"weight":-4})
    if score < 5:
        return None
    return {"id":notice["id"],"title":title,"score":score,
            "window_status":notice.get("window_status","UNKNOWN"),
            "official_url":notice.get("source_url"),
            "eligibility":"UNVERIFIED","status":"DETAIL_REVIEW_REQUIRED",
            "evidence":evidence}


def shortlist(notices, limit=30):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("검토 우선순위 반환 한도 오류")
    candidates=[item for n in notices if (item:=evaluate(n)) is not None]
    candidates.sort(key=lambda x: (x["window_status"] not in ("OPEN","REGISTRATION_REVIEW"),
                                  -x["score"],x["id"]))
    return {"total_review":sum(n.get("department_status")=="REVIEW" for n in notices),
            "priority_count":len(candidates),"results":candidates[:limit],
            "basis":"공식 메타데이터만 사용한 상세검토 우선순위, SW 개발/법적 참가자격 미확인"}
