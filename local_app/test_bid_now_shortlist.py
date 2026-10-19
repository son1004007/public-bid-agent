"""BID-02: synthetic only; local HTTP Host/CSP and source file nonmutation."""
import copy
import json
import tempfile
import threading
import unittest
from datetime import datetime
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from bid_now_shortlist import build
from dashboard_backend import blank
from operations import default_profile
from procurement_filter import KST
import server

NOW=datetime(2026,10,18,12,0,tzinfo=KST)
PROFILE={"schema_version":1,"revision":0,"categories":["SW"],"include_review":False}
SECRET="PRIVATE_STAFF_COST_RATE_123456"
def notice(n,*,department_status="CANDIDATE",categories=None,**kw):
    n0={"id":f"G2B-SYNTH-{n:04d}","bid_no":"SYNTH",
        "bid_order":f"{n:04d}","notice_lifecycle":"CURRENT",
        "notice_kind":"일반공고","end":"2099-10-18T12:00:00+09:00",
        "department_status":department_status,"department_categories":
            ["SW"] if categories is None else categories,
        "document_status":"PENDING","rfp_text":"",
        "document_evidence":[],"attachments":[],
        "title":SECRET,"private_cost":SECRET}
    n0.update(kw)
    return n0

class BidNowShortlistTests(unittest.TestCase):
    def setUp(self):
        self.ops=default_profile()
        self.ops["registers"]["finance"]={
            "status":"reviewed","source":SECRET,
            "summary":SECRET,"reviewed_on":"2026-10-18"}
        self.ops["roles"]=[{"role":SECRET,"available_mm":10,"cost_per_mm_krw":12500000}]

    def test_gap_and_original_protection_and_fixed_codes(self):
        items=[notice(1),notice(2,department_status="OUT_OF_SCOPE",categories=[]),
               notice(3,notice_lifecycle="CANCELLED"),
               notice(4,end="2020-01-01T00:00:00+09:00"),
               notice(5,qualification_deadline="2020-01-01T00:00:00+09:00")]
        before=copy.deepcopy((items,self.ops))
        out=build(items,PROFILE,self.ops,at=NOW)
        self.assertEqual(out["matching_total"],1)
        self.assertEqual(out["augmentation_review_total"],1)
        self.assertEqual(out["registration_review_total"],1)
        self.assertEqual(out["status_counts"]["HOLD_DEADLINE"],1)
        self.assertEqual(out["status_counts"]["HOLD_OFFICIAL_STATUS"],1)
        self.assertEqual(out["augmentation_review_results"][0]["profit_after_augmentation_cost"],"UNVERIFIED")
        self.assertEqual(out["augmentation_review_results"][0]["required_readiness"]["profitability"],"UNVERIFIED")
        self.assertEqual((items,self.ops),before)
        self.assertNotIn(SECRET,json.dumps(out,ensure_ascii=False))
        self.assertTrue(out["human_review_required"])
        self.assertFalse(out["automatic_bid_submittal"])

    def test_category_gap_remains_visible_not_as_verified_profit(self):
        rows=[notice(i,department_status="OUT_OF_SCOPE",categories=[],
                     estimated_profit_krw=99999999999) for i in range(1,35)]
        res=build(rows,PROFILE,self.ops,at=NOW,limit=7)
        self.assertEqual(res["augmentation_review_total"],34)
        self.assertEqual(len(res["augmentation_review_results"]),7)
        self.assertTrue(all(r["legal_eligibility"]=="UNVERIFIED" for r in res["augmentation_review_results"]))
        self.assertNotIn("99999999999",json.dumps(res))
        self.assertEqual(res["matching_total"],0)

    def test_missing_lifecycle_and_tampered_input_fail_closed(self):
        x=notice(10)
        del x["notice_lifecycle"]
        res=build([x],PROFILE,self.ops,at=NOW)
        self.assertEqual(res["status_counts"]["HOLD_OFFICIAL_STATUS"],1)
        self.assertEqual(res["matching_results"],[])
        with self.assertRaises(ValueError):build([notice(11),notice(11)],PROFILE,self.ops,at=NOW)
        with self.assertRaises(ValueError):build([notice(12)],PROFILE,self.ops,at=NOW,limit=0)

    def test_forged_public_id_and_canonical_mismatch_are_held(self):
        forged=notice(35,id="G2B-PRIVATE-STAFF-COST")
        mismatch=notice(36,bid_no="FRAUD")
        checked=build([forged,mismatch,notice(37)],PROFILE,self.ops,at=NOW)
        self.assertEqual(checked["status_counts"]["INVALID_ID_HELD"],2)
        self.assertEqual(checked["matching_total"],1)
        self.assertNotIn("PRIVATE-STAFF",json.dumps(checked))

    def test_http_security_snapshot_and_no_write(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            board=blank()
            board["notices"]=[notice(31),notice(32,department_status="OUT_OF_SCOPE",categories=[])]
            boardfile=root/"dashboard.json"
            profilefile=root/"department_profile.json"
            operationsfile=root/"operations.json"
            boardfile.write_text(json.dumps(board,ensure_ascii=False),encoding="utf-8")
            profilefile.write_text(json.dumps(PROFILE,ensure_ascii=False),encoding="utf-8")
            operationsfile.write_text(json.dumps(self.ops,ensure_ascii=False),encoding="utf-8")
            before={p.name:p.read_bytes() for p in root.iterdir() if p.is_file()}
            with patch.object(server,"ROOT",root):
                http=ThreadingHTTPServer(("127.0.0.1",0),server.Handler)
                th=threading.Thread(target=http.serve_forever,daemon=True)
                th.start()
                try:
                    url=f"http://127.0.0.1:{http.server_port}/api/dashboard/bid-now-shortlist"
                    with urlopen(url,timeout=7) as response:
                        self.assertEqual(response.status,200)
                        self.assertIn("default-src 'self'",response.headers["Content-Security-Policy"])
                        self.assertEqual(response.headers["X-Content-Type-Options"],"nosniff")
                        payload=json.load(response)
                    rows=payload["shortlist"]
                    self.assertEqual(payload["storage"],"LOCAL_READ_ONLY")
                    self.assertEqual(payload["dashboard_revision"],board["revision"])
                    self.assertEqual(rows["matching_total"],1)
                    self.assertEqual(rows["augmentation_review_total"],1)
                    self.assertNotIn(SECRET,json.dumps(payload))
                    with self.assertRaises(HTTPError) as err:
                        urlopen(Request(url,headers={"Host":"malicious.example"}),timeout=7)
                    self.assertEqual(err.exception.code,403)
                finally:
                    http.shutdown();http.server_close();th.join(timeout=3)
            self.assertEqual(before,{p.name:p.read_bytes() for p in root.iterdir() if p.is_file()})

    def test_bid03_browser_fixture_real_api_three_queues_and_held_sources_preserved(self):
        from test_local_acceptance import synthetic_server
        with synthetic_server(bid_now=True) as fixture:
            root=fixture["root"]
            before={p:p.read_bytes() for p in root.rglob("*") if p.is_file()}
            with urlopen(fixture["base"]+"/api/dashboard/bid-now-shortlist",timeout=7) as response:
                report=json.load(response)["shortlist"]
            self.assertEqual(report["matching_total"],1)
            self.assertEqual(report["augmentation_review_total"],1)
            self.assertEqual(report["registration_review_total"],1)
            self.assertEqual(report["status_counts"]["HOLD_OFFICIAL_STATUS"],2)
            self.assertEqual(report["status_counts"]["HOLD_DEADLINE"],1)
            self.assertEqual(before,{p:p.read_bytes() for p in root.rglob("*") if p.is_file()})

if __name__=="__main__":
    unittest.main()
