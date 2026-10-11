"""부서의 공식 공고 관심 분야와 검토대기 포함 여부를 로컬에 버전 저장.
입력: 사용자 선택 AI/SW/DATA/SECURITY, 미확정 후보 표시 여부, expected_revision.
출력: 검증된 설정 스냅샷. 실제 업체 면허/입찰 참가자격을 대체하지 않음.
부작용: 호출한 로컬 서버의 department_profile.json만 변경.
보안: 외부 파일/네트워크 접근 없음. 빈 분야 선택을 허용하지만 1개 이상 선택 권고.
"""
from procurement_filter import CATEGORIES


class DepartmentProfileConflict(Exception):
    pass


def default():
    return {"schema_version": 1, "revision": 0, "categories": list(CATEGORIES),
            "include_review": True}


def load(path):
    if not path.exists():
        return default()
    import json
    with path.open(encoding="utf-8") as f:
        value = json.load(f)
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError("부서 분야 설정 파일 형식 오류")
    if type(value.get("revision")) is not int or value["revision"] < 0:
        raise ValueError("부서 분야 설정 버전 오류")
    return {**value, **validate(value)}


def validate(value):
    if not isinstance(value, dict):
        raise ValueError("설정은 JSON 객체여야 합니다")
    categories = value.get("categories")
    if not isinstance(categories, list) or len(categories) > len(CATEGORIES):
        raise ValueError("관심 분야 목록 오류")
    if any(not isinstance(c, str) or c not in CATEGORIES for c in categories):
        raise ValueError("지원하지 않는 관심 분야")
    if len(set(categories)) != len(categories):
        raise ValueError("관심 분야 중복")
    review = value.get("include_review")
    if type(review) is not bool:
        raise ValueError("미확정 공고 표시 여부 오류")
    return {"categories": categories, "include_review": review}


def modify(existing, payload):
    if type(payload.get("expected_revision")) is not int or payload["expected_revision"] != existing["revision"]:
        raise DepartmentProfileConflict("다른 창에서 부서 관심 분야가 변경되었습니다")
    clean = validate(payload.get("profile"))
    return {**existing, **clean, "revision": existing["revision"] + 1}
