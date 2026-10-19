"""BID-04 파일 설계 계약.

목적/책임: 실제 로컬 저장 공고의 현재 검토 상태·위험·일관성을 집계한다.
입력/출력: 비신뢰 JSON 스냅샷과 고정 시각 → 고정 코드·집계 건수만.
신뢰 경계/권한: ID/원문/회사·직원/스킬 분포/원가·경로·SHA 미출력.
상태 변경/부작용: 순수 함수, 입력 불변. 외부 I/O·AI·실제 입찰 없음.
실패/재시도: 잘못된 필수 입력은 고정 ValueError, 증빙 부족은 BLOCKED_EVIDENCE.
핵심 불변조건: 적격·수익·보완 허용 UNVERIFIED; 스킬 부족만으로 기회 제외 금지.
관련 요구사항/테스트/설계: D-20, BID-04, test_bid_now_audit.py,
docs/design/BID04_LOCAL_AGGREGATE_2026-10-19.md.
"""
from collections import Counter, defaultdict
from datetime import datetime
import re

from bid_now_shortlist import VALID_ID, MAX_NOTICE_COUNT
from bid_now_triage import classify
from bid_readiness import REQUIRED, _evidence_gaps, _operational_gaps
from department_profile import validate as validate_department
from notice_lifecycle import is_cancel_kind
from operations import clean_profile
from procurement_filter import KST
from workforce import validate as validate_workforce, TECH_ROLES

TRIAGE_STATES = (
    "PRIORITY_REVIEW", "NEEDS_OFFICIAL_DOCUMENT", "NEEDS_EXTRACTION_REVIEW",
    "CAPABILITY_GAP_MARGIN_REVIEW", "REVIEW_REGISTRATION", "HOLD_OFFICIAL_STATUS",
    "HOLD_STALE_DOCUMENT", "HOLD_DEADLINE", "REVIEW_UNKNOWN_DEADLINE",
    "INVALID_RECORD_HELD", "INCONSISTENT_RECORD_HELD",
)
DEADLINES = ("CLOSED", "UNKNOWN", "WITHIN_24H", "WITHIN_72H", "WITHIN_7D", "LATER")
RISKS = (
    "CANCELLED", "SUPERSEDED", "LIFECYCLE_UNVERIFIED", "STALE_DOCUMENT",
    "DEADLINE_CLOSED", "DEADLINE_UNKNOWN", "REGISTRATION_PASSED",
    "REGISTRATION_UNKNOWN", "REGISTRATION_AFTER_CLOSE", "DOCUMENT_REVIEW",
    "LEGAL_ELIGIBILITY_UNVERIFIED", "STORED_ELIGIBILITY_CLAIM_IGNORED",
)
CONSISTENCY = (
    "MALFORMED_RECORD", "INVALID_OFFICIAL_IDENTITY", "DUPLICATE_ID_ROWS",
    "AMBIGUOUS_NUMERIC_REVISION_ROWS", "LIFECYCLE_MISMATCH_ROWS",
    "STORED_WINDOW_MISMATCH_ROWS", "INVALID_DEPARTMENT_CLASSIFICATION_ROWS",
    "REGISTRATION_AFTER_CLOSE_ROWS",
)


def parse_time(value: object) -> datetime | None:
    """공식 저장 naive 시각은 KST; 명시 음수 offset도 그대로 변환한다."""
    if (not isinstance(value, str) or len(value) > 64
            or not re.match(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}", value)):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return (parsed.replace(tzinfo=KST) if parsed.tzinfo is None
                else parsed.astimezone(KST))
    except (ValueError, OverflowError):
        return None


def _deadline(due, stamp):
    if due is None:
        return "UNKNOWN"
    seconds = (due - stamp).total_seconds()
    if seconds <= 0:
        return "CLOSED"
    for bound, key in ((86400, "WITHIN_24H"), (259200, "WITHIN_72H"),
                       (604800, "WITHIN_7D")):
        if seconds <= bound:
            return key
    return "LATER"


def _evidence(profile, operations, workforce, stamp):
    gaps = set()
    selected = {"categories": []}
    try:
        if (not isinstance(profile, dict) or type(profile.get("schema_version")) is not int
                or profile["schema_version"] != 1
                or type(profile.get("revision")) is not int or profile["revision"] < 0):
            raise ValueError("PROFILE")
        selected = validate_department(profile)
        if not selected["categories"]:
            gaps.add("DEPARTMENT_PROFILE_EMPTY")
    except (ValueError, TypeError, KeyError):
        gaps.add("DEPARTMENT_PROFILE_MISSING_OR_INVALID")
    try:
        if (not isinstance(operations, dict) or type(operations.get("schema_version")) is not int
                or operations["schema_version"] != 1):
            raise ValueError("OPERATIONS")
        clean = clean_profile(operations)
        staffing, costs = _operational_gaps(clean)
        if staffing:
            gaps.add("MM_EVIDENCE_MISSING_OR_INVALID")
        if costs:
            gaps.add("COST_EVIDENCE_MISSING_OR_INVALID")
        for key in REQUIRED:
            record = clean["registers"][key]
            if record["status"] != "reviewed" or _evidence_gaps(record, stamp.date()):
                gaps.add({"utilization": "MM_EVIDENCE_MISSING_OR_INVALID",
                          "finance": "COST_EVIDENCE_MISSING_OR_INVALID"}.get(
                              key, "DEPARTMENT_EVIDENCE_INCOMPLETE"))
    except (ValueError, TypeError, KeyError, AttributeError):
        gaps.update(("OPERATIONS_MISSING_OR_INVALID", "MM_EVIDENCE_MISSING_OR_INVALID",
                     "COST_EVIDENCE_MISSING_OR_INVALID"))
    try:
        staff = validate_workforce(workforce)["staff"]
        delivery = [p for p in staff if p["role"] in TECH_ROLES]
        if not delivery:
            gaps.add("WORKFORCE_MISSING_OR_INVALID")
        if not delivery or any(p["available_mm"] is None for p in delivery):
            gaps.add("MM_EVIDENCE_MISSING_OR_INVALID")
    except (ValueError, TypeError, KeyError, AttributeError):
        gaps.update(("WORKFORCE_MISSING_OR_INVALID", "MM_EVIDENCE_MISSING_OR_INVALID"))
    # v1 only accepts ASSUMED/UNKNOWN: no fabricated verified-skills fallback.
    gaps.add("SKILLS_EVIDENCE_UNVERIFIED")
    gaps.add("NOTICE_SPECIFIC_COMPARISON_NOT_PERFORMED")
    return selected, sorted(gaps)


def evaluate(notices: list, profile: dict | None, operations: dict | None,
             workforce: dict | None, *, at: datetime | None = None) -> dict:
    """파일/네트워크에 접근하지 않고 전수 집계. 실제 자료는 메모리에만 존재한다."""
    if not isinstance(notices, list) or len(notices) > MAX_NOTICE_COUNT:
        raise ValueError("INVALID_NOTICE_COLLECTION")
    if at is not None and (not isinstance(at, datetime) or at.tzinfo is None
                           or at.utcoffset() is None):
        raise ValueError("INVALID_CLOCK")
    stamp = (at or datetime.now(KST)).astimezone(KST)
    selected, gaps = _evidence(profile, operations, workforce, stamp)
    profile_known = not any(code.startswith("DEPARTMENT_PROFILE_") for code in gaps)
    counts = dict.fromkeys(TRIAGE_STATES, 0)
    risks = dict.fromkeys(RISKS, 0)
    consistency = dict.fromkeys(CONSISTENCY, 0)
    deadlines = dict.fromkeys(DEADLINES, 0)
    active_deadlines = dict.fromkeys(DEADLINES, 0)
    rows = []
    ids = Counter()
    groups = defaultdict(list)
    for n in notices:
        if not isinstance(n, dict):
            consistency["MALFORMED_RECORD"] += 1
            continue
        code = n.get("id")
        ident = VALID_ID.fullmatch(code) if isinstance(code, str) else None
        if (not ident or n.get("source") != "G2B_OFFICIAL_API"
                or n.get("bid_no") != ident.group(1)
                or type(n.get("bid_order")) not in (str, int)
                or str(n["bid_order"]) != ident.group(2)):
            consistency["INVALID_OFFICIAL_IDENTITY"] += 1
            continue
        ids[code] += 1
        rows.append(n)
        groups[n["bid_no"]].append(n)
    effective = {}
    ambiguous = set()
    for group in groups.values():
        latest = max(int(n["bid_order"]) for n in group)
        revisions = Counter(int(n["bid_order"]) for n in group)
        latest_cancelled = any(int(n["bid_order"]) == latest and (
            is_cancel_kind(n.get("notice_kind")) or n.get("notice_lifecycle") == "CANCELLED")
            for n in group)
        for n in group:
            order = int(n["bid_order"])
            if revisions[order] > 1:
                ambiguous.add(n["id"])
            effective[n["id"]] = ("SUPERSEDED" if order < latest else
                "CANCELLED" if latest_cancelled else "REVIEW" if revisions[order] > 1
                else "CURRENT")
    active = matching = registration = match_unknown = 0
    invalid = len(notices) - len(rows)
    counts["INVALID_RECORD_HELD"] = invalid
    valid_rows = {id(n) for n in rows}
    for n in (row for row in notices if isinstance(row, dict)):
        valid_identity = id(n) in valid_rows
        code = n.get("id") if valid_identity else None
        state = effective[code] if valid_identity else "UNKNOWN"
        lifecycle = n.get("notice_lifecycle")
        duplicate = valid_identity and ids[code] > 1
        conflict = lifecycle != state
        consistency["DUPLICATE_ID_ROWS"] += int(duplicate)
        consistency["AMBIGUOUS_NUMERIC_REVISION_ROWS"] += int(code in ambiguous)
        consistency["LIFECYCLE_MISMATCH_ROWS"] += int(valid_identity and conflict)
        due = parse_time(n.get("end"))
        cutoff = parse_time(n.get("qualification_deadline"))
        deadline = _deadline(due, stamp)
        deadlines[deadline] += 1
        cancelled = (state == "CANCELLED" or lifecycle == "CANCELLED"
                     or is_cancel_kind(n.get("notice_kind")))
        stale = n.get("rfp_review_status") == "STALE"
        passed = cutoff is not None and cutoff <= stamp
        reversed_dates = due is not None and cutoff is not None and cutoff > due
        computed_window = ("CANCELLED" if cancelled else "UNKNOWN" if due is None else
                           "CLOSED" if due <= stamp else "REGISTRATION_REVIEW" if passed
                           else "OPEN")
        consistency["STORED_WINDOW_MISMATCH_ROWS"] += int(
            "window_status" in n and n["window_status"] != computed_window
            and not (lifecycle in ("CANCELLED", "SUPERSEDED")
                     and n["window_status"] == lifecycle))
        consistency["REGISTRATION_AFTER_CLOSE_ROWS"] += int(reversed_dates)
        risks["CANCELLED"] += int(cancelled)
        risks["SUPERSEDED"] += int(state == "SUPERSEDED" or lifecycle == "SUPERSEDED")
        risks["LIFECYCLE_UNVERIFIED"] += int(lifecycle not in ("CURRENT", "CANCELLED", "SUPERSEDED"))
        risks["STALE_DOCUMENT"] += int(stale)
        risks["DEADLINE_CLOSED"] += int(deadline == "CLOSED")
        risks["DEADLINE_UNKNOWN"] += int(deadline == "UNKNOWN")
        risks["REGISTRATION_PASSED"] += int(passed)
        risks["REGISTRATION_UNKNOWN"] += int(cutoff is None)
        risks["REGISTRATION_AFTER_CLOSE"] += int(reversed_dates)
        risks["STORED_ELIGIBILITY_CLAIM_IGNORED"] += int(
            n.get("legal_eligibility") not in (None, "", "UNVERIFIED"))
        categories = n.get("department_categories")
        valid_categories = (isinstance(categories, list) and all(
            type(c) is str and c in ("AI", "SW", "DATA", "SECURITY") for c in categories))
        consistency["INVALID_DEPARTMENT_CLASSIFICATION_ROWS"] += int(not valid_categories)
        # Only normalize a shallow copy; preserve snapshots and stored window claims.
        safe = dict(n)
        safe["end"] = due.isoformat() if due else ""
        if "qualification_deadline" in n:
            safe["qualification_deadline"] = cutoff.isoformat() if cutoff else ""
        if not valid_categories:
            safe["department_categories"] = []
        try:
            triage = classify(safe, selected, at=stamp)
        except (ValueError, TypeError, AttributeError, OverflowError):
            consistency["MALFORMED_RECORD"] += 1
            if valid_identity:
                counts["INVALID_RECORD_HELD"] += 1
                invalid += 1
            continue
        risks["DOCUMENT_REVIEW"] += int(bool(triage["document_quality_flags"])
                                         or triage["document_state"] != "EXTRACTED_TEXT")
        if not valid_identity:
            continue
        if duplicate or code in ambiguous or conflict or reversed_dates:
            counts["INCONSISTENT_RECORD_HELD"] += 1
            continue
        counts[triage["status"]] += 1
        if (lifecycle == "CURRENT" and not cancelled and not stale
                and due is not None and due > stamp):
            active += 1
            active_deadlines[deadline] += 1
            match_unknown += int(not profile_known or not valid_categories)
            matching += int(profile_known and valid_categories and triage["department_category_match"])
            registration += int(passed or cutoff is None)
    risks["LEGAL_ELIGIBILITY_UNVERIFIED"] = len(notices)
    return {
        "schema_version": 1, "mode": "READ_ONLY_LOCAL_AGGREGATE",
        "evaluated_at": stamp.isoformat(), "status": "BLOCKED_EVIDENCE",
        "evidence_gap_codes": gaps,
        "total_notices": len(notices), "active_notice_count": active,
        "held_notice_count": len(notices) - active - invalid,
        "invalid_notice_count": invalid,
        "department_match_status": "METADATA_ONLY_UNVERIFIED" if profile_known else "BLOCKED_EVIDENCE",
        "active_department_category_match_count": matching,
        "active_department_match_unknown_count": match_unknown,
        "active_augmentation_review_count": active - matching - match_unknown,
        "active_registration_review_count": registration,
        "triage_status_counts": counts, "deadline_counts": deadlines,
        "active_deadline_counts": active_deadlines, "risk_counts": risks,
        "consistency_counts": consistency,
        "legal_eligibility": "UNVERIFIED", "profitability": "UNVERIFIED",
        "augmentation_permitted": "UNVERIFIED", "official_freshness": "UNVERIFIED",
        "bid_decision": "HUMAN_ONLY", "automatic_bid_submittal": False,
        "cannot_auto_discard_on_capability_gap": True,
        "risk_counts_overlap": True, "private_data_included": False,
    }
