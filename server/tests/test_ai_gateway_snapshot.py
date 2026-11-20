"""AGW-05/09 pure contract regression; synthetic data only, no model/network."""
import copy
import json
import unittest
import uuid

from ai_gateway_core.snapshot import (
    SnapshotError, EvidenceSnapshot, build_snapshot, payload_hash, verify_snapshot,
)
from ai_gateway_core.result_contract import (
    ResultContractError, validate_model_result, validate_raw_result,
)

RUN = "11111111-2222-4333-8444-555555555555"
NOTICE_VERSION = "22222222-3333-4444-8555-666666666666"
CORPUS = "33333333-4444-4555-8666-777777777777"
DOC = "44444444-5555-4666-8777-888888888888"
SOURCE_VERSION = "55555555-6666-4777-8888-999999999999"
SPAN1 = "66666666-7777-4888-8999-aaaaaaaaaaaa"
SPAN2 = "77777777-8888-4999-8aaa-bbbbbbbbbbbb"


def request_args():
    return {
        "run_id": RUN,
        "notice_version_id": NOTICE_VERSION,
        "corpus_snapshot_id": CORPUS,
        "prompt_version": "agw-v1",
        "requirements": [{
            "requirement_id": "R1", "source_document_id": DOC,
            "source_version": SOURCE_VERSION, "source_span_id": SPAN1,
            "source_hash": "a" * 64,
            "required_kind": "QUALIFICATION", "excerpt": "Synthetic 3 projects required",
            "extraction_state": "PARSED",
        }],
        "evidence": [{
            "evidence_id": "E1", "evidence_type": "RFP",
            "source_document_id": DOC, "source_version": SOURCE_VERSION,
            "source_span_id": SPAN2, "source_hash": "b" * 64,
            "excerpt": "Synthetic official qualification",
            "classification": "SYNTHETIC", "approved_for_provider": True,
            "requirement_ids": ["R1"],
        }],
        "approved_document_ids": frozenset({DOC}),
    }


def model_result(snapshot, assessment="UNKNOWN", citations=None):
    p = snapshot.payload
    return {
        "schema_version": "bid_analysis_v1",
        "run_id": p["run_id"], "provider": "CODEX",
        "notice_version_id": p["notice_version_id"],
        "corpus_snapshot_id": p["corpus_snapshot_id"],
        "snapshot_sha256": snapshot.sha256,
        "prompt_version": p["prompt_version"],
        "requirements": [{
            "requirement_id": "R1", "assessment": assessment,
            "evidence_ids": ["E1"] if citations is None else citations,
            "missing_evidence_ids": [] if assessment != "UNKNOWN" else ["NEEDS_PROOF"],
            "rationale_short": "Three projects required; evidence incomplete.",
        }],
        "risks": [], "scenarios": [], "unknowns": [],
    }


class SnapshotContractTests(unittest.TestCase):
    def make(self, **changes):
        args = request_args()
        args.update(changes)
        return build_snapshot(**args)

    def test_valid_canonical_digest(self):
        snapshot = self.make()
        self.assertEqual(snapshot.sha256, payload_hash(snapshot.payload))
        self.assertEqual(snapshot.requirement_ids, {"R1"})
        self.assertEqual(snapshot.evidence_ids, {"E1"})
        verify_snapshot(snapshot, expected_sha256=snapshot.sha256)

    def test_order_independent_canonical_packet(self):
        a = request_args()
        a["requirements"][0] = dict(reversed(list(a["requirements"][0].items())))
        a["evidence"][0] = dict(reversed(list(a["evidence"][0].items())))
        self.assertEqual(self.make().sha256, build_snapshot(**a).sha256)

    def test_tampered_packet_rejected(self):
        s = self.make()
        s.payload["requirements"][0]["excerpt"] = "Changed"
        with self.assertRaisesRegex(SnapshotError, "SNAPSHOT_DIGEST_MISMATCH"):
            verify_snapshot(s, expected_sha256=s.sha256)

    def test_source_not_approved_rejected(self):
        with self.assertRaisesRegex(SnapshotError, "UNAUTHORIZED_SOURCE_DOCUMENT"):
            self.make(approved_document_ids=frozenset({RUN}))

    def test_company_private_evidence_rejected(self):
        a = request_args()
        a["evidence"][0]["classification"] = "PRIVATE"
        with self.assertRaisesRegex(SnapshotError, "EGRESS_CLASSIFICATION_DENIED"):
            build_snapshot(**a)

    def test_provider_approval_required(self):
        a = request_args()
        a["evidence"][0]["approved_for_provider"] = False
        with self.assertRaisesRegex(SnapshotError, "PROVIDER_EGRESS_NOT_APPROVED"):
            build_snapshot(**a)

    def test_partial_extraction_rejected(self):
        a = request_args()
        a["requirements"][0]["extraction_state"] = "PARTIAL"
        with self.assertRaisesRegex(SnapshotError, "INCOMPLETE_EXTRACTION"):
            build_snapshot(**a)

    def test_unknown_fields_rejected(self):
        a = request_args()
        a["requirements"][0]["employee_salary"] = 123
        with self.assertRaisesRegex(SnapshotError, "INVALID_REQUIREMENT_SCHEMA"):
            build_snapshot(**a)

    def test_duplicate_requirements_rejected(self):
        a = request_args()
        a["requirements"] *= 2
        with self.assertRaisesRegex(SnapshotError, "DUPLICATE_REQUIREMENT_ID"):
            build_snapshot(**a)

    def test_unlinked_evidence_rejected(self):
        a = request_args()
        a["evidence"][0]["requirement_ids"] = ["R2"]
        with self.assertRaisesRegex(SnapshotError, "INVALID_EVIDENCE_REQUIREMENT_LINK"):
            build_snapshot(**a)

    def test_packet_size_limit(self):
        a = request_args()
        a["requirements"][0]["excerpt"] = "x" * 120000
        with self.assertRaises(SnapshotError):
            build_snapshot(**a)

    def test_illegal_classification_allowlist_rejected(self):
        with self.assertRaisesRegex(SnapshotError, "MISSING_APPROVED_SOURCE_SCOPE"):
            self.make(allowed_classifications=frozenset({"COMPANY_PRIVATE"}))


class ResultContractTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = build_snapshot(**request_args())

    def result(self, **changes):
        r = model_result(self.snapshot)
        r.update(changes)
        return r

    def test_valid_result_normalized_and_digest(self):
        r = validate_model_result(result=self.result(), snapshot=self.snapshot,
                                  expected_provider="CODEX")
        self.assertEqual(r.sha256, payload_hash(r.payload))
        self.assertEqual(r.payload["requirements"][0]["assessment"], "UNKNOWN")

    def test_raw_json_no_duplicate_keys(self):
        result = self.result()
        raw = json.dumps(result)[:-1] + ',"run_id":"WRONG"}'
        with self.assertRaisesRegex(ResultContractError, "DUPLICATE_JSON_KEY"):
            validate_raw_result(raw_json=raw, snapshot=self.snapshot,
                                expected_provider="CODEX")

    def test_other_run_rejected(self):
        with self.assertRaisesRegex(ResultContractError, "RUN_OR_SNAPSHOT_MISMATCH"):
            validate_model_result(result=self.result(run_id=CORPUS), snapshot=self.snapshot,
                                  expected_provider="CODEX")

    def test_other_snapshot_rejected(self):
        with self.assertRaisesRegex(ResultContractError, "RUN_OR_SNAPSHOT_MISMATCH"):
            validate_model_result(result=self.result(snapshot_sha256="f" * 64),
                                  snapshot=self.snapshot, expected_provider="CODEX")

    def test_forged_provider_rejected(self):
        with self.assertRaisesRegex(ResultContractError, "PROVIDER_MISMATCH"):
            validate_model_result(result=self.result(provider="CLAUDE"),
                                  snapshot=self.snapshot, expected_provider="CODEX")

    def test_forged_evidence_id_rejected(self):
        r = self.result()
        r["requirements"][0]["evidence_ids"] = ["E_FAKE"]
        with self.assertRaisesRegex(ResultContractError, "UNSUPPORTED_CITATION"):
            validate_model_result(result=r, snapshot=self.snapshot,
                                  expected_provider="CODEX")

    def test_rfp_alone_cannot_prove_met(self):
        r = self.result()
        r["requirements"][0]["assessment"] = "MET"
        with self.assertRaisesRegex(ResultContractError, "UNPROVEN_ELIGIBILITY_ASSESSMENT"):
            validate_model_result(result=r, snapshot=self.snapshot,
                                  expected_provider="CODEX")

    def test_unknown_requires_missing_reason(self):
        r = self.result()
        r["requirements"][0]["assessment"] = "UNKNOWN"
        r["requirements"][0]["missing_evidence_ids"] = []
        with self.assertRaisesRegex(ResultContractError, "UNKNOWN_REQUIRES_MISSING_EVIDENCE"):
            validate_model_result(result=r, snapshot=self.snapshot,
                                  expected_provider="CODEX")

    def test_unknown_with_missing_reason_allowed(self):
        r = model_result(self.snapshot, assessment="UNKNOWN")
        self.assertEqual(validate_model_result(
            result=r, snapshot=self.snapshot, expected_provider="CODEX",
        ).payload["requirements"][0]["assessment"], "UNKNOWN")

    def test_missing_requirement_rejected(self):
        with self.assertRaisesRegex(ResultContractError, "INCOMPLETE_REQUIREMENT_COVERAGE"):
            validate_model_result(
                result=self.result(requirements=[]), snapshot=self.snapshot,
                expected_provider="CODEX",
            )

    def test_new_field_or_salary_rejected(self):
        r = self.result()
        r["annual_salary"] = 100000000
        with self.assertRaisesRegex(ResultContractError, "INVALID_RESULT_SCHEMA"):
            validate_model_result(result=r, snapshot=self.snapshot,
                                  expected_provider="CODEX")

    def test_unreviewed_narrative_rejected(self):
        with self.assertRaisesRegex(ResultContractError, "UNSUPPORTED_NARRATIVE_SCHEMA"):
            validate_model_result(result=self.result(risks=[{"secret": "fake"}]),
                                  snapshot=self.snapshot, expected_provider="CODEX")

    def test_tampered_approved_snapshot_rejected(self):
        self.snapshot.payload["evidence"][0]["excerpt"] = "manipulated"
        with self.assertRaisesRegex(ResultContractError, "INVALID_SNAPSHOT"):
            validate_model_result(result=self.result(), snapshot=self.snapshot,
                                  expected_provider="CODEX")

    def test_result_oversized_rejected(self):
        raw = "{" + "x" * 100000 + "}"
        with self.assertRaisesRegex(ResultContractError, "RESULT_TOO_LARGE"):
            validate_raw_result(raw_json=raw, snapshot=self.snapshot,
                                expected_provider="CODEX")


if __name__ == "__main__":
    unittest.main()
