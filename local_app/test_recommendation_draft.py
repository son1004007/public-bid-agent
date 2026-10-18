"""P07 합성 출처/불확실성/fallback 회귀.

가상 메모리 문서와 임시 JSON/loopback HTTP만 사용한다. 외부 CLI는 항상 mock한다.
인용 변조·과거 자료·불완전 추출·AI 장애가 사용자 결정을 확정/변경하지 않아야 한다.
"""
import copy
import hashlib
import json
import tempfile
import threading
import types
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import server
from decision_support import advise, clean_citations, context_digest, model_input, MODEL_INPUT_LIMIT


def fixture():
    case = server.create_case("합성 P07")
    text = "가상 공고 😀\n소프트웨어 등록 증빙을 확인해야 한다."
    case["documents"] = [{"name":"synthetic.txt", "text":text, "truncated":False, "warnings":[]}]
    quote = "소프트웨어 등록 증빙을 확인해야 한다."
    start = text.index(quote)
    citation = {"source_id":"document:0", "text_sha256":hashlib.sha256(text.encode()).hexdigest(),
                "offset_start":start, "offset_end":start+len(quote), "quote":quote}
    case["ai_draft"] = server.normalize({
        "recommendation":"bid", "reason":"등록 증빙을 검토해야 합니다.", "citations":[citation],
        "gates":{"eligibility":{"status":"pass", "evidence":"가상 등록 주장", "citations":[citation]}},
        "factors":{"technical":{"score":5, "evidence":"가상 기술 주장", "citations":[citation]}}
    })
    case["decision"] = "no_bid"
    case["reason"] = "사용자 사유 보존"
    case["history"] = [{"decision":"no_bid", "reason":"합성 결정 이력"}]
    case["ai_draft_context_sha256"] = context_digest(case)
    return case


def capped_fixture():
    case = fixture()
    case["prompt"] = "설" * 44000
    case["documents"] = [
        {"name":"first.txt", "text":"일" * 44000},
        {"name":"second.txt", "text":"😀" * 44000},
        {"name":"omitted.txt", "text":"OMITTED_SYNTHETIC_REQUIREMENT"},
    ]
    citation = {"source_id":"document:1", "text_sha256":hashlib.sha256(("😀" * 44000).encode()).hexdigest(),
                "offset_start":0, "offset_end":2, "quote":"😀😀"}
    case["ai_draft"] = server.normalize({
        "recommendation":"bid", "reason":"합성 초안", "citations":[citation],
        "gates":{"eligibility":{"status":"fail", "evidence":"합성 미충족 주장", "citations":[citation]}},
        "factors":{"technical":{"score":5, "evidence":"합성 점수", "citations":[citation]}}
    })
    case["ai_draft_context_sha256"] = context_digest(case)
    return case


class DraftTests(unittest.TestCase):
    def test_prompt_cap_records_partial_source_and_omitted_document(self):
        case = capped_fixture()
        before = copy.deepcopy(case)
        prompt = server.prompt_for(case)
        result = advise(case)
        coverage = result["input_coverage"]
        second = coverage["sources"][2]
        omitted = coverage["sources"][3]
        self.assertEqual(second["transmitted_end"], prompt.count("😀"))
        self.assertEqual(second["transmitted_start"], 0)
        self.assertEqual(second["total_chars"], 44000)
        self.assertGreater(second["transmitted_end"], 0)
        self.assertLess(second["transmitted_end"], 44000)
        self.assertEqual(second["status"], "TRUNCATED")
        self.assertEqual(omitted["status"], "OMITTED")
        self.assertEqual(omitted["transmitted_end"], 0)
        self.assertNotIn("OMITTED_SYNTHETIC_REQUIREMENT", prompt)
        self.assertEqual(coverage["omitted_source_ids"], ["document:2"])
        self.assertTrue(result["source_checks"]["recommendation"]["links"][0]["partial"])
        self.assertEqual(result["draft_context_status"], "CURRENT")
        self.assertEqual(result["analysis_mode"], "RULE_BASED_FALLBACK")
        self.assertIn("MODEL_INPUT_INCOMPLETE", result["fallback_reasons"])
        self.assertEqual(result["status"], "HOLD_INPUT_INCOMPLETE")
        self.assertEqual(result["scored_factor_count"], 0)
        self.assertEqual(result["failed_gate_keys"], [])
        self.assertTrue(any("90,000" in message for message in result["uncertainty"]))
        self.assertEqual(case, before)

    def test_citations_outside_transmitted_range_cannot_match(self):
        end = model_input(capped_fixture())["coverage"]["sources"][2]["transmitted_end"]
        for source_id, offset, quote in (("document:1", end-1, "😀😀"),
                                         ("document:1", 43998, "😀😀"),
                                         ("document:2", 0, "OMITTED_SYNTHETIC_REQUIREMENT")):
            case = capped_fixture()
            text = case["documents"][int(source_id[-1])]["text"]
            case["ai_draft"]["citations"] = [{"source_id":source_id,
                "text_sha256":hashlib.sha256(text.encode()).hexdigest(),
                "offset_start":offset, "offset_end":offset+len(quote), "quote":quote}]
            check = advise(case)["source_checks"]["recommendation"]
            self.assertEqual(check["status"], "MISMATCH")
            self.assertEqual(check["links"], [])

    def test_incomplete_input_cannot_be_ready_but_preserves_user_failure(self):
        case = capped_fixture()
        for key in case["gates"]:
            case["gates"][key] = {"status":"pass", "evidence":"합성 사용자 확인", "verified":True}
        self.assertEqual(advise(case)["status"], "HOLD_INPUT_INCOMPLETE")
        case["gates"]["licenses"]["status"] = "fail"
        before = copy.deepcopy(case)
        self.assertEqual(advise(case)["status"], "REVIEW_NO_BID_VERIFIED")
        self.assertEqual(case, before)

    def test_exact_limit_and_one_character_over_use_unicode_ranges(self):
        header = len("[source_id=prompt; text_sha256=" + "0"*64 + "]\n")
        for extra in (0, 1):
            with self.subTest(extra=extra):
                case = {"prompt":"😀" * (MODEL_INPUT_LIMIT - header + extra)}
                packed = model_input(case)
                coverage = packed["coverage"]
                self.assertEqual(len(packed["content"]), MODEL_INPUT_LIMIT)
                self.assertEqual(coverage["incomplete"], bool(extra))
                self.assertEqual(coverage["sources"][0]["transmitted_end"], MODEL_INPUT_LIMIT-header)
                self.assertEqual(coverage["content_sha256"], hashlib.sha256(packed["content"].encode()).hexdigest())
                self.assertIn(packed["content"], server.prompt_for(case))

    def test_header_boundary_records_omission_without_partial_header(self):
        header = len("[source_id=prompt; text_sha256=" + "0"*64 + "]\n")
        case = {"prompt":"설" * (MODEL_INPUT_LIMIT-header-5),
                "documents":[{"name":"tail.txt", "text":"synthetic"}]}
        packed = model_input(case)
        self.assertNotIn("source_id=document:0", packed["content"])
        self.assertEqual(packed["coverage"]["omitted_source_ids"], ["document:0"])
        self.assertEqual(packed["coverage"]["sources"][1]["transmitted_end"], 0)

    def test_context_binds_coverage_and_detects_changes_to_omitted_sources(self):
        case = capped_fixture()
        digest = context_digest(case)
        content = model_input(case)["content"]
        case["documents"][2]["text"] += "changed"
        self.assertEqual(model_input(case)["content"], content)
        self.assertNotEqual(context_digest(case), digest)
        self.assertEqual(advise(case)["draft_context_status"], "CHANGED")
        changed_digest = context_digest(case)
        with patch("decision_support.MODEL_INPUT_LIMIT", 100000):
            self.assertNotEqual(context_digest(case), changed_digest)

    def test_linked_claims_stay_draft_and_unverified_without_mutation(self):
        case = fixture()
        before = copy.deepcopy(case)
        result = advise(case)
        self.assertEqual(result, advise(case))
        self.assertEqual(case, before)
        self.assertEqual(result["draft_state"], "DRAFT")
        self.assertEqual(result["status"], "HOLD_UNVERIFIED")
        self.assertEqual(result["analysis_mode"], "RULE_BASED_WITH_AI_DRAFT")
        self.assertEqual(result["human_decision"], "no_bid")
        self.assertEqual(result["unverified_gate_count"], 8)
        self.assertEqual(result["scored_factor_count"], 1)
        check = result["source_checks"]["gates"]["eligibility"]
        self.assertEqual(check["status"], "EXTRACTED_TEXT_MATCH_ONLY")
        self.assertEqual(check["semantic_verification"], "UNVERIFIED")
        self.assertEqual(check["links"][0]["quote"], case["ai_draft"]["citations"][0]["quote"])
        self.assertNotIn("page", check["links"][0])

    def test_changed_source_and_wrong_hash_quote_or_offset_fail_closed(self):
        for field, value in (("text_sha256", "b"*64), ("source_id", "document:1"),
                             ("offset_start", 0), ("quote", "존재하지 않는 합성 원문")):
            with self.subTest(field=field):
                case = fixture()
                case["ai_draft"]["citations"][0][field] = value
                check = advise(case)["source_checks"]["recommendation"]
                self.assertEqual(check["status"], "MISMATCH")
                self.assertEqual(check["links"], [])
                self.assertEqual(advise(case)["analysis_mode"], "RULE_BASED_FALLBACK")
        case = fixture()
        case["documents"][0]["text"] += "\n정정된 내용"
        self.assertEqual(advise(case)["source_checks"]["recommendation"]["status"], "MISMATCH")

    def test_partial_extraction_is_visible_even_with_matching_citation(self):
        for flag in ({"truncated":True}, {"warnings":["합성 OCR 불완전"]}):
            case = fixture()
            case["documents"][0].update(flag)
            result = advise(case)
            self.assertTrue(result["source_checks"]["recommendation"]["links"][0]["partial"])
            self.assertEqual(result["status"], "HOLD_UNVERIFIED")

    def test_missing_malformed_and_failed_ai_still_use_human_rules(self):
        for draft in ({}, None, [], "bad", {"gates":[], "factors":7, "reason":None}):
            with self.subTest(draft=draft):
                case = fixture()
                case["ai_draft"] = draft
                case["ai_reports"] = {"codex":{"status":"timeout", "error":"synthetic"}}
                case["gates"]["licenses"] = {"status":"fail", "evidence":"가상 면허 미확인 결과", "verified":True}
                before = copy.deepcopy(case)
                result = advise(case)
                self.assertEqual(result["status"], "REVIEW_NO_BID_VERIFIED")
                self.assertEqual(result["analysis_mode"], "RULE_BASED_FALLBACK")
                self.assertEqual(case, before)

    def test_unknown_invalid_or_blank_verified_gate_cannot_be_ready(self):
        for status, evidence in (("unknown", "근거"), ("invalid", "근거"), ("pass", " \n "), ("na", {})):
            case = fixture()
            for key in case["gates"]:
                case["gates"][key] = {"status":"pass", "evidence":"합성 사용자 확인", "verified":True}
            case["gates"]["licenses"].update(status=status, evidence=evidence)
            result = advise(case)
            self.assertEqual(result["status"], "HOLD_UNVERIFIED")
            self.assertEqual(result["unverified_gate_count"], 1)

    def test_unlinked_model_failure_is_flagged_but_cannot_recommend_no_bid(self):
        case = fixture()
        case["ai_draft"]["gates"]["eligibility"].update(status="fail", citations=[])
        result = advise(case)
        self.assertEqual(result["status"], "HOLD_UNVERIFIED")
        self.assertEqual(result["failed_gate_keys"], [])
        self.assertIn("GATE_SOURCE_UNVERIFIED", result["fallback_reasons"])
        self.assertTrue(any(flag["type"] == "ai_claim_unlinked" for flag in result["flags"]))

    def test_linked_model_failure_is_still_counted_unverified(self):
        case = fixture()
        case["ai_draft"]["gates"]["eligibility"]["status"] = "fail"
        result = advise(case)
        self.assertEqual(result["status"], "REVIEW_NO_BID_PROVISIONAL")
        self.assertEqual(result["unverified_gate_count"], 8)
        self.assertTrue(result["not_legal_eligibility"])

    def test_boolean_score_and_unknown_factor_are_not_counted(self):
        case = fixture()
        case["ai_draft"]["factors"]["technical"]["score"] = True
        case["ai_draft"]["factors"]["invented"] = {"score":5}
        self.assertEqual(advise(case)["scored_factor_count"], 0)

    def test_other_input_changed_or_legacy_context_cannot_reuse_ai_gate(self):
        for missing in (True, False):
            case = fixture()
            case["ai_draft"]["gates"]["eligibility"]["status"] = "fail"
            if missing:
                del case["ai_draft_context_sha256"]
            else:
                case["prompt"] = "가상 회사 조건 정정"
            result = advise(case)
            self.assertEqual(result["draft_context_status"], "MISSING" if missing else "CHANGED")
            self.assertEqual(result["source_checks"]["gates"]["eligibility"]["status"], "EXTRACTED_TEXT_MATCH_ONLY")
            self.assertEqual(result["status"], "HOLD_UNVERIFIED")
            self.assertEqual(result["scored_factor_count"], 0)

    def test_manual_unknown_or_blank_evidence_cannot_set_verified(self):
        case = fixture()
        server.update_case(case, {"gates":{"licenses":{"status":"unknown", "evidence":"메모", "verified":True},
                                            "resources":{"status":"pass", "evidence":" \n ", "verified":True}},
                                  "factors":{"staff":{"score":5, "evidence":" \n ", "verified":True}}})
        self.assertFalse(case["gates"]["licenses"]["verified"])
        self.assertFalse(case["gates"]["resources"]["verified"])
        self.assertFalse(case["factors"]["staff"]["verified"])

    def test_citation_normalization_drops_authority_and_rejects_bad_types(self):
        citation = fixture()["ai_draft"]["citations"][0]
        altered = {**citation, "verified":True, "url":"javascript:alert(1)", "page":123}
        self.assertEqual(clean_citations([altered]), [citation])
        for invalid in ([{**citation, "offset_start":True}], [citation]*5,
                        [{**citation, "source_id":"https://example.invalid/"}],
                        [{**citation, "quote":" "}], "bad", [None]):
            with self.subTest(invalid=invalid):
                self.assertEqual(clean_citations(invalid), [])

    def test_prompt_contains_source_identifiers_and_does_not_serialize_company_registers(self):
        case = fixture()
        case["company_register"] = "SYNTHETIC_PRIVATE_MARKER"
        prompt = server.prompt_for(case)
        self.assertIn("source_id=document:0", prompt)
        self.assertIn(case["ai_draft"]["citations"][0]["text_sha256"], prompt)
        self.assertIn("citations=[]", prompt)
        self.assertNotIn("SYNTHETIC_PRIVATE_MARKER", prompt)


class DraftHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.file = self.root/"cases.json"
        self.rp = patch.object(server, "ROOT", self.root)
        self.fp = patch.object(server, "FILE", self.file)
        self.rp.start()
        self.fp.start()
        self.case = fixture()
        server.persist({"schema_version":1, "cases":[self.case]})
        self.http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.worker = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.worker.start()
        self.url = f"http://127.0.0.1:{self.http.server_port}"

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.worker.join(timeout=3)
        self.fp.stop()
        self.rp.stop()
        self.tmp.cleanup()

    def post(self, path, payload):
        req = Request(self.url+path, json.dumps(payload).encode(), method="POST",
                      headers={"Content-Type":"application/json", "Origin":self.url,
                               "X-Local-CSRF":server.TOKEN})
        with urlopen(req, timeout=5) as response:
            return json.load(response)

    def test_get_recomputes_draft_without_writing_or_calling_model(self):
        before = self.file.read_bytes()
        with patch.object(server, "call_cli", side_effect=AssertionError("external call forbidden")) as call:
            with urlopen(self.url+"/api/state", timeout=5) as response:
                data = json.load(response)["data"]["cases"][0]
            call.assert_not_called()
        self.assertEqual(data["decision_support"]["draft_state"], "DRAFT")
        self.assertEqual(data["decision"], "no_bid")
        self.assertEqual(self.file.read_bytes(), before)

    def test_model_failure_falls_back_and_keeps_final_decision_and_history(self):
        # Graph 결과 경계만 합성 대체한다. 실제 LangGraph/외부 모델의 성공 검증이 아니다.
        graph = types.ModuleType("cross_review")
        def execute(prompt, providers, caller):
            return {"independent":{p:caller(p, prompt) for p in providers},
                    "critiques":{}, "comparison":{"status":"single_or_failed"}}
        graph.execute_cross_review = execute
        with patch.dict("sys.modules", {"cross_review":graph}):
            with patch.object(server, "call_cli", return_value={"status":"error", "error":"synthetic timeout"}):
                result = self.post("/api/analyze", {"id":self.case["id"], "providers":["codex"], "consent":True})
        case = result["case"]
        self.assertEqual(case["decision_support"]["analysis_mode"], "RULE_BASED_FALLBACK")
        self.assertEqual(case["decision_support"]["status"], "HOLD_UNVERIFIED")
        self.assertEqual(case["ai_draft"], {})
        for field in ("decision", "reason", "history", "documents"):
            self.assertEqual(case[field], self.case[field])

    def test_graph_unavailable_or_timeout_is_explicit_fallback(self):
        for failure in (ImportError("synthetic missing dependency"), TimeoutError("synthetic timeout")):
            graph = types.ModuleType("cross_review")
            def execute(*args):
                raise failure
            graph.execute_cross_review = execute
            with patch.dict("sys.modules", {"cross_review":graph}):
                with patch.object(server, "call_cli", side_effect=AssertionError("external call forbidden")) as call:
                    result = self.post("/api/analyze", {"id":self.case["id"], "providers":["codex"], "consent":True})
                    call.assert_not_called()
            self.assertEqual(result["case"]["decision_support"]["analysis_mode"], "RULE_BASED_FALLBACK")
            self.assertEqual(result["case"]["decision"], self.case["decision"])
            self.assertEqual(result["case"]["ai_reports"]["codex"]["status"], "unavailable")

    def test_successful_synthetic_draft_binds_context_and_edit_invalidates_it(self):
        graph = types.ModuleType("cross_review")
        graph.execute_cross_review = lambda *args: {
            "independent":{"codex":{"status":"success", "result":self.case["ai_draft"]}},
            "critiques":{}, "comparison":{"status":"single_or_failed"}}
        with patch.dict("sys.modules", {"cross_review":graph}):
            with patch.object(server, "call_cli", side_effect=AssertionError("external call forbidden")):
                result = self.post("/api/analyze", {"id":self.case["id"], "providers":["codex"], "consent":True})
        case = result["case"]
        self.assertEqual(case["ai_draft_context_sha256"], context_digest(self.case))
        self.assertEqual(case["decision_support"]["analysis_mode"], "RULE_BASED_WITH_AI_DRAFT")
        result = self.post("/api/save", {"id":self.case["id"], "prompt":"가상 조건 변경"})
        self.assertEqual(result["case"]["decision_support"]["draft_context_status"], "CHANGED")
        self.assertEqual(result["case"]["decision"], "no_bid")
        self.assertEqual(result["case"]["history"], self.case["history"])

    def test_truncated_analysis_records_actual_ranges_and_preserves_user_history(self):
        case = capped_fixture()
        server.persist({"schema_version":1, "cases":[case]})
        graph = types.ModuleType("cross_review")
        captured = []
        def execute(prompt, providers, caller):
            captured.append(prompt)
            return {"independent":{"codex":{"status":"success", "result":case["ai_draft"]}},
                    "critiques":{}, "comparison":{"status":"single_or_failed"}}
        graph.execute_cross_review = execute
        with patch.dict("sys.modules", {"cross_review":graph}):
            with patch.object(server, "call_cli", side_effect=AssertionError("external call forbidden")) as call:
                result = self.post("/api/analyze", {"id":case["id"], "providers":["codex"], "consent":True})
                call.assert_not_called()
        stored = server.load()["cases"][0]
        coverage = stored["ai_input_coverage"]
        self.assertEqual(coverage, result["case"]["decision_support"]["input_coverage"])
        self.assertEqual(coverage["sources"][2]["transmitted_end"], captured[0].count("😀"))
        self.assertNotIn("OMITTED_SYNTHETIC_REQUIREMENT", captured[0])
        self.assertEqual(stored["decision_support"]["status"], "HOLD_INPUT_INCOMPLETE")
        for field in ("decision", "reason", "history", "documents"):
            self.assertEqual(stored[field], case[field])
        before = self.file.read_bytes()
        with urlopen(self.url+"/api/state", timeout=5) as response:
            reloaded = json.load(response)["data"]["cases"][0]
        self.assertEqual(reloaded["decision_support"]["input_coverage"], coverage)
        self.assertEqual(self.file.read_bytes(), before)

    def test_concurrent_source_edit_rejects_late_ai_result(self):
        graph = types.ModuleType("cross_review")
        def execute(*args):
            state = server.load()
            state["cases"][0]["prompt"] = "합성 동시 수정"
            server.persist(state)
            return {"independent":{"codex":{"status":"success", "result":self.case["ai_draft"]}},
                    "critiques":{}, "comparison":{"status":"single_or_failed"}}
        graph.execute_cross_review = execute
        with patch.dict("sys.modules", {"cross_review":graph}):
            with self.assertRaises(HTTPError) as error:
                self.post("/api/analyze", {"id":self.case["id"], "providers":["codex"], "consent":True})
        self.assertEqual(error.exception.code, 409)
        stored = server.load()["cases"][0]
        self.assertEqual(stored["prompt"], "합성 동시 수정")
        self.assertEqual(stored["decision"], self.case["decision"])
        self.assertEqual(stored["history"], self.case["history"])

    def test_missing_consent_does_not_call_model_or_modify_file(self):
        before = self.file.read_bytes()
        with patch.object(server, "call_cli", side_effect=AssertionError("external call forbidden")) as call:
            with self.assertRaises(HTTPError) as error:
                self.post("/api/analyze", {"id":self.case["id"], "providers":["codex"], "consent":False})
            self.assertEqual(error.exception.code, 400)
            call.assert_not_called()
        self.assertEqual(self.file.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
