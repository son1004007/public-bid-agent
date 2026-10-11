"""공식 수집 어댑터 및 대시보드 HTTP 계약의 네트워크 비의존 회귀 테스트.

실제 serviceKey/사용자 운영 JSON을 읽거나 외부 제공자에 요청하지 않는다.
"""
import io
import json
import os
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import server
import dashboard_backend as db
from decision_profiles import default_state as default_profiles

RAW = {
    "bidNtceNo": "202610110001", "bidNtceOrd": "00",
    "bidNtceNm": "공공 AI 데이터 분석 플랫폼 용역",
    "ntceInsttNm": "가상 시험기관",
    "asignBdgtAmt": "150000000",
    "bidClseDt": "2026-10-20 10:00:00",
    "bidNtceDtlUrl": "https://www.g2b.go.kr/",
}


class _Stream(io.BytesIO):
    def geturl(self):
        return db.API_URL


class FakeTransport:
    def __init__(self, documents):
        self.documents = documents
        self.count = 0

    def open(self, request, timeout):
        self.count += 1
        self.request = request
        return _Stream(json.dumps(self.documents[self.count - 1]).encode())


def response(rows, total=None, code="00"):
    return {"response": {"header": {"resultCode": code},
                         "body": {"items": {"item": rows}, "totalCount": len(rows) if total is None else total}}}


class ProcurementUnitTests(unittest.TestCase):
    def test_provider_selects_and_normalizes_provenance(self):
        raw = {**RAW, "bidNtceDtlUrl": "javascript:alert(1)"}
        n = db.normalize(raw)
        self.assertEqual(n["id"], "G2B-202610110001-00")
        self.assertEqual(n["source"], "G2B_OFFICIAL_API")
        self.assertIsNone(n["source_url"])
        self.assertIsNone(n["fit"])
        self.assertIsNone(n["margin"])
        self.assertEqual(n["hard"], "unknown")
        retained = db.normalize({**RAW, "bidNtceNm": "사무실 책상 구매"})
        self.assertIsNotNone(retained)
        self.assertEqual(retained["department_status"], "REVIEW")
        self.assertEqual(retained["legal_eligibility"], "UNVERIFIED")
        with self.assertRaises(db.ProviderError):
            db.normalize({"bidNtceNm": "AI 용역"})

    def test_page_contract_and_fail_closed(self):
        t = FakeTransport([response([RAW])])
        values, scanned = db.collect("synthetic-test-key-12345", datetime(2026, 10, 11, tzinfo=timezone(timedelta(hours=9))), t)
        self.assertEqual(scanned, 1)
        self.assertEqual(len(values), 1)
        self.assertIn("ServiceKey=synthetic-test-key-12345", t.request.full_url)
        self.assertEqual(t.count, 1)
        for wrong in (response([RAW], code="20"), {"response": {"header": {"resultCode": "00"}, "body": {}}}):
            with self.assertRaises(db.ProviderError):
                db.collect("synthetic-test-key-12345", transport=FakeTransport([wrong]))
        with self.assertRaises(db.ProviderError):
            db.collect("", transport=t)

    def test_snapshot_decision_and_revision(self):
        state = db.blank()
        notice = db.normalize(RAW)
        state = db.update_collection(state, [notice], 1, "2026-10-11T00:00:00")
        self.assertEqual(state["revision"], 1)
        state2 = db.record_action(state, {"expected_revision": 1, "id": notice["id"], "kind": "recommendation"},
                                  default_profiles(), "2026-10-11T00:00:02")
        self.assertEqual(state2["notices"][0]["rec"], "hold")
        self.assertIsNone(state2["notices"][0]["final"])
        self.assertEqual(len(state2["history"]), 1)
        self.assertEqual(state2["history"][0]["source"], "G2B_OFFICIAL_API")
        self.assertIn("weights_snapshot", state2["history"][0])
        self.assertEqual(state["notices"][0]["rec"], None)
        with self.assertRaises(db.DashboardConflict):
            db.record_action(state2, {"expected_revision": 1, "id": notice["id"], "kind": "human_bid", "reason": "검토"},
                             default_profiles(), "2026-10-11T00:00:03")
        with self.assertRaises(ValueError):
            db.record_action(state2, {"expected_revision": 2, "id": notice["id"], "kind": "human_bid", "reason": ""},
                             default_profiles(), "2026-10-11T00:00:04")
        state3 = db.record_action(state2, {"expected_revision": 2, "id": notice["id"], "kind": "human_no_bid",
                                          "reason": "사내 검토 결과 불참"}, default_profiles(), "2026-10-11T00:00:05")
        self.assertEqual(state3["notices"][0]["final"], "no_bid")
        self.assertEqual(len(state3["history"]), 2)
        refreshed = db.update_collection(state3, [{**notice, "title": "AI 데이터 분석 수정 공고"}], 1, "later")
        self.assertEqual(refreshed["notices"][0]["final"], "no_bid")
        self.assertEqual(len(refreshed["history"]), 2)
        self.assertEqual(db.failed_collection(refreshed, "error")["notices"], refreshed["notices"])


class DashboardHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.root_patch = patch.object(server, "ROOT", root)
        self.file_patch = patch.object(server, "FILE", root / "cases.json")
        self.root_patch.start()
        self.file_patch.start()
        # 사용자 Windows DPAPI에 실키가 등록돼 있어도 unittest는 그 키를 읽지 않는다.
        # 이 서버 테스트는 명시된 합성 환경변수만 사용해 완전 격리한다.
        self.key_patch = patch.object(server, "procurement_key",
                                      side_effect=lambda: os.environ.get(db.KEY_ENV) or None)
        self.available_patch = patch.object(server, "key_available",
                                            side_effect=lambda: bool(os.environ.get(db.KEY_ENV)))
        self.key_patch.start()
        self.available_patch.start()
        server.persist({"schema_version": 1, "cases": [{"id": "old-case", "title": "preserve"}]})
        self.original = (root / "cases.json").read_bytes()
        self.root = root
        self.http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.http.server_port}"

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(timeout=4)
        self.available_patch.stop()
        self.key_patch.stop()
        self.root_patch.stop()
        self.file_patch.stop()
        self.temp.cleanup()

    def get(self):
        with urlopen(self.base + "/api/dashboard", timeout=5) as r:
            return r.status, json.load(r)

    def post(self, url, body, headers=True):
        hdr = {"Content-Type": "application/json"}
        if headers:
            hdr.update({"Origin": self.base, "X-Local-CSRF": server.TOKEN})
        req = Request(self.base + url, json.dumps(body).encode(), headers=hdr, method="POST")
        try:
            with urlopen(req, timeout=5) as response:
                return response.status, json.load(response)
        except HTTPError as response:
            return response.code, json.load(response)

    def test_reclassify_existing_record_preserves_human_history(self):
        state = db.update_collection(db.blank(),[db.normalize(RAW)],1,"initial")
        state["notices"][0]["department_categories"] = []
        state["notices"][0]["department_status"] = "REVIEW"
        state["notices"][0]["final"] = "hold"
        state["history"] = [{"id":state["notices"][0]["id"],"reason":"사전 검토 메모"}]
        server.persist(state,self.root/"dashboard.json")
        status,payload=self.post("/api/dashboard/reclassify",{})
        self.assertEqual(status,200)
        self.assertEqual(payload["updated"],1)
        self.assertIn("AI",payload["dashboard"]["notices"][0]["department_categories"])
        self.assertEqual(payload["dashboard"]["notices"][0]["final"],"hold")
        self.assertEqual(payload["dashboard"]["history"],state["history"])
        self.assertEqual((self.root/"cases.json").read_bytes(),self.original)

    def test_enrich_official_document_mock_keeps_separate_human_decision(self):
        state=db.update_collection(db.blank(),[db.normalize(RAW)],1,"initial")
        state["notices"][0]["final"]="no_bid"
        server.persist(state,self.root/"dashboard.json")
        with patch.object(server,"extract_official_document",return_value={
                "text":"주요 과업: LLM 서비스 구현과 데이터 파이프라인 구축",
                "source_name":"제안요청서.hwpx",
                "warnings":[]}) as mock:
            status,result=self.post("/api/dashboard/enrich",{"id":state["notices"][0]["id"]})
        self.assertEqual(status,200)
        mock.assert_called_once()
        new=result["dashboard"]["notices"][0]
        self.assertEqual(new["document_status"],"EXTRACTED")
        self.assertIn("데이터 파이프라인",new["rfp_text"])
        self.assertIn("DATA",new["department_categories"])
        self.assertEqual(new["final"],"no_bid")
        self.assertEqual((self.root/"cases.json").read_bytes(),self.original)

    def test_department_categories_save_and_conflict(self):
        with urlopen(self.base+"/api/department-profile",timeout=5) as response:
            self.assertEqual(response.status,200)
            self.assertEqual(json.load(response)["profile"]["revision"],0)
        status,body=self.post("/api/department-profile/save",{
            "expected_revision":0,"profile":{"categories":["DATA","SECURITY"],"include_review":False}
        })
        self.assertEqual(status,200)
        self.assertEqual(body["profile"]["categories"],["DATA","SECURITY"])
        self.assertEqual(self.post("/api/department-profile/save",{
            "expected_revision":0,"profile":{"categories":["AI"],"include_review":True}
        })[0],409)
        self.assertEqual((self.root/"cases.json").read_bytes(),self.original)

    def test_no_key_is_explicit_not_demo(self):
        with patch.dict(os.environ, {db.KEY_ENV: ""}):
            status, initial = self.get()
            self.assertEqual(status, 200)
            self.assertFalse(initial["collection_available"])
            self.assertEqual(initial["dashboard"]["notices"], [])
            self.assertEqual(self.post("/api/dashboard/collect", {})[0], 424)
            self.assertFalse((self.root / "dashboard.json").exists())
            self.assertEqual(self.post("/api/dashboard/action", {"expected_revision": 0, "id": "DEMO-AI-001", "kind": "recommendation"})[0], 400)

    def test_collection_and_human_decisions_persist_separately(self):
        with patch.dict(os.environ, {db.KEY_ENV: "SYNTHETIC-KEY-FOR-TEST-123456"}):
            with patch.object(server, "fetch_official_notices", return_value=([db.normalize(RAW)], 1)):
                status, payload = self.post("/api/dashboard/collect", {})
        self.assertEqual(status, 200)
        self.assertEqual(payload["dashboard"]["collection"]["last_scanned"], 1)
        ident = payload["dashboard"]["notices"][0]["id"]
        self.assertEqual(self.post("/api/dashboard/action",
                    {"expected_revision": 1, "id": ident, "kind": "recommendation"})[0], 200)
        self.assertEqual(self.post("/api/dashboard/action",
                    {"expected_revision": 1, "id": ident, "kind": "human_bid", "reason": "가상 검토"})[0], 409)
        self.assertEqual(self.post("/api/dashboard/action",
                    {"expected_revision": 2, "id": ident, "kind": "human_bid", "reason": "가상 검토"})[0], 200)
        _, loaded = self.get()
        self.assertEqual(len(loaded["dashboard"]["history"]), 2)
        self.assertEqual(loaded["dashboard"]["notices"][0]["final"], "bid")
        self.assertEqual((self.root / "cases.json").read_bytes(), self.original)
        self.assertFalse((self.root / "operations.json").exists())

    def test_seven_day_collection_deduplicates_across_days(self):
        with patch.dict(os.environ, {db.KEY_ENV: "SYNTHETIC-KEY-FOR-TEST-123456"}):
            with patch.object(server, "fetch_official_notices", return_value=([db.normalize(RAW)], 1)) as fetcher:
                code, response = self.post("/api/dashboard/collect", {"days": 7})
        self.assertEqual(code, 200)
        self.assertEqual(fetcher.call_count, 7)
        self.assertEqual(response["dashboard"]["collection"]["lookback_days"], 7)
        self.assertEqual(response["dashboard"]["collection"]["last_scanned"], 7)
        self.assertEqual(response["dashboard"]["collection"]["last_count"], 1)
        self.assertEqual(len(response["dashboard"]["notices"]), 1)
        self.assertEqual((self.root / "cases.json").read_bytes(), self.original)
        for invalid in (0, 2, 30, True, "7"):
            self.assertEqual(self.post("/api/dashboard/collect", {"days": invalid})[0], 400)

    def test_seven_day_partial_failure_preserves_previous_records(self):
        prior = db.update_collection(db.blank(), [db.normalize(RAW)], 1, "initial")
        server.persist(prior, self.root / "dashboard.json")
        with patch.dict(os.environ, {db.KEY_ENV: "SYNTHETIC-KEY-FOR-TEST-123456"}):
            with patch.object(server, "fetch_official_notices",
                    side_effect=[([db.normalize(RAW)], 1), db.ProviderError("simulated provider failure")]):
                code, _ = self.post("/api/dashboard/collect", {"days": 7})
        self.assertEqual(code, 503)
        _, loaded = self.get()
        self.assertEqual(loaded["dashboard"]["collection"]["status"], "ERROR")
        self.assertEqual(loaded["dashboard"]["notices"], prior["notices"])
        self.assertEqual(loaded["dashboard"]["history"], prior["history"])
        self.assertEqual((self.root / "cases.json").read_bytes(), self.original)

    def test_csrf_and_failed_provider_keep_previous(self):
        self.assertEqual(self.post("/api/dashboard/collect", {}, headers=False)[0], 403)
        server.persist(db.update_collection(db.blank(), [db.normalize(RAW)], 1, "initial"),
                       self.root / "dashboard.json")
        with patch.dict(os.environ, {db.KEY_ENV: "SYNTHETIC-KEY-FOR-TEST-123456"}):
            with patch.object(server, "fetch_official_notices", side_effect=db.ProviderError("upstream failed")):
                status, _ = self.post("/api/dashboard/collect", {})
        self.assertEqual(status, 503)
        _, loaded = self.get()
        self.assertEqual(len(loaded["dashboard"]["notices"]), 1)
        self.assertEqual(loaded["dashboard"]["collection"]["status"], "ERROR")
        (self.root / "dashboard.json").write_text("{", encoding="utf8")
        response = self.get  # broken state must not be hidden as 0 results
        with self.assertRaises(HTTPError) as error:
            with urlopen(self.base + "/api/dashboard", timeout=5) as r:
                r.read()
        self.assertEqual(error.exception.code, 503)
        self.assertEqual((self.root / "dashboard.json").read_text(), "{")


if __name__ == "__main__":
    unittest.main()
