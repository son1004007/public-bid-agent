"""부서 분류/마감/공공문서 경계/부서 프로필 회귀 테스트.

실 사용자 키·실제 공고 DB·공식 첨부 URL에 접속하지 않는다.
"""
import io
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import dashboard_backend as db
import procurement_filter as flt
import procurement_documents as docs
import department_profile as dept

KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 10, 11, 12, tzinfo=KST)


class DepartmentClassificationTests(unittest.TestCase):
    def test_title_without_technical_words_but_official_taxonomy_sw(self):
        n = db.normalize({
            "bidNtceNo":"R26BK01760557","bidNtceOrd":"000","bidNtceNm":"차세대 업무혁신 추진",
            "pubPrcrmntClsfcNm":"정보시스템개발서비스","infoBizYn":"Y",
            "bidClseDt":"2026-10-20 10:00:00","ntceKindNm":"등록공고",
            "ntceSpecFileNm1":"제안요청서.hwpx",
            "ntceSpecDocUrl1":"https://www.g2b.go.kr/pn/pnp/pnpe/UntyAtchFile/downloadRfpFile.do?test=1",
        })
        self.assertEqual(n["department_status"],"CANDIDATE")
        self.assertIn("SW",n["department_categories"])
        self.assertEqual(n["category_evidence"][0]["sources"][0],"공공조달분류")
        self.assertEqual(n["window_status"],"OPEN")
        self.assertEqual(n["legal_eligibility"],"UNVERIFIED")
        self.assertEqual(len(n["attachments"]),1)
        self.assertEqual(n["document_status"],"PENDING")
        self.assertEqual(n["rfp_text"],"")

    def test_generic_construction_word_does_not_make_software_candidate(self):
        r=flt.classify("부동산제도 간 상호작용을 고려한 이론모형 구축",
                       "기타연구조사서비스")
        self.assertNotIn("SW",r["department_categories"])
        self.assertEqual(r["department_status"],"REVIEW")

    def test_no_title_gate_retains_unmatched_rows(self):
        n = db.normalize({"bidNtceNo":"R26BK12345678","bidNtceOrd":"000",
                          "bidNtceNm":"통합업무지원","ntceKindNm":"등록공고",
                          "bidClseDt":"2026-10-20 10:00:00"})
        self.assertEqual(n["department_status"],"REVIEW")
        self.assertEqual(n["department_categories"],[])
        self.assertEqual(n["legal_eligibility"],"UNVERIFIED")

    def test_status_closing_cancelled_unknown_and_registration(self):
        self.assertEqual(flt.bid_window("2026-10-20 00:00","등록공고",at=NOW),"OPEN")
        self.assertEqual(flt.bid_window("2026-10-01 00:00","등록공고",at=NOW),"CLOSED")
        self.assertEqual(flt.bid_window("2026-10-25 00:00","취소공고",at=NOW),"CANCELLED")
        self.assertEqual(flt.bid_window("미확인","등록공고",at=NOW),"UNKNOWN")
        self.assertEqual(flt.bid_window("2026-10-25 00:00","등록공고",
                         "2026-10-10 18:00",at=NOW),"REGISTRATION_REVIEW")

    def test_rfp_text_can_reclassify_unrelated_title(self):
        n = db.normalize({"bidNtceNo":"R26BK12345678","bidNtceOrd":"001",
                          "bidNtceNm":"과업 수행 용역", "bidClseDt":"2026-10-20 00:00"})
        self.assertEqual(n["department_status"],"REVIEW")
        n["rfp_text"]="주요 과업: 자연어 질의 기반 데이터 파이프라인 구축과 API 개발"
        flt.apply(n,at=NOW)
        self.assertIn("DATA",n["department_categories"])
        self.assertIn("SW",n["department_categories"])
        self.assertFalse(n["needs_document"])
        self.assertIn("RFP 추출본문",str(n["category_evidence"]))
    
    def test_existing_decision_survives_reclassification(self):
        item=db.normalize({"bidNtceNo":"R26BK99999999","bidNtceOrd":"000",
                          "bidNtceNm":"데이터 파이프라인 구축"})
        item["final"]="no_bid";item["finalReason"]="검토 후 불참"
        state=db.update_collection(db.blank(),[item],1,"now")
        changed=db.normalize({"bidNtceNo":"R26BK99999999","bidNtceOrd":"000",
                          "bidNtceNm":"업무 혁신 구축", "pubPrcrmntClsfcNm":"정보시스템개발서비스"})
        new=db.update_collection(state,[changed],1,"later")
        self.assertEqual(new["notices"][0]["final"],"no_bid")
        self.assertEqual(new["notices"][0]["finalReason"],"검토 후 불참")
        self.assertEqual(new["notices"][0]["department_status"],"CANDIDATE")


class DocumentBoundaryTests(unittest.TestCase):
    def test_official_domain_only(self):
        self.assertTrue(docs.official_url("https://www.g2b.go.kr/document.pdf"))
        for url in ("http://www.g2b.go.kr/doc.pdf","https://evil.example/file.pdf",
                    "https://www.g2b.go.kr.evil.example/a.pdf",
                    "https://www.g2b.go.kr:444/a.pdf","file:///etc/passwd",
                    "https://user@www.g2b.go.kr/path"):
            self.assertFalse(docs.official_url(url))

    def test_document_priority_and_safe_fetch(self):
        n={"attachments":[
          {"name":"공고문.pdf","url":"https://www.g2b.go.kr/one.pdf"},
          {"name":"제안요청서.hwpx","url":"https://www.g2b.go.kr/two.hwpx"}]}
        chosen,extension=docs.choose_attachment(n)
        self.assertEqual(extension,".hwpx")
        self.assertEqual(chosen["name"],"제안요청서.hwpx")
        with self.assertRaises(docs.DocumentFetchError):
            docs.choose_attachment({"attachments":[{"name":"bad.exe","url":"https://evil.example/a.exe"}]})

    def test_extraction_fake_binary_without_network(self):
        class Response(io.BytesIO):
            def geturl(self):
                return "https://www.g2b.go.kr/two.hwpx"
        class FakeOpener:
            def open(self,request,timeout):
                self.assert_dummy=True
                return Response(b"fake-binary-fixture")
        n={"attachments":[{"name":"제안요청서.hwpx","url":"https://www.g2b.go.kr/two.hwpx"}]}
        with patch.object(docs,"fetch_attachment",return_value=b"fake-binary-fixture"):
            x=docs.extract(n,lambda name,data:{"text":"정보시스템 구축 및 데이터 분석","warnings":[]})
        self.assertIn("정보시스템",x["text"])
        self.assertEqual(x["source_name"],"제안요청서.hwpx")
        self.assertNotIn("url",x)

    def test_profile_validation_conflict_and_version(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"department_profile.json"
            base=dept.load(path)
            self.assertEqual(len(base["categories"]),4)
            next_state=dept.modify(base,{"expected_revision":0,
                "profile":{"categories":["DATA","SW"],"include_review":True}})
            self.assertEqual(next_state["revision"],1)
            with self.assertRaises(dept.DepartmentProfileConflict):
                dept.modify(next_state,{"expected_revision":0,
                    "profile":{"categories":["SW"],"include_review":False}})
            with self.assertRaises(ValueError):
                dept.validate({"categories":["UNKNOWN"],"include_review":False})
            with self.assertRaises(ValueError):
                dept.validate({"categories":["SW","SW"],"include_review":True})


if __name__=="__main__":
    unittest.main()
