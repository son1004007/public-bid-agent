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
        self.assertEqual(report["ready_active"], 1)
        self.assertEqual(report["needs_related_lookup_active"], 1)
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

    def test_quality_flags_distinguish_unverified_refs_excerpts_and_parser_losses(self):
        mixed=item("1",state="EXTRACTED",excerpt="합성 발췌")
        mixed["document_evidence"]=[
            {"status":"EXTRACTED","fulltext_ref":"a"*64,"fulltext_truncated":True,
             "warnings":["합성: 표 미확인"],"secret":"NEVER_RETURN_MARKER"},
            {"status":"EXTRACTED","excerpt":"합성 발췌"},
            {"status":"EXTRACTED","fulltext_ref":"b"*64},
        ]
        legacy=item("2",state="EXTRACTED",excerpt="예전 합성 발췌")
        legacy["document_evidence"]=[]
        stale=item("3",state="EXTRACTED",excerpt="과거 발췌")
        stale["rfp_review_status"]="STALE"
        cancelled=item("4",state="EXTRACTED",excerpt="철회")
        cancelled["notice_lifecycle"]="CANCELLED"
        report=summarize([mixed,legacy,stale,cancelled],PROFILE)
        active=report["by_quality_active"]
        self.assertEqual(report["candidate_count"],4)
        self.assertEqual(report["active_candidate_count"],3)
        self.assertEqual(active["FULLTEXT_REFERENCE_UNVERIFIED"],1)
        self.assertEqual(active["EXCERPT_OR_LEGACY_ONLY"],1)
        self.assertEqual(active["EXTRACTED_WITHOUT_PROVENANCE"],2)
        self.assertEqual(active["PARSER_TRUNCATION_REPORTED"],1)
        self.assertEqual(active["PARSER_WARNING_REPORTED"],1)
        self.assertEqual(active["EXTRACTED_EVIDENCE_OVER_TWO"],1)
        self.assertEqual(active["STALE_RFP"],1)
        self.assertEqual(report["by_quality_all"]["CANCELLED_OR_SUPERSEDED"],1)
        self.assertEqual(active["CANCELLED_OR_SUPERSEDED"],0)
        self.assertEqual(report["quality_mode"],"UNVERIFIED_STORED_METADATA_ONLY")
        raw=json.dumps(report,ensure_ascii=False)
        self.assertNotIn("NEVER_RETURN_MARKER",raw)
        self.assertNotIn("합성: 표 미확인",raw)
        self.assertNotIn("합성 발췌",raw)

    def test_quality_flags_detect_metadata_limits_and_malformed_evidence(self):
        over=item("1",state="EXTRACTED",excerpt="합성")
        over["attachments"]=[{"name":"자료", "url": URL}]*401
        over["document_evidence"]=[{"status":"FAILED"}]*121+[None]
        report=summarize([over],PROFILE)
        q=report["by_quality_active"]
        self.assertEqual(q["ATTACHMENT_SCAN_OVER_LIMIT"],1)
        self.assertEqual(q["EVIDENCE_SCAN_OVER_LIMIT"],1)
        # 121번째 이후의 잘못된 레코드는 탐색 상한 밖이므로 독립 플래그에 전파 금지.
        self.assertEqual(q["MALFORMED_EVIDENCE"],0)
        self.assertEqual(q["EXTRACTED_WITHOUT_PROVENANCE"],1)
        self.assertEqual(q["PARSER_TRUNCATION_REPORTED"],0)
        malformed=item("2",state="EXTRACTED",excerpt="합성")
        malformed["document_evidence"]={"broken":"UNSAFE"}
        result=summarize([malformed],PROFILE)
        self.assertEqual(result["by_quality_active"]["MALFORMED_EVIDENCE"],1)

    def test_review_is_not_cancelled_and_limit_ignores_tail_entries(self):
        review=item("77",state="EXTRACTED",excerpt="합성")
        review["notice_lifecycle"]="REVIEW"
        old=item("78",state="EXTRACTED",excerpt="합성")
        old["notice_lifecycle"]="SUPERSEDED"
        cancel=item("79",state="EXTRACTED",excerpt="합성")
        cancel["notice_kind"]="취소공고"
        excessive=item("80",state="EXTRACTED",excerpt="합성")
        excessive["document_evidence"]=[{"status":"FAILED"}]*120+[
            {"status":"EXTRACTED","fulltext_ref":"a"*64,"fulltext_truncated":True,
             "warnings":["MUST_NOT_SURFACE"]},None,
        ]
        report=summarize([review,old,cancel,excessive],PROFILE)
        self.assertEqual(report["candidate_count"],4)
        self.assertEqual(report["active_candidate_count"],1)
        self.assertEqual(report["by_quality_all"]["LIFECYCLE_REVIEW"],1)
        self.assertEqual(report["by_quality_all"]["CANCELLED_OR_SUPERSEDED"],2)
        self.assertEqual(report["by_quality_active"]["CANCELLED_OR_SUPERSEDED"],0)
        q=report["by_quality_active"]
        self.assertEqual(q["EVIDENCE_SCAN_OVER_LIMIT"],1)
        self.assertEqual(q["EXTRACTED_WITHOUT_PROVENANCE"],1)
        self.assertEqual(q["MALFORMED_EVIDENCE"],0)
        self.assertEqual(q["FULLTEXT_REFERENCE_UNVERIFIED"],0)
        self.assertEqual(q["PARSER_TRUNCATION_REPORTED"],0)
        self.assertEqual(q["PARSER_WARNING_REPORTED"],0)
        self.assertNotIn("MUST_NOT_SURFACE",json.dumps(report))

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
                    self.assertIn("by_quality_active",result["coverage"])
                    self.assertEqual(result["coverage"]["by_quality_active"]["FULLTEXT_REFERENCE_UNVERIFIED"],0)
                    self.assertEqual(result["coverage"]["quality_mode"],"UNVERIFIED_STORED_METADATA_ONLY")
                    self.assertEqual(result["coverage"]["loss_mode"],"STORED_PARSER_METADATA_UNVERIFIED_ORIGINAL")
                    self.assertEqual(result["coverage"]["extraction_loss_active"]["reported_unstored_characters"],0)
                    self.assertEqual(result["storage"],"LOCAL_JSON")
                    self.assertNotIn("SECRET_DO_NOT_RETURN",json.dumps(result))
                    self.assertNotIn("https://",json.dumps(result))
                    self.assertEqual(before,(path.read_bytes(),profile.read_bytes()))
                finally:
                    http.shutdown();http.server_close();task.join(5)


if __name__=="__main__":
    unittest.main()
