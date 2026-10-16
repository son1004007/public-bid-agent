"""입찰 제출·평가·선정 결과를 담당자 수동 근거로만 기록하는 계약.
입력/출력: 공식 대시보드 스냅샷, expected_revision, 수동 확인 상태/날짜/증거.
신뢰 경계: API 입력·점수·근거는 사용자 입력이며 공식 API 조회를 대신하지 않음.
상태 변경: 복사본 공고에 수동 사건 기록 추가. 낙찰/제출을 자동 실행하지 않음.
실패: 잘못된 전이·중복·충돌/근거 부족 시 원본 보존, 낙찰 확률 산출 안 함.
핵심 불변조건: 사람의 Bid/No-Bid 결정과 recommendation 및 과거 판단 이력 불변.
관련: D-03,D-06,D-07,D-17; test_bid_outcomes.py.
"""
import copy
from datetime import date
import re

STAGES=("SUBMITTED","EVALUATED","AWARDED","NOT_AWARDED","WITHDRAWN")
TERMINAL={"AWARDED","NOT_AWARDED","WITHDRAWN"}
NEXT={
    None: {"SUBMITTED"},
    "SUBMITTED":{"EVALUATED","AWARDED","NOT_AWARDED","WITHDRAWN"},
    "EVALUATED":{"AWARDED","NOT_AWARDED","WITHDRAWN"},
}
MAX_EVENTS=20


class OutcomeConflict(ValueError):
    pass


def record(state, request, stamp):
    if not isinstance(state,dict) or not isinstance(request,dict):
        raise ValueError("입찰 이력 입력 계약 오류")
    revision=request.get("expected_revision")
    if type(revision) is not int or revision!=state.get("revision"):
        raise OutcomeConflict("이력이 다른 창에서 변경되었습니다. 새로고침 후 재입력하세요")
    ident=request.get("id")
    if not isinstance(ident,str) or not re.fullmatch(r"G2B-[A-Za-z0-9-]{4,100}",ident):
        raise ValueError("공고 식별자 오류")
    notice=next((x for x in state.get("notices",[]) if x.get("id")==ident),None)
    if notice is None:
        raise ValueError("공고 없음")
    stage=request.get("stage")
    if stage not in STAGES:
        raise ValueError("입찰 상태 오류")
    evidence=request.get("evidence_reference")
    if not isinstance(evidence,str) or not 2<=len(evidence.strip())<=160 or any(ord(c)<32 for c in evidence):
        raise ValueError("사용자가 확인한 자료 출처를 2~160자로 입력하세요")
    observed=request.get("observed_on")
    if not isinstance(observed,str) or len(observed)!=10:
        raise ValueError("확인 날짜 오류")
    try:
        date.fromisoformat(observed)
    except ValueError as e:
        raise ValueError("확인 날짜 오류") from e
    score=request.get("evaluation_score")
    if score is not None:
        if (type(score) not in (int,float) or not 0<=score<=100
                or round(score,2)!=score or stage not in ("EVALUATED","AWARDED","NOT_AWARDED")):
            raise ValueError("평가 점수는 0~100, 소수 둘째자리까지이며 평가 이후에만 기록")
    previous=notice.get("submission_events",[])
    if not isinstance(previous,list) or len(previous)>=MAX_EVENTS:
        raise ValueError("제출 결과 이력 형식 또는 기록 상한 오류")
    if previous and any(not isinstance(x,dict) or x.get("stage") not in STAGES for x in previous):
        raise ValueError("기존 입찰 이력 손상")
    last=previous[-1]["stage"] if previous else None
    if stage not in NEXT.get(last,set()):
        raise OutcomeConflict("단계 전이가 올바르지 않거나 이미 종결된 입찰입니다")
    # 최초 제출 전에는 담당자의 명시적 참여 결정이 선행돼야 한다.
    if last is None and notice.get("final") not in ("bid","human_bid"):
        raise OutcomeConflict("참여 결정이 기록된 공고만 제출 이력을 시작할 수 있습니다")
    if (not isinstance(stamp,str) or len(stamp)>48 or not stamp):
        raise ValueError("기록 시각 형식 오류")
    out=copy.deepcopy(state)
    target=next(x for x in out["notices"] if x["id"]==ident)
    event={"stage":stage,"observed_on":observed,"evidence_reference":evidence.strip(),
           "evaluation_score":score,"recorded_at":stamp,"source":"HUMAN_DECLARED_UNVERIFIED"}
    target.setdefault("submission_events",[]).append(event)
    out["revision"]+=1
    return out
