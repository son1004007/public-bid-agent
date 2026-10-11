"""RFP 배치 프로세스 충돌 보완 테스트.

책임: 중단 작업은 명시적 재시도 전까지 보존하고, 구형 추출은 최신 근거를 덮어쓰지 않는다.
테스트 자산: 임시 합성 JSON, 루프백 HTTP만 사용. 사용자 운영 데이터/API 키는 사용하지 않는다.
"""
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen

import server
from dashboard_backend import blank, read as read_dashboard
from json_transaction import transaction
from rfp_batch import Manager
from test_rfp_batch import notice, persist


class RfpCrashAndStaleUpdateTest(unittest.TestCase):
    def _setup(self, root):
        board=blank()
        board["notices"]=[notice("1")]
        board["history"]=[{"decision":"no_bid","id":"1"}]
        with patch.object(server,"ROOT",root):
            server.persist(board,root/"dashboard.json")
        persist({"schema_version":1,"revision":0,"categories":["SW"],
                 "include_review":False},root/"department_profile.json")
        return board

    def test_in_progress_from_crash_requires_explicit_retry(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            self._setup(root)
            persist({"schema_version":1,"revision":5,"status":"RUNNING",
                     "target_ids":["1"],"items":{"1":{"status":"IN_PROGRESS","attempts":1}},
                     "updated_at":None},root/"rfp_batch.json")
            calls=[]
            manager=Manager(root,threading.RLock(),persist,
                lambda *_:{"text":"재시도 후 새 RFP"},
                fetcher=lambda url: (calls.append(url),b"FAKE")[1],delay=0)
            first=manager.start(1)
            self.assertEqual(first["statistics"]["failed"],1)
            self.assertIsNone(manager.worker)
            self.assertEqual(calls,[])
            ledger=json.loads((root/"rfp_batch.json").read_text(encoding="utf-8"))
            self.assertEqual(ledger["items"]["1"]["attempts"],1)
            self.assertEqual(ledger["items"]["1"]["status"],"FAILED")
            self.assertEqual(read_dashboard(root/"dashboard.json")["notices"][0]["rfp_text"],"")
            manager.start(1,retry_failed=True)
            manager.worker.join(6)
            self.assertFalse(manager.worker.is_alive())
            self.assertEqual(len(calls),1)
            self.assertEqual(manager.status()["statistics"]["done"],1)
            ledger=json.loads((root/"rfp_batch.json").read_text(encoding="utf-8"))
            self.assertEqual(ledger["items"]["1"]["attempts"],2)
            self.assertEqual(read_dashboard(root/"dashboard.json")["history"],
                             [{"decision":"no_bid","id":"1"}])

    def test_failed_batch_remains_paused_until_explicit_retry(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            self._setup(root)
            attempts=[]
            def fetcher(url):
                attempts.append(url)
                raise OSError("synthetic failed attachment")
            manager=Manager(root,threading.RLock(),persist,
                lambda *_:{"text":"미사용"},fetcher=fetcher,delay=0)
            manager.start(1)
            manager.worker.join(6)
            self.assertFalse(manager.worker.is_alive())
            status=manager.status()
            self.assertEqual(status["status"],"PAUSED")
            self.assertEqual(status["statistics"]["failed"],1)
            self.assertEqual(len(attempts),1)
            again=manager.start(1)
            self.assertEqual(again["status"],"PAUSED")
            self.assertEqual(len(attempts),1)

    def test_pending_items_resume_without_retrying_failed_items(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            self._setup(root)
            board=read_dashboard(root/"dashboard.json")
            board["notices"].append(notice("2"))
            server.persist(board,root/"dashboard.json")
            calls=[]
            def fetcher(url):
                calls.append(url)
                if url.endswith("1"):raise OSError("first item failed")
                return b"SYNTHETIC"
            manager=Manager(root,threading.RLock(),persist,
                lambda *_:{"text":"합성 RFP"},fetcher=fetcher,delay=0)
            manager.start(1)
            manager.worker.join(6)
            first=manager.status()
            self.assertEqual(first["status"],"PAUSED")
            self.assertEqual(first["statistics"],{"total":2,"done":0,"failed":1,"pending":1})
            self.assertEqual(len(calls),1)
            manager.start(1)
            manager.worker.join(6)
            second=manager.status()
            self.assertEqual(second["status"],"PAUSED")
            self.assertEqual(second["statistics"],{"total":2,"done":1,"failed":1,"pending":0})
            self.assertEqual(len(calls),2)
            ledger=json.loads((root/"rfp_batch.json").read_text(encoding="utf-8"))
            self.assertEqual(ledger["items"]["1"]["attempts"],1)
            self.assertEqual(ledger["items"]["2"]["attempts"],1)

    def test_paused_living_worker_cannot_be_recovered_by_second_manager(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            self._setup(root)
            board=read_dashboard(root/"dashboard.json")
            board["notices"].append(notice("2"))
            server.persist(board,root/"dashboard.json")
            entered,release=threading.Event(),threading.Event()
            def slow_fetch(url):
                entered.set()
                if not release.wait(7):
                    raise RuntimeError("synthetic worker unblocked too late")
                return b"FAKE"
            first=Manager(root,threading.RLock(),persist,
                          lambda *_:{"text":"합성 RFP"},fetcher=slow_fetch,delay=0)
            second=Manager(root,threading.RLock(),persist,
                           lambda *_:{"text":"중복"},fetcher=slow_fetch,delay=0)
            try:
                first.start(3)
                self.assertTrue(entered.wait(4))
                second.pause()
                prior=(root/"rfp_batch.json").read_bytes()
                with self.assertRaisesRegex(ValueError,"다른 프로세스"):
                    second.start(1)
                self.assertEqual((root/"rfp_batch.json").read_bytes(),prior)
            finally:
                release.set()
                if first.worker:first.worker.join(8)
            self.assertFalse(first.worker.is_alive())
            self.assertEqual(first.status()["status"],"PAUSED")
            self.assertEqual(first.status()["statistics"]["done"],1)
            self.assertEqual(first.status()["statistics"]["pending"],1)

    def test_late_enrich_cannot_override_batch_newer_document(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            self._setup(root)
            with patch.object(server,"ROOT",root):
                http=ThreadingHTTPServer(("127.0.0.1",0),server.Handler)
                runner=threading.Thread(target=http.serve_forever,daemon=True)
                runner.start()
                entered=threading.Event()
                release=threading.Event()
                captured={}
                def delayed_extract(*args):
                    entered.set()
                    if not release.wait(8):
                        raise RuntimeError("synthetic extraction did not resume")
                    return {"text":"이전 추출 결과","source_name":"old.pdf"}
                def request():
                    url=f"http://127.0.0.1:{http.server_port}/api/dashboard/enrich"
                    body=json.dumps({"id":"1"}).encode("utf-8")
                    req=Request(url,body,method="POST",
                        headers={"Origin":f"http://127.0.0.1:{http.server_port}",
                                 "Content-Type":"application/json",
                                 "X-Local-CSRF":server.TOKEN})
                    try:
                        with urlopen(req,timeout=12) as resp:
                            captured["status"]=resp.status
                            captured["data"]=json.load(resp)
                    except Exception as exc:
                        captured["error"]=repr(exc)
                try:
                    with patch.object(server,"extract_official_document",side_effect=delayed_extract):
                        client=threading.Thread(target=request,daemon=True)
                        client.start()
                        self.assertTrue(entered.wait(4),"legacy enrich did not reach extraction")
                        with transaction(root):
                            board=read_dashboard(root/"dashboard.json")
                            row=board["notices"][0]
                            row["document_status"]="EXTRACTED"
                            row["rfp_text"]="최신 배치의 확인된 과업 원문"
                            row["document_source_name"]="new-batch.pdf"
                            row["document_evidence"]=[{"status":"EXTRACTED","excerpt":"합성"}]
                            board["revision"]+=1
                            server.persist(board,root/"dashboard.json")
                        release.set()
                        client.join(8)
                        self.assertFalse(client.is_alive())
                finally:
                    release.set()
                    http.shutdown()
                    http.server_close()
                    runner.join(4)
                self.assertNotIn("error",captured,str(captured))
                self.assertEqual(captured.get("status"),200)
                self.assertEqual(captured["data"]["applied"],0)
                self.assertEqual(captured["data"]["skipped_conflicts"],1)
                result=read_dashboard(root/"dashboard.json")
                self.assertEqual(result["revision"],1)
                self.assertEqual(result["notices"][0]["rfp_text"],"최신 배치의 확인된 과업 원문")
                self.assertEqual(result["notices"][0]["document_source_name"],"new-batch.pdf")
                self.assertEqual(result["history"],[{"decision":"no_bid","id":"1"}])


if __name__ == "__main__":
    unittest.main()
