"""구형 검증 플래그 회귀 계약.

합성 메모리/임시 JSON만 사용하며 외부 AI 호출은 금지한다.
조언·요약의 불확실성, 점수 보류 및 GET 원본/최종 결정/이력 불변을 검증한다.
"""
import copy
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen

import server
from decision_support import advise


def legacy_case(evidence="   "):
    case = server.create_case("합성 구형 검증 기록")
    # 새 저장 검증기를 거치지 않는다. 이전 버전이 저장할 수 있던 상태를 재현한다.
    for key, _ in server.GATES:
        case["gates"][key] = {"status":"pass", "evidence":evidence, "verified":True}
    for key, _, _ in server.FACTORS:
        case["factors"][key] = {"score":5, "evidence":evidence, "verified":True}
    case.update(decision="no_bid", reason="합성 사용자 결정 보존",
                history=[{"decision":"no_bid", "reason":"합성 이력 보존"}])
    return case


class LegacyVerificationTests(unittest.TestCase):
    def test_legacy_blank_records_withhold_score_and_preserve_input(self):
        for evidence in ("", "   ", "\t\r\n", "\u00a0\u3000", "\u0085\u001c", "\ufeff"):
            with self.subTest(evidence=repr(evidence)):
                case = legacy_case(evidence)
                before = copy.deepcopy(case)
                advice, summary = advise(case), server.summary(case)
                self.assertEqual(advice["status"], "HOLD_UNVERIFIED")
                self.assertEqual(advice["unverified_gate_count"], 8)
                self.assertEqual(summary["status"], "NEEDS_REVIEW")
                self.assertEqual(len(summary["missing_gates"]), 8)
                self.assertEqual(len(summary["missing_factors"]), 12)
                self.assertEqual(summary["hard_fail"], [])
                self.assertIsNone(summary["illustrative_index"])
                self.assertEqual(case, before)

    def test_unbacked_failure_is_unknown_but_backed_failure_still_stops(self):
        case = legacy_case("합성 근거")
        case["gates"]["licenses"].update(status="fail", evidence=" \n ")
        self.assertEqual(advise(case)["status"], "HOLD_UNVERIFIED")
        result = server.summary(case)
        self.assertEqual(result["hard_fail"], [])
        self.assertEqual(result["missing_gates"], ["licenses"])
        self.assertIsNone(result["illustrative_index"])
        case["gates"]["licenses"]["evidence"] = "합성 미충족 근거"
        self.assertEqual(advise(case)["status"], "REVIEW_NO_BID_VERIFIED")
        self.assertEqual(server.summary(case)["status"], "STOP_CONDITION")

    def test_factor_only_blank_withholds_index_and_valid_na_keeps_score(self):
        case = legacy_case("  합성 확인 근거  ")
        case["gates"]["teaming"]["status"] = "na"
        self.assertEqual(server.summary(case)["illustrative_index"], 100)
        self.assertEqual(advise(case)["unverified_gate_count"], 0)
        case["factors"]["technical"]["evidence"] = "\t"
        result = server.summary(case)
        self.assertEqual(result["missing_gates"], [])
        self.assertEqual(result["missing_factors"], ["technical"])
        self.assertIsNone(result["illustrative_index"])

    def test_invalid_verification_values_remain_unknown(self):
        for change in ({"verified":"true"}, {"verified":1}, {"verified":False},
                       {"evidence":None}, {"evidence":123}):
            with self.subTest(change=change):
                case = legacy_case("합성 근거")
                case["gates"]["licenses"].update(change)
                case["factors"]["technical"].update(change)
                self.assertEqual(advise(case)["unverified_gate_count"], 1)
                result = server.summary(case)
                self.assertEqual(result["missing_gates"], ["licenses"])
                self.assertEqual(result["missing_factors"], ["technical"])
                self.assertIsNone(result["illustrative_index"])
        for status in ("unknown", "invalid", None):
            case = legacy_case("합성 근거")
            case["gates"]["licenses"]["status"] = status
            self.assertEqual(advise(case)["unverified_gate_count"], 1)
            self.assertEqual(server.summary(case)["missing_gates"], ["licenses"])
        for score in (None, True, "5", 0, 6):
            case = legacy_case("합성 근거")
            case["factors"]["technical"]["score"] = score
            self.assertEqual(server.summary(case)["missing_factors"], ["technical"])

    def test_save_uses_same_evidence_rule(self):
        for evidence in (" \n ", "\u0085\u001c", "\ufeff", "  합성 근거  "):
            case = legacy_case(evidence)
            server.update_case(case, copy.deepcopy(case))
            expected = evidence == "  합성 근거  "
            self.assertTrue(all(item["verified"] is expected for item in case["gates"].values()))
            self.assertTrue(all(item["verified"] is expected for item in case["factors"].values()))
            self.assertEqual(advise(case)["unverified_gate_count"], 0 if expected else 8)
            self.assertEqual(server.summary(case)["illustrative_index"], 100 if expected else None)

    def test_http_legacy_get_and_summary_preserve_records_and_final_decision(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            file = root / "cases.json"
            with patch.object(server, "ROOT", root), patch.object(server, "FILE", file), \
                    patch.object(server, "call_cli", side_effect=AssertionError("external call forbidden")) as cli:
                case = legacy_case()
                server.persist({"schema_version":1, "cases":[case]})
                before = file.read_bytes()
                http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
                worker = threading.Thread(target=http.serve_forever, daemon=True)
                worker.start()
                url = f"http://127.0.0.1:{http.server_port}"
                try:
                    with patch.object(server, "persist", side_effect=AssertionError("GET must not write")):
                        with urlopen(url+"/api/state", timeout=5) as response:
                            loaded = json.load(response)["data"]["cases"][0]
                    self.assertEqual(file.read_bytes(), before)
                    self.assertEqual(loaded["decision_support"]["status"], "HOLD_UNVERIFIED")
                    self.assertEqual(loaded["decision_support"]["unverified_gate_count"], 8)
                    self.assertIsNone(server.summary(loaded)["illustrative_index"])
                    # 부분 저장은 기존 항목을 재작성하지 않지만 응답 요약은 보수적이어야 한다.
                    request = Request(url+"/api/save", json.dumps({"id":case["id"]}).encode(),
                                      headers={"Content-Type":"application/json", "Origin":url,
                                               "X-Local-CSRF":server.TOKEN}, method="POST")
                    with urlopen(request, timeout=5) as response:
                        result = json.load(response)
                    self.assertEqual(result["summary"]["status"], "NEEDS_REVIEW")
                    self.assertIsNone(result["summary"]["illustrative_index"])
                    self.assertEqual(len(result["summary"]["missing_gates"]), 8)
                    self.assertEqual(len(result["summary"]["missing_factors"]), 12)
                    for record in (loaded, result["case"], server.load()["cases"][0]):
                        for field, value in case.items():
                            if field != "decision_support":
                                self.assertEqual(record[field], value, field)
                    cli.assert_not_called()
                finally:
                    http.shutdown()
                    http.server_close()
                    worker.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
