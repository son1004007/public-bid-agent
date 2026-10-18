"""수기 입찰 이력의 합성 저장·복구 계약 테스트.

목적/책임: HTTP 재조회/재시도, 실제 프로세스 revision 경합, 원자 저장 실패를 검증.
입력/출력: 합성 공고·자료 설명·점수만 사용하고 저장 JSON/응답/충돌을 대조.
신뢰 경계: 임시 디렉터리와 임의 포트 127.0.0.1만 사용; 실제 자료/외부 API/AI 접근 없음.
상태 변경: 테스트 소유 임시 JSON·잠금·동기화 파일만 생성하고 종료 시 정리.
실패/재시도: 저장 전 실패는 기존 바이트 보존, 같은 revision 재시도는 한 번만 기록.
핵심 불변조건: 과거 수기 사건·사람 결정·추천·다른 JSON 보존, 공식 확인으로 승격 금지.
관련: D-03/D-06/D-07, P08, bid_outcomes.py, json_transaction.py, server.persist.
"""
import copy
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import server
from bid_outcomes import record
from dashboard_backend import read as read_dashboard, update_collection, normalize
from json_transaction import transaction
from test_bid_outcomes import data


STAMP = "2026-10-18T00:00:00+00:00"
HERE = Path(__file__).resolve().parent
WORKER = r'''
import json, os, sys, time
from pathlib import Path
root = Path(sys.argv[1])
os.environ["PUBLIC_BID_LOCAL_DATA"] = str(root)
sys.path.insert(0, sys.argv[2])
import server
from bid_outcomes import record, OutcomeConflict
from dashboard_backend import read
from json_transaction import transaction
tag = sys.argv[3]
payload = json.loads((root / (tag + ".request.json")).read_text(encoding="utf-8"))
(root / (tag + ".ready")).write_text("ready", encoding="utf-8")
deadline = time.monotonic() + 10
while not (root / "go").exists():
    if time.monotonic() >= deadline:
        raise TimeoutError("synthetic start barrier")
    time.sleep(.01)
with transaction(root, timeout=5):
    state = read(root / "dashboard.json")
    try:
        updated = record(state, payload, "2026-10-18T00:00:00+00:00")
    except OutcomeConflict:
        print("CONFLICT")
    else:
        server.persist(updated, root / "dashboard.json")
        print("SAVED")
'''


class OutcomeRecoveryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="p08-synthetic-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / "dashboard.json"
        self.state, self.ident = data()
        self.original = copy.deepcopy(self.state)
        self.source.write_text(json.dumps(self.state, ensure_ascii=False), encoding="utf-8")
        self.sentinels = {}
        for name in ("cases.json", "operations.json", "decision_profiles.json", "rfp_batch.json"):
            content = b'{"synthetic_sentinel":"P08 must preserve these bytes"}\n'
            (self.root / name).write_bytes(content)
            self.sentinels[name] = content
        patches = patch.multiple(server, ROOT=self.root, FILE=self.root / "cases.json")
        patches.start()
        self.addCleanup(patches.stop)
        # GET /api/dashboard must not inspect a real credential configuration.
        key_patch = patch.object(server, "key_available", return_value=False)
        key_patch.start()
        self.addCleanup(key_patch.stop)

    def payload(self, stage="SUBMITTED", score=None):
        return {"id": self.ident, "expected_revision": self.state["revision"],
                "stage": stage, "observed_on": "2026-10-18",
                "evidence_reference": "합성 담당자 확인 기록", "evaluation_score": score}

    def assert_preserved(self, board):
        self.assertEqual(board["history"], self.original["history"])
        for field in ("final", "finalReason", "rec"):
            self.assertEqual(board["notices"][0][field], self.original["notices"][0][field])
        for name, content in self.sentinels.items():
            self.assertEqual((self.root / name).read_bytes(), content)

    @contextmanager
    def http(self):
        http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{http.server_port}"
        finally:
            http.shutdown()
            http.server_close()
            thread.join(5)
            self.assertFalse(thread.is_alive())

    def request(self, base, payload=None):
        url = base + ("/api/dashboard" if payload is None else "/api/dashboard/outcome")
        headers = {"Content-Type": "application/json", "Origin": base, "X-Local-CSRF": server.TOKEN}
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        req = Request(url, data=body, headers=headers)
        try:
            with urlopen(req, timeout=5) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            with error:
                return error.code, json.load(error)

    def test_all_terminal_histories_survive_http_restart_and_reject_rewrite(self):
        for terminal in ("AWARDED", "NOT_AWARDED", "WITHDRAWN"):
            with self.subTest(terminal=terminal):
                self.state = copy.deepcopy(self.original)
                server.persist(self.state, self.source)
                expected_events = []
                for stage, score in (("SUBMITTED", None), ("EVALUATED", 82.5),
                                     (terminal, None if terminal == "WITHDRAWN" else 85.25)):
                    # A fresh HTTP server reads the persisted history at every stage.
                    with self.http() as base:
                        status, before = self.request(base)
                        self.assertEqual(status, 200)
                        self.assertEqual(before["dashboard"], self.state)
                        payload = self.payload(stage, score)
                        with patch.object(server, "now", return_value=STAMP):
                            status, response = self.request(base, payload)
                        self.assertEqual(status, 200)
                        expected_events.append({"stage": stage, "observed_on": "2026-10-18",
                            "evidence_reference": "합성 담당자 확인 기록", "evaluation_score": score,
                            "recorded_at": STAMP, "source": "HUMAN_DECLARED_UNVERIFIED"})
                        self.assertEqual(response["source"], "HUMAN_DECLARED_UNVERIFIED")
                        self.assertEqual(response["dashboard"]["revision"], self.state["revision"] + 1)
                        self.state = response["dashboard"]
                        self.assertEqual(self.state["notices"][0]["submission_events"], expected_events)
                        self.assertEqual(read_dashboard(self.source), self.state)
                        self.assert_preserved(self.state)
                        committed = self.source.read_bytes()
                        self.assertEqual(self.request(base, payload)[0], 409)
                        self.assertEqual(self.source.read_bytes(), committed)
                with self.http() as base:
                    self.assertEqual(self.request(base)[1]["dashboard"], self.state)
                    committed = self.source.read_bytes()
                    # Existing contract has no overwrite/correction transition for terminal history.
                    self.assertEqual(self.request(base, self.payload("NOT_AWARDED", 0))[0], 409)
                    self.assertEqual(self.source.read_bytes(), committed)

    def test_atomic_write_failures_preserve_bytes_and_retry_exactly_once(self):
        def partial_dump(value, stream, **kwargs):
            stream.write('{"partial":')
            raise OSError("synthetic private path must not appear in HTTP error")

        failures = (("json.dump", partial_dump),
                    ("os.fsync", OSError("synthetic disk flush failure")),
                    ("os.replace", OSError("synthetic file replacement failure")))
        with self.http() as base:
            for boundary, failure in failures:
                with self.subTest(boundary=boundary):
                    self.state = copy.deepcopy(self.original)
                    server.persist(self.state, self.source)
                    original_bytes = self.source.read_bytes()
                    payload = self.payload()
                    with patch("server." + boundary, side_effect=failure):
                        status, response = self.request(base, payload)
                    self.assertEqual(status, 500)
                    self.assertEqual(set(response), {"error"})
                    self.assertNotIn("synthetic", response["error"])
                    self.assertEqual(self.source.read_bytes(), original_bytes)
                    self.assertEqual(list(self.root.glob(".pending-*.json")), [])
                    self.assert_preserved(read_dashboard(self.source))
                    # The failed transaction must release its lock and consume no revision.
                    self.assertEqual(self.request(base, payload)[0], 200)
                    saved = self.source.read_bytes()
                    self.assertEqual(self.request(base, payload)[0], 409)
                    self.assertEqual(self.source.read_bytes(), saved)
                    restored = read_dashboard(self.source)
                    self.assertEqual(restored["revision"], 1)
                    self.assertEqual(len(restored["notices"][0]["submission_events"]), 1)
                    self.assert_preserved(restored)

    def test_atomic_replace_exposes_only_complete_generations(self):
        old_bytes = self.source.read_bytes()
        updated = record(self.state, self.payload(), STAMP)
        actual_replace = os.replace

        def inspect_replace(staged, destination):
            self.assertEqual(Path(staged).parent, self.root)
            self.assertEqual(Path(destination), self.source)
            self.assertEqual(self.source.read_bytes(), old_bytes)
            self.assertEqual(json.loads(Path(staged).read_text(encoding="utf-8")), updated)
            actual_replace(staged, destination)
            self.assertEqual(read_dashboard(self.source), updated)

        with transaction(self.root), patch.object(server.os, "replace", side_effect=inspect_replace) as replace:
            server.persist(updated, self.source)
        replace.assert_called_once()
        self.assertEqual(list(self.root.glob(".pending-*.json")), [])
        self.assert_preserved(read_dashboard(self.source))

    def test_corrupt_dashboard_refuses_read_and_write_without_erasing_bytes(self):
        for content in (b'{"broken":', b'[]',
                        json.dumps({**self.state, "revision": True}).encode()):
            with self.subTest(content=content), self.http() as base:
                self.source.write_bytes(content)
                self.assertEqual(self.request(base)[0], 503)
                self.assertEqual(self.request(base, self.payload())[0], 503)
                self.assertEqual(self.source.read_bytes(), content)
                self.assertEqual(list(self.root.glob(".pending-*.json")), [])

    def test_two_processes_with_same_revision_commit_one_terminal_event(self):
        self.state = record(self.state, self.payload(), STAMP)
        self.state = record(self.state, self.payload("EVALUATED", 82.5), STAMP)
        server.persist(self.state, self.source)
        children = []
        for stage in ("AWARDED", "NOT_AWARDED"):
            request = self.root / (stage + ".request.json")
            request.write_text(json.dumps(self.payload(stage, 85.25)), encoding="utf-8")
        try:
            for stage in ("AWARDED", "NOT_AWARDED"):
                children.append(subprocess.Popen(
                    [sys.executable, "-c", WORKER, str(self.root), str(HERE), stage],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
            deadline = time.monotonic() + 10
            while not all((self.root / (stage + ".ready")).exists() for stage in ("AWARDED", "NOT_AWARDED")):
                self.assertLess(time.monotonic(), deadline, "synthetic workers did not reach barrier")
                self.assertTrue(all(child.poll() is None for child in children), "worker exited before barrier")
                time.sleep(.01)
            (self.root / "go").write_text("go", encoding="utf-8")
            results = []
            for child in children:
                stdout, stderr = child.communicate(timeout=10)
                self.assertEqual(child.returncode, 0, stderr)
                results.append(stdout.strip())
            self.assertCountEqual(results, ["SAVED", "CONFLICT"])
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                child.communicate(timeout=5)
        restored = read_dashboard(self.source)
        self.assertEqual(restored["revision"], self.state["revision"] + 1)
        events = restored["notices"][0]["submission_events"]
        self.assertEqual(len(events), 3)
        self.assertEqual(events[:2], self.state["notices"][0]["submission_events"])
        winner = ("AWARDED", "NOT_AWARDED")[results.index("SAVED")]
        self.assertEqual(events[-1]["stage"], winner)
        self.assertEqual(events[-1]["source"], "HUMAN_DECLARED_UNVERIFIED")
        self.assert_preserved(restored)

    def test_collection_revision_conflict_requires_reload_and_preserves_history(self):
        self.state = record(self.state, self.payload(), STAMP)
        self.state = record(self.state, self.payload("EVALUATED", 82.5), STAMP)
        stale_request = self.payload("NOT_AWARDED", 82.5)
        fresh = normalize({"bidNtceNo": "ABC700", "bidNtceOrd": "001",
                           "bidNtceNm": "합성 갱신 공고"})
        self.assertEqual(fresh["id"], self.ident)
        refreshed = update_collection(self.state, [fresh], 1, STAMP)
        server.persist(refreshed, self.source)
        with self.http() as base:
            before = self.source.read_bytes()
            self.assertEqual(self.request(base, stale_request)[0], 409)
            self.assertEqual(self.source.read_bytes(), before)
            status, response = self.request(base)
            self.assertEqual(status, 200)
            self.state = response["dashboard"]
            self.assertEqual(self.state["notices"][0]["submission_events"],
                             refreshed["notices"][0]["submission_events"])
            status, saved = self.request(base, self.payload("NOT_AWARDED", 82.5))
            self.assertEqual(status, 200)
            self.assertEqual(saved["dashboard"]["notices"][0]["submission_events"][:2],
                             refreshed["notices"][0]["submission_events"])
            self.assertEqual(saved["dashboard"]["notices"][0]["title"], fresh["title"])
            self.assert_preserved(saved["dashboard"])


if __name__ == "__main__":
    unittest.main()
