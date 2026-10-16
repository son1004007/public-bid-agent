"""합성 제출·평가·낙찰 기록 전이/충돌/과거 결정 보존 테스트."""
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from unittest.mock import patch

import server
from bid_outcomes import record, OutcomeConflict
from dashboard_backend import blank
from test_rfp_coverage import item


def data():
    board=blank()
    n=item("700")
    n["final"]="bid"
    n["finalReason"]="담당자 결정"
    n["rec"]="hold"
    board["notices"]=[n]
    board["history"]=[{"id":n["id"],"actor":"기존 담당자","reason":"이전 판단"}]
    return board,n["id"]


class BidOutcomeTests(unittest.TestCase):
    def test_explicit_manual_transition_history_immutable_and_terminal(self):
        state,ident=data()
        before=json.dumps(state,sort_keys=True,ensure_ascii=False)
        def push(board,stage,score=None):
            return record(board,{"id":ident,"expected_revision":board["revision"],
                "stage":stage,"observed_on":"2026-10-16","evidence_reference":"가상 제출서류 확인 기록",
                "evaluation_score":score},"2026-10-16T07:00:00+00:00")
        submitted=push(state,"SUBMITTED")
        self.assertEqual(json.dumps(state,sort_keys=True,ensure_ascii=False),before)
        self.assertEqual(submitted["notices"][0]["final"],"bid")
        self.assertEqual(submitted["notices"][0]["rec"],"hold")
        self.assertEqual(submitted["history"],state["history"])
        evaluated=push(submitted,"EVALUATED",82.5)
        awarded=push(evaluated,"AWARDED",85.25)
        self.assertEqual([x["stage"] for x in awarded["notices"][0]["submission_events"]],
                         ["SUBMITTED","EVALUATED","AWARDED"])
        with self.assertRaises(OutcomeConflict):
            push(awarded,"NOT_AWARDED")
        with self.assertRaises(OutcomeConflict):
            push(submitted,"SUBMITTED")

    def test_requires_human_bid_and_rejects_invalid_inputs(self):
        state,ident=data()
        state["notices"][0]["final"]="hold"
        payload={"id":ident,"expected_revision":state["revision"],"stage":"SUBMITTED",
                 "observed_on":"2026-10-16","evidence_reference":"가상 출처"}
        with self.assertRaises(OutcomeConflict):record(state,payload,"now")
        state["notices"][0]["final"]="bid"
        for change in ({"expected_revision":False},{"expected_revision":777},
                       {"observed_on":"2026-02-30"},{"evidence_reference":"X"},
                       {"stage":"AWARDED"},{"evaluation_score":120},
                       {"evaluation_score":True},{"evaluation_score":80.123}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                record(state,{**payload,**change},"now")

    def test_http_roundtrip_and_csrf_denial(self):
        state,ident=data()
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            source=root/"dashboard.json"
            source.write_text(json.dumps(state,ensure_ascii=False),encoding="utf-8")
            with patch.object(server,"ROOT",root):
                http=ThreadingHTTPServer(("127.0.0.1",0),server.Handler)
                thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
                try:
                    url=f"http://127.0.0.1:{http.server_port}/api/dashboard/outcome"
                    headers={"Content-Type":"application/json","Origin":f"http://127.0.0.1:{http.server_port}",
                             "X-Local-CSRF":server.TOKEN}
                    body=json.dumps({"id":ident,"expected_revision":state["revision"],"stage":"SUBMITTED",
                                     "observed_on":"2026-10-16","evidence_reference":"가상 신청서 사본"}).encode()
                    def post(h):
                        req=Request(url,data=body,headers=h,method="POST")
                        try:
                            with urlopen(req,timeout=5) as resp:return resp.status,json.load(resp)
                        except HTTPError as e:return e.code,json.load(e)
                    denied,_=post({k:v for k,v in headers.items() if k!="X-Local-CSRF"})
                    self.assertEqual(denied,403)
                    self.assertEqual(json.loads(source.read_text())["revision"],state["revision"])
                    success,response=post(headers)
                    self.assertEqual(success,200)
                    self.assertEqual(response["source"],"HUMAN_DECLARED_UNVERIFIED")
                    self.assertEqual(response["dashboard"]["notices"][0]["submission_events"][0]["stage"],"SUBMITTED")
                    self.assertEqual(response["dashboard"]["history"],state["history"])
                    conflict,_=post(headers)
                    self.assertEqual(conflict,409)
                    self.assertEqual(len(json.loads(source.read_text())["notices"][0]["submission_events"]),1)
                finally:
                    http.shutdown();http.server_close();thread.join(4)


if __name__=="__main__":unittest.main()
