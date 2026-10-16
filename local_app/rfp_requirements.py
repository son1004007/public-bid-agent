"""공식 RFP 요구사항 후보의 증거 결속형, 읽기 전용 규칙 추출기.

목적: 기존 44,000자 청크/검증된 excerpt에서 참가자격·평가기준·면허·실적·과업·기술·인력·기간·예산의 9개 원문 표현 후보 추출.
입력/출력: 공식 공고 record와 비공개 root -> 카테고리별 근거 JSON, 원본 페이지 불명 표시.
신뢰 경계: 비신뢰 문서 본문을 자연어 데이터로만 취급; 유료 AI/API/도구 지시 금지.
부작용: 없음. 호출 시 파일을 쓰지 않고 저장 RFP/담당자 판단을 보존.
실패: 원문 청크 무결성·첨부 identity 불일치 시 사용 거부; STALE·취소·구차수는 분석 보류.
불변조건: 추출된 표현과 5건 표시 상한 이후의 생략 후보 수는 원문 전체 필수요건/Recall 또는 참가자격 판정이 아니다. 원본 PDF/HWP 페이지·표 위치를 추정하지 않는다.
관련: rfp_fulltext.py, rfp_batch.py, test_rfp_requirements.py, docs/design/RFP_REQUIREMENTS_SLICE_2026-10-13.md.
"""
import hashlib
import re
from pathlib import Path

from rfp_fulltext import load as load_fulltext
from procurement_documents import official_url
from notice_lifecycle import is_cancel_kind

SCHEMA_VERSION = 2
MAX_DOCS = 2
MAX_EVIDENCE_SCAN = 120
MAX_ATTACHMENT_SCAN = 400
MAX_MATCHES_PER_CATEGORY = 5
MAX_EVIDENCE_CHARS = 220
MAX_TEXT = 44000
_CATEGORIES = (
    # 공동수급 '점수 합산/동점 처리'는 참가자격이 아니므로 공동수급 단독 매칭을 금지한다.
    ("participation", "입찰참가자격",
     r"입찰\s*참가\s*자격|참가\s*자격|입찰\s*등록|"
     r"공동\s*(?:수급|도급)(?:체)?\s*(?:의\s*)?(?:구성(?!원)|참여|가능|허용|불허|제한|협정|자격|방식)|"
     r"공동\s*수급\s*협정서|단독\s*입찰|직접생산확인|중소기업확인"),
    ("evaluation", "평가기준·선정방식",
     r"평가\s*(?:기준|방법|항목|배점|점수|결과|표|위원)|"
     r"(?:기술|가격|정량|정성|적격)\s*평가|제안서\s*평가|"
     r"배점|득점|평점|가점|감점|동점|점수\s*(?:를|을|가|에|의|로)?\s*(?:합산|산정|배분|차등|지분율|곱하|높은|따라|평가)|"
     r"(?:협상|낙찰)\s*(?:대상자|적격자|순위|기준)|평가\s*순위|"
     r"(?:최종|종합)\s*평가|소수점\s*이하\s*(?:점수|숫자)|"
     r"(?:사업\s*(?:내용|목표|이해도)|제안사의\s*추진\s*전략).{0,65}평가|"
     r"(?:적절성|적합성|우수성|이해도)\s*[:：].{0,120}(?:하였는가|있는가|되는가|여부|대책)"),
    ("licenses", "업종·면허·인증", r"소프트웨어사업자|정보통신공사업|업종\s*제한|면허|인가|인증\s*(?:요건|자격|서)|ISO\s*27001|ISMS-P|조달청\s*등록"),
    ("track_record", "수행실적", r"유사\s*(?:사업|용역)|수행\s*실적|납품\s*실적|실적\s*증명|최근\s*\d{1,2}\s*년"),
    ("scope", "과업 요구사항", r"과업\s*(?:범위|내용|목적)|주요\s*과업|사업\s*내용|구축\s*대상|기능\s*요구|수행\s*내용|업무\s*범위"),
    ("technology", "기술요건", r"(?<![A-Za-z])(?:Java|Spring|Python|FastAPI|LLM|RAG|LangGraph|DBMS|PostgreSQL|Oracle|API)(?![A-Za-z])|클라우드|데이터베이스|컨테이너|생성형\s*AI|인공지능"),
    ("staffing", "인력·공수", r"투입\s*인력|인력\s*(?:구성|운영|배치)|[초중고특]급\s*기술자|상주\s*인력|인력\s*투입|투입\s*공수|인월|(?<![A-Za-z])M/M(?![A-Za-z])|인건비"),
    ("duration", "사업기간", r"(?:사업|수행|계약)\s*기간|납품\s*기한|착수일|준공일|완료\s*기한|\d{1,2}\s*개월\s*(?:이내|동안|간)"),
    ("budget", "예산·사업비", r"사업\s*예산|(?:총\s*)?사업비|예산액|추정\s*가격|기초\s*금액|사업\s*금액|부가가치세|계약\s*금액"),
)
COMPILED = [(key, name, re.compile(expr, re.IGNORECASE)) for key,name,expr in _CATEGORIES]
_HEX = re.compile(r"^[0-9a-f]{64}$")
_SCOPE_ACTION = re.compile(
    r"구축|개발|도입|연계|수집|운영|분석|설계|구현|개선|제공|점검|정비|산출물|"
    r"유지\s*보수|가공|검수|제작|처리|관리|작성|연동|명세|교육|지원|통합")
# 행정 안내와 실제 기술 수행 범위가 같은 줄에 섞여 있으면 과업 후보를 소거하지 않는다.
_SCOPE_DELIVERY = re.compile(
    r"(?:데이터|시스템|API|플랫폼|서비스|기능|인터페이스).{0,45}(?:연계|개발|구축|구현|개선|가공|수집|처리)|"
    r"(?:연계|개발|구축|구현|개선).{0,40}(?:시스템|API|플랫폼|서비스|기능)", re.IGNORECASE)
_PARTICIPATION_DECISION = re.compile(
    r"(?:참여|참가)\s*(?:가능|허용|제한|불가|금지)|"
    r"공동\s*(?:수급|도급)(?:체)?\s*(?:(?:참여|참가)\s*(?:가능|허용|불가|제한)|가능|허용|불허|제한|금지)|"
    r"구성\s*(?:이|을|은)?\s*(?:가능|허용|불허|제한)")
_EVALUATION_ADMIN = re.compile(r"평가\s*결과\s*(?:승복|확인|동의|통보)|(?:평가|제안서)\s*(?:승복|확인|동의)\s*(?:서|서약)")
_SCOPE_ADMIN = re.compile(
    r"사업\s*내용(?:이|의)?\s*변경|과업\s*(?:범위|내용)\s*(?:변경|확정)|"
    r"과업\s*심의위원회|하자\s*(?:보증|보수)|보증\s*기간|계약\s*금액.{0,45}조정|"
    r"과업\s*내용서에\s*규정되지|과업\s*내용의\s*(?:추진|진행)|"
    r"과업\s*내용.{0,30}(?:사업비\s*정산|계약\s*금액)")
_SCOPE_HEADING = re.compile(
    r"^\s*(?:\d+(?:[.\-]\d+)*[.)]?\s*|[가-하][.)]\s*)?"
    r"(?:세부\s*)?(?:(?:감리\s*대상)?\s*사업|과업)\s*(?:내용|범위|목적)\s*[:：]?\s*$")
_REQUIREMENT_HEADING = re.compile(r"^\s*(?:[가-하]|\d+)[.)]\s*(?:시스템\s*)?기능\s*요구사항\s*$")
_PARTICIPATION_HEADING = re.compile(
    r"^\s*(?:\d+(?:[.\-]\d+)*[.)]?\s*|[가-하][.)]\s*)?(?:입찰\s*)?참가\s*자격\s*[:：]?\s*$")
_EVALUATION_HEADING = re.compile(
    r"^\s*(?:(?:[가-하]|\d+)[.)]|\d+\.\d+\.?\s*)\s*"
    r"(?:제안서\s*)?평가\s*(?:기준|방법|항목|및\s*.{0,30}선정)\s*$|"
    r"^\s*\d+[.)]\s*동점\s*시\s*처리\s*(?:방침|기준)\s*$")
_SCOPE_REFERENCE = re.compile(
    r"(?:과업\s*내용서|과업\s*내용|과업\s*범위).{0,65}(?:참고|참조|확인|첨부|"
    r"명시되지|규정되지|변경|변동)|사업\s*내용에\s*적시한")
_PARTICIPATION_REFERENCE = re.compile(r"참가\s*자격.{0,20}(?:관련이\s*없|무관|공고서에\s*의함|서약|박탈)")
_SCOPE_INVENTORY = re.compile(r"요구사항.{0,45}(?:[A-Z]{2,6}-\d{3,5}|Requirement)",re.IGNORECASE)
_SCOPE_NOISE = re.compile(
    r"개발\s*범위.{0,100}(?:정의\s*단계|추후\s*확정)|"
    r"명기되지\s*않은\s*사항.{0,95}(?:낙찰자|계약\s*상대자)|"
    r"사업\s*개요.{0,85}(?:개발\s*방향|사업\s*내용\s*분석)|"
    r"발주자는.{0,130}과업\s*(?:추진|수행)\s*내용.{0,50}조정|"
    r"과업\s*내용서에\s*의하여\s*수행|"
    r"전자정부법.{0,100}(?:감리법인|업무\s*범위)|"
    r"하도급.{0,95}과업\s*(?:내용서|지시서)|"
    r"(?:사업|과업)\s*내용.{0,80}(?:전화번호|연락처|☎)|"
    r"감리법인.{0,70}교육훈련.{0,65}제시|"
    r"사업\s*내용.{0,95}(?:이해하고|이해도|추진\s*전략)|"
    r"계약상대자는\s*수행내용별\s*착안사항|"
    r"ECR-\d+.{0,110}SFR-\d+.{0,110}PER-\d+|"
    r"과업\s*내용\s*및\s*시스템\s*관련\s*문의|"
    r"사업\s*내용.{0,65}(?:참조|참고|첨부|이해도)|"
    r"과업\s*(?:목적|지시서).{0,90}(?:누락|경미한|을\s*의\s*부담)|"
    r"계약\s*체결.{0,70}과업\s*범위.{0,30}추가|"
    r"^\s*\d+\.?\s*(?:사업|과업)\s*내용\s*[·.\s]{6,}|"
    r"설계\s*산출물.{0,35}과업\s*내용.{0,35}검토|"
    r"과업\s*내용서.{0,55}(?:열람|숙지)|"
    r"본\s*과업\s*지시서.{0,70}명시되지|"
    r"발주처가\s*과업\s*목적.{0,40}인정|"
    r"과업\s*내용\s*:\s*(?:한국|국립|서울|경기).{0,60}(?:연구원|대학교|기관|연구부문)")
_SCOPE_GENERIC_HEADING = re.compile(
    r"^\s*(?:[①-⑳]|[가-하][.)]|\d+\.?\d*[.)]?)?\s*"
    r"(?:(?:감리\s*시행\s*절차\s*및\s*)?업무\s*범위|"
    r"(?:시스템\s*)?(?:기타\s*)?(?:비)?기능\s*요구사항|(?:세부\s*)?과업\s*내용)\s*(?:\([A-Z]{2,6}\))?\s*$")


def _category_matches(part):
    """문서 한 줄의 탐지 후보만 반환. 평가 문맥의 공동수급·과업 언급을 과잉 분류하지 않는다."""
    found = {key: match for key, _, regex in COMPILED
             if (match := regex.search(part)) is not None}
    if "evaluation" in found:
        if _EVALUATION_ADMIN.search(part) and not re.search(r"배점|득점|평점|동점|산정|점수|기준|방법",part):
            found.pop("evaluation")
        participant = found.get("participation")
        if (participant is not None and participant.group().replace(" ", "").startswith("공동")
                and not _PARTICIPATION_DECISION.search(part)):
            found.pop("participation")
        if "scope" in found and (
                not _SCOPE_ACTION.search(part)
                or re.search(r"(?:적절성|적합성|우수성)\s*[:：].{0,110}(?:하였는가|있는가|되는가)",part)):
            found.pop("scope")
    if "participation" in found and (
            _PARTICIPATION_HEADING.fullmatch(part) or _PARTICIPATION_REFERENCE.search(part)
            or ("이의를 제기하지" in part and "자격" in part)):
        found.pop("participation")
    if "evaluation" in found and _EVALUATION_HEADING.fullmatch(part):
        found.pop("evaluation")
    if "scope" in found and (
            (_SCOPE_ADMIN.search(part) or _SCOPE_NOISE.search(part))
            and not _SCOPE_DELIVERY.search(part)
            or _SCOPE_HEADING.fullmatch(part)
            or _REQUIREMENT_HEADING.fullmatch(part)
            or _SCOPE_GENERIC_HEADING.fullmatch(part)
            or (_SCOPE_REFERENCE.search(part) and not _SCOPE_ACTION.search(part))
            or (_SCOPE_INVENTORY.search(part) and not _SCOPE_ACTION.search(part))):
        found.pop("scope")
    return found


class EvidenceError(ValueError):
    """출처 식별/청크 무결성 오류. 근거를 생성하지 않는다."""


def _identity(entry):
    if not isinstance(entry, dict):
        return None
    name, url = entry.get("name"), entry.get("url")
    if not isinstance(name, str) or not isinstance(url, str) or not official_url(url):
        return None
    return hashlib.sha256((url + "\n" + name).encode("utf-8")).hexdigest()


def _documents(notice, root):
    attachments = notice.get("attachments") or []
    proofs = notice.get("document_evidence") or []
    if not isinstance(attachments, list) or not isinstance(proofs, list):
        raise EvidenceError("문서 증거 메타데이터 형식이 올바르지 않습니다")
    warnings = []
    if len(attachments) > MAX_ATTACHMENT_SCAN:
        warnings.append("공식 첨부 탐색 400건 상한: 뒤의 첨부/근거는 미검증")
    known = {identifier: attachment for attachment in attachments[:MAX_ATTACHMENT_SCAN]
             if (identifier := _identity(attachment)) is not None}
    if len(proofs) > MAX_EVIDENCE_SCAN:
        warnings.append("증거 탐색 120건 상한: 나머지는 미분석")
    scanned = proofs[:MAX_EVIDENCE_SCAN]

    # 동일 공식 파일 링크의 서로 다른 원문 SHA가 공존하면 최신성을 알 수 없다.
    source_versions = {}
    conflicts = set()
    for proof in scanned:
        if not isinstance(proof, dict) or proof.get("status") != "EXTRACTED":
            continue
        ident, source_sha = proof.get("identity"), proof.get("sha256")
        if ident not in known or not isinstance(source_sha, str) or not _HEX.fullmatch(source_sha):
            continue
        if ident in source_versions and source_versions[ident] != source_sha:
            conflicts.add(ident)
        source_versions.setdefault(ident, source_sha)

    valid = []
    used = set()
    for proof in scanned:
        if len(valid) >= MAX_DOCS:
            break
        if not isinstance(proof, dict) or proof.get("status") != "EXTRACTED":
            continue
        ident = proof.get("identity")
        source_sha = proof.get("sha256")
        official = known.get(ident) if isinstance(ident,str) else None
        if official is None or not isinstance(source_sha,str) or not _HEX.fullmatch(source_sha):
            warnings.append("공식 첨부 결속 오류: 해당 증거 제외")
            continue
        if ident in conflicts:
            warnings.append("같은 첨부의 원본 SHA-256 충돌: 해당 증거 제외")
            continue
        if ident in used:
            continue
        # 원문 증거의 사용자 표시 파일명을 trust하지 않고 공식 첨부와 일치시킨다.
        if proof.get("name") != official.get("name"):
            warnings.append("증거 파일명과 공식 첨부 불일치: 해당 증거 제외")
            continue
        ref = proof.get("fulltext_ref")
        if ref:
            try:
                record = load_fulltext(root, ref)
                if record.get("source_sha256") != source_sha:
                    raise EvidenceError("원문 SHA-256과 청크 캐시의 출처가 일치하지 않습니다")
                text = "".join(chunk["text"] for chunk in record["chunks"])
            except (ValueError, OSError, KeyError, TypeError) as exc:
                raise EvidenceError("RFP 청크 캐시 무결성 검증 실패") from exc
            truncated = bool(record.get("truncated_by_parser"))
            position = "EXTRACTED_TEXT_OFFSET_NOT_PDF_PAGE"
            mode = "FULLTEXT_VERIFIED"
        else:
            excerpt = proof.get("excerpt")
            if (not isinstance(excerpt, str) or not excerpt.strip()
                    or len(excerpt) > 6000
                    or excerpt not in (notice.get("rfp_text") or "")):
                warnings.append("RFP 발췌 근거 불일치: 해당 증거 제외")
                continue
            text = excerpt
            truncated = True
            position = "STORED_EXCERPT_OFFSET_NOT_PDF_PAGE"
            mode = "EXCERPT_ONLY"
        if not text.strip() or len(text) > MAX_TEXT:
            raise EvidenceError("RFP 보관 텍스트 길이 검증 실패")
        used.add(ident)
        parser_warnings = proof.get("warnings")
        if not isinstance(parser_warnings, list):
            parser_warnings = []
        valid.append({"text":text, "file":official["name"][:160],
                      "source_sha256":source_sha,"source_ref":ref if ref else None,
                      "position_basis":position,"mode":mode,"truncated":truncated,
                      "parser_warnings":[str(v)[:120] for v in parser_warnings[:5]]})
    if sum(1 for proof in scanned if isinstance(proof,dict)
           and proof.get("status")=="EXTRACTED") > len(valid):
        warnings.append("일부 기록은 불일치·중복·처리 상한으로 제외")
    return valid, warnings


def structure(notice, root):
    """공고 1건의 *근거 후보*만 구조화. 원문 내용의 참·거짓, 필수/선택, 적격을 추정하지 않는다."""
    if not isinstance(notice, dict):
        raise ValueError("공고 객체가 필요합니다")
    if (notice.get("notice_lifecycle") in ("CANCELLED", "SUPERSEDED", "REVIEW")
            or is_cancel_kind(notice.get("notice_kind"))
            or notice.get("window_status") in ("CANCELLED", "SUPERSEDED")):
        return _empty(notice, "EXCLUDED_NOTICE", "공식 취소·구차수 또는 중복 차수 검토 공고")
    if notice.get("rfp_review_status") == "STALE":
        return _empty(notice, "STALE_RFP", "정정 후 원문 최신성 재검증 필요")
    if notice.get("document_status") != "EXTRACTED":
        return _empty(notice, "NO_EXTRACTED_RFP", "추출이 검증된 RFP 원문 없음")
    docs, warnings = _documents(notice, Path(root))
    if not docs:
        out = _empty(notice, "NO_TRUSTED_EVIDENCE", "첨부/본문 원문 결속이 확인된 추출 증거 없음")
        out["warnings"].extend(warnings)
        if any("상한" in message for message in warnings):
            out["source_coverage"] = "PARTIAL"
        return out
    groups = {key: [] for key, _, _ in COMPILED}
    # 화면에 표시하지 못한 후보도 검증된 추출 텍스트 범위에서만 계수한다.
    # 이 수치는 원본 RFP 전체 요구사항 수나 분류 Recall이 아니다.
    seen = {key: set() for key, _, _ in COMPILED}
    omitted = {key: 0 for key, _, _ in COMPILED}
    for doc in docs:
        # 문단 줄바꿈을 보존; 원문 페이지 위치라고 표시하지 않는다.
        for line in re.finditer(r"[^\r\n]+", doc["text"]):
            part = line.group()
            if not part.strip():
                continue
            matched = _category_matches(part)
            for key, _, _ in COMPILED:
                match = matched.get(key)
                if match is None:
                    continue
                lo = max(0, match.start() - 60)
                hi = min(len(part), max(match.end()+100, lo+120))
                hi = min(hi, lo + MAX_EVIDENCE_CHARS)
                raw_excerpt = part[lo:hi]
                leading = len(raw_excerpt) - len(raw_excerpt.lstrip())
                excerpt = raw_excerpt.strip()
                fingerprint = (doc["source_sha256"], excerpt)
                if len(excerpt) < 7 or fingerprint in seen[key]:
                    continue
                seen[key].add(fingerprint)
                if len(groups[key]) >= MAX_MATCHES_PER_CATEGORY:
                    omitted[key] += 1
                    continue
                start=line.start()+lo+leading
                groups[key].append({
                    "status":"TEXTUAL_SIGNAL_REVIEW_REQUIRED",
                    "evidence":{
                        "file":doc["file"], "source_sha256":doc["source_sha256"],
                        "fulltext_ref":doc["source_ref"],
                        "offset_start":start, "offset_end":start+len(excerpt),
                        "position_basis":doc["position_basis"],
                        "source_mode":doc["mode"], "page":None, "excerpt":excerpt}})
    if any(omitted.values()):
        warnings.append("유형별 표시 상한으로 일부 추가 텍스트 후보가 생략됨: 각 유형의 생략 건수 확인")
    limited = any(doc["truncated"] for doc in docs)
    if limited: warnings.append("파서 절단 또는 6천자 발췌만 사용: 누락 가능")
    if any(doc["parser_warnings"] for doc in docs):
        warnings.append("원문 파서 경고 있음: 표·각주·그림 등 원본 재확인")
    warning = list(dict.fromkeys(warnings))[:8]
    count=sum(len(v) for v in groups.values())
    return {
        "schema_version":SCHEMA_VERSION,"id":notice.get("id"),
        "state":"EVIDENCE_CANDIDATES" if count else "NO_TEXTUAL_SIGNALS",
        "analysis_mode":"RULE_BASED_TEXTUAL_EVIDENCE_ONLY",
        "requirements":[{"category":key,"label":label,"items":groups[key],
                         "count":len(groups[key]),"omitted_count":omitted[key]}
                        for key,label,_ in COMPILED],
        "candidate_display_limit_per_category":MAX_MATCHES_PER_CATEGORY,
        "omitted_candidate_count":sum(omitted.values()),
        "requirement_count":count,
        "sources_used":len(docs),"source_coverage":"PARTIAL" if warning else "EXTRACTED_TEXT_ONLY",
        "warnings":warning,
        "uncertainty":"모든 항목은 키워드 포함 원문 표현 후보이며 필수·선택 조건, 적격성, 원본 페이지는 사람이 검증",
        "legal_eligibility":"UNVERIFIED","technical_fit":"UNVERIFIED",
        "staffing_fit":"UNVERIFIED","profitability":"UNVERIFIED",
    }


def _empty(notice, state, reason):
    return {"schema_version":SCHEMA_VERSION,"id":notice.get("id"),"state":state,
            "analysis_mode":"RULE_BASED_TEXTUAL_EVIDENCE_ONLY",
            "requirements":[{"category":key,"label":label,"items":[],"count":0,"omitted_count":0}
                            for key,label,_ in COMPILED],
            "candidate_display_limit_per_category":MAX_MATCHES_PER_CATEGORY,
            "omitted_candidate_count":0,
            "requirement_count":0,"sources_used":0,"source_coverage":"NONE",
            "warnings":[reason], "uncertainty":"원문 검증 전 판단 보류",
            "legal_eligibility":"UNVERIFIED","technical_fit":"UNVERIFIED",
            "staffing_fit":"UNVERIFIED","profitability":"UNVERIFIED"}
