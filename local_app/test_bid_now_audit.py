"""BID-04 합성 검증: 기한·공식 상태·증빙·집계 비식별·읽기 전용 경계.

임시 생성 JSON만 사용. 실제 공고/회사/인력/원가는 접근하지 않는다.
CLI stdout/stderr까지 canary 누출·오류 경계를 검사하고 스냅샷 변경을 재현한다.
"""
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from bid_now_audit import evaluate
import bid_now_audit_cli as cli
from operations import default_profile
from procurement_filter import KST

NOW = datetime(2026, 10, 19, 12, tzinfo=KST)
PROFILE = {"schema_version": 1, "revision": 1, "categories": ["SW"], "include_review": False}
CANARY = "SYNTHETIC_PRIVATE_CANARY_987654321"


def notice(i=1, **kw):
    row = {"id": f"G2B-SYNTH{i:04d}-000", "bid_no": f"SYNTH{i:04d}", "bid_order": "000",
           "source": "G2B_OFFICIAL_API", "notice_lifecycle": "CURRENT", "notice_kind": "일반공고",
           "end": (NOW + timedelta(days=30)).isoformat(),
           "department_status": "CANDIDATE", "department_categories": ["SW"],
           "document_status": "PENDING", "attachments": [], "document_evidence": [],
           "title": CANARY, "rfp_text": CANARY, "private_cost": CANARY}
    row.update(kw)
    return row


def workforce():
    return {"schema_version": 1, "annual_grade_rates_krw": {
        "junior": 30000000, "intermediate": 50000000, "senior": 70000000},
        "staff": [{"id": "A", "role": "developer", "grade": "junior", "lead": False,
                   "skills": ["PYTHON"], "skills_evidence": "ASSUMED",
                   "responsibility": "합성 담당 분야", "responsibility_evidence": "ASSUMED",
                   "available_mm": 1.0}]}


def operations():
    value = default_profile()
    value["roles"] = [{"role": CANARY, "available_mm": 1.0, "cost_per_mm_krw": 1000000}]
    for record in value["registers"].values():
        record.update(status="reviewed", source=CANARY, summary=CANARY, reviewed_on="2026-10-18")
    return value


def report(rows, profile=PROFILE, ops=None, staff=None, at=NOW):
    return evaluate(rows, profile, operations() if ops is None else ops,
                    workforce() if staff is None else staff, at=at)


class AggregateTests(unittest.TestCase):
    def test_canary_counts_and_inputs_unchanged(self):
        items = [notice(1), notice(2, department_categories=[], department_status="OUT_OF_SCOPE",
                                  expected_profit_krw=999999999999)]
        inputs = (items, PROFILE, operations(), workforce())
        before = copy.deepcopy(inputs)
        out = evaluate(*inputs, at=NOW)
        self.assertEqual(inputs, before)
        self.assertEqual(out["total_notices"], 2)
        self.assertEqual(out["active_notice_count"], 2)
        self.assertEqual(out["active_department_category_match_count"], 1)
        self.assertEqual(out["active_department_match_unknown_count"], 0)
        self.assertEqual(out["active_augmentation_review_count"], 1)
        self.assertEqual(sum(out["triage_status_counts"].values()), 2)
        encoded = json.dumps(out)
        for secret in (CANARY, items[0]["id"], "PYTHON", "999999999999", "30000000"):
            self.assertNotIn(secret, encoded)
        for field in ("legal_eligibility", "profitability", "augmentation_permitted"):
            self.assertEqual(out[field], "UNVERIFIED")
        self.assertEqual(out["status"], "BLOCKED_EVIDENCE")
        self.assertEqual(out["evidence_gap_codes"], ["NOTICE_SPECIFIC_COMPARISON_NOT_PERFORMED",
                                                     "SKILLS_EVIDENCE_UNVERIFIED"])

    def test_exact_time_buckets_and_timezone(self):
        hours = [-1, 0, 24, 24.0001, 72, 72.0001, 168, 168.0001]
        rows = [notice(i, end=(NOW+timedelta(hours=h)).isoformat()) for i, h in enumerate(hours)]
        rows += [notice(20, end="bad"), notice(21, end="2026-10-20")]
        out = report(rows)
        self.assertEqual(out["deadline_counts"], {"CLOSED": 2, "UNKNOWN": 2, "WITHIN_24H": 1,
                          "WITHIN_72H": 2, "WITHIN_7D": 2, "LATER": 1})
        self.assertEqual(out["active_notice_count"], 6)
        for offset in (timezone.utc, timezone(timedelta(hours=-7)), KST):
            out = report([notice(end=(NOW + timedelta(hours=24)).astimezone(offset).isoformat())])
            self.assertEqual(out["deadline_counts"]["WITHIN_24H"], 1)
        naive = report([notice(end="2026-10-20 12:00:00")])
        self.assertEqual(naive["deadline_counts"]["WITHIN_24H"], 1)
        self.assertEqual(report(rows, at=NOW.astimezone(timezone.utc)), report(rows))

    def test_lifecycle_deadline_stale_risks_overlap(self):
        rows = [notice(1, notice_lifecycle="CANCELLED", rfp_review_status="STALE"),
                notice(2, notice_kind="취소공고", notice_lifecycle="CANCELLED"),
                notice(3, rfp_review_status="STALE"),
                notice(4, end=NOW.isoformat()), notice(5, notice_lifecycle="REVIEW"),
                notice(6, end="0001-01-01T00:00:00+23:59")]
        out = report(rows)
        self.assertEqual(out["active_notice_count"], 0)
        self.assertEqual(out["held_notice_count"], 6)
        self.assertEqual(out["risk_counts"]["CANCELLED"], 2)
        self.assertEqual(out["risk_counts"]["STALE_DOCUMENT"], 2)
        self.assertEqual(out["risk_counts"]["DEADLINE_UNKNOWN"], 1)
        self.assertEqual(out["risk_counts"]["LEGAL_ELIGIBILITY_UNVERIFIED"], 6)

    def test_revision_comparison_does_not_promote_stored_holds(self):
        old = notice(1)
        fresh = notice(1, id="G2B-SYNTH0001-001", bid_order="001")
        out = report([old, fresh])
        self.assertEqual(out["active_notice_count"], 1)
        self.assertEqual(out["consistency_counts"]["LIFECYCLE_MISMATCH_ROWS"], 1)
        self.assertEqual(out["risk_counts"]["SUPERSEDED"], 1)
        self.assertEqual(report([notice(notice_lifecycle="SUPERSEDED")])["active_notice_count"], 0)

    def test_duplicates_numeric_alias_and_cancellation_are_held(self):
        a = notice()
        alias = notice(id="G2B-SYNTH0001-0", bid_order="0", notice_kind="취소공고")
        for rows in ([a, copy.deepcopy(a)], [a, alias]):
            out = report(rows)
            self.assertEqual(out["active_notice_count"], 0)
            self.assertEqual(out["consistency_counts"]["AMBIGUOUS_NUMERIC_REVISION_ROWS"], 2)
            self.assertEqual(sum(out["triage_status_counts"].values()), 2)
        self.assertEqual(report([a, alias])["risk_counts"]["CANCELLED"], 2)

    def test_registration_and_stored_window_consistency(self):
        rows = [notice(1, qualification_deadline=NOW.isoformat()),
                notice(2, qualification_deadline="bad"), notice(3),
                notice(4, qualification_deadline=(NOW+timedelta(days=40)).isoformat()),
                notice(5, window_status="CLOSED", legal_eligibility="VERIFIED")]
        out = report(rows)
        self.assertEqual(out["active_notice_count"], 4)
        self.assertEqual(out["active_registration_review_count"], 4)
        self.assertEqual(out["risk_counts"]["REGISTRATION_PASSED"], 1)
        self.assertEqual(out["consistency_counts"]["REGISTRATION_AFTER_CLOSE_ROWS"], 1)
        self.assertEqual(out["consistency_counts"]["STORED_WINDOW_MISMATCH_ROWS"], 1)
        self.assertEqual(out["risk_counts"]["STORED_ELIGIBILITY_CLAIM_IGNORED"], 1)

    def test_invalid_rows_and_category_fields_do_not_leak_or_crash(self):
        rows = [None, "bad", notice(1, id=CANARY), notice(2, source=CANARY),
                notice(3, bid_order=True), notice(4, department_categories=[{}])]
        out = report(rows)
        self.assertEqual(out["invalid_notice_count"], 5)
        self.assertEqual(out["active_notice_count"], 1)
        self.assertEqual(out["active_department_match_unknown_count"], 1)
        self.assertEqual(out["active_augmentation_review_count"], 0)
        self.assertEqual(out["consistency_counts"]["INVALID_DEPARTMENT_CLASSIFICATION_ROWS"], 1)
        self.assertEqual(sum(out["triage_status_counts"].values()), len(rows))
        self.assertNotIn(CANARY, json.dumps(out))

    def test_invalid_identity_still_reports_known_metadata_risks(self):
        out = report([notice(id=CANARY, notice_kind="취소공고", rfp_review_status="STALE",
                             end=NOW.isoformat()), notice(2, notice_kind=[],
                             document_status="EXTRACTED", document_evidence=[None])])
        self.assertEqual(out["invalid_notice_count"], 1)
        self.assertEqual(out["risk_counts"]["CANCELLED"], 1)
        self.assertEqual(out["risk_counts"]["STALE_DOCUMENT"], 1)
        self.assertEqual(out["deadline_counts"]["CLOSED"], 1)
        self.assertEqual(sum(out["triage_status_counts"].values()), 2)

    def test_missing_and_invalid_evidence_never_defaults_to_ready(self):
        for p in (None, {}, {**PROFILE, "categories": []}, {**PROFILE, "categories": [CANARY]}):
            out = evaluate([notice()], p, None, None, at=NOW)
            self.assertEqual(out["status"], "BLOCKED_EVIDENCE")
            self.assertEqual(out["department_match_status"], "BLOCKED_EVIDENCE")
            self.assertEqual(out["active_department_match_unknown_count"], 1)
            self.assertTrue(any(x.startswith("DEPARTMENT_PROFILE_") for x in out["evidence_gap_codes"]))
            self.assertIn("MM_EVIDENCE_MISSING_OR_INVALID", out["evidence_gap_codes"])
            self.assertIn("COST_EVIDENCE_MISSING_OR_INVALID", out["evidence_gap_codes"])
        for bad in (default_profile(), {**operations(), "cost_basis": "SALARY_ONLY"},
                    {**operations(), "roles": [{"role": CANARY, "available_mm": None,
                                                "cost_per_mm_krw": 0}]}):
            self.assertIn("COST_EVIDENCE_MISSING_OR_INVALID", report([notice()], ops=bad)["evidence_gap_codes"])
        future = operations()
        future["registers"]["finance"]["reviewed_on"] = "2099-01-01"
        self.assertIn("COST_EVIDENCE_MISSING_OR_INVALID", report([notice()], ops=future)["evidence_gap_codes"])
        forged = workforce()
        forged["staff"][0]["skills_evidence"] = "VERIFIED"
        self.assertIn("WORKFORCE_MISSING_OR_INVALID", report([notice()], staff=forged)["evidence_gap_codes"])

    def test_empty_limit_and_invalid_clock(self):
        self.assertEqual(report([])["active_notice_count"], 0)
        self.assertEqual(report([notice(i) for i in range(10000)])["total_notices"], 10000)
        for items in (None, {}, [None]*10001):
            with self.assertRaises(ValueError):
                report(items)
        with self.assertRaises(ValueError):
            report([], at=datetime(2026, 10, 19))


class LocalReadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.write("dashboard.json", {"schema_version": 1, "revision": 1, "notices": [notice()]})
        self.write("department_profile.json", PROFILE)
        self.write("operations.json", operations())
        self.write("workforce.json", workforce())
        self.write("rfp_batch.json", {"synthetic": CANARY})
        self.write("cases.json", {"untouched": CANARY})

    def write(self, name, data):
        (self.root/name).write_text(json.dumps(data), encoding="utf-8")

    def files(self):
        return {p.name: p.read_bytes() for p in self.root.iterdir()}

    def blocked(self, code="BLOCKED_INPUT"):
        with self.assertRaises(cli.AuditBlocked) as caught:
            cli.audit_local(self.root, at=NOW)
        self.assertEqual(str(caught.exception), code)

    def test_end_to_end_sources_and_directory_unchanged(self):
        before = self.files()
        out = cli.audit_local(self.root, at=NOW)
        self.assertEqual(out["snapshot_check"], "STABLE_OBSERVED_READS")
        self.assertEqual(out["active_notice_count"], 1)
        self.assertFalse(out["source_files_written"])
        self.assertEqual(self.files(), before)
        self.assertFalse((self.root/".dashboard-rfp.lock").exists())

    def test_optional_missing_corrupt_evidence_and_no_directory_creation(self):
        for name in ("department_profile.json", "operations.json", "workforce.json"):
            (self.root/name).unlink()
        out = cli.audit_local(self.root, at=NOW)
        self.assertEqual(out["status"], "BLOCKED_EVIDENCE")
        self.write("operations.json", [CANARY])
        (self.root/"department_profile.json").write_text("bad", encoding="utf-8")
        self.assertEqual(cli.audit_local(self.root, at=NOW)["status"], "BLOCKED_EVIDENCE")
        missing = self.root/"not_created"
        with self.assertRaises(cli.AuditBlocked):
            cli.audit_local(missing)
        self.assertFalse(missing.exists())

    def test_malformed_json_duplicate_keys_nonfinite_and_limits(self):
        for body in ('{"schema_version":1,"schema_version":1}', 'NaN', '{',
                     '{"schema_version":1,"revision":1,"notices":[],"ignored":1e999}',
                     '{"schema_version":true,"revision":1,"notices":[]}'):
            (self.root/"dashboard.json").write_text(body, encoding="utf-8")
            self.blocked()
        with patch.dict(cli.LIMITS, {"dashboard.json": 1}):
            self.blocked()
        (self.root/"dashboard.json").unlink()
        self.blocked()

    def test_concurrent_modification_discards_aggregate(self):
        real = cli.evaluate
        def changed(*args, **kwargs):
            self.write("department_profile.json", {**PROFILE, "revision": 2})
            return real(*args, **kwargs)
        with patch.object(cli, "evaluate", changed):
            self.blocked("BLOCKED_SNAPSHOT")

    def test_optional_file_appearing_during_evaluation_is_blocked(self):
        (self.root/"workforce.json").unlink()
        real = cli.evaluate
        def changed(*args, **kwargs):
            self.write("workforce.json", workforce())
            return real(*args, **kwargs)
        with patch.object(cli, "evaluate", changed):
            self.blocked("BLOCKED_SNAPSHOT")

    def expected(self):
        return {name: hashlib.sha256((self.root/name).read_bytes()).hexdigest()
                for name in ("dashboard.json", "rfp_batch.json")}

    def intent(self, phase, payload):
        db = sqlite3.connect(self.root/cli.INTENT)
        try:
            db.execute("CREATE TABLE release_state(key INTEGER PRIMARY KEY,phase TEXT,payload TEXT)")
            db.execute("INSERT INTO release_state VALUES(1,?,?)", (phase, json.dumps(payload)))
            db.commit()
        finally:
            db.close()

    def test_release_prepared_and_sidecar_block_without_writes(self):
        for name in cli.SIDECARS:
            (self.root/name).write_bytes(b"synthetic")
            before = self.files()
            self.blocked("BLOCKED_SNAPSHOT")
            self.assertEqual(self.files(), before)
            (self.root/name).unlink()
        self.write(cli.JOURNAL, {"status": "PREPARED"})
        self.blocked("BLOCKED_SNAPSHOT")
        (self.root/cli.JOURNAL).unlink()
        self.intent("PREPARED", {"status": "PREPARED"})
        before = self.files()
        self.blocked("BLOCKED_SNAPSHOT")
        self.assertEqual(self.files(), before)

    def test_completed_and_verified_generations_and_hash_mismatch(self):
        payload = {"status": "COMPLETED", "expected_new_files": self.expected()}
        self.write(cli.JOURNAL, payload)
        self.intent("COMPLETED", payload)
        before = self.files()
        self.assertEqual(cli.audit_local(self.root, at=NOW)["active_notice_count"], 1)
        self.assertEqual(self.files(), before)
        self.write("rfp_batch.json", {"changed": 1})
        self.blocked("BLOCKED_SNAPSHOT")
        (self.root/cli.INTENT).unlink()
        self.intent("VERIFIED", payload)
        before = self.files()
        self.assertEqual(cli.audit_local(self.root, at=NOW)["active_notice_count"], 1)
        self.assertEqual(self.files(), before)

    def test_legacy_completed_never_claims_generation_verification(self):
        payload = {"status": "COMPLETED", "expected_new_files": self.expected()}
        self.write(cli.JOURNAL, payload)
        for changed in (False, True):
            if changed:
                self.write("dashboard.json", {"schema_version": 1, "revision": 2, "notices": []})
            before = self.files()
            out = cli.audit_local(self.root, at=NOW)
            self.assertEqual(out["release_metadata_state"], "LEGACY_COMPLETED_UNVERIFIED")
            self.assertEqual(out["official_freshness"], "UNVERIFIED")
            self.assertEqual(out["status"], "BLOCKED_EVIDENCE")
            self.assertEqual(self.files(), before)

    def test_corrupt_unknown_conflicting_release_states(self):
        (self.root/cli.JOURNAL).write_text("null", encoding="utf-8")
        self.blocked("BLOCKED_SNAPSHOT")
        self.write(cli.JOURNAL, {"status": "UNKNOWN"})
        self.blocked("BLOCKED_SNAPSHOT")
        (self.root/cli.JOURNAL).unlink()
        (self.root/cli.INTENT).write_bytes(b"not sqlite")
        self.blocked("BLOCKED_SNAPSHOT")
        (self.root/cli.INTENT).unlink()
        payload = {"expected_new_files": self.expected()}
        self.intent("COMPLETED", payload)
        self.write(cli.JOURNAL, {"status": "COMPLETED", "expected_new_files": {}})
        self.blocked("BLOCKED_SNAPSHOT")

    def test_reparse_rejection_is_sanitized(self):
        with patch.object(cli, "reject_reparse", side_effect=ValueError(CANARY)):
            self.blocked()
        with patch.object(cli, "_capture", side_effect=PermissionError(CANARY)):
            self.blocked()

    def test_cli_success_and_failures_do_not_echo_arguments_or_paths(self):
        command = [sys.executable, "-B", str(Path(cli.__file__))]
        before = self.files()
        for args, exit_code in ((["--data-dir", str(self.root)], 0),
                                (["--data-dir", str(self.root/CANARY)], 2),
                                (["--unknown", CANARY], 2), (["--apply"], 2)):
            result = subprocess.run(command+args, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, exit_code)
            self.assertEqual(result.stderr, "")
            self.assertNotIn(CANARY, result.stdout)
            self.assertNotIn(str(self.root), result.stdout)
            json.loads(result.stdout)
        self.assertEqual(self.files(), before)
        stream = io.StringIO()
        with patch.object(cli, "audit_local", side_effect=cli.AuditBlocked("BLOCKED_SNAPSHOT")), patch("sys.stdout", stream):
            self.assertEqual(cli.main([]), 2)
        self.assertEqual(json.loads(stream.getvalue())["status"], "BLOCKED_SNAPSHOT")


if __name__ == "__main__":
    unittest.main()
