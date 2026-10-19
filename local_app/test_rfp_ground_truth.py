"""BID-06 완전 합성 정답·원본 결속·충돌/멱등·범위 평가 및 HTTP 보안 검증."""
import base64
import copy
import hashlib
import json
import tempfile
import threading
import unittest
import uuid
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from unittest.mock import patch

import server
import rfp_ground_truth as gt
from test_rfp_audit_labels import fixture
from rfp_fulltext import store

STAMP = "2026-10-19T08:00:00+00:00"
SECRET = "synthetic-secret-no-operational-credentials"
RAW = b"synthetic document bytes"


def choice(ctx, *, status="APPROVED", route="TEXT"):
    doc = ctx["documents"][0]
    candidates = [c for c in ctx["candidates"] if c["identity"] == doc["identity"]]
    return {"id": ctx["id"], "expected_revision": 0, "request_id": str(uuid.uuid4()),
            "scope_id": str(uuid.uuid4()), "version_key": ctx["version_key"], "identity": doc["identity"],
            "scope": {"start": 0, "end": len(doc["text"]), "page_start": 1, "page_end": 3,
                      "location": "합성 페이지·표·각주", "route": route},
            "gold": [{"category": c["category"], "text": c["text"], "page": 1, "location": "합성 문단"}
                     for c in candidates], "status": status,
            "checks": {k: "REVIEWED" for k in gt.CHECKS},
            "official_current_confirmed": True, "independent_review_confirmed": True,
            "source_ticket": gt.source_ticket(ctx, doc["identity"], RAW, SECRET)}


class GroundTruthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.board, self.notice, _ = fixture(self.root)
        self.ctx = gt.context(self.notice, self.root)

    def approve(self, request=None, state=None, ctx=None):
        return gt.append(state or gt.initial(), ctx or self.ctx, request or choice(self.ctx), STAMP, SECRET)

    def test_no_approved_gold_means_no_numbers(self):
        view = gt.view(gt.initial(), self.ctx)
        self.assertEqual(view["evaluation"]["state"], "NOT_EVALUATED")
        self.assertTrue(all(v is None for v in view["evaluation"]["metrics"].values()))
        request = choice(self.ctx, status="HOLD");request["source_ticket"] = ""
        held = self.approve(request)
        self.assertEqual(gt.view(held, self.ctx)["evaluation"]["approved_gold_count"], 0)

    def test_approved_sample_and_scope_cannot_generalize(self):
        view = gt.view(self.approve(), self.ctx)
        self.assertEqual(view["evaluation"]["metrics"]["tp"], 3)
        self.assertEqual(view["evaluation"]["metrics"]["recall"], 1)
        self.assertEqual(view["evaluation"]["whole_document_accuracy"], "NOT_EVALUATED")
        self.assertEqual(view["evaluation"]["representativeness"], "NOT_ESTABLISHED")
        self.assertEqual(view["legal_eligibility"], "UNVERIFIED")

    def test_partial_match_is_fp_and_fn(self):
        r = choice(self.ctx);r["gold"][0]["text"] += " 원본에 있는 추가 필수조건"
        m = gt.view(self.approve(r), self.ctx)["evaluation"]["metrics"]
        self.assertEqual((m["tp"], m["fp"], m["fn"]), (2, 1, 1))
        self.assertAlmostEqual(m["f1"], 2/3)
        self.assertAlmostEqual(m["miss_rate"], 1/3)

    def test_classification_error_counts_both_categories(self):
        r = choice(self.ctx);old = r["gold"][0]["category"]
        new = next(c for c in gt.CATEGORIES if c != old);r["gold"][0]["category"] = new
        m = gt.view(self.approve(r), self.ctx)["evaluation"]
        self.assertEqual(m["by_category"][old]["fp"], 1)
        self.assertEqual(m["by_category"][new]["fn"], 1)

    def test_manual_missing_table_footnote_image_ocr(self):
        for route in gt.ROUTES:
            with self.subTest(route=route):
                r = choice(self.ctx, route=route)
                r["gold"].append({"category":"participation", "text":"원본에만 존재하는 누락 면허 요건", "page":3, "location":"각주 2/표 1"})
                m = gt.view(self.approve(r), self.ctx)["evaluation"]
                self.assertEqual(m["metrics"]["fn"], 1)
                self.assertEqual(m["by_route"][route]["fn"], 1)
                self.assertEqual(m["approved_gold_count"], 4)

    def test_duplicate_predictions_one_to_one(self):
        r = choice(self.ctx);state = self.approve(r);e = copy.deepcopy(state["events"][0])
        e["predictions"].append(copy.deepcopy(e["predictions"][0]))
        m = gt.evaluate([e])["metrics"]
        self.assertEqual((m["tp"],m["fp"],m["fn"]),(3,1,0))
        r["gold"].append(copy.deepcopy(r["gold"][0]))
        with self.assertRaises(ValueError):self.approve(r)

    def test_whitespace_nfc_only_no_fuzzy_invention(self):
        r = choice(self.ctx);r["gold"][0]["text"] = r["gold"][0]["text"].replace(" ", "\n  ")
        self.assertEqual(gt.view(self.approve(r),self.ctx)["evaluation"]["metrics"]["tp"],3)
        self.assertNotEqual(gt.normalized("ABC."),gt.normalized("abc"))

    def test_no_gold_even_approved_negative_has_null_metrics(self):
        r = choice(self.ctx);r["gold"] = []
        m = gt.view(self.approve(r),self.ctx)["evaluation"]
        self.assertEqual(m["state"],"NOT_EVALUATED");self.assertIsNone(m["metrics"]["fp"])

    def test_current_source_changed_or_stale_invalidates_approval(self):
        state = self.approve()
        for changes in ({"rfp_review_status":"STALE"},{"notice_lifecycle":"CANCELLED"},
                        {"notice_kind":"취소공고"},{"bid_order":"002"},{"document_status":"FAILED"}):
            ctx = gt.context({**self.notice,**changes},self.root)
            v = gt.view(state,ctx)
            self.assertEqual(v["evaluation"]["state"],"NOT_EVALUATED")
            self.assertEqual(v["stale_scope_count"],1)
            self.assertEqual(len(state["events"]),1)

    def test_sha_cache_and_legacy_version_mismatch_hold(self):
        for mutation in ({"sha256":"0"*64},{"notice_bid_order":"002"},{"notice_id":None}):
            n = copy.deepcopy(self.notice);n["document_evidence"][0].update(mutation)
            ctx = gt.context(n,self.root)
            if ctx["documents"]:
                with self.assertRaises(gt.ReviewConflict):gt.source_ticket(ctx,ctx["documents"][0]["identity"],RAW,SECRET)
            else:self.assertEqual(ctx["candidates"],[])

    def test_conflicting_duplicate_proofs_not_accepted(self):
        n = copy.deepcopy(self.notice);n["document_evidence"].append(copy.deepcopy(n["document_evidence"][0]))
        self.assertEqual(gt.context(n,self.root)["documents"],[])

    def test_ticket_tamper_expiry_restart_or_other_document(self):
        r = choice(self.ctx)
        for token in ("",r["source_ticket"]+"x",gt.source_ticket(self.ctx,r["identity"],RAW,SECRET,clock=0)):
            r["source_ticket"] = token
            with self.assertRaises(gt.ReviewConflict):self.approve(r)
        r = choice(self.ctx)
        with self.assertRaises(gt.ReviewConflict):gt.append(gt.initial(),self.ctx,r,STAMP,"different-server-secret")
        with self.assertRaises(gt.ReviewConflict):gt.source_ticket(self.ctx,r["identity"],b"wrong file",SECRET)

    def test_human_confirmations_required_and_boolean_strict(self):
        for mutation in ({"independent_review_confirmed":False},{"official_current_confirmed":False},
                         {"official_current_confirmed":"yes"},{"checks":{k:"UNKNOWN" for k in gt.CHECKS}},
                         {"checks":{k:"NOT_APPLICABLE" for k in gt.CHECKS}}):
            r = choice(self.ctx);r.update(mutation)
            with self.assertRaises(ValueError):self.approve(r)

    def test_conflict_and_identical_resubmission_no_duplicate_event(self):
        r = choice(self.ctx);saved = self.approve(r)
        self.assertIs(self.approve(r,state=saved),saved)
        altered = copy.deepcopy(r);altered["status"]="HOLD"
        with self.assertRaises(gt.ReviewConflict):self.approve(altered,state=saved)
        r2=choice(self.ctx)
        with self.assertRaises(gt.ReviewConflict):self.approve(r2,state=saved)

    def test_edit_and_hold_preserve_approval_history(self):
        r=choice(self.ctx);saved=self.approve(r)
        r.update(request_id=str(uuid.uuid4()),expected_revision=1,status="HOLD",source_ticket="")
        revised=self.approve(r,state=saved)
        self.assertEqual(len(revised["events"]),2)
        self.assertEqual(revised["events"][0]["status"],"APPROVED")
        self.assertEqual(gt.view(revised,self.ctx)["evaluation"]["state"],"NOT_EVALUATED")

    def test_approved_overlapping_scope_rejected(self):
        saved=self.approve();r=choice(self.ctx);r["expected_revision"]=1
        with self.assertRaises(gt.ReviewConflict):self.approve(r,state=saved)

    def test_bad_bounds_pages_duplicate_gold_and_unknown_fields(self):
        for mutation in ({"page_start":True},{"page_end":0},{"end":99999},{"start":1},{"location":""}):
            r=choice(self.ctx);r["scope"].update(mutation)
            with self.assertRaises(ValueError):self.approve(r)
        r=choice(self.ctx);r["gold"][0]["page"]=4
        with self.assertRaises(ValueError):self.approve(r)
        r=choice(self.ctx);r["sensitive_extra"]="not allowed"
        with self.assertRaises(ValueError):self.approve(r)

    def test_changed_extraction_version_requires_new_review(self):
        saved=self.approve();changed=copy.deepcopy(self.ctx);changed["version_key"]="0"*64
        self.assertEqual(gt.view(saved,changed)["stale_scope_count"],1)
        with self.assertRaises(gt.ReviewConflict):self.approve(choice(self.ctx),ctx=changed)

    def test_load_no_creation_corrupt_size_and_schema_fail_closed(self):
        before=list(self.root.iterdir());self.assertEqual(gt.load(self.root),gt.initial())
        self.assertEqual(list(self.root.iterdir()),before)
        p=self.root/gt.FILE_NAME;p.write_text('{"schema_version":1,"schema_version":1}')
        with self.assertRaises(ValueError):gt.load(self.root)
        p.write_bytes(b'x'*(gt.MAX_BYTES+1))
        with self.assertRaises(ValueError):gt.load(self.root)
        good=self.approve();good["events"][0]["status"]="APPROVED_BY_AI"
        with self.assertRaises(ValueError):gt.validate(good)

    def test_pretty_serialized_save_cap_preserves_previous_state(self):
        r=choice(self.ctx);state=gt.initial();saved=self.approve(r)
        compact=len(json.dumps(saved,ensure_ascii=False).encode())
        pretty=len(json.dumps(saved,ensure_ascii=False,indent=2).encode())
        self.assertGreater(pretty,compact)
        with patch.object(gt,'MAX_BYTES',(pretty+compact)//2):
            with self.assertRaises(gt.ReviewConflict):self.approve(r,state=state)
        self.assertEqual(state,gt.initial())

    def test_parser_truncation_stays_visible_and_no_whole_doc_accuracy(self):
        n=copy.deepcopy(self.notice);proof=n["document_evidence"][0]
        ref=store(self.root,proof["sha256"],{"text":"입찰참가자격: 원본 일부만 추출", "characters":10000,"truncated":True})
        proof.update(ref);proof["warnings"]=["synthetic OCR warning"]
        ctx=gt.context(n,self.root)
        self.assertTrue(ctx["documents"][0]["truncated"])
        self.assertTrue(ctx["documents"][0]["parser_warnings_present"])
        m=gt.view(self.approve(choice(ctx),ctx=ctx),ctx)["evaluation"]
        self.assertEqual(m["whole_document_accuracy"],"NOT_EVALUATED")


class GroundTruthHttpTests(unittest.TestCase):
    def test_http_csrf_sha_save_idempotence_conflict_and_sources_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);board,n,_=fixture(root)
            (root/'dashboard.json').write_text(json.dumps(board,ensure_ascii=False),encoding='utf-8')
            before={p:p.read_bytes() for p in root.rglob('*') if p.is_file()}
            with patch.object(server,'ROOT',root):
                h=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
                thread=threading.Thread(target=h.serve_forever,daemon=True);thread.start()
                base=f'http://127.0.0.1:{h.server_port}'
                def call(path,body=None,csrf=True,origin=True,host=True):
                    headers={'Content-Type':'application/json'}
                    if csrf:headers['X-Local-CSRF']=server.TOKEN
                    if origin:headers['Origin']=base
                    if not host:headers['Host']='malicious.invalid'
                    req=Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
                    try:
                        with urlopen(req,timeout=8) as r:return r.status,json.load(r)
                    except HTTPError as e:return e.code,json.load(e)
                try:
                    path='/api/dashboard/rfp-ground-truth';code,data=call(path+'?id='+n['id']);self.assertEqual(code,200)
                    ctx=data['review']['context'];r=choice(ctx)
                    source={'id':n['id'],'version_key':ctx['version_key'],'identity':r['identity'],'base64':base64.b64encode(RAW).decode()}
                    for args in ({'csrf':False},{'origin':False},{'host':False}):self.assertEqual(call(path+'/save',r,**args)[0],403)
                    self.assertFalse((root/gt.FILE_NAME).exists())
                    self.assertEqual(call(path+'?id=../PRIVATE')[0],400)
                    self.assertEqual(call(path+'?id=G2B-MISSING-001')[0],404)
                    self.assertEqual(call(path,host=False)[0],403)
                    code,checked=call(path+'/source-check',source);self.assertEqual(code,200)
                    r['source_ticket']=checked['source_ticket']
                    self.assertEqual(call(path+'/save',r)[0],200)
                    saved=(root/gt.FILE_NAME).read_bytes()
                    self.assertEqual(call(path+'/save',r)[0],200);self.assertEqual((root/gt.FILE_NAME).read_bytes(),saved)
                    r['gold'][0]['text']+=' changed'
                    self.assertEqual(call(path+'/save',r)[0],409)
                    source['base64']=base64.b64encode(b'wrong').decode()
                    self.assertEqual(call(path+'/source-check',source)[0],409)
                    for p,body in before.items():self.assertEqual(p.read_bytes(),body)
                    original_context=gt.context
                    def changing_snapshot(notice,folder):
                        result=original_context(notice,folder)
                        changed=copy.deepcopy(board);changed['revision']+=1
                        (root/'dashboard.json').write_text(json.dumps(changed),encoding='utf-8')
                        return result
                    with patch.object(gt,'context',side_effect=changing_snapshot):
                        self.assertEqual(call(path+'?id='+n['id'])[0],503)
                    (root/'dashboard.json').write_bytes(before[root/'dashboard.json'])
                    (root/gt.FILE_NAME).write_text('PRIVATE_BROKEN_FILE')
                    code,data=call(path+'?id='+n['id']);self.assertEqual(code,503)
                    self.assertNotIn('PRIVATE_BROKEN_FILE',json.dumps(data))
                    self.assertNotIn(str(root),json.dumps(data))
                finally:h.shutdown();h.server_close();thread.join(5)


if __name__=='__main__':unittest.main()
