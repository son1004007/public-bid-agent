"""입찰 참여 참고판단: AI 원문 출력과 사용자 최종 선택을 분리하는 보수적 게이트.

입력: 미검증 AI 구조화 결과, 현재 로컬 추출 텍스트, 사람이 확인한 공고별 자격·점수.
출력: DRAFT 위험 분류, 인용 문자 일치/불확실성 및 결정적 규칙 fallback.
신뢰 경계: 인용은 source ID·현재 텍스트 SHA·문자 범위·직접 인용을 대조한다.
문자 일치는 원본 완전성/의미/회사 자격 검증이 아니며 모델의 verified 주장을 사용하지 않는다.
모델 입력: 자료 헤더 포함 90,000자 한도의 실제 전달 범위와 누락을 공통 계산한다.
전달 범위 밖 인용은 거부하고 입력 절단 시 AI 조건·점수를 제외하며 보류한다.
부작용/실패: 파일·네트워크 I/O 없음. 모델 누락/오류/출처 불일치는 규칙 fallback으로 보류.
불변: AI 단독으로 법적 자격·낙찰확률을 확정하거나 사용자 결정을 변경하지 않음.
사용자 확인: 구형 기록도 엄격한 true·유효 상태/점수·비공백 문자열 근거를 함께 검사하며 원본은 변경하지 않는다.
관련: D-03/D-07/D-08, P07, test_decision_support.py, test_recommendation_draft.py.
"""
from __future__ import annotations

import hashlib
import json
import re

GATE_NAMES = {
 "eligibility":"입찰 등록·참가자격",
 "licenses":"면허·인증·보험·보증",
 "track_record":"필수 수행 실적",
 "resources":"핵심인력·재무·수행여력",
 "teaming":"공동수급·지역 제한",
 "deadline":"제안·입찰 마감",
 "security":"보안·수행 장소",
 "contract":"계약 조건·배제 요건",
}

FACTOR_KEYS = ("technical", "staff", "experience", "buyer", "competition",
               "differentiation", "profit", "bid_cost", "relationship",
               "strategy", "readiness", "risk")
MODEL_INPUT_LIMIT = 90000


def _object(value):
    return value if isinstance(value, dict) else {}


def _text(value, limit=600):
    return value[:limit] if isinstance(value, str) else ""


def effective_verified(item, category: str) -> bool:
    """저장 플래그는 주장이다. 원본 변경 없이 상태/점수와 비공백 근거를 함께 확인."""
    item = _object(item)
    evidence = item.get("evidence")
    # Python/JS 공백 집합의 합집합(BOM 포함)을 UI와 동일하게 적용한다.
    if (item.get("verified") is not True or not isinstance(evidence, str)
            or not re.search(r"[^\s\ufeff]", evidence)):
        return False
    if category == "gates":
        return item.get("status") in ("pass", "fail", "na")
    if category == "factors":
        return type(item.get("score")) is int and 1 <= item["score"] <= 5
    return False


def text_sources(case: dict) -> dict:
    """현재 메모리 내 추출 텍스트만 식별. 원본 파일 SHA/페이지를 만들지 않는다."""
    sources = {}
    prompt = case.get("prompt")
    if isinstance(prompt, str) and prompt.strip():
        sources["prompt"] = {"name":"사용자 설명", "text":prompt, "partial":False}
    documents = case.get("documents")
    for index, document in enumerate(documents[:6] if isinstance(documents, list) else []):
        document = _object(document)
        text = document.get("text")
        if isinstance(text, str) and text.strip():
            sources[f"document:{index}"] = {
                "name":_text(document.get("name"), 120), "text":text,
                "partial":bool(document.get("truncated") or document.get("warnings")),
            }
    for source in sources.values():
        source["text_sha256"] = hashlib.sha256(source["text"].encode("utf-8")).hexdigest()
    return sources


def model_input(case: dict) -> dict:
    """프롬프트 자료 본문과 실제 전달 범위를 함께 생성. offset은 Unicode 문자/끝 제외."""
    parts, ranges = [], []
    used = 0
    for ident, source in text_sources(case).items():
        text = source["text"]
        header = ("\n\n" if parts else "") + (
            "[source_id="+ident+"; text_sha256="+source["text_sha256"]+"]\n")
        sent = min(len(text), max(0, MODEL_INPUT_LIMIT - used - len(header)))
        # 헤더만 잘려 전송되는 것을 피한다. 남은 문서도 누락 목록에 남긴다.
        if sent:
            parts.append(header + text[:sent])
            used += len(header) + sent
        ranges.append({"source_id":ident, "name":source["name"],
                       "text_sha256":source["text_sha256"], "total_chars":len(text),
                       "transmitted_start":0, "transmitted_end":sent,
                       "extraction_partial":source["partial"],
                       "status":"COMPLETE" if sent == len(text) else "TRUNCATED" if sent else "OMITTED"})
    content = "".join(parts)
    return {"content":content, "coverage":{
        "schema_version":1, "limit_chars":MODEL_INPUT_LIMIT, "content_chars":len(content),
        "content_sha256":hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "incomplete":any(source["status"] != "COMPLETE" for source in ranges),
        "omitted_source_ids":[source["source_id"] for source in ranges if source["status"] == "OMITTED"],
        "sources":ranges,
    }}


def clean_citations(value) -> list:
    """모델의 URL/verified/페이지 주장은 버리고 제한된 인용 스키마만 보존."""
    if not isinstance(value, list) or len(value) > 4:
        return []
    result = []
    for citation in value:
        if not isinstance(citation, dict):
            return []
        source_id = citation.get("source_id")
        digest = citation.get("text_sha256")
        start, end, quote = (citation.get(k) for k in ("offset_start", "offset_end", "quote"))
        if (not isinstance(source_id, str) or not re.fullmatch(r"prompt|document:[0-5]", source_id)
                or not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest)
                or type(start) is not int or type(end) is not int or not 0 <= start < end <= 90000
                or not isinstance(quote, str) or not quote.strip() or len(quote) > 400
                or end - start != len(quote)):
            return []
        result.append({"source_id":source_id, "text_sha256":digest,
                       "offset_start":start, "offset_end":end, "quote":quote})
    return result


def context_digest(case: dict) -> str:
    """실제 전달 본문/범위 및 선택 자료 버전 결속. 누락 문서도 입력 변경 감지용으로 식별."""
    return hashlib.sha256(json.dumps(model_input(case)["coverage"], ensure_ascii=True).encode()).hexdigest()


def _check_citations(value, sources):
    citations = clean_citations(value)
    links = []
    for citation in citations:
        source = sources.get(citation["source_id"])
        if (source and source["text_sha256"] == citation["text_sha256"]
                and citation["offset_end"] <= source["transmitted_end"]
                and source["text"][citation["offset_start"]:citation["offset_end"]] == citation["quote"]):
            links.append({**citation, "name":source["name"], "partial":source["partial"],
                          "input_truncated":source["input_truncated"]})
    status = ("EXTRACTED_TEXT_MATCH_ONLY" if citations and len(links) == len(citations)
              else "MISMATCH" if value else "MISSING")
    return {"status":status, "links":links, "semantic_verification":"UNVERIFIED"}


def advise(case: dict) -> dict:
    """제공된 근거 기반 경고만 도출. AI 출력 이유가 비어 있어도 가짜 이유를 만들지 않는다."""
    draft = _object(case.get("ai_draft"))
    ai_gates = _object(draft.get("gates"))
    ai_factors = _object(draft.get("factors"))
    saved_gates = _object(case.get("gates"))
    sources = text_sources(case)
    coverage = model_input(case)["coverage"]
    for item in coverage["sources"]:
        source = sources[item["source_id"]]
        source["transmitted_end"] = item["transmitted_end"]
        source["input_truncated"] = item["status"] != "COMPLETE"
        source["partial"] = source["partial"] or source["input_truncated"]
    incomplete = coverage["incomplete"]
    context_status = ("MISSING" if not case.get("ai_draft_context_sha256") else
                      "CURRENT" if case["ai_draft_context_sha256"] == context_digest(case) else "CHANGED")
    checks = {
        "gates":{key:_check_citations(_object(ai_gates.get(key)).get("citations"), sources)
                 for key in GATE_NAMES},
        "factors":{key:_check_citations(_object(ai_factors.get(key)).get("citations"), sources)
                   for key in FACTOR_KEYS},
        "recommendation":_check_citations(draft.get("citations"), sources),
    }
    fallback = []
    if incomplete:
        fallback.append("MODEL_INPUT_INCOMPLETE")
    if not draft:
        fallback.append("AI_MISSING_OR_INVALID")
    else:
        if context_status != "CURRENT":
            fallback.append("AI_INPUT_"+context_status)
        if checks["recommendation"]["status"] != "EXTRACTED_TEXT_MATCH_ONLY":
            fallback.append("RECOMMENDATION_SOURCE_UNVERIFIED")
    failed_user, failed_ai, conflicts, unknown = [], [], [], []
    flags = []
    for key, name in GATE_NAMES.items():
        actual=_object(saved_gates.get(key))
        suggested=_object(ai_gates.get(key))
        verified=effective_verified(actual, "gates")
        ai_status=suggested.get("status", "unknown")
        linked=(not incomplete and context_status == "CURRENT"
                and checks["gates"][key]["status"] == "EXTRACTED_TEXT_MATCH_ONLY")
        if ai_status in ("pass", "fail", "na") and not linked:
            if incomplete:
                flags.append({"type":"ai_input_incomplete", "gate":key, "name":name,
                              "evidence":"선택 자료가 모델 입력에서 잘리거나 누락되어 AI 조건을 규칙 판단에서 제외했습니다."})
            else:
                fallback.append("GATE_SOURCE_UNVERIFIED")
                flags.append({"type":"ai_claim_unlinked", "gate":key, "name":name,
                              "evidence":"AI 조건 주장의 출처가 없거나 현재 텍스트와 일치하지 않아 규칙 판단에서 제외했습니다."})
        if not verified:
            unknown.append(key)
        if verified:
            if actual.get("status")=="fail":
                failed_user.append(key)
                flags.append({"type":"user_confirmed_failure","gate":key,"name":name,
                              "evidence":_text(actual.get("evidence"), 300)})
            if linked and ai_status in ("pass","na","fail") and actual.get("status")!=ai_status:
                conflicts.append(key)
                flags.append({"type":"ai_user_disagreement","gate":key,"name":name,
                              "evidence":_text(suggested.get("evidence"), 300)})
        elif linked and ai_status=="fail" and _text(suggested.get("evidence")).strip():
            failed_ai.append(key)
            flags.append({"type":"ai_suspected_failure","gate":key,"name":name,
                          "evidence":_text(suggested.get("evidence"), 300)})
    scored = 0
    for key in FACTOR_KEYS:
        factor = _object(ai_factors.get(key))
        if type(factor.get("score")) is int and 1 <= factor["score"] <= 5:
            if not incomplete and context_status == "CURRENT" and checks["factors"][key]["status"] == "EXTRACTED_TEXT_MATCH_ONLY":
                scored += 1
            else:
                fallback.append("FACTOR_SOURCE_UNVERIFIED")
    if failed_user:
        status,title="REVIEW_NO_BID_VERIFIED","사용자 확인상 필수조건 미충족: 미참여 검토"
    elif incomplete:
        status,title="HOLD_INPUT_INCOMPLETE","모델 입력 잘림·누락: 원문 검토 전 참여 판단 보류"
    elif conflicts:
        status,title="HOLD_CONFLICT","AI와 사용자가 확인한 조건이 상충: 재검토"
    elif failed_ai:
        status,title="REVIEW_NO_BID_PROVISIONAL","AI가 조건 불일치를 제안: 원문 의미 재검토"
    elif unknown:
        status,title="HOLD_UNVERIFIED","필수조건 확인 부족: 참여 판단 보류"
    else:
        status,title="READY_FOR_HUMAN","사용자 확인 기록 충족: 최종 판단 대기 (독립 검증 아님)"
    if not _text(draft.get("reason")).strip():
        fallback.append("MODEL_REASON_MISSING")
        flags.append({"type":"model_reason_missing" if draft else "model_unavailable", "gate":"",
                      "name":"AI 권고 사유 미제공" if draft else "AI 결과 없음",
                      "evidence":"유효한 AI 사유가 없습니다. 사용자 확인 기록과 원문을 검토하세요."})
    return {
        "status":status,"title":title,"flags":flags,
        "draft_state":"DRAFT",
        "draft_context_status":context_status,
        "analysis_mode":"RULE_BASED_FALLBACK" if fallback else "RULE_BASED_WITH_AI_DRAFT",
        "fallback_reasons":list(dict.fromkeys(fallback)),
        "source_checks":checks,
        "input_coverage":coverage,
        "uncertainty":(["모델 입력 90,000자 제한으로 선택 자료 일부가 전달 범위에서 제외됩니다. AI 조건·점수를 판단에서 제외했습니다."]
                       if incomplete else []) + ["인용 문자 일치는 원문 의미·완전성·최신성 검증이 아닙니다.",
                       "회사 자격·기술·가용 인력·원가와 실제 수주 가능성은 미검증입니다.",
                       "추천 초안은 사용자 최종 결정을 변경하지 않습니다."],
        "human_decision":case.get("decision") if case.get("decision") in
                         ("undecided", "bid", "hold", "no_bid") else "undecided",
        "unverified_gate_count":len(unknown),"scored_factor_count":scored,
        "failed_gate_keys":failed_user+failed_ai,
        "ai_raw_recommendation":draft.get("recommendation") if draft.get("recommendation") in
                                ("bid", "hold", "no_bid") else None,
        "basis":"AI 추출(미검증) + 사용자 확인 입력에 대한 규칙 기반 위험 분류. 수주확률/법적 적격 판정 아님.",
        "not_legal_eligibility":True,
    }
