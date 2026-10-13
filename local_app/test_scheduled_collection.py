"""예약 수집의 충돌·부분 실패·공식 정정/사람 판단 보존 합성 검증.

실제 API와 DPAPI 키 및 사용자 PC 원본은 이용하지 않는다.
"""
import contextlib
import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import dashboard_backend as backend
from scheduled_collection import sync_once, fetch_window, safe_mark_failed, atomic_write, main, CollectionFailed
from procurement_filter import KST

NOW = datetime(2026, 10, 13, 9, 0, tzinfo=KST)
RAW = {
    "bidNtceNo": "202610130001", "bidNtceOrd": "00",
    "bidNtceNm": "공식 AI 사업 구축",
    "ntceInsttNm": "가상 기관",
    "asignBdgtAmt": "120000000",
    "bidClseDt": "2026-10-31 18:00:00",
    "bidNtceDtlUrl": "https://www.g2b.go.kr/",
}


class CollectionScheduleTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.path = self.root / "dashboard.json"
        notice = backend.normalize(RAW)
        notice["final"] = "no_bid"
        notice["finalReason"] = "가상 담당자의 불참 결정"
        notice["rfp_text"] = "과거 추출 원문 변경 금지"
        notice["document_evidence"] = [{"status": "EXTRACTED", "id": "prior"}]
        base = backend.blank()
        base["notices"] = [notice]
        base["history"] = [{"id": "human-judgment", "kind": "human_no_bid"}]
        base["revision"] = 12
        atomic_write(self.path, base)

    def result(self):
        return json.loads(self.path.read_text(encoding="utf-8"))

    def test_daily_seven_day_overlap_and_latest_official_correction(self):
        times = []
        def collector(_key, clock):
            times.append(clock)
            name = clock.strftime("%Y-%m-%d")
            item = backend.normalize({**RAW, "bidNtceNm": "정정 공식 공고 " + name})
            return [item], 1
        before = self.result()
        output = sync_once(self.root, collector=collector, days=7,
                           key_provider=lambda: "synthetic-key", clock=NOW, apply=True)
        result = self.result()
        self.assertEqual(len(times), 7)
        self.assertEqual((times[0] - times[-1]).days, -6)
        self.assertEqual(output["scanned"], 7)
        self.assertEqual(output["unique"], 1)
        self.assertEqual(result["notices"][0]["title"], "정정 공식 공고 2026-10-13")
        for key in ("final", "finalReason", "rfp_text", "document_evidence"):
            self.assertEqual(result["notices"][0][key], before["notices"][0][key])
        self.assertEqual(result["history"], before["history"])
        self.assertEqual(result["revision"], 13)
        self.assertEqual(result["collection"]["mode"], "SCHEDULED_INCREMENTAL")
        self.assertEqual(result["collection"]["lookback_days"], 7)

    def test_scheduled_dry_run_keeps_entire_json_hash(self):
        original = self.path.read_bytes()
        out = sync_once(self.root, apply=False, days=1,
                        key_provider=lambda: "synthetic-key", clock=NOW,
                        collector=lambda key, clock: ([backend.normalize(RAW)], 1))
        self.assertEqual(out["status"], "DRY_RUN")
        self.assertEqual(self.path.read_bytes(), original)

    def test_partially_failed_day_preserves_every_notice_and_history(self):
        before = self.path.read_bytes()
        calls = [0]
        def collector(key, clock):
            calls[0] += 1
            if calls[0] >= 5:
                raise backend.ProviderError("synthetic network error")
            return [backend.normalize(RAW)], 1
        with self.assertRaises(backend.ProviderError):
            sync_once(self.root, apply=True, collector=collector,
                      key_provider=lambda: "synthetic-key", clock=NOW)
        self.assertEqual(self.path.read_bytes(), before)
        safe_mark_failed(self.root)
        after = self.result()
        old = json.loads(before)
        self.assertEqual(after["notices"], old["notices"])
        self.assertEqual(after["history"], old["history"])
        self.assertEqual(after["collection"]["status"], "ERROR")

    def test_rebase_on_latest_state_after_network_returns(self):
        def collector(key, clock):
            updated = self.result()
            updated["revision"] += 1
            updated["notices"][0]["finalReason"] = "수집 실행 중 추가한 사람 결정"
            atomic_write(self.path, updated)
            return [backend.normalize(RAW)], 1
        sync_once(self.root, days=1, apply=True, clock=NOW,
                  collector=collector, key_provider=lambda: "synthetic-key")
        self.assertEqual(self.result()["notices"][0]["finalReason"],
                         "수집 실행 중 추가한 사람 결정")
        self.assertEqual(self.result()["revision"], 14)

    def test_incomplete_journal_fails_before_calling_collector(self):
        original = self.path.read_bytes()
        (self.root / ".rfp-release-transaction.json").write_text(
            json.dumps({"status": "PREPARED"}), encoding="utf-8")
        def should_not_fetch(*args, **kwargs):
            self.fail("API must not be contacted during failed release")
        with self.assertRaises(CollectionFailed):
            sync_once(self.root, apply=True, collector=should_not_fetch,
                      key_provider=lambda: "synthetic-key")
        self.assertEqual(self.path.read_bytes(), original)

    def test_second_collect_can_add_new_notice_without_deleting_old(self):
        new = backend.normalize({**RAW, "bidNtceNo": "202610130002",
                                 "bidNtceNm": "두번째 신규 정정"})
        sync_once(self.root, days=1, apply=True,
                  collector=lambda key, clock: ([new], 1),
                  key_provider=lambda: "synthetic-key", clock=NOW)
        self.assertEqual(len(self.result()["notices"]), 2)
        self.assertEqual(self.result()["notices"][0]["final"], "no_bid")

    def test_duplicate_newest_wins_and_inconsistent_response_fails(self):
        def collector(key, clock):
            n = backend.normalize({**RAW, "bidNtceNm": str(clock.day)})
            return [n], 1
        rows, scanned, at = fetch_window("synthetic", days=7, at=NOW, collector=collector)
        self.assertEqual(scanned, 7)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "13")
        with self.assertRaises(CollectionFailed):
            fetch_window("synthetic", days=1, at=NOW,
                         collector=lambda key, clock: ([backend.normalize(RAW)], 0))


    def test_transient_provider_failure_retries_same_day_once(self):
        calls = [0]
        def collector(key, clock):
            calls[0] += 1
            if calls[0] == 1:
                raise backend.ProviderError("temporary unavailable")
            return [backend.normalize(RAW)], 1
        with patch("scheduled_collection.time.sleep", return_value=None):
            report = sync_once(self.root, days=1, apply=True,
                               collector=collector, key_provider=lambda: "synthetic-key",
                               clock=NOW)
        self.assertEqual(report["unique"], 1)
        self.assertEqual(calls[0], 2)

    def test_completed_sqlite_generation_mismatch_blocks_api_and_writes(self):
        from release_lease import save_intent
        original = self.path.read_bytes()
        save_intent(self.root, "COMPLETED", {
            "expected_new_files": {
                "dashboard.json": "0" * 64,
                "rfp_batch.json": "0" * 64,
            }
        })
        with self.assertRaises(RuntimeError):
            sync_once(self.root, days=1, apply=True,
                      collector=lambda *args, **kwargs: self.fail("API must not be called"),
                      key_provider=lambda: "synthetic-key", clock=NOW)
        self.assertEqual(self.path.read_bytes(), original)

    def test_credential_failure_records_error_without_data_loss(self):
        from procurement_credentials import CredentialError
        original = self.result()
        output = io.StringIO()
        with patch("scheduled_collection.active_key",
                   side_effect=CredentialError("synthetic")), contextlib.redirect_stderr(output):
            code = main(["--data-dir", str(self.root), "--days", "1", "--apply"])
        self.assertEqual(code, 1)
        self.assertIn('"failure_state_saved": true', output.getvalue())
        current = self.result()
        self.assertEqual(current["collection"]["status"], "ERROR")
        self.assertEqual(current["history"], original["history"])
        self.assertEqual(current["notices"], original["notices"])

    def test_cli_error_does_not_echo_synthetic_secret(self):
        secret = "DO-NOT-PRINT-THIS-SECRET"
        output = io.StringIO()
        with patch("scheduled_collection.active_key", return_value=secret), patch(
                "scheduled_collection.collect_day",
                side_effect=backend.ProviderError("raw upstream URL " + secret)), contextlib.redirect_stderr(output):
            # collector default argument is bound before monkeypatch, so inject the
            # provider via a wrapper replacement of sync_once for this CLI contract.
            with patch("scheduled_collection.sync_once",
                       side_effect=backend.ProviderError("URL?ServiceKey=" + secret)):
                code = main(["--data-dir", str(self.root), "--days", "1", "--apply"])
        self.assertEqual(code, 1)
        self.assertNotIn(secret, output.getvalue())
        self.assertEqual(self.result()["collection"]["status"], "ERROR")


if __name__ == "__main__":
    unittest.main()
