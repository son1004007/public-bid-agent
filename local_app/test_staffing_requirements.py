"""RFP 인력 요구사항: 근거 보존, 보수적 후보, 내부등급 비확정, 읽기 전용 HTTP 회귀.

모든 문서/인원/공고는 합성 fixture. 외부 네트워크 및 사용자 파일 접근 없음.
"""
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.request import urlopen
from urllib.error import HTTPError
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parent))
from staffing_requirements import assess
from workforce import summary
import server
import dashboard_backend


def sample_notice(text, status="EXTRACTED"):
    return {"id":"G2B-SYNTHETIC-00", "document_status":status,
            "rfp_text":text, "document_source_name":"합성_제안요청서.pdf",
            "document_evidence":[{
                "name":"합성_제안요청서.pdf", "status":"EXTRACTED",
                "sha256":"a"*64, "excerpt":text}]}


def aggregate():
    data={"schema_version":1,
          "annual_grade_rates_krw":{"junior":30000000,
                                     "intermediate":40000000,"senior":50000000},
          "staff":[
              {"id":"T1","role":"developer","grade":"senior","lead":False,
               "skills":["JAVA"],"skills_evidence":"ASSUMED",
               "responsibility":"합성 담당 분야","responsibility_evidence":"ASSUMED",
               "available_mm":None},
              {"id":"T2","role":"analyst","grade":"intermediate","lead":False,
               "skills":["PYTHON"],"skills_evidence":"ASSUMED",
               "responsibility":"합성 담당 분야","responsibility_evidence":"ASSUMED",
               "available_mm":None}
          ]}
    return summary(data),data


class StaffingExtractionTest(unittest.TestCase):
    def test_explicit_table_lines_with_provenance(self):
        notice=sample_notice("사업개요\n투입인력 및 자격요건\n직무 등급 인원 기술\n개발자 고급 2명 JAVA\n데이터 분석가 중급 1명 PYTHON DB\n기타 설명")
        result=assess(notice,aggregate()[0])
        self.assertEqual(result["document_count"],1)
        self.assertEqual(result["requirement_count"],2)
        req1,req2=result["requirements"]
        self.assertEqual((req1["role"],req1["grade"],req1["headcount"]),
                         ("developer","senior",2))
        self.assertEqual(req1["skills"],["JAVA"])
        self.assertEqual(req2["skills"],["DB","PYTHON"])
        self.assertEqual(req1["source_sha256"],"a"*64)
        self.assertEqual(req1["source_status"],"HASH_FORMAT_PRESENT_UNVERIFIED")
        self.assertEqual(len(req1["excerpt_sha256"]),64)
        self.assertNotIn("nominal_capacity_mm",json.dumps(result))
        self.assertEqual(req1["nominal_internal_grade_count"],1)
        self.assertEqual(req1["matching_status"],"NEEDS_EVIDENCE")
        self.assertEqual(result["staffing_eligibility"],"UNVERIFIED")
        self.assertNotIn("T1",json.dumps(result))

    def test_no_rfp_is_unknown_not_zero_or_unqualified(self):
        n=sample_notice("투입인력\n고급 개발자 2명",status="FAILED")
        r=assess(n,aggregate()[0])
        self.assertEqual(r["document_state"],"NO_RFP_EXTRACTED")
        self.assertEqual(r["requirements"],[])
        self.assertEqual(r["staffing_eligibility"],"UNVERIFIED")

    def test_optional_and_ambiguous_are_not_explicit(self):
        for text in ("개발자 고급 2명",
                     "참고 자료\n투입인력 예시\n개발자 고급 2명",
                     "투입인력\n개발자 고급 2MM",
                     "투입인력\n개발자 고급 2명 분석가 중급 1명",
                     "투입인력\n고급 개발자 2명 우대사항\n개발자 중급 1명",
                     "우대사항\n제안 인력 구성\n개발자 고급 2명",
                     "제안 인력 구성\n개발자 고급 2명",
                     "우대사항\n투입인력\n개발자 고급 2명"):
            with self.subTest(text=text):
                result=assess(sample_notice(text))
                self.assertEqual(result["requirement_count"],0)

    def test_optional_section_reactivated_only_by_explicit_required_heading(self):
        n=sample_notice("우대사항\n투입인력\n고급 개발자 2명\n필수 인력\n분석가 중급 1명")
        r=assess(n)
        self.assertEqual(r["requirement_count"],1)
        self.assertEqual(r["requirements"][0]["role"],"analyst")

    def test_document_count_limits_and_truncation_are_explicit(self):
        n=sample_notice("필수 투입인력\n고급 개발자 2명"+"A"*6020)
        n["document_evidence"][0]["chars"]=7000
        n["document_evidence"].extend([
            {"name":"second.pdf","status":"EXTRACTED","sha256":"b"*64,"excerpt":"필수 투입인력\n고급 개발자 1명"},
            {"name":"third.pdf","status":"EXTRACTED","sha256":"c"*64,"excerpt":"필수 투입인력\n고급 개발자 3명"}])
        r=assess(n)
        self.assertEqual(r["processed_document_count"],2)
        self.assertEqual(r["total_document_evidence_count"],3)
        self.assertEqual(r["skipped_document_count"],1)
        self.assertEqual(r["skipped_due_to_limit_count"],1)
        self.assertTrue(r["any_text_truncated"])
        self.assertEqual(r["excerpt_char_limit"],6000)
        self.assertEqual(r["requirement_count"],1)
        self.assertTrue(all("excerpt_sha256" in x for x in r["requirements"]))

    def test_at_least_is_minimum_not_exact(self):
        report=assess(sample_notice("필수 인력\n개발자 고급 2명 이상"))
        self.assertEqual(report["requirement_count"],1)
        self.assertEqual(report["requirements"][0]["headcount"],2)
        self.assertEqual(report["requirements"][0]["count_kind"],"AT_LEAST")
        ordinary=assess(sample_notice("필수 인력\n개발자 고급 2명"))
        self.assertEqual(ordinary["requirements"][0]["count_kind"],"STATED")

    def test_minimum_and_postpositional_at_least_counts(self):
        for text in ("개발자 고급 최소 2명",
                     "개발자 고급 2명 이상을 투입",
                     "개발자 고급 2명 이상으로 구성",
                     "개발자 고급 2명 이상의 인력"):
            with self.subTest(text=text):
                report=assess(sample_notice("필수 인력\n"+text))
                self.assertEqual(report["requirement_count"],1)
                self.assertEqual(report["requirements"][0]["headcount"],2)
                self.assertEqual(report["requirements"][0]["count_kind"],"AT_LEAST")

    def test_inline_exception_negates_only_explicitly_referenced_staff(self):
        report=assess(sample_notice(
            "필수 인력: 개발자 고급 2명(단, 해당 인력은 요구하지 않음)"))
        self.assertEqual(report["requirement_count"],0)
        positive=assess(sample_notice(
            "필수 인력\n개발자 고급 2명 (별도 자격증 필요 없음)"))
        self.assertEqual(positive["requirement_count"],1)

    def test_truncated_last_line_not_treated_as_complete_requirement(self):
        prefix="필수 인력\n"+"X"*(6000-len("필수 인력\n")-len("\n개발자 고급 2명"))+"\n"
        full=prefix+"개발자 고급 2명 요구하지 않음"
        n=sample_notice(full)
        n["document_evidence"][0]["excerpt"]=full[:6000]
        n["document_evidence"][0]["chars"]=len(full)
        report=assess(n)
        self.assertTrue(report["any_text_truncated"])
        self.assertEqual(report["requirement_count"],0)

    def test_postposition_negation_and_explicit_no_staff_heading(self):
        for text in ("필수 인력\n개발자 고급 2명 이상으로 필요 없음",
                     "필수 인력 없음(필요 시 개발자 고급 2명 배치)"):
            with self.subTest(text=text):
                self.assertEqual(assess(sample_notice(text))["requirement_count"],0)

    def test_broad_staffing_headings_are_not_mandatory(self):
        for heading in ("수행 인력","참여 인력","인력 구성","사업 수행 조직"):
            with self.subTest(heading=heading):
                report=assess(sample_notice(heading+"\n개발자 고급 2명"))
                self.assertEqual(report["requirement_count"],0)

    def test_third_valid_document_selected_after_invalid_evidence(self):
        n=sample_notice("필수 인력\n개발자 고급 2명")
        n["document_evidence"]=[
            {"status":"FAILED","name":"bad.pdf","sha256":None},
            {"status":"EXTRACTED","name":"wrong-hash.pdf","sha256":"wrong",
             "excerpt":""},
            {"status":"EXTRACTED","name":"valid.pdf","sha256":"b"*64,
             "excerpt":"필수 인력\n개발자 고급 3명"}]
        r=assess(n)
        self.assertEqual(r["document_count"],1)
        self.assertEqual(r["requirements"][0]["headcount"],3)
        self.assertEqual(r["requirements"][0]["source_document"],"저장 문서 #3")
        self.assertEqual(r["skipped_document_count"],2)
        self.assertEqual(r["skipped_nonextracted_or_invalid_count"],2)

    def test_late_lines_within_6000_chars_are_scanned(self):
        n=sample_notice(("x\n"*460)+"필수 인력\n개발자 고급 2명")
        r=assess(n)
        self.assertEqual(r["requirement_count"],1)

    def test_malformed_document_evidence_fails_closed(self):
        for invalid in (None,{},{"test":1},"string"):
            n=sample_notice("필수 인력\n개발자 고급 2명")
            n["document_evidence"]=invalid
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):
                assess(n)

    def test_negative_required_staff_context_does_not_activate(self):
        for text in ("필수 투입인력은 별도 요구하지 않음\n개발자 고급 2명",
                     "필수 인력은 제안사가 자율 구성\n개발자 고급 2명",
                     "필수 인력은 제안사가 자율 구성(별도 자격증 필요 없음)\n개발자 고급 2명",
                     "필수 인력\n없음\n개발자 고급 2명",
                     "필수 인력은 개발자 고급 2명 요구하지 않음",
                     "필수 인력은 개발자 고급 2명을 요구하지 않음",
                     "필수 인력은 개발자 고급 2명 별도로 필요 없음",
                     "필수 인력은 개발자 고급 2명 이상 요구하지 않음",
                     "필수 인력은 개발자 고급 2명 이상은 요구하지 않음",
                     "필수 인력: 개발자 고급 2명은 필요하지 않음",
                     "필수 인력: 개발자 고급 2명은 요구되지 않음",
                     "필수 인력: 개발자 고급 2명은 필요치 않음",
                     "필수 인력은 별도 요구하지 않음, 개발자 고급 2명"):
            with self.subTest(text=text):
                self.assertEqual(assess(sample_notice(text))["requirement_count"],0)

    def test_negated_second_role_does_not_hide_first_required_role(self):
        report=assess(sample_notice("필수 인력: 개발자 고급 2명, PM 1명 요구하지 않음"))
        self.assertEqual(report["requirement_count"],1)
        item=report["requirements"][0]
        self.assertEqual(item["role"],"developer")
        self.assertEqual(item["headcount"],2)

    def test_unrelated_certificate_exemption_keeps_required_staff(self):
        for line in (
            "개발자 고급 2명 (별도 자격증 필요 없음)",
            "필수 인력: 개발자 고급 2명 (자격증 필요 없음)",
            "개발자 고급 2명 (별도 면허 없음)",
        ):
            with self.subTest(line=line):
                report=assess(sample_notice("필수 인력\n"+line))
                self.assertEqual(report["requirement_count"],1)
                self.assertEqual(report["requirements"][0]["headcount"],2)

    def test_header_exemption_of_certification_keeps_staffing(self):
        report=assess(sample_notice(
            "필수 인력 자격요건: 별도 자격증 필요 없음\n개발자 고급 2명"))
        self.assertEqual(report["requirement_count"],1)
        self.assertEqual(report["requirements"][0]["headcount"],2)

    def test_upper_bound_is_not_misreported_as_required_exact_count(self):
        for line in ("개발자 고급 최대 2명", "개발자 고급 2명 이내",
                     "개발자 고급 2명 내외", "개발자 고급 2명 이하"):
            with self.subTest(line=line):
                report=assess(sample_notice("필수 인력\n"+line))
                self.assertEqual(report["requirement_count"],0)

    def test_shared_count_with_two_roles_is_not_assigned_to_one(self):
        report=assess(sample_notice("필수 인력\n개발자·분석가 고급 2명"))
        self.assertEqual(report["requirement_count"],0)
        report2=assess(sample_notice("필수 인력\n개발자 고급 2명, 분석가 중급 1명"))
        self.assertEqual(report2["requirement_count"],2)

    def test_certificate_holder_exemption_preserves_staffing(self):
        report=assess(sample_notice(
            "필수 인력은 자격증 소지자를 요구하지 않음\n개발자 고급 2명"))
        self.assertEqual(report["requirement_count"],1)
        self.assertEqual(report["requirements"][0]["headcount"],2)

    def test_api_candidate_excerpt_does_not_echo_pii(self):
        report=assess(sample_notice(
            "필수 인력\n홍길동 010-1234-5678 개발자 고급 2명 hello@example.com"))
        self.assertEqual(report["requirement_count"],1)
        body=json.dumps(report,ensure_ascii=False)
        for term in ("홍길동","010-1234-5678","hello@example.com","합성_제안요청서.pdf"):
            self.assertNotIn(term,body)
        self.assertEqual(report["requirements"][0]["source_excerpt"],"개발자 고급 2명")
        self.assertEqual(report["requirements"][0]["source_document"],"저장 문서 #1")

    def test_three_and_four_digit_staff_counts_are_visible(self):
        for count in (100,120,1000):
            text="필수 인력\n개발자 고급 "+str(count)+"명 이상"
            report=assess(sample_notice(text))
            self.assertEqual(report["requirement_count"],1)
            item=report["requirements"][0]
            self.assertEqual(item["headcount"],count)
            self.assertEqual(item["count_kind"],"AT_LEAST")
            self.assertEqual(item["headcount_check"],"OUT_OF_RANGE_FOR_REVIEW" if count>500 else "STANDARD_CANDIDATE")

    def test_missing_or_bad_hash_still_extracts_with_lower_provenance(self):
        for sha, expected in ((None,"HASH_MISSING_UNVERIFIED"),
                              ("not-a-sha","HASH_INVALID_UNVERIFIED")):
            n=sample_notice("필수 인력\n개발자 고급 2명")
            n["document_evidence"][0]["sha256"]=sha
            report=assess(n)
            self.assertEqual(report["requirement_count"],1)
            self.assertEqual(report["requirements"][0]["source_status"],expected)
            self.assertIsNone(report["requirements"][0]["source_sha256"])
            self.assertEqual(report["document_state"],"EXTRACTED_REQUIREMENTS_FOR_REVIEW")
            self.assertEqual(report["skipped_nonextracted_or_invalid_count"],0)

    def test_excerpt_line_and_identity_do_not_claim_pdf_page(self):
        n=sample_notice("설명\n필수 인력\n개발자 고급 2명")
        n["document_evidence"][0]["identity"]="c"*64
        result=assess(n)
        item=result["requirements"][0]
        self.assertEqual(item["excerpt_line"],3)
        self.assertEqual(item["source_identity"],"c"*64)
        self.assertEqual(item["original_page"],"UNKNOWN")

    def test_legacy_text_is_marked_low_provenance(self):
        n=sample_notice("필수 투입인력\n고급 개발자 2명")
        n["document_evidence"]=[]
        r=assess(n)
        self.assertEqual(r["requirement_count"],1)
        self.assertEqual(r["requirements"][0]["source_status"],"LEGACY_SOURCE_UNVERIFIED")
        self.assertIsNone(r["requirements"][0]["source_sha256"])
        self.assertIsNone(r["requirements"][0]["nominal_internal_grade_count"])

    def test_duplicate_source_lines_do_not_duplicate_requirements(self):
        n=sample_notice("필수 투입인력\n고급 개발자 2명\n고급 개발자 2명")
        r=assess(n)
        self.assertEqual(r["requirement_count"],1)

    def test_poor_footnotes_without_grade_number_are_unknown(self):
        n=sample_notice("필수 인력\nPM(사업관리자) 1명 이상\n경력 5년 이상\n정보처리기사 자격증")
        r=assess(n)
        self.assertEqual(r["document_state"],"NO_EXPLICIT_REQUIREMENT_FOUND")
        self.assertEqual(r["staffing_eligibility"],"UNVERIFIED")


class StaffingHTTPTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.root_patch=patch.object(server,"ROOT",self.root)
        self.root_patch.start()
        notice=sample_notice("필수 투입인력\n고급 개발자 2명 JAVA")
        state=dashboard_backend.blank()
        state["notices"]=[notice]
        server.persist(state,self.root/"dashboard.json")
        self.before=(self.root/"dashboard.json").read_bytes()
        server.persist({"schema_version":1,"cases":[{"id":"synthetic-old","title":"preserve"}]},self.root/"cases.json")
        self.cases_before=(self.root/"cases.json").read_bytes()
        self.http=ThreadingHTTPServer(("127.0.0.1",0),server.Handler)
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True)
        self.thread.start()
        self.url="http://127.0.0.1:"+str(self.http.server_port)
    def tearDown(self):
        self.http.shutdown();self.http.server_close();self.thread.join(timeout=3)
        self.root_patch.stop();self.temp.cleanup()

    def test_endpoint_read_only_and_no_private_details(self):
        code=None
        with urlopen(self.url+"/api/dashboard/staffing?id=G2B-SYNTHETIC-00",timeout=4) as response:
            code=response.status
            data=json.load(response)
        self.assertEqual(code,200)
        self.assertEqual(data["staffing"]["requirement_count"],1)
        self.assertEqual(data["staffing"]["workforce_state"],"NOT_CONFIGURED")
        self.assertEqual(self.before,(self.root/"dashboard.json").read_bytes())
        self.assertEqual(self.cases_before,(self.root/"cases.json").read_bytes())
        self.assertFalse((self.root/"workforce.json").exists())

    def test_private_staffing_api_exposes_only_aggregate_count(self):
        self.root.joinpath("workforce.json").write_text(
            json.dumps(aggregate()[1], ensure_ascii=False), encoding="utf-8")
        with urlopen(self.url+"/api/dashboard/staffing?id=G2B-SYNTHETIC-00",timeout=4) as response:
            data=json.load(response)
        item=data["staffing"]["requirements"][0]
        self.assertEqual(item["nominal_internal_grade_count"],1)
        self.assertEqual(data["staffing"]["staffing_eligibility"],"UNVERIFIED")
        serialized=json.dumps(data)
        for prohibited in ("T1","T2","nominal_capacity_mm","available_mm",
                           "annual_assumed_salary", "cost_per_mm_krw"):
            self.assertNotIn(prohibited,serialized)

    def test_http_extracted_candidate_does_not_return_source_pii(self):
        path=self.root/"dashboard.json"
        dashboard=json.loads(self.before)
        notice=dashboard["notices"][0]
        notice["document_evidence"][0]["name"]="홍길동-개인정보-문서.pdf"
        notice["document_evidence"][0]["excerpt"]=(
            "필수 인력\\n홍길동 010-1234-5678 개발자 고급 2명 hello@example.com")
        notice["rfp_text"]=notice["document_evidence"][0]["excerpt"]
        path.write_text(json.dumps(dashboard,ensure_ascii=False),encoding="utf-8")
        original=path.read_bytes()
        with urlopen(self.url+"/api/dashboard/staffing?id=G2B-SYNTHETIC-00",timeout=4) as response:
            text=response.read().decode("utf-8")
        for secret in ("홍길동","010-1234-5678","hello@example.com","개인정보-문서.pdf"):
            self.assertNotIn(secret,text)
        self.assertIn("개발자 고급 2명",text)
        self.assertEqual(path.read_bytes(),original)
        self.assertEqual((self.root/"cases.json").read_bytes(),self.cases_before)

    def test_unknown_and_injection_fail_and_preserve_data(self):
        for query,expected in (("id=G2B-MISSING-00",404),
                               ("id=../../private",400),
                               ("id=G2B-SYNTHETIC-00&id=G2B-OTHER-00",400),
                               ("something=else",400)):
            with self.subTest(query=query):
                with self.assertRaises(HTTPError) as ctx:
                    urlopen(self.url+"/api/dashboard/staffing?"+query,timeout=4)
                self.assertEqual(ctx.exception.code,expected)
        self.assertEqual(self.before,(self.root/"dashboard.json").read_bytes())

    def test_corrupt_document_evidence_returns_503(self):
        path=self.root/"dashboard.json"
        for invalid in (None,{}, "malformed"):
            state=json.loads(self.before)
            state["notices"][0]["document_evidence"]=invalid
            raw=json.dumps(state).encode("utf-8")
            path.write_bytes(raw)
            with self.subTest(invalid=invalid),self.assertRaises(HTTPError) as error:
                urlopen(self.url+"/api/dashboard/staffing?id=G2B-SYNTHETIC-00",timeout=4)
            self.assertEqual(error.exception.code,503)
            self.assertEqual(path.read_bytes(),raw)

    def test_corrupt_workforce_fails_without_overwriting(self):
        p=self.root/"workforce.json"
        p.write_text("not-json",encoding="utf-8")
        with self.assertRaises(HTTPError) as ctx:
            urlopen(self.url+"/api/dashboard/staffing?id=G2B-SYNTHETIC-00",timeout=4)
        self.assertEqual(ctx.exception.code,503)
        self.assertEqual(p.read_text(encoding="utf-8"),"not-json")


if __name__=="__main__":
    unittest.main()
