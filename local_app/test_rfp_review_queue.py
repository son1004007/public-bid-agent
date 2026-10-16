"""메타데이터 전용 RFP 검토 큐: 합성 공고/보안/취소 검증."""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import urlopen
from http.server import ThreadingHTTPServer

import server
from dashboard_backend import blank
from rfp_review_queue import build
from test_rfp_coverage import item,PROFILE

class RfpReviewQueueTests(unittest.TestCase):
    def test_priority_and_private_evidence_omission(self):
        base=item("501",state="EXTRACTED",excerpt="sensitive original")
        base.update({"notice_lifecycle":"CURRENT","document_evidence":[
          {"status":"EXTRACTED","fulltext_truncated":True,"warnings":["SECRET_WARNING"],
           "excerpt":"RAW_SECRET_TEXT"}]})
        low=item("502",state="PENDING")
        old=item("503",state="EXTRACTED",excerpt="old")
        old["notice_lifecycle"]="SUPERSEDED"
        report=build([low,base,old],PROFILE,limit=1)
        self.assertEqual(report["total"],2)
        self.assertEqual(report["results"][0]["id"],base["id"])
        self.assertIn("PARSER_TRUNCATION_REPORTED",report["results"][0]["flags"])
        self.assertEqual(report["omitted_count"],1)
        raw=json.dumps(report)
        for secret in ("RAW_SECRET_TEXT","SECRET_WARNING","sensitive original"):
            self.assertNotIn(secret,raw)
        self.assertEqual(report["original_page_recall"],"NOT_VERIFIED")

    def test_http_read_only(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);board=blank()
            n=item("503",state="EXTRACTED",excerpt="synthetic confidential")
            n["document_evidence"]=[{"status":"EXTRACTED","warnings":["sensitive warning"]}]
            board["notices"]=[n]
            file=root/"dashboard.json"
            file.write_text(json.dumps(board,ensure_ascii=False),encoding="utf8")
            profile=root/"department_profile.json"
            profile.write_text(json.dumps({"schema_version":1,**PROFILE}),encoding="utf8")
            before=file.read_bytes(),profile.read_bytes()
            with patch.object(server,"ROOT",root):
                h=ThreadingHTTPServer(("127.0.0.1",0),server.Handler)
                task=threading.Thread(target=h.serve_forever,daemon=True);task.start()
                try:
                    with urlopen(f"http://127.0.0.1:{h.server_port}/api/dashboard/rfp-review-queue",timeout=5) as resp:
                        self.assertEqual(resp.status,200);reply=json.load(resp)
                    self.assertEqual(reply["queue"]["total"],1)
                    self.assertEqual(reply["storage"],"LOCAL_READ_ONLY")
                    self.assertNotIn("sensitive",json.dumps(reply))
                    self.assertEqual(before,(file.read_bytes(),profile.read_bytes()))
                finally:
                    h.shutdown();h.server_close();task.join(3)

if __name__=="__main__": unittest.main()
