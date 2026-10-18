"""입찰 준비도 상태: 입력 전부 합성, 원문·직원정보 비노출."""
import json
import copy
from datetime import date
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
    def test_reviewed_without_evidence_or_with_future_date_is_incomplete(self):
        for changes,expected in (({"source":" "},"SOURCE_MISSING_OR_INVALID"),
                                 ({"summary":[]},"SUMMARY_MISSING_OR_INVALID"),
                                 ({"reviewed_on":"2026-02-30"},"REVIEW_DATE_MISSING_OR_INVALID"),
                                 ({"reviewed_on":"20261001"},"REVIEW_DATE_MISSING_OR_INVALID"),
                                 ({"reviewed_on":"2026-10-19"},"REVIEW_DATE_IN_FUTURE")):
            with self.subTest(changes=changes):
                ops=default_profile()
                ops["registers"]["registrations"]={"status":"reviewed","source":"SYNTHETIC_SOURCE",
                    "summary":"SYNTHETIC_SUMMARY","reviewed_on":"2026-10-18",**changes}
                report=assess(item("201"),ops,today=date(2026,10,18))
                check=report["checks"][0]
                self.assertEqual(check["status"],"EVIDENCE_RECORD_INCOMPLETE")
                self.assertIn(expected,check["evidence_gaps"])
                self.assertEqual(check["evidence_verification"],"UNVERIFIED")

    def test_complete_records_do_not_assert_eligibility_or_company_evidence_validation(self):
        ops=default_profile()
        for key in ops["registers"]:
            ops["registers"][key]={"status":"reviewed","source":"SYNTHETIC_PRIVATE_SOURCE",
                "summary":"SYNTHETIC_PRIVATE_SUMMARY","reviewed_on":"2026-10-18"}
        ops["roles"]=[{"role":"SYNTHETIC_PRIVATE_ROLE","available_mm":12,"cost_per_mm_krw":1000}]
        notice=item("202")
        notice["human_decision"]={"decision":"HOLD","reason":"SYNTHETIC_PRIVATE_REASON"}
        before=copy.deepcopy((notice,ops))
        out=assess(notice,ops,today=date(2026,10,18))
        self.assertTrue(all(c["status"]=="USER_REVIEWED_UNVERIFIED" for c in out["checks"]))
        self.assertTrue(all(c["requirement_comparison"]=="NOT_PERFORMED" for c in out["checks"]))
        for key in ("legal_eligibility","technical_fit","staffing_fit","profitability"):
            self.assertEqual(out[key],"UNVERIFIED")
        self.assertEqual(out["status"],"HOLD_FOR_EVIDENCE_REVIEW")
        self.assertNotIn("SYNTHETIC_PRIVATE",json.dumps(out))
        self.assertEqual((notice,ops),before)
        self.assertIn("면허",out["checks"][0]["required_review"][1])
        self.assertIn("실적증명",out["checks"][1]["required_review"][0])

    def test_capacity_and_cost_data_gaps(self):
        cases=[([],"FULLY_LOADED","ROLE_CAPACITY_NOT_RECORDED","ROLE_COST_NOT_RECORDED"),
               ([{"role":"synthetic","available_mm":None,"cost_per_mm_krw":0}],
                "SALARY_ONLY","AVAILABLE_MM_UNKNOWN","ZERO_ROLE_COST_REQUIRES_REVIEW"),
               ([{"role":"synthetic","available_mm":0,"cost_per_mm_krw":10}],
                "SALARY_ONLY","NO_RECORDED_AVAILABLE_MM","FULL_COST_BASIS_NOT_RECORDED"),
               ([{"role":"synthetic","available_mm":True,"cost_per_mm_krw":10}],
                "FULLY_LOADED","OPERATIONS_PROFILE_INVALID","OPERATIONS_PROFILE_INVALID")]
        for roles,basis,staff_gap,cost_gap in cases:
            with self.subTest(roles=roles,basis=basis):
                ops=default_profile();ops.update(roles=roles,cost_basis=basis)
                out=assess(item("203"),ops,today=date(2026,10,18))
                by_code={c["code"]:c for c in out["checks"]}
                self.assertIn(staff_gap,by_code["utilization"]["data_gaps"])
                self.assertIn(cost_gap,by_code["finance"]["data_gaps"])
                self.assertEqual(out["profitability"],"UNVERIFIED")

    def test_blocked_states_and_refresh_cannot_be_cleared_by_reviewed_records(self):
        ops=default_profile()
        ops["registers"]["registrations"]={"status":"needs_refresh","source":"synthetic",
             "summary":"synthetic","reviewed_on":"2026-10-18"}
        for change in ({"notice_lifecycle":"CANCELLED"},{"notice_lifecycle":"SUPERSEDED"},
                       {"notice_lifecycle":"REVIEW"},{"notice_kind":"취소공고"},
                       {"rfp_review_status":"STALE"}):
            with self.subTest(change=change):
                out=assess({**item("204"),**change},ops,today=date(2026,10,18))
                self.assertEqual(out["status"],"BLOCKED_LIFECYCLE")
                self.assertEqual(out["checks"][0]["status"],"STALE_OR_REFRESH_NEEDED")

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
                    checks={c["code"]:c for c in data["readiness"]["checks"]}
                    self.assertIn("ROLE_COST_NOT_RECORDED",checks["finance"]["data_gaps"])
                    self.assertEqual(checks["finance"]["requirement_comparison"],"NOT_PERFORMED")
                    self.assertNotIn("SENSITIVE_COSTS",json.dumps(data))
                    self.assertNotIn("PRIVATE_REPORT",json.dumps(data))
                    self.assertEqual(before,(dashboard.read_bytes(),operations.read_bytes()))
                finally:
                    http.shutdown();http.server_close();thread.join(4)

if __name__=="__main__":unittest.main()
