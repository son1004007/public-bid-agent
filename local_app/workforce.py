"""부서 비식별 인력 계획 파일 및 가정 원가 조회 계약.

목적/책임: 로컬 비공개 workforce.json을 검증하고 역할·등급별 인력/원가를 집계한다.
입력/출력: 직원 코드, 역할, 내부분류 등급, 기술 추정치, 미정 가용 MM, 가정 연봉.
신뢰 경계: 공개 소스에는 실제 부서 인원을 두지 않고 로컬 파일을 읽기 전용으로 처리한다.
상태 변경/부작용: 없음. LLM 제공자에게 인력명세나 가정 원가를 자동 전송하지 않는다.
실패/재시도: 파일 누락은 미설정, 손상·범위 오류는 명시적 실패(임의 기본값 사용 금지).
핵심 불변조건: 실명 보관 금지, 등급은 내부 가정, 기술/담당분야는 확인 전 추정,
가용 공수 미정은 None이며 수익/자격/입찰 가능 확정을 허용하지 않는다.
관련: local_app/test_workforce.py, docs/design/WORKFORCE_PRIVATE_PROFILE_2026-10-11.md.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP

ROLES = {"analyst": "분석가", "developer": "개발자",
         "executive": "임원", "accounting": "경리"}
GRADES = {"junior": "초급", "intermediate": "중급", "senior": "고급"}
TECH = frozenset(("JAVA", "PYTHON", "DB", "ML", "AI"))
TECH_ROLES = frozenset(("analyst", "developer"))
STAFF_FIELDS = frozenset(("id", "role", "grade", "lead", "skills",
                          "skills_evidence", "responsibility",
                          "responsibility_evidence", "available_mm"))
# 공개 코드에는 정형 담당분야 어휘만 기록. 실제 직원과 분류 매핑은 PC 비공개에 보관한다.
RESPONSIBILITIES = frozenset((
    "경비 정산 및 회계 지원", "부서 운영 및 사업 의사결정",
    "데이터 수집·정제 및 SQL 분석", "AI 분석 설계 및 모델 결과 검증",
    "데이터 분석·지표 설계", "데이터 전처리·적재",
    "데이터 품질 검증·보고", "머신러닝 모델링·성능 평가",
    "데이터 아키텍처·DB 분석", "AI 서비스 요구분석·품질 검증",
    "Java 백엔드·업무 API 개발", "개발 총괄·설계 검토·코드 리뷰",
    "Python API·AI 서비스 연계", "데이터 연계·서비스 API 개발",
    "Java 백엔드 및 데이터 처리 개발", "합성 담당 분야",
))
MAX_STAFF = 100


def _valid_mm(value):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("가용 MM은 미정(null) 또는 0 이상 24 이하의 수치여야 합니다")
    number = Decimal(str(value))
    if not number.is_finite() or not 0 <= number <= 24 or number.as_tuple().exponent < -2:
        raise ValueError("가용 MM 범위 오류")
    return float(number)


def validate(data):
    if not isinstance(data, dict) or set(data) != {"schema_version", "staff", "annual_grade_rates_krw"}:
        raise ValueError("인력 프로필 최상위 형식 오류")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ValueError("지원하지 않는 인력 프로필 버전")
    rates = data["annual_grade_rates_krw"]
    if not isinstance(rates, dict) or set(rates) != set(GRADES):
        raise ValueError("등급별 가정 연봉 기준 오류")
    if any(type(v) is not int or not 1_000_000 <= v <= 1_000_000_000 for v in rates.values()):
        raise ValueError("등급별 가정 연봉은 원화 정수여야 합니다")
    staff = data["staff"]
    if not isinstance(staff, list) or len(staff) > MAX_STAFF:
        raise ValueError("인력 명단 크기 오류")
    ids = set()
    clean = []
    for person in staff:
        if not isinstance(person, dict) or set(person) != STAFF_FIELDS:
            raise ValueError("개인정보 또는 알 수 없는 인력 필드가 있습니다")
        ident = person["id"]
        if not isinstance(ident, str) or not re.fullmatch(r"(?:[A-Z]{1,2}[1-9][0-9]{0,2}|[A-Z])", ident) or ident in ids:
            raise ValueError("비식별 코드가 잘못됐거나 중복됐습니다")
        ids.add(ident)
        role, grade = person["role"], person["grade"]
        if (not isinstance(role, str) or role not in ROLES or
            (role in TECH_ROLES and (not isinstance(grade, str) or grade not in GRADES)) or
            (role not in TECH_ROLES and grade is not None)):
            raise ValueError("역할 또는 내부 등급 분류 오류")
        lead = person["lead"]
        if type(lead) is not bool or (lead and role not in ("developer",)):
            raise ValueError("팀장 표기 오류")
        skills = person["skills"]
        if (not isinstance(skills, list) or len(skills) > len(TECH) or
            any(not isinstance(x, str) or x not in TECH for x in skills) or
            len(set(skills)) != len(skills)):
            raise ValueError("보유기술 목록 오류")
        if role not in TECH_ROLES and skills:
            raise ValueError("비기술 인력 기술 추정을 등록하지 않습니다")
        if person["skills_evidence"] not in ("ASSUMED", "UNKNOWN") or (
            person["responsibility_evidence"] not in ("ASSUMED", "UNKNOWN")
        ):
            raise ValueError("실제 기술·담당 확인은 증빙 스키마 도입 후에만 승인됩니다")
        responsibility = person["responsibility"]
        if not isinstance(responsibility, str) or responsibility not in RESPONSIBILITIES:
            raise ValueError("담당분야는 승인된 일반 분류에서 선택해야 합니다")
        mm = _valid_mm(person["available_mm"])
        clean.append({**person, "available_mm": mm})
    return {"schema_version": 1, "annual_grade_rates_krw": dict(rates), "staff": clean}


def load(path):
    repo_root = Path(__file__).resolve().parents[1]
    if path.resolve() == repo_root or repo_root in path.resolve().parents:
        raise ValueError("인력 프로필은 소스 저장소 밖의 로컬 디렉터리에만 보관해야 합니다")
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as handle:
        return validate(json.load(handle))


def _monthly(annual):
    return int((Decimal(annual) / Decimal(12)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def summary(data):
    validated = validate(data)
    staff = validated["staff"]
    rates = validated["annual_grade_rates_krw"]
    delivery = [p for p in staff if p["role"] in TECH_ROLES]
    grouped = Counter((p["role"], p["grade"]) for p in delivery)
    roles = []
    for role in ("analyst", "developer"):
        for grade in ("junior", "intermediate", "senior"):
            count = grouped[(role, grade)]
            if count:
                members = [p for p in delivery if p["role"] == role and p["grade"] == grade]
                known_capacity = all(p["available_mm"] is not None for p in members)
                available = (float(sum((Decimal(str(p["available_mm"])) for p in members),
                                      Decimal("0")).quantize(Decimal("0.01")))
                             if known_capacity else None)
                roles.append({"role": ROLES[role] + " " + GRADES[grade],
                              "role_code": role, "grade": grade, "headcount": count,
                              "cost_per_mm_krw": _monthly(rates[grade]),
                              "available_mm": available,
                              "capacity_status": "KNOWN" if known_capacity else "UNKNOWN"})
    return {
        "schema_version": 1,
        "headcount_total": len(staff),
        "delivery_headcount": len(delivery),
        "excluded_from_cost_headcount": len(staff) - len(delivery),
        "grade_counts": {g: sum(p["grade"] == g for p in delivery) for g in GRADES},
        "annual_assumed_salary_total_krw": sum(rates[p["grade"]] for p in delivery),
        "monthly_assumed_salary_total_krw": sum(_monthly(rates[p["grade"]]) for p in delivery),
        "pricing_basis": "ANNUAL_SALARY_ASSUMPTION_DIVIDED_BY_12",
        "pricing_excludes": ["임원·경리 원가", "법정부담금", "퇴직급여", "간접비", "위험충당금"],
        "capacity_status": ("NOT_CONFIGURED" if not delivery else
                            "UNKNOWN" if any(p["available_mm"] is None for p in delivery) else "KNOWN"),
        "roles": roles,
        "staff": list(staff),
        "eligibility_status": "NOT_ASSESSED",
        "fit_status": "NEEDS_RFP_REQUIREMENTS_AND_CONFIRMED_SKILLS",
    }
