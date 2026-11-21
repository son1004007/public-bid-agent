"""AGW-09: validate model JSON against one independently verified AGW-05 packet.

This is structural citation and provenance validation, NOT fact-checking,
not a legal qualification decision and not a source of financial truth.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .snapshot import EvidenceSnapshot, SnapshotError, canonical_json, payload_hash, verify_snapshot

_RESULT_KEYS = frozenset({
    "schema_version", "run_id", "provider", "notice_version_id",
    "corpus_snapshot_id", "snapshot_sha256", "prompt_version",
    "requirements", "risks", "scenarios", "unknowns",
})
_ROW_KEYS = frozenset({
    "requirement_id", "assessment", "evidence_ids",
    "missing_evidence_ids", "rationale_short",
})
_ASSESSMENTS = frozenset({"MET", "NOT_MET", "PARTIAL", "UNKNOWN"})
_PROVIDERS = frozenset({"CODEX", "CLAUDE"})
_MAX_RESULT = 64 * 1024


class ResultContractError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ValidatedResult:
    payload: dict[str, Any]
    sha256: str


def _bounded_text(value, limit: int, code: str) -> str:
    if type(value) is not str or len(value.encode("utf-8")) > limit or "\x00" in value:
        raise ResultContractError(code)
    return value


def validate_model_result(
    *,
    result: dict[str, Any],
    snapshot: EvidenceSnapshot,
    expected_provider: str,
) -> ValidatedResult:
    """No raw CLI stdout, extra claims, invented IDs or unapproved citations."""
    if type(result) is not dict or frozenset(result) != _RESULT_KEYS:
        raise ResultContractError("INVALID_RESULT_SCHEMA")
    if expected_provider not in _PROVIDERS or result.get("provider") != expected_provider:
        raise ResultContractError("PROVIDER_MISMATCH")
    try:
        verify_snapshot(snapshot, expected_sha256=snapshot.sha256)
    except SnapshotError as exc:
        raise ResultContractError("INVALID_SNAPSHOT") from exc
    packet = snapshot.payload
    for key, expected in (
        ("schema_version", "bid_analysis_v1"),
        ("run_id", packet["run_id"]),
        ("notice_version_id", packet["notice_version_id"]),
        ("corpus_snapshot_id", packet["corpus_snapshot_id"]),
        ("snapshot_sha256", snapshot.sha256),
        ("prompt_version", packet["prompt_version"]),
    ):
        if type(result.get(key)) is not str or result[key] != expected:
            raise ResultContractError("RUN_OR_SNAPSHOT_MISMATCH")
    reqs = result.get("requirements")
    if type(reqs) is not list or len(reqs) > 200:
        raise ResultContractError("INVALID_RESULT_REQUIREMENTS")
    allowed = {r["requirement_id"] for r in packet["requirements"]}
    evidence = {r["evidence_id"]: r for r in packet["evidence"]}
    found: set[str] = set()
    normalized: list[dict] = []
    for row in reqs:
        if type(row) is not dict or frozenset(row) != _ROW_KEYS:
            raise ResultContractError("INVALID_RESULT_ROW")
        rid = row.get("requirement_id")
        if type(rid) is not str or rid not in allowed or rid in found:
            raise ResultContractError("UNEXPECTED_OR_DUPLICATE_REQUIREMENT")
        found.add(rid)
        assessment = row.get("assessment")
        if type(assessment) is not str or assessment not in _ASSESSMENTS:
            raise ResultContractError("INVALID_ASSESSMENT")
        cited = row.get("evidence_ids")
        missing = row.get("missing_evidence_ids")
        if (
            type(cited) is not list or len(cited) > 100
            or type(missing) is not list or len(missing) > 100
        ):
            raise ResultContractError("INVALID_EVIDENCE_LIST")
        if (
            any(type(x) is not str or x not in evidence for x in cited)
            or len(set(cited)) != len(cited)
            or any(type(x) is not str for x in missing)
            or len(set(missing)) != len(missing)
        ):
            raise ResultContractError("UNSUPPORTED_CITATION")
        if any(rid not in evidence[eid]["requirement_ids"] for eid in cited):
            raise ResultContractError("CROSS_REQUIREMENT_CITATION")
        if any(x in cited for x in missing):
            raise ResultContractError("CONTRADICTORY_EVIDENCE_IDS")
        if assessment in {"MET", "NOT_MET"}:
            # RFP explains the requirement, never whether the company complies.
            # Both positive AND negative definitive eligibility need trusted,
            # independently approved company evidence, never RFP citations alone.
            if not any(evidence[eid]["evidence_type"] == "COMPANY_FACT" for eid in cited):
                raise ResultContractError("UNPROVEN_ELIGIBILITY_ASSESSMENT")
        rationale = _bounded_text(row.get("rationale_short"), 2000, "INVALID_RATIONALE")
        if assessment == "UNKNOWN" and not missing:
            raise ResultContractError("UNKNOWN_REQUIRES_MISSING_EVIDENCE")
        normalized.append({
            "requirement_id": rid,
            "assessment": assessment,
            "evidence_ids": sorted(cited),
            "missing_evidence_ids": sorted(missing),
            "rationale_short": rationale,
        })
    if found != allowed:
        raise ResultContractError("INCOMPLETE_REQUIREMENT_COVERAGE")
    for array_key in ("risks", "scenarios", "unknowns"):
        if type(result.get(array_key)) is not list or result[array_key]:
            # v1 intentionally disallows unbounded subjective claims until
            # independently validated risk/scenario schemas are introduced.
            raise ResultContractError("UNSUPPORTED_NARRATIVE_SCHEMA")
    validated = dict(result)
    validated["requirements"] = sorted(normalized, key=lambda r: r["requirement_id"])
    validated["risks"], validated["scenarios"], validated["unknowns"] = [], [], []
    try:
        encoded = canonical_json(validated)
    except SnapshotError as exc:
        raise ResultContractError("INVALID_RESULT_JSON") from exc
    if len(encoded) > _MAX_RESULT:
        raise ResultContractError("RESULT_TOO_LARGE")
    return ValidatedResult(payload=validated, sha256=payload_hash(validated))


def validate_raw_result(
    *,
    raw_json: str,
    snapshot: EvidenceSnapshot,
    expected_provider: str,
) -> ValidatedResult:
    if type(raw_json) is not str or len(raw_json.encode("utf-8")) > _MAX_RESULT:
        raise ResultContractError("RESULT_TOO_LARGE")
    def reject_duplicate(pairs):
        out = {}
        for k, v in pairs:
            if k in out:
                raise ResultContractError("DUPLICATE_JSON_KEY")
            out[k] = v
        return out
    try:
        result = json.loads(raw_json, object_pairs_hook=reject_duplicate,
                            parse_constant=lambda _: (_ for _ in ()).throw(
                                ResultContractError("NONFINITE_VALUE")
                            ))
    except ResultContractError:
        # Preserve explicit duplicate-key and nonfinite-value rejection codes.
        raise
    except (ValueError, TypeError, RecursionError) as exc:
        raise ResultContractError("INVALID_RESULT_JSON") from exc
    return validate_model_result(result=result, snapshot=snapshot,
                                 expected_provider=expected_provider)
