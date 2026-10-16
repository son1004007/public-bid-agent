"""사람 텍스트 근거 라벨 - 완전 합성, 실 원본·개인정보·외부 통신 없음."""
import hashlib
import json
import tempfile
import threading
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from unittest.mock import patch

import server
from dashboard_backend import blank,normalize
from rfp_fulltext import store
from rfp_requirements import structure
from rfp_audit_labels import initial,append,summarize,validate,AuditConflict

TEXT="입찰참가자격: 소프트웨어사업자 등록 의무\n평가기준: 기술평가 80점\n과업범위: API 연계 시스템 구축\n"

def fixture(root):
    n=normalize({"bidNtceNo":"R26BK12000001","bidNtceOrd":"000",
      "bidNtceNm":"합성 용역","bidClseDt":"2099-12-31 18:00:00",
      "pubPrcrmntClsfcNm":"소프트웨어개발",
      "ntceSpecFileNm1":"제안요청서.pdf","ntceSpecDocUrl1":"https://www.g2b.go.kr/doc.pdf"})
    original=hashlib.sha256(b"synthetic document bytes").hexdigest()
    ref=store(root,original,{"text":TEXT,"characters":len(TEXT),"truncated":False})
    attached=n["attachments"][0]
    identity=hashlib.sha256((attached["url"]+"\n"+attached["name"]).encode()).hexdigest()
    proof={"identity":identity,"name":attached["name"],
           "status":"EXTRACTED","sha256":original,"excerpt":TEXT,
           "notice_id":n["id"],"notice_bid_no":n["bid_no"],
           "notice_bid_order":n["bid_order"],**ref}
    n.update({"document_status":"EXTRACTED","rfp_text":TEXT,"document_evidence":[proof]})
    board=blank();board["notices"]=[n]
    report=structure(n,root)
    return board,n,report

def choice(n,report,revision=0,label="SUPPORTED_SIGNAL"):
    group=next(x for x in report["requirements"] if x["category"]=="participation")
    ev=group["items"][0]["evidence"]
    return {"expected_revision":revision,"id":n["id"],"category":"participation",
      "label":label,"evidence":{
        "source_sha256":ev["source_sha256"],"fulltext_ref":ev["fulltext_ref"],
        "offset_start":ev["offset_start"],"offset_end":ev["offset_end"],
        "excerpt_sha256":hashlib.sha256(ev["excerpt"].encode()).hexdigest()}}

class RfpAuditLabelTests(unittest.TestCase):
    def test_human_label_no_ground_truth_or_private_text_and_conflict(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);board,n,report=fixture(root)
            before=json.dumps(board,ensure_ascii=False,sort_keys=True)
            saved=append(initial(),n,report,choice(n,report),"2026-10-16T12:00:00Z")
            self.assertEqual(saved["revision"],1)
            self.assertEqual(json.dumps(board,ensure_ascii=False,sort_keys=True),before)
            self.assertEqual(saved["events"][0]["provenance"],"VERSION_MATCHED")
            self.assertNotIn("소프트웨어사업자",json.dumps(saved,ensure_ascii=False))
            view=summarize(saved,n,report)
            self.assertEqual(view["current_label_counts"]["SUPPORTED_SIGNAL"],1)
            self.assertEqual(view["recall"],"NOT_MEASURABLE")
            self.assertEqual(view["current_reviewed_unique"],1)
            revised=append(saved,n,report,choice(n,report,revision=1,label="FALSE_POSITIVE"),"2026-10-16T12:00:00Z")
            current=summarize(revised,n,report)
            self.assertEqual(len(revised["events"]),2)
            self.assertEqual(current["current_label_counts"]["SUPPORTED_SIGNAL"],0)
            self.assertEqual(current["current_label_counts"]["FALSE_POSITIVE"],1)
            self.assertEqual(current["current_reviewed_unique"],1)
            with self.assertRaises(AuditConflict):
                append(saved,n,report,choice(n,report),"2026-10-16T12:00:00Z")
            corrupt=choice(n,report,revision=1)
            corrupt["evidence"]["offset_start"]+=1
            with self.assertRaises(AuditConflict):
                append(saved,n,report,corrupt,"2026-10-16T12:00:00Z")
            changed={**n,"bid_order":"001"}
            self.assertEqual(summarize(saved,changed,report)["records"][0]["status"],"STALE_REVIEW")
            old={**n,"document_evidence":[{k:v for k,v in n["document_evidence"][0].items()
                if k not in ("notice_id","notice_bid_no","notice_bid_order")}]}
            legacy=append(initial(),old,report,choice(n,report),"2026-10-16T12:00:00Z")
            self.assertEqual(legacy["events"][0]["provenance"],"VERSION_UNVERIFIED")

    def test_corrupt_persisted_event_schema_fails_closed(self):
        import copy
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);_,n,report=fixture(root)
            good=append(initial(),n,report,choice(n,report),"2026-10-16T12:00:00Z")
            variants=[
                {"label":"BOGUS"}, {"category":"licenses"}, {"provenance":"VERSION_MATCHED_HACK"},
                {"source":"AUTOMATIC_CONFIRMED"}, {"rfp_schema_version":True},
                {"id":"G2B-../../forged"}, {"bid_order":"bad"}, {"recorded_at":"now"},
                {"evidence":{**good["events"][0]["evidence"],"offset_start":True}},
                {"evidence":{**good["events"][0]["evidence"],"fulltext_ref":"0"*63}},
                {"extra_sensitive":"MUST_NOT_ACCEPT"}
            ]
            for mutation in variants:
                with self.subTest(mutation=mutation):
                    fake=copy.deepcopy(good)
                    fake["events"][0].update(mutation)
                    with self.assertRaises(ValueError):
                        validate(fake)
                    with self.assertRaises(ValueError):
                        summarize(fake,n,report)
            missing=copy.deepcopy(good);del missing["events"][0]["label"]
            with self.assertRaises(ValueError):validate(missing)

    def test_http_csrf_input_validation_and_no_dashboard_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);board,n,report=fixture(root)
            file=root/"dashboard.json"
            file.write_text(json.dumps(board,ensure_ascii=False),encoding="utf-8")
            before=file.read_bytes()
            with patch.object(server,"ROOT",root):
                h=ThreadingHTTPServer(("127.0.0.1",0),server.Handler)
                thread=threading.Thread(target=h.serve_forever,daemon=True);thread.start()
                base=f"http://127.0.0.1:{h.server_port}"
                try:
                    req=Request(base+"/api/dashboard/rfp-audit?id="+n["id"])
                    with urlopen(req,timeout=5) as response:
                        self.assertEqual(response.status,200)
                        self.assertEqual(json.load(response)["audit"]["revision"],0)
                    body=json.dumps(choice(n,report)).encode()
                    headers={"Content-Type":"application/json","Origin":base,"X-Local-CSRF":server.TOKEN}
                    def post(headers):
                        req=Request(base+"/api/dashboard/rfp-audit/save",data=body,
                                    headers=headers,method="POST")
                        try:
                            with urlopen(req,timeout=5) as resp:return resp.status,json.load(resp)
                        except HTTPError as err:return err.code,json.load(err)
                    code,_=post({k:v for k,v in headers.items() if k!="X-Local-CSRF"})
                    self.assertEqual(code,403)
                    code,data=post(headers)
                    self.assertEqual(code,200)
                    self.assertEqual(data["audit"]["current_label_counts"]["SUPPORTED_SIGNAL"],1)
                    self.assertEqual(post(headers)[0],409)
                    self.assertEqual(file.read_bytes(),before)
                    self.assertEqual(len(json.loads((root/"rfp_review_annotations.json").read_text())["events"]),1)
                    self.assertNotIn("소프트웨어사업자",(root/"rfp_review_annotations.json").read_text())
                finally:
                    h.shutdown();h.server_close();thread.join(5)

if __name__=="__main__":unittest.main()
