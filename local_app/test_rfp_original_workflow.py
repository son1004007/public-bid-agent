"""원본 파일 로컬 업로드 검증: 합성 TXT, 실제 파일과 회사정보·외부 호출 없음."""
import base64
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from unittest.mock import patch

import server
from dashboard_backend import blank
from extractors import extract_document
from rfp_original_workflow import verify
from test_rfp_coverage import item, PROFILE
from test_rfp_original_compare import setup_fixture


class OriginalWorkflowTest(unittest.TestCase):
    def test_local_offline_verify_approved_and_lifecycle_block(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            raw=b"synthetic eligibility and evaluation evidence"
            att,proof,cache=setup_fixture(root,"synthetic.txt",raw)
            n=item("500", [att],state="EXTRACTED",excerpt="synthetic")
            n["bid_no"]="R26BK0000500"
            n["bid_order"]="001"
            proof.update({"notice_id":n["id"],"notice_bid_no":n["bid_no"],
                          "notice_bid_order":n["bid_order"]})
            n["document_evidence"]=[proof]
            self.assertEqual(verify(n,root,proof["identity"],raw,extract_document)["status"],
                             "REPRODUCED_TEXT")
            self.assertEqual(verify(n,root,proof["identity"],b"different",extract_document)["status"],
                             "ORIGINAL_SHA_MISMATCH")
            self.assertEqual(verify(n,root,"x"*64,raw,extract_document)["status"],
                             "INVALID_EVIDENCE")
            copy={**n,"notice_lifecycle":"SUPERSEDED"}
            self.assertEqual(verify(copy,root,proof["identity"],raw,extract_document)["status"],
                             "NOTICE_REVIEW_BLOCKED")
            copy={**n,"rfp_review_status":"STALE"}
            self.assertEqual(verify(copy,root,proof["identity"],raw,extract_document)["status"],
                             "NOTICE_REVIEW_BLOCKED")
            copy={**n,"document_evidence":[proof,proof]}
            self.assertEqual(verify(copy,root,proof["identity"],raw,extract_document)["status"],
                             "EVIDENCE_AMBIGUOUS_OR_MISSING")
            reused={**n,"id":"G2B-ABC501-001"}
            self.assertEqual(verify(reused,root,proof["identity"],raw,extract_document)["status"],
                             "PROVENANCE_VERSION_UNVERIFIED")
            amended={**n,"bid_order":"002"}
            self.assertEqual(verify(amended,root,proof["identity"],raw,extract_document)["status"],
                             "PROVENANCE_VERSION_UNVERIFIED")
            legacy={**n,"document_evidence":[{k:v for k,v in proof.items()
                if k not in ("notice_id","notice_bid_no","notice_bid_order")}]}
            self.assertEqual(verify(legacy,root,proof["identity"],raw,extract_document)["status"],
                             "PROVENANCE_VERSION_UNVERIFIED")

    def test_http_csrf_source_and_data_immutability(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            raw=b"synthetic official evidence"
            att,proof,cache=setup_fixture(root,"synthetic.txt",raw)
            n=item("500",[att],state="EXTRACTED",excerpt="synthetic")
            n["bid_no"]="R26BK0000500"
            n["bid_order"]="001"
            proof.update({"notice_id":n["id"],"notice_bid_no":n["bid_no"],
                          "notice_bid_order":n["bid_order"]})
            n["document_evidence"]=[proof]
            state=blank()
            state["notices"]=[n]
            (root/"dashboard.json").write_text(json.dumps(state,ensure_ascii=False),encoding="utf-8")
            (root/"department_profile.json").write_text(json.dumps(
                {"schema_version":1,**PROFILE},ensure_ascii=False),encoding="utf-8")
            before={p.name:p.read_bytes() for p in root.glob("*.json")}
            before_caches={p.name:p.read_bytes() for p in (root/"rfp_fulltext").glob("*.json")}
            with patch.object(server,"ROOT",root):
                http=ThreadingHTTPServer(("127.0.0.1",0),server.Handler)
                task=threading.Thread(target=http.serve_forever,daemon=True)
                task.start()
                try:
                    url=f"http://127.0.0.1:{http.server_port}/api/dashboard/rfp-original-compare"
                    body=json.dumps({"id":n["id"],"identity":proof["identity"],
                                     "base64":base64.b64encode(raw).decode()}).encode()
                    good={"Content-Type":"application/json","Origin":f"http://127.0.0.1:{http.server_port}",
                          "X-Local-CSRF":server.TOKEN}
                    def post(headers, encoded):
                        req=Request(url,data=encoded,headers=headers,method="POST")
                        try:
                            with urlopen(req,timeout=8) as response:return response.status,json.load(response)
                        except HTTPError as err:return err.code,json.load(err)
                    denied,_=post({k:v for k,v in good.items() if k!="X-Local-CSRF"},body)
                    self.assertEqual(denied,403)
                    with patch.object(server,"extract_in_subprocess",side_effect=extract_document):
                        status,response=post(good,body)
                    self.assertEqual(status,200)
                    self.assertTrue(response["ok"])
                    self.assertFalse(response["original_file_retained"])
                    self.assertEqual(response["comparison"]["status"],"REPRODUCED_TEXT")
                    serialized=json.dumps(response,ensure_ascii=False)
                    self.assertNotIn(proof["sha256"],serialized)
                    self.assertNotIn(att["url"],serialized)
                    self.assertNotIn("synthetic official evidence",serialized)
                    self.assertEqual(before,{p.name:p.read_bytes() for p in root.glob("*.json")})
                    self.assertEqual(before_caches,{p.name:p.read_bytes() for p in (root/"rfp_fulltext").glob("*.json")})
                finally:
                    http.shutdown();http.server_close();task.join(4)


if __name__=="__main__": unittest.main()
