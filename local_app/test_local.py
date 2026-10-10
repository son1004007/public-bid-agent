"""로컬 데이터 저장/자동 추출 초안/HTTP 경계 회귀 테스트.
외부 Codex/Claude CLI를 호출하지 않고 모든 입력은 가상 데이터로 검증.
"""
import json
import os
import stat
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from http.server import ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).parent))
import server as app


class LogicTests(unittest.TestCase):
    def test_factors_and_initial_states(self):
        self.assertEqual(len(app.GATES), 8)
        self.assertEqual(len(app.FACTORS), 12)
        self.assertEqual(sum(w for _, _, w in app.FACTORS), 100)
        obj = app.create_case("테스트 공고")
        self.assertEqual(app.summary(obj)["status"], "NEEDS_REVIEW")
        self.assertIsNone(app.summary(obj)["illustrative_index"])
        self.assertEqual(obj["decision"], "undecided")

    def test_ai_draft_does_not_verify(self):
        obj = app.create_case("합성")
        raw = {"gates": {"eligibility": {"status": "pass", "evidence": "가상 공고 3조"}},
               "factors": {"technical": {"score": 5, "evidence": "가상 2항"}},
               "recommendation": "bid", "reason": "예시"}
        cleaned = app.normalize(raw)
        self.assertFalse(cleaned["gates"]["eligibility"]["verified"])
        self.assertFalse(cleaned["factors"]["technical"]["verified"])
        self.assertEqual(obj["decision"], "undecided")

    def test_unknown_is_not_zero_and_fail_blocks(self):
        obj = app.create_case("합성")
        for key, _ in app.GATES:
            obj["gates"][key] = {"status": "pass", "evidence": "공고 근거", "verified": True}
        for key, _, _ in app.FACTORS:
            obj["factors"][key] = {"score": 5, "evidence": "확인", "verified": True}
        self.assertEqual(app.summary(obj)["illustrative_index"], 100)
        obj["gates"]["eligibility"]["status"] = "fail"
        self.assertEqual(app.summary(obj)["status"], "STOP_CONDITION")
        self.assertIsNone(app.summary(obj)["illustrative_index"])
        obj["gates"]["eligibility"]["status"] = "unknown"
        self.assertIsNone(app.summary(obj)["illustrative_index"])
        obj["gates"]["eligibility"]["status"] = "pass"
        obj["factors"]["technical"]["verified"] = False
        self.assertIsNone(app.summary(obj)["illustrative_index"])

    def test_manual_edits_become_unverified_without_evidence(self):
        obj = app.create_case("합성")
        app.update_case(obj, {"gates": {"eligibility": {"status": "pass", "evidence": "", "verified": True}},
                              "factors": {"staff": {"score": 4, "evidence": "", "verified": True}}})
        self.assertFalse(obj["gates"]["eligibility"]["verified"])
        self.assertFalse(obj["factors"]["staff"]["verified"])
        with self.assertRaises(ValueError):
            app.update_case(obj, {"factors": {"technical": {"score": 10, "evidence": "X", "verified": True}}})


    def test_windows_codex_cmd_selected_instead_of_npm_shim(self):
        from unittest.mock import patch
        def exe(name):
            return {"codex": r"C:\\Temp\\codex", "codex.cmd":r"C:\\Temp\\codex.cmd",
                    "claude.exe":r"C:\\Temp\\claude.exe"}.get(name)
        with patch.object(app.shutil, "which", side_effect=exe):
            self.assertTrue(app.cli_executable("codex", windows=True).endswith("codex.cmd"))
            self.assertTrue(app.cli_executable("claude", windows=True).endswith("claude.exe"))
            self.assertTrue(app.cli_executable("codex", windows=False).endswith("codex"))

    def test_codex_only_command_and_json_result(self):
        import subprocess
        from unittest.mock import patch
        proc=subprocess.CompletedProcess([],0,stdout='{"recommendation":"hold","reason":"자료 부족"}',stderr="")
        with patch.object(app,"cli_executable",return_value="codex.cmd"):
            with patch.object(app.subprocess,"run",return_value=proc) as run:
                result=app.call_cli("codex","합성 입찰")
        self.assertEqual(result["status"],"success")
        self.assertEqual(result["result"]["recommendation"],"hold")
        self.assertFalse(result["result"]["gates"]["eligibility"]["verified"])
        args=run.call_args.args[0]
        self.assertEqual(args[0],"codex.cmd")
        self.assertEqual(args[args.index("-m")+1],"gpt-5.6-terra")
        self.assertIn("--sandbox",args)
        self.assertIn("read-only",args)
        self.assertIn("--ephemeral",args)

    def test_cli_os_error_returns_failure_not_http_500(self):
        from unittest.mock import patch
        with patch.object(app,"cli_executable",return_value="codex.cmd"):
            with patch.object(app.subprocess,"run",side_effect=OSError(193,"Bad executable")):
                result=app.call_cli("codex","합성 자료")
        self.assertEqual(result["status"],"error")
        self.assertNotIn("Traceback",result["error"])


    def test_ai_prompt_defines_positive_score_direction(self):
        case=app.create_case("synthetic")
        p=app.prompt_for(case)
        self.assertIn("위험이 많고 통제되지 않으면 1점",p)
        self.assertIn("부담이 높을수록 1점",p)
        self.assertIn("reason에는 전체 권고 사유",p)

    def test_ai_variable_read_only_preview_is_in_html_js(self):
        html=app.HTML.read_text(encoding="utf-8")
        js=app.APP_JS.read_text(encoding="utf-8")
        self.assertIn('id="aiFactorsPreview"',html)
        self.assertIn('id="aiIndependentVariables"',html)
        self.assertIn('function renderAiFactors()',js)
        self.assertIn('const draft=active?.ai_draft;',js)
        self.assertIn('group("필수 참가조건 8개"',js)
        self.assertIn('group("비교 평가요인 12개"',js)

    def test_file_whitelist(self):
        self.assertEqual(app.ingest("example.md", "가상 자료".encode()), "가상 자료")
        with self.assertRaises(ValueError): app.ingest("config.py", b"print('hello')")
        with self.assertRaises(ValueError): app.ingest("too-big.md", b"x"*(10*1024*1024+1))

    def test_local_json_atomic_and_private_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)/"nested"
            with patch.object(app,"ROOT",root), patch.object(app,"FILE",root/"cases.json"):
                obj = app.create_case("한국어 합성")
                app.persist({"schema_version":1,"cases":[obj]})
                self.assertEqual(app.load()["cases"][0]["title"],"한국어 합성")
                if os.name=="posix":
                    self.assertEqual(stat.S_IMODE(app.FILE.stat().st_mode),0o600)
                    self.assertEqual(stat.S_IMODE(root.stat().st_mode),0o700)


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)/"private"
        self.rp=patch.object(app,"ROOT",self.root)
        self.fp=patch.object(app,"FILE",self.root/"cases.json")
        self.rp.start()
        self.fp.start()
        app.persist({"schema_version":1,"cases":[]})
        self.http=ThreadingHTTPServer(("127.0.0.1",0),app.Handler)
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True)
        self.thread.start()
        self.url=f"http://127.0.0.1:{self.http.server_port}"

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(timeout=2)
        self.fp.stop()
        self.rp.stop()
        self.tmp.cleanup()

    def post(self,path,payload,with_security=True):
        headers={"Content-Type":"application/json"}
        if with_security:
            headers["Origin"]=self.url
            headers["X-Local-CSRF"]=app.TOKEN
        request=Request(self.url+path,json.dumps(payload).encode(),headers=headers,method="POST")
        try:
            with urlopen(request,timeout=4) as response:
                return response.status,json.load(response)
        except HTTPError as error:
            return error.code,json.load(error)

    def test_csrf_and_local_json_workflow(self):
        with urlopen(self.url+"/",timeout=4) as response:
            self.assertIn(b"Public Bid Agent",response.read())
        with urlopen(self.url+"/app.js",timeout=4) as response:
            self.assertIn(b"function render()",response.read())
        with urlopen(self.url+"/api/state",timeout=4) as response:
            self.assertEqual(json.load(response)["data"]["cases"],[])
        status,_=self.post("/api/new",{"title":"가상 사업"},False)
        self.assertEqual(status,403)
        status,result=self.post("/api/new",{"title":"가상 사업"})
        self.assertEqual(status,200)
        ident=result["case"]["id"]
        status,result=self.post("/api/save",{"id":ident,"prompt":"AI 데이터 처리 서비스"})
        self.assertEqual(status,200)
        status,result=self.post("/api/decide",{"id":ident,"decision":"hold","reason":"근거 부족"})
        self.assertEqual(result["case"]["decision"],"hold")
        self.assertEqual(len(result["case"]["history"]),1)
        self.assertIn("AI 데이터",app.load()["cases"][0]["prompt"])

    def test_document_upload_persists_only_extracted_text(self):
        import base64
        from io import BytesIO
        from zipfile import ZipFile
        with BytesIO() as file:
            with ZipFile(file,"w") as z:
                z.writestr("Contents/section0.xml",'<hp:section xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"><hp:p><hp:run><hp:t>가상 제안 공고</hp:t></hp:run></hp:p></hp:section>')
            raw=file.getvalue()
        _,created=self.post("/api/new",{"title":"HWPX 테스트"})
        status,result=self.post("/api/file",{"id":created["case"]["id"],
                            "name":"bid.hwpx","base64":base64.b64encode(raw).decode()})
        self.assertEqual(status,200)
        doc=result["case"]["documents"][0]
        self.assertEqual(doc["text"],"가상 제안 공고")
        self.assertEqual(doc["method"],"HWPX 문단/표 XML")
        self.assertNotIn("base64",str(app.load()))
        self.assertNotIn("application/hwp+zip",str(app.load()))

    def test_external_ai_requires_consent_and_real_cli(self):
        _,case=self.post("/api/new",{"title":"데모"})
        ident=case["case"]["id"]
        self.post("/api/save",{"id":ident,"prompt":"가상 공고"})
        status,_=self.post("/api/analyze",{"id":ident,"providers":["codex"],"consent":False})
        self.assertEqual(status,400)
        with patch.object(app.shutil,"which",return_value=None):
            status,data=self.post("/api/analyze",{"id":ident,"providers":["codex"],"consent":True})
        self.assertEqual(status,200)
        self.assertEqual(data["case"]["ai_reports"]["codex"]["status"],"unavailable")
        self.assertEqual(data["case"]["decision"],"undecided")
        self.assertEqual(data["case"]["ai_draft"],{})


if __name__=="__main__":
    unittest.main()