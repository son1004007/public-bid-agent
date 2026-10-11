"""로컬 JSON RFP 배치·대시보드 프로세스 간 동시성 테스트.

목적/책임: 실제 별도 Python 프로세스 2개가 같은 dashboard.json을 갱신할 때 병합·revision 보존.
입력: 임시 합성 공고 JSON; 실제 공고·인력·키 접근 없음.
부작용: tempfile 디렉터리만 생성/삭제.
실패: 잠금 시간 초과·예상치 못한 중복 배치·변경 유실 시 실패.
불변: 원자 저장과 잠금은 다르며 양측의 read-modify-write 전체가 잠겨야 한다.
검증: Python 3.12 Windows/CI Linux의 unittest.
"""
import json
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from dashboard_backend import blank, read as read_dashboard, normalize, update_collection
from json_transaction import transaction
from rfp_batch import Manager
from server import persist as atomic_persist

HERE = Path(__file__).parent
WORKER = r'''
import json
import sys
import time
from pathlib import Path
sys.path.insert(0, sys.argv[3])
import server
from dashboard_backend import read as read_dashboard
from json_transaction import transaction
root=Path(sys.argv[1])
tag=sys.argv[2]
server.ROOT=root
with transaction(root,timeout=5):
    board=read_dashboard(root/"dashboard.json")
    time.sleep(0.25)
    board["history"].append({"tag":tag})
    board["notices"][0][tag]=True
    board["revision"]+=1
    server.persist(board,root/"dashboard.json")
'''

HOLDER = r'''
import sys
import time
from pathlib import Path
sys.path.insert(0,sys.argv[2])
from json_transaction import transaction
root=Path(sys.argv[1])
with transaction(root,timeout=4):
    (root/"entered").write_text("1",encoding="utf-8")
    time.sleep(0.65)
'''


WORKER_HOLDER = r'''
import sys,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from json_transaction import transaction
root=Path(sys.argv[2])
with transaction(root,timeout=2,name=".rfp-batch-worker.lock"):
    (root/"worker-held").write_text("yes",encoding="utf-8")
    for _ in range(400):
        if (root/"worker-release").exists():break
        time.sleep(.01)
    else:raise TimeoutError("synthetic worker-release timeout")
'''


class JsonTransactionTests(unittest.TestCase):
    def test_worker_lease_is_exclusive_between_real_processes(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            p=subprocess.Popen(
                [sys.executable,"-c",WORKER_HOLDER,str(Path(__file__).parent),td],
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                for _ in range(140):
                    if (root/"worker-held").exists():break
                    if p.poll() is not None:break
                    time.sleep(.02)
                self.assertTrue((root/"worker-held").exists(),"child did not acquire lease")
                with self.assertRaises(TimeoutError):
                    with transaction(root,timeout=.12,name=".rfp-batch-worker.lock"):
                        pass
            finally:
                (root/"worker-release").write_text("release",encoding="utf-8")
                out,err=p.communicate(timeout=8)
                if p.poll() is None:p.kill()
            self.assertEqual(p.returncode,0,msg=out+err)
            with transaction(root,timeout=.25,name=".rfp-batch-worker.lock"):
                self.assertTrue((root/"worker-held").exists())


    def test_two_actual_processes_preserve_both_updates(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            import server
            prior=server.ROOT
            try:
                server.ROOT=root
                obj=blank()
                obj["notices"]=[{"id":"G2B-FAKE-001","final":"no_bid","rfp_text":"기존 검증 본문"}]
                atomic_persist(obj,root/"dashboard.json")
            finally:
                server.ROOT=prior
            children=[subprocess.Popen([sys.executable,"-c",WORKER,str(root),tag,str(HERE)],
                       stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                      for tag in ("collector","rfp_batch")]
            try:
                for child in children:
                    stdout,stderr=child.communicate(timeout=12)
                    self.assertEqual(child.returncode,0,stderr[:500])
            finally:
                for child in children:
                    if child.poll() is None:
                        child.kill()
                    child.communicate(timeout=4)
            outcome=read_dashboard(root/"dashboard.json")
            self.assertEqual(outcome["revision"],2)
            self.assertEqual({x["tag"] for x in outcome["history"]},{"collector","rfp_batch"})
            self.assertTrue(outcome["notices"][0]["collector"])
            self.assertTrue(outcome["notices"][0]["rfp_batch"])
            self.assertEqual(outcome["notices"][0]["final"],"no_bid")
            self.assertEqual(outcome["notices"][0]["rfp_text"],"기존 검증 본문")

    def test_cross_process_timeout_and_release(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            holder=subprocess.Popen([sys.executable,"-c",HOLDER,str(root),str(HERE)],
                    stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                deadline=time.monotonic()+4
                while not (root/"entered").exists() and time.monotonic()<deadline:
                    time.sleep(0.02)
                self.assertTrue((root/"entered").exists(),"잠금 선점 프로세스 시작 실패")
                with self.assertRaises(TimeoutError):
                    with transaction(root,timeout=0.1):
                        self.fail("잠금 중복 획득")
                holder.communicate(timeout=6)
                self.assertEqual(holder.returncode,0)
                with transaction(root,timeout=1):
                    self.assertTrue((root/".dashboard-rfp.lock").exists())
            finally:
                if holder.poll() is None:
                    holder.kill()
                holder.communicate(timeout=4)

    def test_terminated_process_releases_os_lock_without_deleting_lockfile(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            holder=subprocess.Popen([sys.executable,"-c",HOLDER,str(root),str(HERE)],
                    stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                deadline=time.monotonic()+4
                while not (root/"entered").exists() and time.monotonic()<deadline:
                    time.sleep(0.02)
                self.assertTrue((root/"entered").exists())
                holder.kill()
                holder.wait(timeout=4)
                with transaction(root,timeout=1):
                    self.assertTrue((root/".dashboard-rfp.lock").exists())
            finally:
                if holder.poll() is None:
                    holder.kill()
                holder.communicate(timeout=4)

    def test_recrawl_preserves_rfp_and_official_attachments(self):
        source={"bidNtceNo":"R26BK1234567","bidNtceOrd":"001",
                "bidNtceNm":"AI 개발 용역",
                "ntceSpecFileNm1":"기본공고.pdf",
                "ntceSpecDocUrl1":"https://www.g2b.go.kr/pn/files/base.pdf"}
        old_notice=normalize(source)
        old_notice["final"]="no_bid"
        old_notice["rfp_text"]="기존 검증한 과업 본문"
        old_notice["document_status"]="EXTRACTED"
        old_notice["document_evidence"]=[{"status":"EXTRACTED","excerpt":"합성 내용"}]
        old_notice["attachments"].append({
            "name":"상세 RFP.pdf",
            "url":"https://www.g2b.go.kr/pn/files/rfp.pdf","source":"공식 상세"})
        board=blank()
        board["notices"]=[old_notice]
        board["history"]=[{"id":old_notice["id"],"decision":"no_bid"}]
        refreshed=update_collection(board,[normalize(source)],1,"SYNTHETIC")
        stored=refreshed["notices"][0]
        self.assertEqual(stored["final"],"no_bid")
        self.assertEqual(stored["rfp_text"],"기존 검증한 과업 본문")
        self.assertEqual(stored["document_evidence"],old_notice["document_evidence"])
        self.assertEqual(len(stored["attachments"]),2)
        self.assertEqual({x["url"] for x in stored["attachments"]},
                         {"https://www.g2b.go.kr/pn/files/base.pdf",
                          "https://www.g2b.go.kr/pn/files/rfp.pdf"})
        self.assertEqual(refreshed["history"],board["history"])
        self.assertEqual(len(board["notices"][0]["attachments"]),2)
        self.assertEqual(refreshed["revision"],1)

    def test_remote_manager_pause_visible_to_running_worker(self):
        from test_rfp_batch import notice, persist
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            board=blank()
            board["notices"]=[notice("1"),notice("2")]
            persist(board,root/"dashboard.json")
            persist({"schema_version":1,"revision":0,"categories":["SW"],
                    "include_review":False},root/"department_profile.json")
            started=threading.Event()
            release=threading.Event()
            def fetcher(url):
                started.set()
                if not release.wait(6):
                    raise TimeoutError("합성 다운로드 대기")
                return b"PDF"
            one=Manager(root,threading.RLock(),persist,lambda *_:{"text":"합성"},
                        fetcher=fetcher,delay=0)
            two=Manager(root,threading.RLock(),persist,lambda *_:{"text":"합성"},
                        fetcher=fetcher,delay=0)
            try:
                one.start(3)
                self.assertTrue(started.wait(3))
                self.assertEqual(two.status()["status"],"RUNNING")
                self.assertEqual(two.pause()["status"],"PAUSED")
            finally:
                release.set()
                if one.worker:
                    one.worker.join(7)
            self.assertFalse(one.worker.is_alive())
            ledger=one.status()
            self.assertEqual(ledger["status"],"PAUSED")
            self.assertEqual(ledger["statistics"]["done"],1)
            self.assertEqual(ledger["statistics"]["pending"],1)

    def test_second_manager_cannot_start_duplicate_worker(self):
        from test_rfp_batch import notice, persist
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            board=blank()
            board["notices"]=[notice("1")]
            persist(board,root/"dashboard.json")
            persist({"schema_version":1,"revision":0,"categories":["SW"],
                    "include_review":False},root/"department_profile.json")
            started=threading.Event()
            release=threading.Event()
            def controlled_fetch(_url):
                started.set()
                if not release.wait(6):
                    raise TimeoutError("합성 다운로드 대기 시간 초과")
                return b"SYNTHETIC"
            one=Manager(root,threading.RLock(),persist,
                        lambda *_:{"text":"합성 문서"},fetcher=controlled_fetch,delay=0)
            two=Manager(root,threading.RLock(),persist,
                        lambda *_:{"text":"중복 문서"},fetcher=controlled_fetch,delay=0)
            try:
                one.start(1)
                self.assertTrue(started.wait(3))
                saved_before=(root/"rfp_batch.json").read_bytes()
                with self.assertRaisesRegex(ValueError,"다른 프로세스"):
                    two.start(1)
                self.assertEqual((root/"rfp_batch.json").read_bytes(),saved_before)
            finally:
                release.set()
                if one.worker:
                    one.worker.join(timeout=7)
            self.assertFalse(one.worker.is_alive())
            self.assertEqual(one.status()["status"],"COMPLETE")
            self.assertEqual(read_dashboard(root/"dashboard.json")["notices"][0]["rfp_text"],"합성 문서")


if __name__ == "__main__":
    unittest.main()
