"""입찰 준비도 상태: 입력 전부 합성, 원문·직원정보 비노출."""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from urllib.request import urlopen

from bid_readiness import assess
from dashboard_backend import blank
from operations import default_profile
from test_rfp_coverage import item
import server


class ReadinessTest(unittest.TestCase):
    def test_metadata_only_readiness_and_lifecycle(self):
        notice=item("200")
        ops=default_profile()
        result=assess(notice,ops)
        self.assertEqual(result["status"],"HOLD_FOR_EVIDENCE_REVIEW")
        self.assertEqual(len(result["checks"]),6)
        self.assertTrue(all(x["status"]=="NOT_COLLECTED" for x in result["checks"]))
        self.assertEqual(result["legal_eligibility"],"UNVERIFIED")
        ops["registers"]["registrations"]={"status":"reviewed","summary":"CONFIDENTIAL_PERSONNEL",
             "source":"TOP_SECRET_SOURCE","reviewed_on":"2026-10-16"}
        result=assess(notice,ops)
        self.assertEqual(result["checks"][0]["status"],"USER_REVIEWED_UNVERIFIED")
        self.assertNotIn("CONFIDENTIAL",json.dumps(result))
        self.assertNotIn("TOP_SECRET",json.dumps(result))
        cancelled={**notice,"notice_lifecycle":"CANCELLED"}
        self.assertEqual(assess(cancelled,ops)["status"],"BLOCKED_LIFECYCLE")
        stale={**notice,"rfp_review_status":"STALE"}
        self.assertEqual(assess(stale,ops)["status"],"BLOCKED_LIFECYCLE")
        closed={**notice,"end":"2020-01-01T12:00:00"}
        self.assertEqual(assess(closed,ops)["status"],"DEADLINE_NOT_OPEN")

    def test_readiness_http_no_private_data_or_file_write(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            board=blank()
            notice=item("200")
            board["notices"]=[notice]
            dashboard=root/"dashboard.json"
            dashboard.write_text(json.dumps(board,ensure_ascii=False),encoding="utf-8")
            ops=default_profile()
            ops["registers"]["finance"]={"status":"reviewed","summary":"SENSITIVE_COSTS",
                "source":"PRIVATE_REPORT","reviewed_on":"2026-10-16"}
            operations=root/"operations.json"
            operations.write_text(json.dumps(ops,ensure_ascii=False),encoding="utf-8")
            before=dashboard.read_bytes(),operations.read_bytes()
            with patch.object(server,"ROOT",root):
                http=ThreadingHTTPServer(("127.0.0.1",0),server.Handler)
                thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
                try:
                    url=f"http://127.0.0.1:{http.server_port}/api/dashboard/readiness?id="+notice["id"]
                    with urlopen(url,timeout=5) as resp:
                        self.assertEqual(resp.status,200);data=json.load(resp)
                    self.assertEqual(data["readiness"]["automated_bid_recommendation"],"NOT_AVAILABLE")
                    self.assertNotIn("SENSITIVE_COSTS",json.dumps(data))
                    self.assertNotIn("PRIVATE_REPORT",json.dumps(data))
                    self.assertEqual(before,(dashboard.read_bytes(),operations.read_bytes()))
                finally:
                    http.shutdown();http.server_close();thread.join(4)

if __name__=="__main__":unittest.main()
