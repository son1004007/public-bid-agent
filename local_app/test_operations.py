"""운영정보 관리와 입찰별 예상원가 계산 검증.

출처/인력·금액 입력은 전부 합성. 회사/고객 데이터·외부 AI 호출 없음.
"""
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError

sys.path.insert(0,str(Path(__file__).parent))
import server
from operations import default_profile,clean_profile,clean_plan,calculate,REFERENCE_SECTIONS

MOCK_PROFILE={"roles":[
    {"role":"Python 백엔드","cost_per_mm_krw":8000000,"available_mm":3},
    {"role":"프런트엔드","cost_per_mm_krw":7000000,"available_mm":2}
],"overhead_pct":10,"reserve_pct":5}
MOCK_PLAN={"entries":[{"role":"Python 백엔드","mm":2.5},{"role":"프런트엔드","mm":1}],
           "subcontract_krw":3000000,"direct_expenses_krw":1000000,
           "proposal_krw":2000000,"proposed_supply_price_krw":50000000}

class CostUnitTests(unittest.TestCase):
 def test_eight_business_registers_stay_unverified_until_summary_and_source(self):
  profile=clean_profile(MOCK_PROFILE)
  self.assertEqual(len(REFERENCE_SECTIONS),8)
  self.assertEqual(len(profile["registers"]),8)
  self.assertTrue(all(item["status"]=="not_collected" for item in profile["registers"].values()))
  with self.assertRaises(ValueError):
   clean_profile({**MOCK_PROFILE,"registers":{"finance":{"status":"reviewed","summary":"","source":"","reviewed_on":""}}})
  known=clean_profile({**MOCK_PROFILE,"registers":{"finance":{"status":"reviewed","summary":"가상 재무 요약","source":"가상 손익분석표","reviewed_on":"2026-10-10"}}})
  self.assertEqual(known["registers"]["finance"]["status"],"reviewed")
  self.assertEqual(known["registers"]["pipeline"]["status"],"not_collected")

 def test_cost_calculation_vat_excluded_and_no_model_inference(self):
  ops=clean_profile(MOCK_PROFILE)
  plan=clean_plan(MOCK_PLAN,ops)
  result=calculate(ops,plan)
  self.assertEqual(result["labor_krw"],27000000)
  self.assertEqual(result["overhead_krw"],3100000)
  self.assertEqual(result["reserve_krw"],1705000)
  self.assertEqual(result["total_cost_krw"],37805000)
  self.assertEqual(result["expected_profit_krw"],12195000)
  self.assertEqual(result["expected_margin_pct"],24.4)
  self.assertEqual(result["warnings"],[])
 def test_no_price_is_not_zero_profit(self):
  p=clean_profile(MOCK_PROFILE)
  data={**MOCK_PLAN,"proposed_supply_price_krw":None}
  out=calculate(p,clean_plan(data,p))
  self.assertIsNone(out["expected_profit_krw"])
  self.assertIsNone(out["expected_margin_pct"])
 def test_excess_capacity_warns_and_does_not_silently_adjust(self):
  p=clean_profile(MOCK_PROFILE)
  plan=clean_plan({**MOCK_PLAN,"entries":[{"role":"Python 백엔드","mm":4}]},p)
  out=calculate(p,plan)
  self.assertTrue(any("초과" in w for w in out["warnings"]))
  self.assertEqual(out["labor_krw"],32000000)
 def test_invalid_numbers_roles_and_duplicate_rejected(self):
  invalid=[
   {**MOCK_PROFILE,"roles":[MOCK_PROFILE["roles"][0]]*2},
   {**MOCK_PROFILE,"roles":[{**MOCK_PROFILE["roles"][0],"cost_per_mm_krw":-1}]},
   {**MOCK_PROFILE,"roles":[{**MOCK_PROFILE["roles"][0],"available_mm":"NaN"}]},
   {**MOCK_PROFILE,"reserve_pct":101},
  ]
  for case in invalid:
   with self.subTest(case=case),self.assertRaises(ValueError):
    clean_profile(case)
  profile=clean_profile(MOCK_PROFILE)
  for cost in (float("nan"),-100,1.5,True):
   with self.subTest(cost=cost),self.assertRaises(ValueError):
    clean_plan({**MOCK_PLAN,"subcontract_krw":cost},profile)
  with self.assertRaises(ValueError):
   clean_plan({**MOCK_PLAN,"entries":[{"role":"유령 직무","mm":3}]},profile)
 def test_prompt_ignores_cost_fields_by_default(self):
  case=server.create_case("테스트")
  case["prompt"]="가상 공개 입찰 123"
  before=server.prompt_for(case)
  case["cost_plan"]=MOCK_PLAN
  case["cost_estimate"]={"expected_profit_krw":12195000}
  case["operations"]={"salary":"TOP-SECRET-NO-SEND"}
  self.assertEqual(before,server.prompt_for(case))
  self.assertNotIn("TOP-SECRET-NO-SEND",server.prompt_for(case))

class CostHTTPTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.root=Path(self.tmp.name)
  self.rootPatch=patch.object(server,"ROOT",self.root)
  self.filePatch=patch.object(server,"FILE",self.root/"cases.json")
  self.rootPatch.start();self.filePatch.start()
  server.persist({"schema_version":1,"cases":[]})
  self.http=ThreadingHTTPServer(("127.0.0.1",0),server.Handler)
  self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
  self.base=f"http://127.0.0.1:{self.http.server_port}"
 def tearDown(self):
  self.http.shutdown();self.http.server_close();self.thread.join(timeout=3)
  self.filePatch.stop();self.rootPatch.stop();self.tmp.cleanup()
 def post(self,path,body):
  r=Request(self.base+path,json.dumps(body).encode(),headers={"Content-Type":"application/json","Origin":self.base,"X-Local-CSRF":server.TOKEN},method="POST")
  try:
   with urlopen(r,timeout=4) as resp:return resp.status,json.load(resp)
  except HTTPError as resp:return resp.code,json.load(resp)
 def get(self,path):
  with urlopen(self.base+path,timeout=4) as resp:return json.load(resp)
 def test_operations_profile_revision_and_cost_case_json_are_separate(self):
  self.assertEqual(self.get("/api/operations")["operations"]["revision"],0)
  self.assertEqual(len(self.get("/api/operations")["sections"]),8)
  code,saved=self.post("/api/operations/save",{"expected_revision":0,"operations":MOCK_PROFILE})
  self.assertEqual(code,200)
  self.assertEqual(saved["operations"]["revision"],1)
  self.assertTrue((self.root/"operations.json").exists())
  self.assertFalse("roles" in (self.root/"cases.json").read_text(encoding="utf8"))
  code,conflict=self.post("/api/operations/save",{"expected_revision":0,"operations":MOCK_PROFILE})
  self.assertEqual(code,409)
  self.assertIn("변경",conflict["error"])
  code,created=self.post("/api/new",{"title":"가상 입찰"})
  cid=created["case"]["id"]
  code,estimated=self.post("/api/cost-plan",{"id":cid,"expected_operations_revision":1,"cost_plan":MOCK_PLAN})
  self.assertEqual(code,200)
  self.assertEqual(estimated["case"]["cost_estimate"]["total_cost_krw"],37805000)
  self.assertEqual(estimated["case"]["decision"],"undecided")
  self.assertEqual(estimated["case"]["ai_reports"],{})
  self.assertNotIn("cost_per_mm_krw",(self.root/"cases.json").read_text(encoding="utf8"))
  code,saved=self.post("/api/operations/save",{"expected_revision":1,"operations":{**MOCK_PROFILE,"overhead_pct":15}})
  self.assertEqual(code,200)
  self.assertEqual(saved["operations"]["revision"],2)
  self.assertNotEqual(estimated["case"]["cost_estimate"]["operations_revision"],2)
  code,conflict=self.post("/api/cost-plan",{"id":cid,"expected_operations_revision":1,"cost_plan":MOCK_PLAN})
  self.assertEqual(code,409)
 def test_security_requires_csrf_for_operations_write(self):
  r=Request(self.base+"/api/operations/save",json.dumps({"expected_revision":0,"operations":MOCK_PROFILE}).encode(),
            headers={"Content-Type":"application/json"},method="POST")
  with self.assertRaises(HTTPError) as e:urlopen(r,timeout=4)
  self.assertEqual(e.exception.code,403)
  self.assertFalse((self.root/"operations.json").exists())
