"""로컬 참여판단·영향인자 프로필 데이터 계약.

목적/책임: 가상 입찰용 판단 기준과 12개 평가 가중치를 독립 버전으로 검증·보관한다.
입력/출력: 정수 revision과 policy/factors JSON -> 새 버전의 검증된 프로필.
신뢰 경계/권한: 사용자 브라우저의 입력을 신뢰하지 않으며 호출 서버가 Host/Origin/CSRF를 검사한다.
상태 변경/부작용: 서버가 별도 decision_profiles.json을 원자 저장한다. AI 전송 없음.
실패/동시성: 잘못된 입력은 ValueError, 오래된 revision은 ProfileConflict로 실패한다.
핵심 불변조건: 버전 기록 불변, 8개 필수조건과 12개 가중치의 정의는 서버 기준, 합계 100%.
관련 요구사항/테스트: CURRENT_STATE.md, local_app/test_decision_profiles.py.
"""

import copy
import json
import math
from pathlib import Path

GATE_KEYS = (
    "eligibility", "licenses", "track_record", "resources",
    "teaming", "deadline", "security", "contract",
)
FACTOR_DEFAULTS = {
    "technical": 15, "staff": 10, "experience": 10, "buyer": 10,
    "competition": 10, "differentiation": 10, "profit": 10,
    "bid_cost": 5, "relationship": 5, "strategy": 5,
    "readiness": 5, "risk": 5,
}
POLICY_DEFAULT = {
    "name": "AI·데이터 사업 기본 참여 기준",
    "minFit": 65,
    "minMargin": 15,
    "require": True,
    "ops": True,
    "proof": True,
}


class ProfileConflict(Exception):
    """다른 창에서 프로필이 먼저 변경되었다."""


def default_state() -> dict:
    return {
        "schema_version": 1,
        "revision": 0,
        "policy_version": 1,
        "factor_version": 1,
        "policy": copy.deepcopy(POLICY_DEFAULT),
        "weights": dict(FACTOR_DEFAULTS),
        "versions": [
            {"kind": "policy", "version": 1, "value": copy.deepcopy(POLICY_DEFAULT), "at": None},
            {"kind": "factors", "version": 1, "value": dict(FACTOR_DEFAULTS), "at": None},
        ],
    }


def _finite_number(value, lo: float, hi: float, name: str) -> int | float:
    if type(value) not in (int, float) or not math.isfinite(value) or not lo <= value <= hi:
        raise ValueError(name + " 범위 오류")
    return value


def clean_policy(value: object) -> dict:
    if not isinstance(value, dict) or set(value) != set(POLICY_DEFAULT):
        raise ValueError("판단 기준 필드 오류")
    name = value["name"]
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 50 or any(ord(c) < 32 for c in name):
        raise ValueError("프로필 이름 오류")
    for key in ("require", "ops", "proof"):
        if type(value[key]) is not bool:
            raise ValueError("판단 기준 불리언 오류")
    return {
        "name": name.strip(),
        "minFit": _finite_number(value["minFit"], 0, 100, "기술점수"),
        "minMargin": _finite_number(value["minMargin"], -100, 100, "예상이익률"),
        "require": value["require"],
        "ops": value["ops"],
        "proof": value["proof"],
    }


def clean_weights(value: object) -> dict[str, int]:
    if not isinstance(value, dict) or set(value) != set(FACTOR_DEFAULTS):
        raise ValueError("평가 영향인자 12개 필드 오류")
    if any(type(n) is not int or not 0 <= n <= 25 for n in value.values()):
        raise ValueError("개별 가중치 0~25 정수 조건 오류")
    if sum(value.values()) != 100:
        raise ValueError("가중치 총합은 100이어야 합니다")
    return {key: value[key] for key in FACTOR_DEFAULTS}


def load_state(path: Path) -> dict:
    if not path.exists():
        return default_state()
    with path.open(encoding="utf-8") as stream:
        state = json.load(stream)
    if not isinstance(state, dict) or state.get("schema_version") != 1:
        raise ValueError("지원하지 않는 판단 프로필 파일")
    for key in ("revision", "policy_version", "factor_version"):
        if type(state.get(key)) is not int or state[key] < (0 if key == "revision" else 1):
            raise ValueError("판단 프로필 버전 형식 오류")
    if not isinstance(state.get("versions"), list):
        raise ValueError("프로필 이력 형식 오류")
    clean_policy(state.get("policy"))
    clean_weights(state.get("weights"))
    return state


def next_state(current: dict, request: dict, timestamp: str) -> dict:
    expected = request.get("expected_revision")
    if type(expected) is not int or expected != current["revision"]:
        raise ProfileConflict("프로필이 다른 창에서 변경되었습니다. 최신 버전을 다시 불러오세요")
    kind = request.get("kind")
    if kind == "policy":
        value = clean_policy(request.get("profile"))
        value_key, version_key = "policy", "policy_version"
    elif kind == "factors":
        value = clean_weights(request.get("weights"))
        value_key, version_key = "weights", "factor_version"
    else:
        raise ValueError("프로필 유형 오류")
    if len(current["versions"]) >= 1000:
        raise ValueError("프로필 이력 상한에 도달했습니다. 백업 후 보존 정책을 결정하세요")
    result = copy.deepcopy(current)
    result["revision"] += 1
    result[version_key] += 1
    result[value_key] = value
    result["versions"].append({
        "kind": kind, "version": result[version_key], "value": copy.deepcopy(value),
        "at": timestamp,
    })
    return result
