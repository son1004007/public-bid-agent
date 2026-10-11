"""비식별 인력/연봉 가정 원가의 단위·HTTP 계약 검증.

모든 인원 코드는 합성 시험 코드이며 실제 회사 구성은 공개 소스에 저장하지 않는다.
"""
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from urllib.request import urlopen, Request
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).parent))
from workforce import validate, load, summary
import server


def person(ident, role, grade=None, skills=None, mm=None):
    return {"id": ident, "role": role, "grade": grade,
            "lead": False, "skills": list(skills or []),
            "skills_evidence": "ASSUMED", "responsibility": "합성 담당 분야",
            "responsibility_evidence": "ASSUMED", "available_mm": mm}


def sample():
    return {"schema_version": 1,
            "annual_grade_rates_krw": {"junior": 24000000,
                                       "intermediate": 36000000,
                                       "senior": 60000000},
            "staff": [person("T1", "analyst", "junior", ["DB"]),
                      person("T2", "developer", "senior", ["JAVA", "DB"]),
                      person("T3", "accounting")]}


class WorkforceContractTests(unittest.TestCase):
    def test_summary_distinguishes_salary_assumption_and_unknown_capacity(self):
        result = summary(sample())
        self.assertEqual(result["headcount_total"], 3)
        self.assertEqual(result["delivery_headcount"], 2)
        self.assertEqual(result["excluded_from_cost_headcount"], 1)
        self.assertEqual(result["annual_assumed_salary_total_krw"], 84000000)
        self.assertEqual(result["monthly_assumed_salary_total_krw"], 7000000)
        self.assertEqual(result["grade_counts"], {"junior":1, "intermediate":0, "senior":1})
        self.assertEqual(result["roles"][0]["available_mm"], None)
        self.assertEqual(result["capacity_status"], "UNKNOWN")
        self.assertEqual(result["staff"][2]["grade"], None)
        self.assertEqual(result["eligibility_status"], "NOT_ASSESSED")

    def test_known_capacity_zero_and_positive_are_aggregated(self):
        data = sample()
        data["staff"].append(person("T4", "analyst", "junior", ["DB"], mm=2))
        data["staff"][0]["available_mm"] = 0
        result = summary(data)
        self.assertEqual(result["roles"][0]["available_mm"], 2)
        self.assertEqual(result["roles"][0]["capacity_status"], "KNOWN")
        data["staff"][0]["available_mm"] = None
        self.assertEqual(summary(data)["roles"][0]["capacity_status"], "UNKNOWN")

    def test_individual_monthly_rounding_is_consistent_with_role_rates(self):
        data = sample()
        data["annual_grade_rates_krw"]["junior"] = 24000001
        data["annual_grade_rates_krw"]["senior"] = 60000002
        view = summary(data)
        total = sum(x["cost_per_mm_krw"] * x["headcount"] for x in view["roles"])
        self.assertEqual(view["monthly_assumed_salary_total_krw"], total)

    def test_person_name_and_extra_fields_are_rejected(self):
        for invalid_id in ("KIM-MINSU", "PARK", "KIM3", "LEE_JH"):
            data = sample()
            data["staff"][0]["id"] = invalid_id
            with self.subTest(id=invalid_id), self.assertRaises(ValueError):
                validate(data)
        for field in ("name", "email", "actual_salary"):
            data = sample()
            data["staff"][0][field] = "not-allowed"
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate(data)

    def test_duplicate_bad_grade_bad_skills_and_invalid_capacity_are_rejected(self):
        cases = []
        data = sample();data["staff"][1]["id"]="T1";cases.append(data)
        data = sample();data["staff"][0]["grade"]="senior_typo";cases.append(data)
        data = sample();data["staff"][1]["skills"]=["JAVA","JAVA"];cases.append(data)
        data = sample();data["staff"][0]["role"]=["analyst"];cases.append(data)
        data = sample();data["staff"][0]["grade"]=["junior"];cases.append(data)
        data = sample();data["staff"][1]["available_mm"]=-1;cases.append(data)
        data = sample();data["staff"][1]["available_mm"]=True;cases.append(data)
        data = sample();data["annual_grade_rates_krw"]["senior"]=0;cases.append(data)
        for data in cases:
            with self.subTest(data=data["staff"][1]["id"]), self.assertRaises(ValueError):
                validate(data)


class WorkforceHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.p=patch.object(server,"ROOT",self.root)
        self.p.start()
        self.http=ThreadingHTTPServer(("127.0.0.1",0),server.Handler)
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True)
        self.thread.start()
        self.base=f"http://127.0.0.1:{self.http.server_port}"

    def tearDown(self):
        self.http.shutdown();self.http.server_close()
        self.thread.join(timeout=3)
        self.p.stop();self.tmp.cleanup()

    def read_api(self):
        with urlopen(self.base+"/api/workforce",timeout=5) as response:
            return response.status,json.load(response)

    def test_missing_is_not_configured_and_does_not_initialize_file(self):
        code,response=self.read_api()
        self.assertEqual(code,200)
        self.assertEqual(response["status"],"NOT_CONFIGURED")
        self.assertIsNone(response["workforce"])
        self.assertFalse((self.root/"workforce.json").exists())

    def test_nonempty_private_roster_is_served_readonly(self):
        path=self.root/"workforce.json"
        path.write_text(json.dumps(sample()),encoding="utf-8")
        before=path.read_bytes()
        code,response=self.read_api()
        self.assertEqual(code,200)
        self.assertEqual(response["storage"],"LOCAL_JSON")
        self.assertEqual(response["workforce"]["delivery_headcount"],2)
        self.assertNotIn("staff",response["workforce"])
        self.assertEqual(before,path.read_bytes())

    def test_bad_private_data_fails_closed_without_exposing_content(self):
        path=self.root/"workforce.json"
        path.write_text('{"staff": "SECRET-DO-NOT-LEAK"}',encoding="utf-8")
        try:
            urlopen(self.base+"/api/workforce",timeout=5)
            self.fail("503 expected")
        except HTTPError as error:
            self.assertEqual(error.code,503)
            self.assertNotIn("SECRET-DO-NOT-LEAK",error.read().decode("utf-8"))

    def test_invalid_unicode_returns_503(self):
        path=self.root/"workforce.json"
        path.write_bytes(bytes([0xff, 0xfe]))
        try:
            urlopen(self.base+"/api/workforce",timeout=5)
            self.fail("503 expected")
        except HTTPError as error:
            self.assertEqual(error.code,503)

    @patch.object(server,"WORKFORCE_DETAILS_ENABLED",True)
    def test_detail_requires_local_csrf_and_can_return_synthetic_staff(self):
        path=self.root/"workforce.json"
        path.write_text(json.dumps(sample()),encoding="utf-8")
        with self.assertRaises(HTTPError) as err:
            urlopen(self.base+"/api/workforce?detail=1",timeout=5)
        self.assertEqual(err.exception.code,403)
        req=Request(self.base+"/api/workforce?detail=1",
                    headers={"X-Local-CSRF":server.TOKEN})
        with urlopen(req,timeout=5) as response:
            view=json.load(response)["workforce"]
        self.assertEqual(len(view["staff"]),3)

    def test_detail_disabled_by_default(self):
        self.assertFalse(server.WORKFORCE_DETAILS_ENABLED)
        self.root.joinpath("workforce.json").write_text(json.dumps(sample()), encoding="utf-8")
        req=Request(self.base+"/api/workforce?detail=1",
                    headers={"X-Local-CSRF":server.TOKEN})
        with self.assertRaises(HTTPError) as error:
            urlopen(req,timeout=5)
        self.assertEqual(error.exception.code,403)

    def test_host_header_rejected(self):
        request=Request(self.base+"/api/workforce",headers={"Host":"attacker.invalid"})
        with self.assertRaises(HTTPError) as error:
            urlopen(request,timeout=5)
        self.assertEqual(error.exception.code,403)


if __name__=="__main__":
    unittest.main()
