"""입찰 참여 참고판단: AI 원문 출력과 사용자 최종 선택을 분리하는 보수적 게이트.

입력: 미검증 AI 구조화 결과, 사람이 확인한 공고별 자격·점수.
출력: 입찰 참가·미참여에 대한 확정이 아닌 검증 우선순위/위험 분류.
신뢰 경계: LLM의 실패/충족 추출과 사용자가 체크한 확인값을 다르게 취급.
불변: AI 단독으로 법적 자격·낙찰확률을 확정하거나 사용자 결정을 변경하지 않음.
"""
from __future__ import annotations

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


def advise(case: dict) -> dict:
    """제공된 근거 기반 경고만 도출. AI 출력 이유가 비어 있어도 가짜 이유를 만들지 않는다."""
    draft = case.get("ai_draft") or {}
    if not draft:
        return {
            "status":"NOT_ANALYZED","title":"AI 분석 전",
            "flags":[],"unverified_gate_count":len(GATE_NAMES),"scored_factor_count":0,
            "basis":"사용자 데이터/AI 근거 없음","not_legal_eligibility":True,
        }
    ai_gates = draft.get("gates") or {}
    saved_gates = case.get("gates") or {}
    failed_user, failed_ai, conflicts, unknown = [], [], [], []
    flags = []
    for key, name in GATE_NAMES.items():
        actual=saved_gates.get(key) or {}
        suggested=ai_gates.get(key) or {}
        verified=actual.get("verified") is True and bool(actual.get("evidence"))
        ai_status=suggested.get("status", "unknown")
        if verified:
            if actual.get("status")=="fail":
                failed_user.append(key)
                flags.append({"type":"user_confirmed_failure","gate":key,"name":name,
                              "evidence":str(actual.get("evidence"))[:300]})
            if ai_status in ("pass","na","fail") and actual.get("status")!=ai_status:
                conflicts.append(key)
                flags.append({"type":"ai_user_disagreement","gate":key,"name":name,
                              "evidence":str(suggested.get("evidence") or "")[:300]})
        elif ai_status=="fail" and suggested.get("evidence"):
            failed_ai.append(key)
            flags.append({"type":"ai_suspected_failure","gate":key,"name":name,
                          "evidence":str(suggested.get("evidence"))[:300]})
        else:
            unknown.append(key)
    scored = sum(isinstance(v.get("score"),int) and 1<=v["score"]<=5
                 for v in (draft.get("factors") or {}).values() if isinstance(v,dict))
    if failed_user:
        status,title="REVIEW_NO_BID_VERIFIED","사용자 확인상 필수조건 미충족: 미참여 검토"
    elif conflicts:
        status,title="HOLD_CONFLICT","AI와 사용자가 확인한 조건이 상충: 재검토"
    elif failed_ai:
        status,title="REVIEW_NO_BID_PROVISIONAL","AI가 필수조건 불일치를 발견: 미참여 검토"
    elif unknown:
        status,title="HOLD_UNVERIFIED","필수조건 확인 부족: 참여 판단 보류"
    else:
        status,title="READY_FOR_HUMAN","필수조건 확인 완료: 사용자 판단 대기"
    if not draft.get("reason", "").strip():
        flags.append({"type":"model_reason_missing","gate":"","name":"AI 권고 사유 미제공",
                      "evidence":"AI가 판단 이유 문장을 반환하지 않았습니다. 아래 조건별 근거만 확인하세요."})
    return {
        "status":status,"title":title,"flags":flags,
        "unverified_gate_count":len(unknown),"scored_factor_count":scored,
        "failed_gate_keys":failed_user+failed_ai,
        "ai_raw_recommendation":draft.get("recommendation","hold"),
        "basis":"AI 추출(미검증) + 사용자 확인 입력에 대한 규칙 기반 위험 분류. 수주확률/법적 적격 판정 아님.",
        "not_legal_eligibility":True,
    }
