"""공식 RFP 요구사항 후보의 증거 결속형, 읽기 전용 규칙 추출기.

목적: 기존 44,000자 청크/검증된 excerpt에서 참가자격·면허·실적·과업·기술·인력·기간·예산 후보 추출.
입력/출력: 공식 공고 record와 비공개 root -> 카테고리별 근거 JSON, 원본 페이지 불명 표시.
신뢰 경계: 비신뢰 문서 본문을 자연어 데이터로만 취급; 유료 AI/API/도구 지시 금지.
부작용: 없음. 호출 시 파일을 쓰지 않고 저장 RFP/담당자 판단을 보존.
실패: 원문 청크 무결성·첨부 identity 불일치 시 사용 거부; STALE·취소·구차수는 분석 보류.
불변조건: 추출된 표현은 참가자격 충족 판정이 아니며, 원문 PDF/HWP 페이지·표 위치를 추정하지 않는다.
관련: rfp_fulltext.py, rfp_batch.py, test_rfp_requirements.py, docs/design/RFP_REQUIREMENTS_SLICE_2026-10-13.md.
"""
import hashlib
import re
from pathlib import Path

from rfp_fulltext import load as load_fulltext
from procurement_documents import official_url
from notice_lifecycle import is_cancel_kind

SCHEMA_VERSION = 1
MAX_DOCS = 2
MAX_EVIDENCE_SCAN = 120
MAX_ATTACHMENT_SCAN = 400
MAX_MATCHES_PER_CATEGORY = 5
MAX_EVIDENCE_CHARS = 220
MAX_TEXT = 44000
_CATEGORIES = (
    ("participation", "입찰참가자격", r"입찰\s*참가\s*자격|참가\s*자격|입찰\s*등록|공동\s*(?:수급|도급)|직접생산확인|중소기업확인"),
    ("licenses", "업종·면허·인증", r"소프트웨어사업자|정보통신공사업|업종\s*제한|면허|인가|인증\s*(?:요건|자격|서)|ISO\s*27001|ISMS-P|조달청\s*등록"),
    ("track_record", "수행실적", r"유사\s*(?:사업|용역)|수행\s*실적|납품\s*실적|실적\s*증명|최근\s*\d{1,2}\s*년"),
    ("scope", "과업범위", r"과업\s*(?:범위|내용|목적)|주요\s*과업|사업\s*내용|구축\s*대상|기능\s*요구|수행\s*내용|업무\s*범위"),
    ("technology", "기술요건", r"(?<![A-Za-z])(?:Java|Spring|Python|FastAPI|LLM|RAG|LangGraph|DBMS|PostgreSQL|Oracle|API)(?![A-Za-z])|클라우드|데이터베이스|컨테이너|생성형\s*AI|인공지능"),
    ("staffing", "인력·공수", r"투입\s*인력|인력\s*(?:구성|운영|배치)|[초중고특]급\s*기술자|상주\s*인력|인력\s*투입|투입\s*공수|인월|(?<![A-Za-z])M/M(?![A-Za-z])|인건비"),
    ("duration", "사업기간", r"(?:사업|수행|계약)\s*기간|납품\s*기한|착수일|준공일|완료\s*기한|\d{1,2}\s*개월\s*(?:이내|동안|간)"),
    ("budget", "예산·사업비", r"사업\s*예산|(?:총\s*)?사업비|예산액|추정\s*가격|기초\s*금액|사업\s*금액|부가가치세|계약\s*금액"),
)
COMPILED = [(key, name, re.compile(expr, re.IGNORECASE)) for key,name,expr in _CATEGORIES]
_HEX = re.compile(r"^[0-9a-f]{64}$")


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
    for doc in docs:
        # 문단 줄바꿈을 보존; 원문 페이지 위치라고 표시하지 않는다.
        for line in re.finditer(r"[^\r\n]+", doc["text"]):
            part = line.group()
            if not part.strip():
                continue
            for key, _, regex in COMPILED:
                if len(groups[key]) >= MAX_MATCHES_PER_CATEGORY:
                    continue
                match = regex.search(part)
                if match is None:
                    continue
                lo = max(0, match.start() - 60)
                hi = min(len(part), max(match.end()+100, lo+120))
                hi = min(hi, lo + MAX_EVIDENCE_CHARS)
                raw_excerpt = part[lo:hi]
                leading = len(raw_excerpt) - len(raw_excerpt.lstrip())
                excerpt = raw_excerpt.strip()
                if len(excerpt) < 7 or any(v["evidence"]["excerpt"]==excerpt
                                               and v["evidence"]["source_sha256"]==doc["source_sha256"]
                                               for v in groups[key]):
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
                         "count":len(groups[key])} for key,label,_ in COMPILED],
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
            "requirements":[{"category":key,"label":label,"items":[],"count":0}
                            for key,label,_ in COMPILED],
            "requirement_count":0,"sources_used":0,"source_coverage":"NONE",
            "warnings":[reason], "uncertainty":"원문 검증 전 판단 보류",
            "legal_eligibility":"UNVERIFIED","technical_fit":"UNVERIFIED",
            "staffing_fit":"UNVERIFIED","profitability":"UNVERIFIED"}
