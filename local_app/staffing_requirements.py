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
COUNT = re.compile(
    r"(?<!\d)(최소\s*)?([1-9]\d{0,3})\s*명"
    r"(?:(\s*이상(?:은|이|을|를|으로|의)?)|(?!\s*이상))"
    r"(?![가-힣A-Za-z0-9])"
)
HEADING = re.compile(r"필수\s*(?:투입\s*)?인력|요구\s*(?:투입\s*)?인력|인력\s*요구\s*사항|투입\s*인력.{0,15}(?:자격|요건|기준)|인력\s*자격\s*요건", re.I)
OPTIONAL = re.compile(r"우대\s*사항|권장|예시|참고\s*자료|평가\s*예시|샘플|가점\s*항목|제안\s*인력", re.I)
NEGATIVE = re.compile(r"없음|미요구|요구\s*(?:하지|되지)\s*않|요구\s*없|필요\s*(?:하지|치)\s*않|필요\s*없|자율|불필요|미필요|재량|비요구", re.I)
COUNT_NEGATIVE = re.compile(r"\d{1,4}\s*명(?:\s*이상(?:으로|은|이|을|를|의)?)?(?:은|이|을|를)?\s*(?:별도(?:로)?\s*)?(?:요구\s*(?:하지|되지)\s*않|요구\s*없|필요\s*(?:하지|치)\s*않|필요\s*없|없음|미요구|불필요|자율\s*구성)", re.I)
QUALIFICATION_EXEMPTION = re.compile(r"(?:자격증|면허|기술\s*자격|인증서).{0,48}?(?:요구\s*(?:하지|되지)\s*않|필요\s*(?:하지|치)\s*않|필요\s*없|없음|불필요|미요구)", re.I)
UPPER_BOUND = re.compile(r"최대\s*\d{1,4}\s*명|\d{1,4}\s*명\s*(?:이내|이하|내외)|상한\s*\d{1,4}\s*명", re.I)
COMBINED_ROLES = re.compile(r"(?:"+ROLE.pattern+r")\s*[·/]\s*(?:"+ROLE.pattern+r")", re.I)
# 한 줄에 명시적으로 '해당 인력은 요구하지 않음'이 연결된 수량은 필수 인원으로 판정하지 않는다.
TARGETED_NEGATION = re.compile(
    r"\d{1,4}\s*명(?:\s*이상)?[^\n]{0,90}(?:해당\s*인력|그\s*인력|위\s*인력)"
    r"[^\n]{0,35}(?:요구\s*(?:하지|되지)\s*않|필요\s*(?:하지|치)\s*않|필요\s*없|불필요)",
    re.I
)
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
    for ordinal,item in enumerate(evidence,1):
        if len(result)>=MAX_DOCUMENTS:
            break
        if (not isinstance(item,dict) or item.get("status")!="EXTRACTED"
                or not isinstance(item.get("excerpt"),str) or not item["excerpt"].strip()):
            continue
        sha=item.get("sha256")
        sha_valid=isinstance(sha,str) and bool(re.fullmatch(r"[0-9a-fA-F]{64}",sha))
        identity=item.get("identity")
        identity_valid=isinstance(identity,str) and bool(re.fullmatch(r"[0-9a-fA-F]{64}",identity))
        excerpt=item["excerpt"][:MAX_EXCERPT]
        result.append({"name":"저장 문서 #"+str(ordinal),
                       "sha256":sha.lower() if sha_valid else None,
                       "source_identity":identity.lower() if identity_valid else None,
                       "excerpt_sha256":hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
                       "text":excerpt,
                       "excerpt_truncated":(len(item["excerpt"])>=MAX_EXCERPT
                            or (type(item.get("chars")) is int and item["chars"]>len(item["excerpt"]))),
                       "source_status":("HASH_FORMAT_PRESENT_UNVERIFIED" if sha_valid
                                        else "HASH_MISSING_UNVERIFIED" if sha is None
                                        else "HASH_INVALID_UNVERIFIED")})
    if not result and isinstance(notice.get("rfp_text"),str) and notice["rfp_text"].strip():
        # 해시/원문 결속을 재확인할 수 없는 구형 저장 발췌는 별도 상태로 유지.
        excerpt=notice["rfp_text"][:MAX_EXCERPT]
        result.append({"name":"구형 발췌",
                       "sha256":None,
                       "source_identity":None,
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
        # 원본/발췌가 잘린 마지막 행은 뒤의 부정문·표 요소가 누락될 수 있다.
        if (source["excerpt_truncated"] and i==len(lines)-1
                and not source["text"].endswith(("\n","\r"))):
            continue
        # 우대/예시 구간은 명시적 필수 인력 제목이 다시 등장할 때까지 제외.
        # 부정 표현이 인력요건 자체를 가리킬 때만 영역을 종료한다.
        # 예: "개발자 고급 2명 (별도 자격증 필요 없음)"은 인력 필요가 분명하다.
        # 쉼표 뒤의 별도 인력 부정이 앞의 필수 역할을 무효화하지 않게 한다.
        heading_clause = re.split("[,;|•·]", candidate, maxsplit=1)[0]
        # 같은 문장에 자격증 면제와 인력 자율구성이 공존하면 먼저 나타난
        # 인력 자체의 부정은 살아 있어야 한다.
        qualification_exemption = QUALIFICATION_EXEMPTION.search(heading_clause)
        staffing_negation = bool(NEGATIVE.search(
            heading_clause[:qualification_exemption.start()]
            if qualification_exemption else heading_clause
        ))
        explicit_no_staff = bool(re.search(
            r"(?:필수|요구)\s*(?:투입\s*)?인력\s*(?:은|이|:)?\s*"
            r"(?:없음|미요구|불필요|필요\s*없음|자율\s*구성)",
            heading_clause
        ))
        no_staffing = explicit_no_staff or (
            staffing_negation
            and bool(HEADING.search(heading_clause))
            and not (ROLE.search(heading_clause) and GRADE.search(heading_clause) and COUNT.search(heading_clause))
        ) or bool(re.fullmatch(
            r"(?:해당\s*사항\s*)?(?:없음|미요구|요구\s*없음|필요\s*없음|자율\s*구성|불필요)[.!]?",
            candidate
        ))
        if OPTIONAL.search(candidate) or no_staffing:
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
        # 여러 직무가 동일 인원을 공유하는 표현은 한 직무에 배정하지 않는다.
        if COMBINED_ROLES.search(candidate) or TARGETED_NEGATION.search(candidate):
            continue
        for segment in re.split("[,;|•·]", candidate):
            segment = segment.strip()
            r, g, c = _role(segment), GRADE.search(segment), COUNT.search(segment)
            if (COUNT_NEGATIVE.search(segment) or UPPER_BOUND.search(segment)
                    or not (r and g and c) or len(segment) > 240):
                continue
            # 여러 역할이 섞인 행은 잘못 배정하기 쉬워 자동 후보에서 제외.
            if len(ROLE.findall(segment)) != 1 or len(GRADE.findall(segment)) != 1 or len(COUNT.findall(segment)) != 1:
                continue
            skills = sorted(k for k,pattern in SKILLS.items() if pattern.search(segment))
            yield {"role":r, "grade": {"초급":"junior","중급":"intermediate","고급":"senior"}[g.group(1)],
                   "headcount":int(c.group(2)), "count_kind":"AT_LEAST" if (c.group(1) or c.group(3)) else "STATED",
                   "headcount_check":"OUT_OF_RANGE_FOR_REVIEW" if int(c.group(2))>500 else "STANDARD_CANDIDATE",
                   "skills":skills,
                   # 공개 응답에는 자유서술 발췌를 내보내지 않는다. 개인식별자·연락처 보호.
                   "source_excerpt":" ".join([ROLE.search(segment).group(0),g.group(1),c.group(0)]+skills)[:120],
                   "source_document":source["name"],
                   "source_sha256":source["sha256"], "excerpt_sha256":source["excerpt_sha256"],
                   "source_identity":source["source_identity"],"excerpt_line":i+1,
                   "original_page":"UNKNOWN", "source_status":source["source_status"],
                   "evidence_status":"EXTRACTED_CANDIDATE_UNVERIFIED"}


def assess(notice, workforce=None):
    """집계와만 비교; 추정 기술·내부 등급·공수로 충족/부족을 판정하지 않는다."""
    evidence=notice.get("document_evidence",[])
    if not isinstance(evidence,list):
        raise ValueError("RFP 문서 evidence 배열 손상")
    usable_count=sum(
        isinstance(e,dict) and e.get("status")=="EXTRACTED"
        and isinstance(e.get("excerpt"),str) and bool(e["excerpt"].strip())
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
