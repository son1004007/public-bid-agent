"""팀장 입력문서 가이드의 완결성과 HTTP 제공, AI 전송 차단 계약 검증."""
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.request import urlopen
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import server as app


class DocumentGuideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.guide=json.loads(app.DOCUMENT_GUIDE.read_text(encoding="utf-8"))

    def test_exactly_five_document_categories_and_complete_variable_keys(self):
        docs=self.guide["documents"]
        self.assertEqual(len(docs),5)
        self.assertEqual([v["order"] for v in docs],[1,2,3,4,5])
        self.assertEqual(len({v["id"] for v in docs}),5)
        v=self.guide["variables"]
        self.assertEqual(len(v),20)
        self.assertEqual(len([x for x in v if x["kind"]=="gate"]),8)
        self.assertEqual(len([x for x in v if x["kind"]=="factor"]),12)
        expected={k for k,_ in app.GATES}|{k for k,_,_ in app.FACTORS}
        self.assertEqual({x["key"] for x in v},expected)
        self.assertEqual(len({x["key"] for x in v}),20)
        allowed={x["id"] for x in docs}|{self.guide["additional_source"]["id"]}
        self.assertTrue(all(x["sources"] and set(x["sources"])<=allowed for x in v))
        self.assertTrue(all(x["missing_question"] and x["label"] for x in v))
        self.assertTrue(all(x["purpose"] and x["fallback"] and x["caution"] for x in docs))

    def test_confidential_docs_warn_against_ai_upload(self):
        groups={x["id"]:x for x in self.guide["documents"]}
        self.assertEqual(groups["notice"]["classification"],"public")
        self.assertEqual(groups["business_case"]["classification"],"company_restricted")
        self.assertIn("명시적 승인",self.guide["safety"])
        self.assertIn("미확인",self.guide["missing_policy"])

    def test_guide_is_read_only_http_without_ai_consent_or_case(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)
            with patch.object(app,"ROOT",path),patch.object(app,"FILE",path/"cases.json"):
                app.persist({"schema_version":1,"cases":[]})
                http=ThreadingHTTPServer(("127.0.0.1",0),app.Handler)
                worker=threading.Thread(target=http.serve_forever,daemon=True)
                worker.start()
                try:
                    with urlopen(f"http://127.0.0.1:{http.server_port}/document-guide.json",timeout=3) as response:
                        self.assertEqual(response.status,200)
                        self.assertIn("application/json",response.headers.get("Content-Type",""))
                        response_guide=json.load(response)
                    self.assertEqual(response_guide["variables"],self.guide["variables"])
                    self.assertEqual(app.load()["cases"],[])
                finally:
                    http.shutdown()
                    http.server_close()
                    worker.join(timeout=3)

    def test_first_screen_guidance_available_before_case_creation(self):
        html=app.HTML.read_text(encoding="utf-8")
        js=app.APP_JS.read_text(encoding="utf-8")
        self.assertIn('id="documentGuide"',html)
        self.assertLess(html.index('id="documentGuide"'),html.index('id="workspace"'))
        self.assertIn('function renderDocumentGuide(data)',js)
        self.assertIn('async function loadDocumentGuide()',js)
        self.assertIn('fetch("/document-guide.json"',js)

if __name__=="__main__":
    unittest.main()
