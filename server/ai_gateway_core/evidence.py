"""Deterministic 1st-pass comparison. Model agreement never proves legal eligibility.

approved_evidence_ids MUST be obtained from an ACL-checked immutable server
snapshot. No outside model calls or data access occur here.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class ComparisonState(str, Enum):
    AGREED_WITH_EVIDENCE = "AGREED_WITH_EVIDENCE"
    PARTIAL_AGREEMENT = "PARTIAL_AGREEMENT"
    DISAGREEMENT = "DISAGREEMENT"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


_ALLOWED_ASSESSMENTS = frozenset({"MET", "NOT_MET", "PARTIAL", "UNKNOWN"})


@dataclass(frozen=True)
class RequirementDifference:
    requirement_id: str
    codex: str
    claude: str


@dataclass(frozen=True)
class Comparison:
    state: ComparisonState
    differences: tuple[RequirementDifference, ...]
    unsupported_requirement_ids: tuple[str, ...]
    requires_human_review: bool = True


def _parse_result(value: Mapping[str, object], provider: str, run_id: str,
                  snapshot_hash: str, expected_requirements: frozenset[str],
                  approved_evidence_ids: frozenset[str]) -> dict[str, tuple[str, frozenset[str]]]:
    if not isinstance(value, dict) or value.get("provider") != provider:
        raise ValueError("PROVIDER_MISMATCH")
    if value.get("run_id") != run_id or value.get("snapshot_sha256") != snapshot_hash:
        raise ValueError("RUN_OR_SNAPSHOT_MISMATCH")
    rows = value.get("requirements")
    if not isinstance(rows, list) or len(rows) > 200:
        raise ValueError("INVALID_REQUIREMENTS")
    result: dict[str, tuple[str, frozenset[str]]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("INVALID_REQUIREMENT_ROW")
        rid, status, evidence = row.get("requirement_id"), row.get("assessment"), row.get("evidence_ids")
        if not isinstance(rid, str) or rid not in expected_requirements or rid in result:
            raise ValueError("UNEXPECTED_OR_DUPLICATE_REQUIREMENT")
        if not isinstance(status, str) or status not in _ALLOWED_ASSESSMENTS:
            raise ValueError("INVALID_ASSESSMENT")
        if not isinstance(evidence, list) or len(evidence) > 100 or any(
            not isinstance(e, str) or e not in approved_evidence_ids for e in evidence
        ):
            raise ValueError("UNSUPPORTED_EVIDENCE")
        if len(set(evidence)) != len(evidence):
            raise ValueError("DUPLICATE_EVIDENCE")
        result[rid] = (status, frozenset(evidence))
    return result


def compare_results(*, codex: Mapping[str, object], claude: Mapping[str, object],
                    run_id: str, snapshot_hash: str,
                    expected_requirement_ids: frozenset[str],
                    approved_evidence_ids: frozenset[str]) -> Comparison:
    """Compare approved evidence membership; independent server fact checks remain required."""
    if not expected_requirement_ids or len(expected_requirement_ids) > 200:
        raise ValueError("INVALID_EXPECTED_REQUIREMENTS")
    if not run_id or not snapshot_hash:
        raise ValueError("INVALID_SNAPSHOT_IDENTITY")
    left = _parse_result(codex, "CODEX", run_id, snapshot_hash,
                         expected_requirement_ids, approved_evidence_ids)
    right = _parse_result(claude, "CLAUDE", run_id, snapshot_hash,
                          expected_requirement_ids, approved_evidence_ids)
    differences: list[RequirementDifference] = []
    unsupported: list[str] = []
    same = 0
    missing_any = bool(expected_requirement_ids - left.keys() or expected_requirement_ids - right.keys())
    for rid in sorted(expected_requirement_ids):
        l = left.get(rid, ("UNKNOWN", frozenset()))
        r = right.get(rid, ("UNKNOWN", frozenset()))
        if l[0] != r[0]:
            differences.append(RequirementDifference(rid, l[0], r[0]))
        elif l[0] != "UNKNOWN":
            same += 1
        if l[0] in {"UNKNOWN", "PARTIAL"} or r[0] in {"UNKNOWN", "PARTIAL"} or not l[1] or not r[1]:
            unsupported.append(rid)
    if missing_any:
        state = ComparisonState.INSUFFICIENT_EVIDENCE
    elif differences:
        state = ComparisonState.DISAGREEMENT
    elif unsupported:
        state = ComparisonState.INSUFFICIENT_EVIDENCE
    elif same == len(expected_requirement_ids):
        state = ComparisonState.AGREED_WITH_EVIDENCE
    else:
        state = ComparisonState.PARTIAL_AGREEMENT
    return Comparison(state=state, differences=tuple(differences),
                      unsupported_requirement_ids=tuple(unsupported))
