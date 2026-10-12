"""RFP 확보 병목 집계 합성 테스트: 사용자 원본 JSON 접근 없음."""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.request import urlopen
from unittest.mock import patch

import server
from rfp_coverage import summarize
from dashboard_backend import blank

PROFILE = {"categories": ["SW"], "revision": 0, "include_review": False}
URL = "https://www.g2b.go.kr/document"


def item(ident, attachments=None, *, state="PENDING", excerpt="", end="2099-12-31T23:59:59"):
    return {"id": f"G2B-ABC{ident}-001", "title": "합성 공고", "end": end,
            "notice_kind": "일반공고", "qualification_deadline": "",
            "department_status": "CANDIDATE", "department_categories": ["SW"],
            "document_status": state, "rfp_text": excerpt,
            "attachments": attachments if attachments is not None else []}


class CoverageTests(unittest.TestCase):
    def test_full_diagnostic_and_active_only(self):
        notices = [
            item("1", [{"name": "과업요청.pdf", "url": URL}]),
            item("2", [{"name": "공고원문.hwp", "url": URL}], state="EXTRACTED", excerpt="실제 내용"),
            item("3", [{"name": "원문.pdf", "url": URL}], state="FAILED"),
            item("4", [{"name": "첨부.exe", "url": URL}]),
            item("5", [{"name": "원문.pdf", "url": "https://evil.example/x.pdf"}]),
            item("6", [{"name": "과업.pdf", "url": URL}], end="2020-01-01T12:00:00")
        ]
        report = summarize(notices, PROFILE)
        self.assertEqual(report["candidate_count"], 6)
        self.assertEqual(report["active_candidate_count"], 5)
        self.assertEqual(report["by_state_active"], {
            "EXTRACTED_TEXT": 1, "FAILED_ATTEMPT": 1, "READY_TO_FETCH": 1,
            "UNSUPPORTED_FORMAT": 1, "MISSING_OFFICIAL_LINK": 1,
            "INVALID_ATTACHMENTS": 0})
        self.assertEqual(report["unprocessed_active"], 3)
        self.assertEqual(report["failed_active"], 1)
        self.assertNotIn("URL", json.dumps(report))

    def test_outside_profile_excluded_and_malformed_files_fail_closed(self):
        broken=item("1")
        broken["attachments"]={"name":"x.pdf"}
        not_selected=item("2",[{"name":"원문.pdf","url":URL}])
        not_selected["department_categories"]=["AI"]
        review=item("3",[{"name":"원문.pdf","url":URL}])
        review["department_status"]="REVIEW"
        report=summarize([broken,not_selected,review],PROFILE)
        self.assertEqual(report["candidate_count"],1)
        self.assertEqual(report["by_state_active"]["INVALID_ATTACHMENTS"],1)
        self.assertEqual(summarize([broken],{"categories":[]})["candidate_count"],0)
        with self.assertRaises(ValueError):summarize({},PROFILE)

    def test_local_http_no_secret_fields_no_original_writes(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            board=blank()
            doc=item("123",[{"name":"제안요청.pdf","url":URL}])
            doc["sensitive"]="SECRET_DO_NOT_RETURN"
            board["notices"]=[doc]
            path=root/"dashboard.json"
            path.write_text(json.dumps(board,ensure_ascii=False),encoding="utf-8")
            profile=root/"department_profile.json"
            profile.write_text(json.dumps({
                "schema_version":1,**PROFILE}),encoding="utf-8")
            before=path.read_bytes(),profile.read_bytes()
            with patch.object(server,"ROOT",root):
                http=ThreadingHTTPServer(("127.0.0.1",0),server.Handler)
                task=threading.Thread(target=http.serve_forever,daemon=True)
                task.start()
                try:
                    url=f"http://127.0.0.1:{http.server_port}/api/dashboard/rfp-coverage"
                    with urlopen(url,timeout=5) as response:
                        self.assertEqual(response.status,200)
                        result=json.load(response)
                    self.assertEqual(result["coverage"]["candidate_count"],1)
                    self.assertEqual(result["storage"],"LOCAL_JSON")
                    self.assertNotIn("SECRET_DO_NOT_RETURN",json.dumps(result))
                    self.assertNotIn("https://",json.dumps(result))
                    self.assertEqual(before,(path.read_bytes(),profile.read_bytes()))
                finally:
                    http.shutdown();http.server_close();task.join(5)


if __name__=="__main__":
    unittest.main()
