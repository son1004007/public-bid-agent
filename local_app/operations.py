"""로컬 회사 운영 기준정보와 공고별 예상원가 계산 계약.

목적: 운영정보(role별 월 총원가/가용 공수·간접비/위험충당)와 공고별
투입 공수/외주/직접경비/제안비/예정 공급가액을 분리해 계산한다.
신뢰 경계: 클라이언트 JSON은 비신뢰; 수치·범위·중복·초과 입력을 검증한다.
출력: VAT 제외 기준의 원가 및 사업이익(금액/이익률) 참고 값.
불변: 개인 급여·사내 전략·운영 JSON을 Codex/Claude로 자동 전송하지 않는다.
실제 자격/수주확률/법적 세무 판단이나 실사용 회계 산정은 수행하지 않는다.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re

MAX_MONEY = 10**12
MAX_ROLES = 20


def _money(value, label, optional=False):
    if value is None and optional:
        return None
    if type(value) is not int or not 0 <= value <= MAX_MONEY:
        raise ValueError(label + "은 0~1조 원 사이의 정수여야 합니다")
    return value


def _number(value, label, maximum=1000):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(label + "은 소수 둘째 자리까지 입력하세요")
    try:
        number = Decimal(str(value))
    except InvalidOperation as e:
        raise ValueError(label + "의 숫자 형식이 올바르지 않습니다") from e
    if not number.is_finite() or number < 0 or number > maximum or number.as_tuple().exponent < -2:
        raise ValueError(label + "은 0 이상, 최대 " + str(maximum) + "까지 소수 2자리로 입력하세요")
    return number


def default_profile():
    return {"schema_version": 1, "revision": 0, "roles": [],
            "overhead_pct": 0, "reserve_pct": 0, "updated_at": None}


def clean_profile(value):
    if not isinstance(value, dict):
        raise ValueError("운영정보 객체가 필요합니다")
    roles = value.get("roles")
    if not isinstance(roles, list) or len(roles) > MAX_ROLES:
        raise ValueError("직무 기준은 최대 20개까지 입력할 수 있습니다")
    seen = set()
    cleaned = []
    for item in roles:
        if not isinstance(item, dict):
            raise ValueError("직무 입력 형식이 올바르지 않습니다")
        name = item.get("role")
        if not isinstance(name, str) or not (1 <= len(name.strip()) <= 60):
            raise ValueError("직무명은 1~60자로 입력하세요")
        name = name.strip()
        if not re.fullmatch(r"[^\\/\x00-\x1f]+", name):
            raise ValueError("직무명에 허용되지 않은 문자가 있습니다")
        if name.casefold() in seen:
            raise ValueError("중복된 직무명: " + name)
        seen.add(name.casefold())
        cleaned.append({
            "role": name,
            "cost_per_mm_krw": _money(item.get("cost_per_mm_krw"), "직무별 월 총원가"),
            "available_mm": float(_number(item.get("available_mm", 0), "가용 공수")),
        })
    overhead = _number(value.get("overhead_pct", 0), "간접비율", 100)
    reserve = _number(value.get("reserve_pct", 0), "위험충당률", 100)
    return {"schema_version": 1, "roles": cleaned,
            "overhead_pct": float(overhead), "reserve_pct": float(reserve)}


def clean_plan(value, profile):
    if not isinstance(value, dict):
        raise ValueError("공고별 원가계획 객체가 필요합니다")
    entries = value.get("entries")
    if not isinstance(entries, list) or len(entries) > MAX_ROLES:
        raise ValueError("공고별 투입 공수 형식이 올바르지 않습니다")
    allowed = {r["role"] for r in profile["roles"]}
    seen = set()
    result = []
    for line in entries:
        if not isinstance(line, dict) or line.get("role") not in allowed or line["role"] in seen:
            raise ValueError("등록되지 않았거나 중복된 직무 투입 정보가 있습니다")
        seen.add(line["role"])
        result.append({"role": line["role"], "mm": float(_number(line.get("mm"), "투입 공수"))})
    return {"entries": result,
            "subcontract_krw": _money(value.get("subcontract_krw", 0), "외주비"),
            "direct_expenses_krw": _money(value.get("direct_expenses_krw", 0), "직접경비"),
            "proposal_krw": _money(value.get("proposal_krw", 0), "제안 준비비"),
            "proposed_supply_price_krw": _money(
                value.get("proposed_supply_price_krw"), "예정 공급가액", optional=True),
           }


def _won(value):
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def calculate(profile, plan):
    """항상 동일한 입력에서 동일한 금액을 계산; 원가 기준일/환율/실입찰가 인증 없음."""
    catalog = {r["role"]: r for r in profile["roles"]}
    labor = sum((_won(Decimal(catalog[r["role"]]["cost_per_mm_krw"]) * Decimal(str(r["mm"])))
                 for r in plan["entries"]), 0)
    direct = labor + plan["subcontract_krw"] + plan["direct_expenses_krw"]
    overhead = _won(Decimal(direct) * Decimal(str(profile["overhead_pct"])) / 100)
    reserve = _won(Decimal(direct + overhead) * Decimal(str(profile["reserve_pct"])) / 100)
    total = direct + overhead + reserve + plan["proposal_krw"]
    price = plan["proposed_supply_price_krw"]
    profit = price - total if price is not None else None
    margin = float((Decimal(profit) * 100 / Decimal(price)).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP)) if price else None
    warnings = []
    if not plan["entries"] or all(x["mm"] == 0 for x in plan["entries"]):
        warnings.append("투입 공수가 0입니다. 사업원가를 확정할 수 없습니다")
    for entry in plan["entries"]:
        role = catalog[entry["role"]]
        if entry["mm"] > role["available_mm"]:
            warnings.append(entry["role"] + " 투입 공수가 현재 가용 공수를 초과합니다")
        if entry["mm"] > 0 and role["cost_per_mm_krw"] == 0:
            warnings.append(entry["role"] + " 월 원가 단가가 0원입니다. 회사 기준단가를 확인하세요")
    if price is None:
        warnings.append("예정 공급가액이 없어 사업이익·이익률을 산출하지 않았습니다")
    if price == 0:
        warnings.append("예정 공급가액 0원은 유효한 견적이 아닙니다")
    return {"labor_krw": labor, "subcontract_krw": plan["subcontract_krw"],
            "direct_expenses_krw": plan["direct_expenses_krw"],
            "overhead_krw": overhead, "reserve_krw": reserve,
            "proposal_krw": plan["proposal_krw"], "total_cost_krw": total,
            "proposed_supply_price_krw": price, "expected_profit_krw": profit,
            "expected_margin_pct": margin, "warnings": warnings,
            "status": "NEEDS_REVIEW" if warnings else "ESTIMATE_ONLY",
            "note": "부가세 제외 예상 공급가 기준 내부 참고 계산. 세무/회계 확정·낙찰 가능성 아님."}
