"""RFP 추출 손실 집계의 합성·비공개 입력 격리 테스트."""
import json
import unittest

from rfp_extraction_loss import inspect, MAX_SCAN
from rfp_coverage import summarize

URL = "https://www.g2b.go.kr/document"
REF = "a" * 64
PROFILE = {"categories": ["SW"]}


def extracted(stored=44_000, reported=137_257, truncated=True):
    return {"status": "EXTRACTED", "fulltext_ref": REF,
            "fulltext_chars": stored, "fulltext_reported_chars": reported,
            "fulltext_truncated": truncated, "warnings": []}


def notice(ident, evidence, **kw):
    return {"id": f"G2B-SYN{ident}-001", "title": "비공개 실제자료 아님",
            "department_status": "CANDIDATE", "department_categories": ["SW"],
            "document_status": "EXTRACTED", "rfp_text": "합성 데이터",
            "notice_kind": "일반공고", "end": "2099-12-31T23:59:59",
            "attachments": [{"name": "test.pdf", "url": URL}],
            "document_evidence": evidence, **kw}


class ExtractionLossTests(unittest.TestCase):
    def test_quantifies_only_reported_truncation(self):
        detail = inspect(notice(1, [extracted(), extracted(44000, 44002),
                                    {"status":"FAILED", "fulltext_reported_chars": 200000}]))
        self.assertEqual(detail["extracted_records"], 2)
        self.assertEqual(detail["truncation_records"], 2)
        self.assertEqual(detail["quantified_truncation_records"], 2)
        self.assertEqual(detail["reported_unstored_characters"], 93_259)
        self.assertEqual(detail["unquantified_truncation_records"], 0)

    def test_unknown_and_inconsistent_never_count_as_known_loss(self):
        samples = [
            extracted(44000, 44000),
            extracted(True, 50000),
            extracted(44000, 43000),
            extracted(44000, 20_000_001),
            extracted(44000, 44050, truncated="true"),
            extracted(44000, 44050, truncated=False),
            {**extracted(), "fulltext_ref": "invalid-ref"},
        ]
        detail = inspect(notice(2, samples))
        self.assertEqual(detail["truncation_records"], 5)
        self.assertEqual(detail["unquantified_truncation_records"], 5)
        self.assertEqual(detail["quantified_truncation_records"], 0)
        self.assertEqual(detail["reported_unstored_characters"], 0)
        self.assertEqual(detail["inconsistent_metadata_records"], 2)

    def test_bounded_scan_prevents_tail_contamination(self):
        doc = notice(3, [{"status":"FAILED"}] * MAX_SCAN + [
            {**extracted(), "warnings": ["DO_NOT_RETURN_SECRET"]}, None])
        detail = inspect(doc)
        self.assertEqual(detail["evidence_scan_limit_exceeded"],1)
        self.assertEqual(detail["truncation_records"],0)
        self.assertEqual(detail["malformed_evidence"],0)
        self.assertEqual(detail["reported_unstored_characters"],0)
        self.assertNotIn("DO_NOT_RETURN_SECRET",json.dumps(detail))

    def test_malformed_record_and_parser_warning_only(self):
        doc = notice(4, [{"status":"EXTRACTED", "warnings":["기술평가 원문 PRIVATE"]},None])
        detail = inspect(doc)
        self.assertEqual(detail["extracted_records"],1)
        self.assertEqual(detail["warning_records"],1)
        self.assertEqual(detail["malformed_evidence"],1)
        self.assertEqual(detail["truncation_records"],0)
        self.assertNotIn("PRIVATE",json.dumps(detail))
        broken=notice(5,{})
        self.assertEqual(inspect(broken)["malformed_evidence"],1)

    def test_api_aggregate_separates_all_and_active_without_leakage(self):
        a=notice(6,[extracted(),extracted()])
        old=notice(7,[extracted(44000,44001)],notice_lifecycle="SUPERSEDED")
        unknown=notice(8,[{"status":"EXTRACTED","fulltext_truncated":True,
                            "warnings":["SENSITIVE_DOC_LABEL"]}])
        result=summarize([a,old,unknown],PROFILE)
        self.assertEqual(result["candidate_count"],3)
        self.assertEqual(result["active_candidate_count"],2)
        self.assertEqual(result["extraction_loss_all"]["reported_unstored_characters"],186_515)
        self.assertEqual(result["extraction_loss_active"]["reported_unstored_characters"],186_514)
        self.assertEqual(result["extraction_loss_all"]["notices_with_reported_loss"],2)
        self.assertEqual(result["extraction_loss_active"]["notices_with_reported_loss"],1)
        self.assertEqual(result["extraction_loss_active"]["unquantified_truncation_records"],1)
        self.assertEqual(result["loss_mode"],"STORED_PARSER_METADATA_UNVERIFIED_ORIGINAL")
        serialized=json.dumps(result,ensure_ascii=False)
        self.assertNotIn("SENSITIVE_DOC_LABEL",serialized)
        self.assertNotIn(URL,serialized)


if __name__ == "__main__":
    unittest.main()
