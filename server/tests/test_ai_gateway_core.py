"""Credential-free fail-closed tests: no DB, model calls, secrets or network."""
import unittest
from dataclasses import replace

from ai_gateway_core import Profile, Provider, compare_results, select_plan


ALL_READY = Profile(provider=Provider.CODEX, registered=True, enabled=True,
                    authenticated=True, execution_contract_approved=True,
                    runtime_isolated=True, data_export_approved=True,
                    quota_available=True)


def fixture(provider="CODEX", verdict="MET", evidence=None):
    return {"provider": provider, "run_id": "run-123", "snapshot_sha256": "abc123",
            "requirements": [{"requirement_id": "R1", "assessment": verdict,
                              "evidence_ids": ["e-1"] if evidence is None else evidence}]}


class PlanTests(unittest.TestCase):
    def test_no_ai_by_default(self):
        self.assertEqual(select_plan([]).mode.value, "NO_AI")

    def test_disabled_registration_does_not_enable_execution(self):
        for name in ("registered", "enabled", "authenticated", "execution_contract_approved",
                     "runtime_isolated", "data_export_approved", "quota_available"):
            with self.subTest(name=name):
                self.assertEqual(select_plan([replace(ALL_READY, **{name: False})]).mode.value, "NO_AI")

    def test_single_codex(self):
        self.assertEqual(select_plan([ALL_READY]).mode.value, "SINGLE_CODEX")

    def test_single_claude(self):
        self.assertEqual(select_plan([replace(ALL_READY, provider=Provider.CLAUDE)]).mode.value,
                         "SINGLE_CLAUDE")

    def test_two_ready_independent(self):
        plan = select_plan([replace(ALL_READY, provider=Provider.CLAUDE), ALL_READY])
        self.assertEqual(plan.mode.value, "DUAL_INDEPENDENT")
        self.assertEqual([p.value for p in plan.providers], ["CODEX", "CLAUDE"])
        self.assertTrue(plan.requires_explicit_run_request)

    def test_duplicate_provider_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "DUPLICATE"):
            select_plan([ALL_READY, ALL_READY])

    def test_invalid_profile_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "INVALID"):
            select_plan([{"provider": "CODEX", "enabled": True}])


class EvidenceTests(unittest.TestCase):
    def check(self, a=None, b=None):
        return compare_results(codex=a or fixture(), claude=b or fixture(provider="CLAUDE"),
                               run_id="run-123", snapshot_hash="abc123",
                               expected_requirement_ids=frozenset({"R1"}),
                               approved_evidence_ids=frozenset({"e-1"}))

    def test_supported_agreement_not_automatic_bid(self):
        result = self.check()
        self.assertEqual(result.state.value, "AGREED_WITH_EVIDENCE")
        self.assertTrue(result.requires_human_review)

    def test_same_conclusion_without_evidence_is_insufficient(self):
        result = self.check(fixture(evidence=[]), fixture(provider="CLAUDE", evidence=[]))
        self.assertEqual(result.state.value, "INSUFFICIENT_EVIDENCE")

    def test_conflicting_answers_reported(self):
        result = self.check(fixture(verdict="NOT_MET"),
                            fixture(provider="CLAUDE", verdict="MET"))
        self.assertEqual(result.state.value, "DISAGREEMENT")
        self.assertEqual(result.differences[0].requirement_id, "R1")

    def test_missing_requirement_insufficient(self):
        missing = {"provider":"CLAUDE","run_id":"run-123",
                   "snapshot_sha256":"abc123","requirements":[]}
        self.assertEqual(self.check(fixture(), missing).state.value, "INSUFFICIENT_EVIDENCE")

    def test_fake_evidence_rejected(self):
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_EVIDENCE"):
            self.check(fixture(evidence=["fake"]))

    def test_wrong_snapshot_rejected(self):
        c = fixture()
        c["snapshot_sha256"] = "different"
        with self.assertRaisesRegex(ValueError, "RUN_OR_SNAPSHOT_MISMATCH"):
            self.check(c)

    def test_duplicated_requirements_rejected(self):
        c = fixture()
        c["requirements"] *= 2
        with self.assertRaisesRegex(ValueError, "UNEXPECTED_OR_DUPLICATE_REQUIREMENT"):
            self.check(c)

    def test_cross_provider_spoof_rejected(self):
        with self.assertRaisesRegex(ValueError, "PROVIDER_MISMATCH"):
            self.check(fixture(provider="CLAUDE"))


if __name__ == "__main__":
    unittest.main()
