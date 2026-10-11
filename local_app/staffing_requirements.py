"""공식 RFP 발췌에서 명시적 인력 요건 후보를 추출하는 읽기 전용 계약.

목적/책임: 출처가 있는 공식 문서 발췌에서 역할·내부 등급과 유사한 인원 숫자를 보수적으로 식별.
입력/출력: 공고별 문서 evidence / 검토 필요 요건과 비공개 인력의 역할별 집계 비교.
신뢰 경계: RFP는 비신뢰 텍스트이며 실행 명령으로 처리하지 않는다. 회사 인력 원본은 응답에 포함하지 않는다.
상태 변경/부작용: 없음. 공개 모델 호출, 네트워크 요청, 원본 파일 쓰기 없음.
실패: 문서 누락/불완전, 우대/예시, 근거 부족은 확인 필요로 유지한다.
불변: 내부분류 등급과 발주기관 법정 기술자 등급은 동일하다고 가정하지 않으며 적격/부족/이익 확정 금지.
검증: local_app/test_staffing_requirements.py, docs/design/STAFFING_RFP_SLICE_2026-10-11.md.
"""
from __future__ import annotations

import hashlib
import re

ROLE = re.compile(r"데이터\s*분석가|시스템\s*분석가|분석\s*인력|분석가|SW\s*개발자|소프트웨어\s*개발자|개발\s*인력|개발자|프로그래머", re.I)
GRADE = re.compile(r"(?<![가-힣])(초급|중급|고급)(?![가-힣])")
COUNT = re.compile(r"(?<!\d)([1-9]\d{0,1})\s*명(?:\s*(이상))?(?!\w)")
HEADING = re.compile(r"필수\s*(?:투입\s*)?인력|요구\s*(?:투입\s*)?인력|인력\s*요구\s*사항|투입\s*인력.{0,15}(?:자격|요건|기준)|인력\s*자격\s*요건", re.I)
OPTIONAL = re.compile(r"우대\s*사항|권장|예시|참고\s*자료|평가\s*예시|샘플|가점\s*항목|제안\s*인력", re.I)
SKILLS = {"JAVA": re.compile(r"(?<![A-Za-z])JAVA(?![A-Za-z])", re.I),
          "PYTHON": re.compile(r"(?<![A-Za-z])PYTHON(?![A-Za-z])", re.I),
          "DB": re.compile(r"(?<![A-Za-z])DB(?![A-Za-z])|데이터\s*베이스", re.I),
          "ML": re.compile(r"(?<![A-Za-z])ML(?![A-Za-z])|머신\s*러닝", re.I),
          "AI": re.compile(r"(?<![A-Za-z])AI(?![A-Za-z])|인공\s*지능", re.I)}
MAX_DOCUMENTS = 2
MAX_EXCERPT = 6000
MAX_RESULTS = 30


def sources(notice):
    """추출 성공 evidence 중 유효한 앞 2개를 고르되 문서별 출처 한계를 유지."""
    if notice.get("document_status") != "EXTRACTED":
        return []
    evidence=notice.get("document_evidence",[])
    if not isinstance(evidence,list):
        raise ValueError("RFP 문서 evidence 배열 손상")
    result=[]
    for item in evidence:
        if len(result)>=MAX_DOCUMENTS:
            break
        if (not isinstance(item,dict) or item.get("status")!="EXTRACTED"
                or not isinstance(item.get("excerpt"),str) or not item["excerpt"].strip()):
            continue
        sha=item.get("sha256")
        if not isinstance(sha,str) or not re.fullmatch("[0-9a-fA-F]{64}",sha):
            continue
        excerpt=item["excerpt"][:MAX_EXCERPT]
        result.append({"name":str(item.get("name","공식 문서"))[:150],
                       "sha256":sha.lower(),
                       "excerpt_sha256":hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
                       "text":excerpt,
                       "excerpt_truncated":(len(item["excerpt"])>MAX_EXCERPT
                            or (type(item.get("chars")) is int and item["chars"]>len(item["excerpt"]))),
                       "source_status":"HASH_FORMAT_PRESENT_UNVERIFIED"})
    if not result and isinstance(notice.get("rfp_text"),str) and notice["rfp_text"].strip():
        # 해시/원문 결속을 재확인할 수 없는 구형 저장 발췌는 별도 상태로 유지.
        excerpt=notice["rfp_text"][:MAX_EXCERPT]
        result.append({"name":str(notice.get("document_source_name") or "기존 문서 발췌")[:150],
                       "sha256":None,
                       "excerpt_sha256":hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
                       "text":excerpt,
                       "excerpt_truncated":len(notice["rfp_text"])>MAX_EXCERPT,
                       "source_status":"LEGACY_SOURCE_UNVERIFIED"})
    return result


def _role(text):
    match = ROLE.search(text)
    if not match:
        return None
    return "analyst" if "분석" in match.group(0) else "developer"


def _find_candidates(source):
    lines = source["text"].splitlines()  # 상한 6,000자 이내의 줄은 전부 읽음
    context_to = -1
    optional_section = False
    for i, line in enumerate(lines):
        candidate = re.sub(r"\s+", " ", line).strip()
        if not candidate:
            continue
        # 우대/예시 구간은 명시적 필수 인력 제목이 다시 등장할 때까지 제외.
        if OPTIONAL.search(candidate):
            context_to = -1
            optional_section = True
            continue
        if optional_section:
            if HEADING.search(candidate):
                optional_section = False
            else:
                continue
        if HEADING.search(candidate):
            context_to = i + 7
        if i > context_to:
            continue
        for segment in re.split("[,;|•·]", candidate):
            segment = segment.strip()
            r, g, c = _role(segment), GRADE.search(segment), COUNT.search(segment)
            if not (r and g and c) or len(segment) > 240:
                continue
            # 여러 역할이 섞인 행은 잘못 배정하기 쉬워 자동 후보에서 제외.
            if len(ROLE.findall(segment)) != 1 or len(GRADE.findall(segment)) != 1 or len(COUNT.findall(segment)) != 1:
                continue
            skills = sorted(k for k,pattern in SKILLS.items() if pattern.search(segment))
            yield {"role":r, "grade": {"초급":"junior","중급":"intermediate","고급":"senior"}[g.group(1)],
                   "headcount":int(c.group(1)), "count_kind":"AT_LEAST" if c.group(2) else "STATED", "skills":skills,
                   "source_excerpt":segment[:220], "source_document":source["name"],
                   "source_sha256":source["sha256"], "excerpt_sha256":source["excerpt_sha256"],
                   "source_status":source["source_status"],
                   "evidence_status":"EXTRACTED_CANDIDATE_UNVERIFIED"}


def assess(notice, workforce=None):
    """집계와만 비교; 추정 기술·내부 등급·공수로 충족/부족을 판정하지 않는다."""
    evidence=notice.get("document_evidence",[])
    if not isinstance(evidence,list):
        raise ValueError("RFP 문서 evidence 배열 손상")
    usable_count=sum(
        isinstance(e,dict) and e.get("status")=="EXTRACTED"
        and isinstance(e.get("excerpt"),str) and bool(e["excerpt"].strip())
        and isinstance(e.get("sha256"),str)
        and bool(re.fullmatch(r"[0-9a-fA-F]{64}",e["sha256"]))
        for e in evidence
    )
    docs = sources(notice)
    requirements, seen = [], set()
    for doc in docs:
        for item in _find_candidates(doc):
            signature = (item["role"], item["grade"], item["headcount"], item["count_kind"], tuple(item["skills"]), item["source_excerpt"])
            if signature in seen:
                continue
            seen.add(signature)
            requirements.append(item)
            if len(requirements) >= MAX_RESULTS:
                break
        if len(requirements) >= MAX_RESULTS:
            break
    roles = {}
    if workforce:
        roles = {(row["role_code"],row["grade"]):row for row in workforce["roles"]}
    for item in requirements:
        row = roles.get((item["role"], item["grade"]))
        item["nominal_internal_grade_count"] = row["headcount"] if row else 0 if workforce else None
        item["matching_status"] = "NEEDS_EVIDENCE"
        item["matching_explanation"] = (
            "내부 등급은 발주기관의 공식 기술자 등급을 대체할 수 없고, "
            "기술·자격증·투입기간·개별 가용공수를 검증해야 합니다."
        )
    document_state = ("NO_RFP_EXTRACTED" if not docs else
                      "EXTRACTED_REQUIREMENTS_FOR_REVIEW" if requirements else
                      "NO_EXPLICIT_REQUIREMENT_FOUND")
    return {
        "notice_id":notice.get("id"), "document_state":document_state,
        "document_count":len(docs),
        "total_document_evidence_count":len(evidence),
        "processed_document_count":len(docs),
        "skipped_document_count":len(evidence)-usable_count+max(0,usable_count-MAX_DOCUMENTS),
        "skipped_nonextracted_or_invalid_count":len(evidence)-usable_count,
        "skipped_due_to_limit_count":max(0,usable_count-MAX_DOCUMENTS),
        "any_text_truncated":any(d["excerpt_truncated"] for d in docs),
        "excerpt_char_limit":MAX_EXCERPT, "requirement_count":len(requirements),
        "requirements":requirements, "workforce_state":"LOCAL_AGGREGATE_ONLY" if workforce else "NOT_CONFIGURED",
        "staffing_eligibility":"UNVERIFIED",
        "assessment":"NEEDS_HUMAN_VERIFICATION",
        "warning":"RFP 발췌의 명시적 표현만 탐지한 예비 결과입니다. 표·각주·원본 전체·정정공고·법적 기술등급·투입 기간·실제 가용 공수를 확인해야 합니다.",
    }
