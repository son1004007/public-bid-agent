"""재개형 RFP 배치 회귀 테스트.
목적: 성공 재분석 방지, 문서별 근거, 실패 재시도, 중간 재시작 및 저장 불변조건 확인.
입력: 임시 폴더의 합성 공고와 가짜 추출/다운로드; 실제 인터넷·인증키 사용 안 함.
부작용: 임시 JSON만 작성하고 기존 사용자 데이터는 읽거나 수정하지 않음.
실패: 재시도·중복처리 또는 잘못된 근거가 발생하면 실패.
"""
import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path

from rfp_batch import Manager, analyze, ranked

ROOT_URL="https://www.g2b.go.kr/pn/download/document"

def notice(ident):
    return {"id":ident,"bid_no":"R26BK01234567","bid_order":"001",
        "title":"소프트웨어 개발","department_status":"CANDIDATE",
        "department_categories":["SW"],"window_status":"OPEN",
        "document_status":"PENDING","rfp_text":"","final":"no_bid",
        "attachments":[{"name":"제안요청서.pdf","url":ROOT_URL+ident,"source":"공고규격서"}]}

def persist(value,path):
    temp=path.with_suffix(".tmp")
    temp.write_text(json.dumps(value,ensure_ascii=False),encoding="utf-8")
    temp.replace(path)

class RfpBatchTests(unittest.TestCase):
    def test_attachment_priority_and_source(self):
        n=notice("1")
        n["attachments"].insert(0,{"name":"공고문.docx","url":ROOT_URL+"notice"})
        n["attachments"].append({"name":"악성.pdf","url":"https://example.com/test.pdf"})
        self.assertEqual(ranked(n)[0]["name"],"제안요청서.pdf")
        result=analyze(n,lambda name,raw:{"text":"실제 데이터 분석 구축","warnings":[]},
                       fetcher=lambda url:b"PDFBYTES")
        self.assertEqual(result["document_status"],"EXTRACTED")
        self.assertEqual(len(result["document_evidence"]),2)
        self.assertEqual(result["document_evidence"][0]["chars"],12)
        self.assertEqual(len(result["document_evidence"][0]["sha256"]),64)

    def test_only_failed_document_retried(self):
        n=notice("1")
        first=analyze(n,lambda name,raw:{"text":"OK"},fetcher=lambda url:b"data")
        n["document_evidence"]=first["document_evidence"]
        second=analyze(n,lambda name,raw:{"text":"NEW"},fetcher=lambda url: self.fail("duplicate"))
        self.assertEqual(first["document_evidence"],second["document_evidence"])

    def test_resume_failure_retry_and_decisions_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            original=[notice("1"),notice("2")]
            persist({"schema_version":1,"revision":0,"notices":original,
                "history":[{"id":"1","status":"no_bid"}],
                "collection":{"status":"SUCCESS"}},root/"dashboard.json")
            persist({"schema_version":1,"revision":0,"categories":["SW"],
                "include_review":False},root/"department_profile.json")
            fetch_calls=[]
            def flaky(url):
                fetch_calls.append(url)
                if url.endswith("2") and fetch_calls.count(url)==1:
                    raise OSError("synthetic failure")
                return b"PDF"
            manager=Manager(root,threading.RLock(),persist,
                lambda name,raw:{"text":"정보시스템 개발 과업","warnings":[]},
                fetcher=flaky,delay=0)
            manager.start(1)
            manager.worker.join(5)
            self.assertEqual(manager.status()["statistics"]["done"],1)
            self.assertEqual(manager.status()["statistics"]["pending"],1)
            # 새 서버 프로세스로 재개하는 것과 동일한 새 객체에서 읽는다.
            restored=Manager(root,threading.RLock(),persist,
                lambda name,raw:{"text":"정보시스템 개발 과업","warnings":[]},
                fetcher=flaky,delay=0)
            self.assertEqual(restored.status()["status"],"PAUSED")
            restored.start(1)
            restored.worker.join(5)
            self.assertEqual(restored.status()["statistics"]["failed"],1)
            self.assertEqual(len(fetch_calls),2)
            restored.start(1,retry_failed=True)
            restored.worker.join(5)
            final=restored.status()
            self.assertEqual(final["status"],"COMPLETE")
            self.assertEqual(final["statistics"],{"total":2,"done":2,"failed":0,"pending":0})
            self.assertEqual(len(fetch_calls),3)
            saved=json.loads((root/"dashboard.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["notices"][0]["final"],"no_bid")
            self.assertEqual(len(saved["notices"]),2)
            self.assertEqual(saved["history"],[{"id":"1","status":"no_bid"}])
            self.assertTrue(all(x["document_status"]=="EXTRACTED" for x in saved["notices"]))


    def test_worker_does_not_overwrite_concurrent_newer_document(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            original=notice("1")
            persist({"schema_version":1,"revision":0,"notices":[original],
                "history":[],"collection":{"status":"SUCCESS"}},root/"dashboard.json")
            persist({"schema_version":1,"revision":0,"categories":["SW"],
                "include_review":False},root/"department_profile.json")
            def competing_fetch(url):
                board=json.loads((root/"dashboard.json").read_text(encoding="utf-8"))
                board["notices"][0]["document_status"]="EXTRACTED"
                board["notices"][0]["rfp_text"]="사람이 먼저 확인한 최신 RFP"
                board["revision"]+=1
                persist(board,root/"dashboard.json")
                return b"OLD"
            m=Manager(root,threading.RLock(),persist,
                lambda *_:{"text":"오래된 추출 결과"},fetcher=competing_fetch,delay=0)
            m.start(1)
            m.worker.join(5)
            saved=json.loads((root/"dashboard.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["notices"][0]["rfp_text"],"사람이 먼저 확인한 최신 RFP")
            self.assertEqual(m.status()["statistics"]["done"],1)

    def test_previous_extracted_text_is_versioned(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            n=notice("1")
            n["rfp_text"]="기존 사용자 검토 원문"
            n["document_status"]="FAILED"
            persist({"schema_version":1,"revision":0,"notices":[n],
                "history":[],"collection":{"status":"SUCCESS"}},root/"dashboard.json")
            persist({"schema_version":1,"revision":0,"categories":["SW"],
                "include_review":False},root/"department_profile.json")
            m=Manager(root,threading.RLock(),persist,
                lambda *_:{"text":"새로운 성공 내용"},fetcher=lambda _:b"data",delay=0)
            m.start(1)
            m.worker.join(5)
            result=json.loads((root/"dashboard.json").read_text(encoding="utf-8"))["notices"][0]
            self.assertEqual(result["rfp_text"],"새로운 성공 내용")
            self.assertEqual(result["document_prior_versions"][0]["text"],"기존 사용자 검토 원문")

    def test_corrupt_state_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"rfp_batch.json").write_text('{"schema_version":9}',encoding="utf-8")
            manager=Manager(root,threading.RLock(),persist,lambda *_:{})
            with self.assertRaises(ValueError):
                manager.status()

if __name__=="__main__":
    unittest.main()
