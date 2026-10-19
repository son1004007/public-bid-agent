"""P09 로컬 HTTP·Chrome 합성 인수 테스트 설계 계약.

목적/책임: 실제 Handler의 보안·오류·복구 차단 및 Chrome 테스트용 서버 제공.
입력/출력: 코드에서 만든 공고/TXT/JSON만 사용; HTTP 상태와 불변 바이트 검증.
신뢰 경계: 임시 폴더와 127.0.0.1 임의 포트만 소유. 실제 키·자료 조회/외부 호출 금지.
상태 변경: 임시 합성 이력만 저장; fixture 종료 시 서버 종료와 자료 보존 검사.
실패/시간 제한: HTTP 5초, Chrome용 서버 120초 제한, stdin EOF/종료로 정리.
불변조건: 보안 헤더/Host/Origin/CSRF와 복구 가드를 대체하지 않는다.
배치 격리: RFP_BATCH도 임시 root의 새 manager로 교체하고 외부 어댑터를 차단한다.
회귀 경계: 기존 manager/root는 메모리 차단자로 보호하며 RUNNING 조회의 잠금도 임시 경로만 사용한다.
관련: D-03/D-06/D-10/P09/BID-03, scripts/test_chrome_synthetic.cjs.
후보 검증: 선택적인 bid_now fixture는 세 큐 및 취소·마감·구차수 합성 자료만 추가한다.
"""
import base64
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import ExitStack, contextmanager
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import Mock, patch

import server
import dashboard_backend as db
import rfp_batch
from release_lease import save_intent
from test_rfp_original_compare import setup_fixture


RAW = "합성 문서: 입찰참가자격은 소프트웨어사업자 등록. 평가 배점 80점."
TITLE = 'P09 합성 SW 사업 <img src=x onerror="window.p09Injected=true">'


@contextmanager
def synthetic_server(*, bid_now=False):
    """사용자 데이터 경로를 인수로 받지 않는 일회성 테스트 경계."""
    with tempfile.TemporaryDirectory(prefix="p09-synthetic-") as folder, ExitStack() as stack:
        root = Path(folder)
        stack.enter_context(patch.multiple(server, ROOT=root, FILE=root / "cases.json",
                                          WORKFORCE_DETAILS_ENABLED=False))
        stack.enter_context(patch.object(server, "key_available", return_value=False))
        stack.enter_context(patch.object(server, "procurement_key_status", return_value={
            "configured": False, "can_save": False, "source": "SYNTHETIC_DISABLED"}))
        # No real credential, supplier or model function may be reached by this harness.
        for name in ("procurement_key", "save_procurement_key", "delete_procurement_key",
                     "verify_key", "fetch_official_notices", "fetch_related_constraints",
                     "extract_official_document", "call_cli"):
            stack.enter_context(patch.object(server, name, side_effect=AssertionError(
                "External adapter forbidden in synthetic acceptance")))
        # ROOT patches do not rebind the manager's captured root or adapters.
        # Pass every external adapter explicitly, including the default fetcher.
        disabled_adapter = Mock(side_effect=AssertionError(
            "Batch external adapter forbidden in synthetic acceptance"))
        batch = server.RfpBatchManager(
            root, server.LOCK, server.persist, disabled_adapter,
            related=disabled_adapter, key_getter=disabled_adapter, fetcher=disabled_adapter)
        stack.enter_context(patch.object(server, "RFP_BATCH", batch))
        server.persist({"schema_version": 1, "cases": []})
        raw = RAW.encode("utf-8")
        att, proof, _ = setup_fixture(root, "p09-synthetic.txt", raw)
        notice = db.normalize({"bidNtceNo": "P09SYNTHETIC", "bidNtceOrd": "001",
            "bidNtceNm": TITLE, "ntceInsttNm": "합성 시험기관", "asignBdgtAmt": "100000000",
            "bidClseDt": "2099-12-31 10:00:00", "bidNtceDtlUrl": "https://www.g2b.go.kr/"})
        notice.update(attachments=[att], document_evidence=[proof], document_status="EXTRACTED",
                      rfp_text=RAW, final="bid", finalReason="합성 담당자 결정", rec="hold")
        proof.update(notice_id=notice["id"], notice_bid_no=notice["bid_no"],
                     notice_bid_order=notice["bid_order"])
        board = db.update_collection(db.blank(), [notice], 1, "2026-10-18T00:00:00+00:00")
        if bid_now:
            # 모든 데이터는 여기서 생성한다. 실제 부서/인력·원가/공고를 읽지 않는다.
            board["notices"][0].update(department_status="CANDIDATE", department_categories=["SW"],
                                       qualification_deadline="2099-12-30T10:00:00+09:00")
            for suffix, changes in (
                ("GAP", {"department_status":"OUT_OF_SCOPE", "department_categories":[]}),
                ("REG", {"qualification_deadline":"2000-01-01T00:00:00+09:00"}),
                ("CANCEL", {"notice_lifecycle":"CANCELLED", "notice_kind":"취소공고"}),
                ("OLD", {"notice_lifecycle":"SUPERSEDED"}),
                ("CLOSED", {"end":"2000-01-01T00:00:00+09:00"}),
            ):
                extra=db.normalize({"bidNtceNo":"BID03SYNTH"+suffix,"bidNtceOrd":"001",
                    "bidNtceNm":"BID03 합성 "+suffix,"ntceInsttNm":"합성 시험기관",
                    "bidClseDt":"2099-12-31 10:00:00"})
                extra.update(notice_lifecycle="CURRENT",department_status="CANDIDATE",
                             department_categories=["SW"],
                             qualification_deadline="2099-12-30T10:00:00+09:00")
                extra.update(changes)
                board["notices"].append(extra)
            server.persist({"schema_version":1,"revision":0,"categories":["SW"],
                            "include_review":False},root / "department_profile.json")
        server.persist(board, root / "dashboard.json")
        upload = root / "p09-synthetic.txt"
        upload.write_bytes(raw)
        mismatch = root / "p09-mismatch.txt"
        mismatch.write_text("synthetic mismatched original", encoding="utf-8")
        preserved = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()
                     and p.name != "dashboard.json"}

        class SyntheticHandler(server.Handler):
            def do_POST(self):
                if self.path not in ("/api/dashboard/outcome", "/api/dashboard/rfp-original-compare"):
                    self.close_connection = True
                    return self.respond({"error": "Synthetic harness route disabled"}, 403)
                return super().do_POST()

        http = ThreadingHTTPServer(("127.0.0.1", 0), SyntheticHandler)
        http.daemon_threads = True
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        try:
            yield {"root": root, "http": http, "base": f"http://127.0.0.1:{http.server_port}",
                   "notice": notice, "board": board, "identity": proof["identity"],
                   "upload": upload, "mismatch": mismatch}
        finally:
            http.shutdown()
            http.server_close()
            thread.join(5)
            if thread.is_alive():
                raise AssertionError("Synthetic server failed to stop")
            for path, content in preserved.items():
                if path.read_bytes() != content:
                    raise AssertionError("Synthetic source/cache unexpectedly changed")


class LocalAcceptanceTests(unittest.TestCase):
    def setUp(self):
        # Guard the captured manager before entering the fixture. Even a broken
        # fixture must fail without probing any operational path or worker lock.
        self.original_manager = server.RFP_BATCH
        forbidden_root = Mock(spec=Path)
        forbidden_root.__truediv__ = Mock(side_effect=AssertionError(
            "Original batch root forbidden in synthetic acceptance"))
        guards = ExitStack()
        self.addCleanup(guards.close)
        guards.enter_context(patch.object(self.original_manager, "root", forbidden_root))
        self.original_status = guards.enter_context(patch.object(
            self.original_manager, "status", side_effect=AssertionError(
                "Original batch manager forbidden in synthetic acceptance")))
        scope = synthetic_server()
        self.fixture = scope.__enter__()
        self.addCleanup(scope.__exit__, None, None, None)
        self.root = self.fixture["root"]
        self.base = self.fixture["base"]
        self.before = (self.root / "dashboard.json").read_bytes()

    def request(self, path, body=None, overrides=None, method=None):
        headers = {"Origin": self.base, "X-Local-CSRF": server.TOKEN,
                   "Content-Type": "application/json"}
        for key, value in (overrides or {}).items():
            if value is None:
                headers.pop(key, None)
            else:
                headers[key] = value
        connection = HTTPConnection("127.0.0.1", self.fixture["http"].server_port, timeout=5)
        try:
            encoded = json.dumps(body).encode() if isinstance(body, dict) else body
            connection.request(method or ("POST" if body is not None else "GET"), path,
                               body=encoded, headers=headers)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def assert_headers(self, headers):
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertEqual(headers["Referrer-Policy"], "no-referrer")
        self.assertIn("script-src 'self'", headers["Content-Security-Policy"])
        self.assertIn("connect-src 'self'", headers["Content-Security-Policy"])
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def assert_unchanged(self):
        self.assertEqual((self.root / "dashboard.json").read_bytes(), self.before)

    def payload(self):
        return {"id": self.fixture["notice"]["id"], "expected_revision": 1,
                "stage": "SUBMITTED", "observed_on": "2026-10-18",
                "evidence_reference": "합성 수기 자료", "evaluation_score": None}

    def test_get_assets_and_api_keep_security_headers(self):
        for path in ("/decision-preview", "/dashboard-live.js", "/api/dashboard"):
            with self.subTest(path=path):
                status, headers, _ = self.request(path)
                self.assertEqual(status, 200)
                self.assert_headers(headers)
        self.assert_unchanged()

    def test_get_rfp_batch_uses_temporary_manager(self):
        status, headers, body = self.request("/api/rfp-batch")
        self.assertEqual(status, 200)
        self.assert_headers(headers)
        self.assertEqual(json.loads(body)["batch"]["status"], "IDLE")
        self.assertIsNot(server.RFP_BATCH, self.original_manager)
        self.assertEqual(server.RFP_BATCH.root, self.root)
        self.original_status.assert_not_called()
        self.assert_unchanged()

    def test_rfp_batch_external_adapters_are_disabled(self):
        for name in ("extractor", "related", "key_getter", "fetcher"):
            with self.subTest(adapter=name):
                adapter = getattr(server.RFP_BATCH, name)
                self.assertIsInstance(adapter, Mock, "Never invoke a real adapter to test isolation")
                with self.assertRaisesRegex(AssertionError, "Batch external adapter forbidden"):
                    adapter()

    def test_get_running_rfp_batch_reads_and_locks_only_temporary_root(self):
        batch_path = self.root / "rfp_batch.json"
        state = {"schema_version": 1, "revision": 7, "status": "RUNNING",
                 "target_ids": ["synthetic-pending"], "items": {}, "updated_at": None}
        server.persist(state, batch_path)
        before = batch_path.read_bytes()
        real_transaction = rfp_batch.dashboard_transaction

        def temporary_transaction(root, *args, **kwargs):
            self.assertEqual(root, self.root, "Batch lock escaped the temporary root")
            return real_transaction(root, *args, **kwargs)

        with patch.object(rfp_batch, "dashboard_transaction",
                          side_effect=temporary_transaction) as transaction:
            # A stale RUNNING ledger probes the real worker lock and reports PAUSED.
            # Holding that same synthetic lease exercises the live RUNNING branch.
            for active in (False, True):
                with self.subTest(active_worker_lease=active), ExitStack() as lease:
                    if active:
                        lease.enter_context(real_transaction(
                            self.root, name=".rfp-batch-worker.lock"))
                    status, headers, body = self.request("/api/rfp-batch")
                    self.assertEqual(status, 200)
                    self.assert_headers(headers)
                    batch = json.loads(body)["batch"]
                    self.assertEqual(batch["status"], "RUNNING" if active else "PAUSED")
                    self.assertEqual(batch["revision"], 7)
                    self.assertEqual(batch["statistics"]["pending"], 1)
            self.assertEqual(transaction.call_count, 2)
            transaction.assert_called_with(self.root, timeout=0, name=".rfp-batch-worker.lock")
        self.assertTrue((self.root / ".rfp-batch-worker.lock").is_file())
        self.assertEqual(batch_path.read_bytes(), before)
        self.original_status.assert_not_called()
        self.assert_unchanged()

    def test_host_origin_csrf_rejections_preserve_data(self):
        cases = ({"Host": "localhost:8765"}, {"Host": "attacker.invalid"},
                 {"Origin": None}, {"Origin": "null"}, {"Origin": "https://attacker.invalid"},
                 {"X-Local-CSRF": None}, {"X-Local-CSRF": "synthetic-wrong-token"})
        for headers in cases:
            with self.subTest(headers=headers):
                status, response_headers, body = self.request("/api/dashboard/outcome", self.payload(), headers)
                self.assertEqual(status, 403)
                self.assert_headers(response_headers)
                self.assertNotIn(server.TOKEN.encode(), body)
                self.assert_unchanged()
        self.assertEqual(self.request("/api/dashboard", overrides={"Host": "attacker.invalid"})[0], 403)

    def test_invalid_json_and_media_type_do_not_write(self):
        for body, headers in ((b"{", {}), (b"[]", {}), (b"null", {}),
                              (b"{}", {"Content-Type": "text/plain"})):
            with self.subTest(body=body, headers=headers):
                status, response_headers, data = self.request("/api/dashboard/outcome", body, headers)
                self.assertEqual(status, 400)
                self.assert_headers(response_headers)
                self.assertNotIn(str(self.root).encode(), data)
                self.assertNotIn(b"Traceback", data)
                self.assert_unchanged()

    def test_recovery_intent_blocks_get_and_post_without_leaking_payload(self):
        save_intent(self.root, "PREPARED", {"synthetic_private_marker": "P09-DO-NOT-EXPOSE"})
        for path, body in (("/api/dashboard", None), ("/decision-preview", None),
                           ("/api/dashboard/outcome", self.payload())):
            with self.subTest(path=path):
                status, headers, data = self.request(path, body)
                self.assertEqual(status, 503)
                self.assert_headers(headers)
                self.assertNotIn(b"P09-DO-NOT-EXPOSE", data)
                self.assertNotIn(str(self.root).encode(), data)
                self.assert_unchanged()

    def test_corrupt_recovery_intent_fails_closed(self):
        (self.root / ".rfp-release-intent.sqlite3").write_bytes(b"synthetic corrupt database")
        self.assertEqual(self.request("/api/dashboard")[0], 503)
        self.assertEqual(self.request("/api/dashboard/outcome", self.payload())[0], 503)
        self.assert_unchanged()

    def test_manual_save_duplicate_conflict_and_reload(self):
        payload = self.payload()
        self.assertEqual(self.request("/api/dashboard/outcome", payload)[0], 200)
        saved = (self.root / "dashboard.json").read_bytes()
        self.assertEqual(self.request("/api/dashboard/outcome", payload)[0], 409)
        self.assertEqual((self.root / "dashboard.json").read_bytes(), saved)
        status, _, body = self.request("/api/dashboard")
        self.assertEqual(status, 200)
        board = json.loads(body)["dashboard"]
        self.assertEqual(board["revision"], 2)
        self.assertEqual(board["history"], self.fixture["board"]["history"])
        notice = board["notices"][0]
        self.assertEqual(notice["final"], "bid")
        self.assertEqual(len(notice["submission_events"]), 1)
        self.assertEqual(notice["submission_events"][0]["source"], "HUMAN_DECLARED_UNVERIFIED")

    def test_mismatched_file_is_memory_only_and_preserves_cache(self):
        payload = {"id": self.fixture["notice"]["id"], "identity": self.fixture["identity"],
                   "base64": base64.b64encode(b"synthetic incorrect original").decode()}
        status, headers, body = self.request("/api/dashboard/rfp-original-compare", payload)
        self.assertEqual(status, 200)
        self.assert_headers(headers)
        data = json.loads(body)
        self.assertEqual(data["comparison"]["status"], "ORIGINAL_SHA_MISMATCH")
        self.assertFalse(data["original_file_retained"])
        self.assertNotIn(b"synthetic incorrect original", body)
        self.assert_unchanged()

    def test_parser_stdout_survives_non_utf8_windows_locale(self):
        # Windows CI can default to cp1252 even when the source is UTF-8.
        # The child process must emit ASCII-safe JSON without dropping Korean text.
        environment = dict(os.environ, PYTHONIOENCODING="cp1252")
        completed = subprocess.run(
            [sys.executable, str(server.EXTRACTOR), "p09-synthetic.txt"],
            input=RAW.encode("utf-8"), capture_output=True, timeout=12,
            env=environment, check=False)
        self.assertEqual(completed.returncode, 0, "Extractor must not depend on console encoding")
        result = json.loads(completed.stdout.decode("utf-8"))
        self.assertTrue(result["ok"])
        self.assertEqual(result["text"], RAW)
        self.assert_unchanged()

    def test_matching_file_uses_real_limited_parser_without_retaining_original(self):
        payload = {"id": self.fixture["notice"]["id"], "identity": self.fixture["identity"],
                   "base64": base64.b64encode(RAW.encode()).decode()}
        status, _, body = self.request("/api/dashboard/rfp-original-compare", payload)
        self.assertEqual(status, 200)
        result = json.loads(body)
        self.assertEqual(result["comparison"]["status"], "REPRODUCED_TEXT")
        self.assertEqual(result["storage"], "LOCAL_MEMORY_ONLY")
        self.assertFalse(result["original_file_retained"])
        self.assertNotIn(RAW, body.decode())
        self.assert_unchanged()


def serve_chrome():
    with synthetic_server(bid_now=True) as fixture:
        print(json.dumps({k: str(fixture[k]) for k in ("base", "upload", "mismatch")}), flush=True)
        # stdin is owned by the Node runner; EOF is also a clean shutdown request.
        stop = threading.Event()
        threading.Thread(target=lambda: (sys.stdin.readline(), stop.set()), daemon=True).start()
        if not stop.wait(120):
            raise TimeoutError("Synthetic browser test exceeded 120 seconds")
    print("SYNTHETIC_CLEANUP_PASS", flush=True)


if __name__ == "__main__":
    if sys.argv[1:] == ["--serve-chrome"]:
        serve_chrome()
    else:
        unittest.main()
