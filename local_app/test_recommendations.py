"""공식 공고 검토 우선순위 및 로컬 HTTP 경계의 합성 회귀.

테스트는 임시 dashboard/profile만 사용하며 실제 공고·인력·인증키에 접근하지 않음.
"""
import copy
import hashlib
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.request import urlopen
from urllib.error import HTTPError

import server
from dashboard_backend import blank, normalize
from recommendations import shortlist


def notice(title, code, *, doc=False, due="2099-12-31T18:00:00"):
    r = normalize({"bidNtceNo":code, "bidNtceOrd":"001","bidNtceNm":title,
                   "bidClseDt":due,"pubPrcrmntClsfcNm":"소프트웨어개발",
                   "ntceSpecFileNm1":"제안요청서.pdf",
                   "ntceSpecDocUrl1":"https://www.g2b.go.kr/pn/synthetic.pdf"})
    if doc:
        r["document_status"]="EXTRACTED"
        r["rfp_text"]="공식 본문: 업무시스템 개발 및 데이터 연계, 구현 시험"
        file=r["attachments"][0]
        identity=hashlib.sha256((file["url"]+"\\n"+file["name"]).encode()).hexdigest()
        r["document_evidence"]=[{"status":"EXTRACTED",
                "sha256":"a"*64,"excerpt":r["rfp_text"],
                "identity":identity}]
        from procurement_filter import apply
        apply(r)
    return r


class RankingTests(unittest.TestCase):
    def setUp(self):
        self.profile={"categories":["SW","DATA"],"revision":0}

    def test_rfp_evidence_before_metadata_and_review(self):
        rfp=notice("업무시스템 구축", "R26BK12345001",doc=True)
        meta=notice("업무시스템 구축", "R26BK12345002")
        result=shortlist([meta,rfp],self.profile)
        self.assertEqual(result["results"][0]["id"],rfp["id"])
        self.assertEqual(result["results"][0]["priority_tier"],3)
        self.assertEqual(result["results"][1]["priority_tier"],1)
        self.assertEqual(result["results"][0]["legal_eligibility"],"UNVERIFIED")
        self.assertEqual(result["results"][0]["technical_fit"],"UNVERIFIED")
        self.assertEqual(result["analysis_mode"],"RULE_BASED_READ_ONLY")
        self.assertNotIn("공식 본문: 업무시스템 개발",json.dumps(result,ensure_ascii=False))
        self.assertTrue(all("rfp_text" not in item for item in result["results"]))

    def test_closed_cancelled_and_human_no_bid_excluded(self):
        yes=notice("정보시스템 구축", "R26BK12345011")
        closed=notice("정보시스템 구축", "R26BK12345012",due="2020-01-01T18:00:00")
        cancel=notice("정보시스템 구축", "R26BK12345013")
        cancel["notice_kind"]="취소공고"
        no_bid=notice("정보시스템 구축", "R26BK12345014")
        no_bid["final"]="no_bid"
        result=shortlist([yes,closed,cancel,no_bid],self.profile)
        self.assertEqual(result["review_priority_count"],1)
        self.assertEqual(result["results"][0]["id"],yes["id"])

    def test_empty_profile_never_recommends(self):
        result=shortlist([notice("정보시스템 구축","R26BK12345021")],
                         {"categories":[]})
        self.assertEqual(result["results"],[])

    def test_no_source_does_not_become_rfp_or_legal_pass(self):
        src=notice("업무시스템 구축", "R26BK12345031")
        src["document_status"]="FAILED"
        src["rfp_text"]=""
        before=copy.deepcopy(src)
        item=shortlist([src],self.profile)["results"][0]
        self.assertLess(item["priority_tier"],2)
        self.assertEqual(item["recommendation_state"],"DETAIL_REVIEW_REQUIRED")
        self.assertEqual(item["staffing_fit"],"UNVERIFIED")
        self.assertEqual(src,before)

    def test_result_limit_and_safe_fields(self):
        data=[notice("정보시스템 구축","R26BK12345"+str(i).zfill(3)) for i in range(10)]
        data[0]["private_salary"]="SENSITIVE_SALARY_MARKER"
        data[0]["rfp_text"]="PRIVATE_RFP_MARKER"
        result=shortlist(data,self.profile,limit=3)
        self.assertEqual(len(result["results"]),3)
        self.assertNotIn("SENSITIVE_SALARY_MARKER",json.dumps(result))
        self.assertNotIn("PRIVATE_RFP_MARKER",json.dumps(result))
        with self.assertRaises(ValueError):shortlist(data,self.profile,limit=101)

    def test_review_discovery_is_secondary_not_confirmed_eligibility(self):
        review=notice("정보시스템 구축", "R26BK12345041")
        review["department_status"]="REVIEW"
        review["department_categories"]=[]
        result=shortlist([review],self.profile)
        self.assertEqual(result["results"][0]["priority_tier"],0)
        self.assertEqual(result["results"][0]["legal_eligibility"],"UNVERIFIED")


    def test_cancelled_final_uppercase_and_status_are_excluded(self):
        for extra in ({"final":"NO_BID"},{"final":"closed"},{"status":"CLOSED"},
                      {"status":"cancelled"},{"window_status":"CANCELLED"},
                      {"notice_kind":"유찰공고"}):
            n=notice("정보시스템 개발","R26BK12345072")
            n.update(extra)
            with self.subTest(extra=extra):
                self.assertEqual(shortlist([n],self.profile)["results"],[])

    def test_stale_or_spoofed_rfp_category_label_is_not_trusted(self):
        n=notice("정보시스템 개발","R26BK12345073")
        n["document_status"]="EXTRACTED"
        n["rfp_text"]="서술 없는 임의 문장"
        n["category_evidence"]=[{"category":"SW","sources":["RFP 추출본문"]}]
        result=shortlist([n],self.profile)["results"][0]
        self.assertEqual(result["priority_tier"],2)
        self.assertNotIn("RFP 추출본문",[x["source"] for x in result["evidence"]])

    def test_review_discovery_must_match_selected_profile(self):
        n=notice("정보시스템 구축","R26BK12345074")
        n["department_status"]="REVIEW"
        n["department_categories"]=[]
        result=shortlist([n],{"categories":["DATA"]})
        self.assertEqual(result["results"],[])
        self.assertEqual(shortlist([n],{"categories":["SW"]})["results"][0]["priority_tier"],0)

    def test_arbitrary_human_decision_never_leaks(self):
        n=notice("정보시스템 개발","R26BK12345075")
        n["final"]="PRIVATE_PAYROLL_MARKER"
        result=shortlist([n],self.profile)
        self.assertNotIn("PRIVATE_PAYROLL_MARKER",json.dumps(result))
        self.assertIsNone(result["results"][0]["human_decision"])

    def test_optional_null_metadata_is_safe(self):
        n=notice("정보시스템 개발","R26BK12345076")
        n["category_evidence"]=None
        n["attachments"]=None
        self.assertEqual(shortlist([n],self.profile)["review_priority_count"],1)
        self.assertEqual(shortlist([n],{"categories":None})["results"],[])


    def test_invalid_rfp_link_identity_cannot_claim_document_category(self):
        n=notice("정보시스템 개발","R26BK12345077",doc=True)
        n["document_evidence"][0]["identity"]="c"*64
        item=shortlist([n],self.profile)["results"][0]
        self.assertEqual(item["priority_tier"],2)
        self.assertNotIn("RFP 추출본문",[e["source"] for e in item["evidence"]])

    def test_wrong_attachment_type_or_unofficial_source_is_safe(self):
        n=notice("정보시스템 개발","R26BK12345078")
        n["attachments"]=7
        self.assertEqual(shortlist([n],self.profile)["review_priority_count"],1)
        n["source"]="UNVERIFIED_IMPORT"
        self.assertEqual(shortlist([n],self.profile)["results"],[])


    def test_identifier_provenance_and_status_value_boundary(self):
        n=notice("정보시스템 개발","R26BK12345089")
        n["document_status"]="PRIVATE_PAYROLL_MARKER"
        data=shortlist([n],self.profile)
        self.assertEqual(data["results"][0]["document_status"],"UNKNOWN")
        self.assertNotIn("PRIVATE_PAYROLL_MARKER",json.dumps(data))
        n["id"]="G2B-PRIVATE-1"
        self.assertEqual(shortlist([n],self.profile)["results"],[])

    def test_extract_raw_sha_is_not_excerpt_sha(self):
        import hashlib
        n=notice("정보시스템 개발","R26BK12345090",doc=True)
        # raw-file SHA and excerpt SHA serve different purposes.
        item=n["document_evidence"][0]
        self.assertNotEqual(item["sha256"],hashlib.sha256(item["excerpt"].encode()).hexdigest())
        self.assertEqual(shortlist([n],self.profile)["results"][0]["priority_tier"],3)
        # Tier 3 is a textual signal, never a legal/technical eligibility verdict.


class HttpRankingTests(unittest.TestCase):
    def test_http_get_is_read_only_and_never_exposes_private_fields(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            board=blank()
            obj=notice("정보시스템 구축", "R26BK12345051", doc=True)
            obj["secret"]="PRIVATE_PAYROLL_MARKER"
            board["notices"]=[obj]
            raw=json.dumps(board,ensure_ascii=False).encode("utf-8")
            path=root/"dashboard.json"
            path.write_bytes(raw)
            (root/"department_profile.json").write_text(json.dumps({
                "schema_version":1,"revision":0,"categories":["SW"],
                "include_review":False}),encoding="utf-8")
            with patch.object(server,"ROOT",root):
                http=ThreadingHTTPServer(("127.0.0.1",0),server.Handler)
                worker=threading.Thread(target=http.serve_forever,daemon=True)
                worker.start()
                try:
                    endpoint=f"http://127.0.0.1:{http.server_port}/api/dashboard/recommendations"
                    with urlopen(endpoint,timeout=5) as res:
                        self.assertEqual(res.status,200)
                        data=json.load(res)
                    self.assertEqual(data["recommendations"]["review_priority_count"],1)
                    self.assertNotIn("PRIVATE_PAYROLL_MARKER",json.dumps(data))
                    self.assertTrue(all("rfp_text" not in item for item in data["recommendations"]["results"]))
                    self.assertEqual(path.read_bytes(),raw)
                finally:
                    http.shutdown();http.server_close();worker.join(timeout=5)


if __name__=="__main__":
    unittest.main()
