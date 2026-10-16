"""합성 공식 RFP 청크 구조화와 읽기 전용 HTTP/무결성 경계 회귀.

비공개 사용자 파일/실제 API/원격 AI 접근 없이 임시 SHA 검증 캐시만 생성한다.
"""
import copy
import hashlib
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen

import server
from dashboard_backend import blank, normalize
from rfp_fulltext import store as store_fulltext
from rfp_requirements import structure, EvidenceError, COMPILED, SCHEMA_VERSION

TEXT = (
    "입찰참가자격: 소프트웨어사업자 등록 및 중소기업확인서 제출\n"
    "업종 제한: 정보통신공사업 면허 확인\n"
    "사업실적: 최근 3년 유사 사업 수행실적 증명\n"
    "과업범위: API 연계 및 데이터 수집 플랫폼 구축\n"
    "기술요건: Java Spring Python FastAPI PostgreSQL API\n"
    "투입인력: 중급 기술자 2명, 총 6 M/M\n"
    "사업기간: 계약일부터 8개월 이내\n"
    "사업비: 추정가격 500,000,000원 부가가치세 별도\n"
    "평가기준: 기술평가 80점, 가격평가 20점, 동점자는 고득점 순으로 선정\n"
)


class StructuredRequirementsTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.notice = normalize({
            "bidNtceNo":"R26BK12345678","bidNtceOrd":"000",
            "bidNtceNm":"정보시스템 개발 사업",
            "bidClseDt":"2099-12-31 18:00:00",
            "pubPrcrmntClsfcNm":"소프트웨어개발",
            "ntceSpecFileNm1":"제안요청서.pdf",
            "ntceSpecDocUrl1":"https://www.g2b.go.kr/doc.pdf",
        })
        self.sha = hashlib.sha256(b"synthetic-pdf-raw").hexdigest()
        self.ref = store_fulltext(self.root,self.sha,{"text":TEXT,"characters":len(TEXT),
                                                     "truncated":False,"warnings":[]})
        attachment=self.notice["attachments"][0]
        ident=hashlib.sha256((attachment["url"]+"\n"+attachment["name"]).encode()).hexdigest()
        self.notice.update({"document_status":"EXTRACTED","rfp_text":TEXT[:6000],
                            "document_evidence":[{"identity":ident,"name":attachment["name"],
                                                  "status":"EXTRACTED","sha256":self.sha,
                                                  "excerpt":TEXT[:6000],**self.ref}]})

    def test_all_nine_categories_with_grounded_char_offsets_and_no_page_guess(self):
        result=structure(self.notice,self.root)
        self.assertEqual(result["state"],"EVIDENCE_CANDIDATES")
        self.assertEqual(result["sources_used"],1)
        self.assertEqual(result["legal_eligibility"],"UNVERIFIED")
        self.assertEqual(result["technical_fit"],"UNVERIFIED")
        self.assertEqual(result["source_coverage"],"EXTRACTED_TEXT_ONLY")
        self.assertEqual(result["schema_version"],SCHEMA_VERSION)
        self.assertEqual(SCHEMA_VERSION,2)
        self.assertEqual(len(result["requirements"]),9)
        self.assertTrue(all(x["count"]>=1 for x in result["requirements"]))
        for category in result["requirements"]:
            for item in category["items"]:
                evidence=item["evidence"]
                self.assertIsNone(evidence["page"])
                self.assertEqual(evidence["source_sha256"],self.sha)
                self.assertEqual(evidence["fulltext_ref"],self.ref["fulltext_ref"])
                self.assertEqual(TEXT[evidence["offset_start"]:evidence["offset_end"]],
                                 evidence["excerpt"])
                self.assertLessEqual(len(evidence["excerpt"]),220)

    def test_display_cap_reports_unique_omitted_candidates_without_false_recall_claim(self):
        # 로컬 임시 합성 본문만 사용. 동일 표현은 중복 계수하지 않는다.
        text = "\n".join(
            f"입찰참가자격: 분야 {index} 사업자 등록 및 직접생산확인서 제출"
            for index in range(7)
        ) + "\n입찰참가자격: 분야 6 사업자 등록 및 직접생산확인서 제출\n"
        ref = store_fulltext(self.root, self.sha, {
            "text": text, "characters": len(text), "truncated": False,
        })
        n = copy.deepcopy(self.notice)
        n["document_evidence"][0].update(ref)
        n["document_evidence"][0]["excerpt"] = text
        n["rfp_text"] = text
        out = structure(n, self.root)
        categories = {item["category"]: item for item in out["requirements"]}
        self.assertEqual(out["candidate_display_limit_per_category"], 5)
        self.assertEqual(categories["participation"]["count"], 5)
        self.assertEqual(categories["participation"]["omitted_count"], 2)
        self.assertEqual(out["omitted_candidate_count"], 2)
        self.assertEqual(out["source_coverage"], "PARTIAL")
        self.assertTrue(any("표시 상한" in msg for msg in out["warnings"]))
        self.assertEqual(out["legal_eligibility"], "UNVERIFIED")

    def test_omission_aggregation_and_source_sha_dedup_across_two_documents(self):
        text = "\n".join(
            [f"입찰참가자격: 참가 등록 제한 조건 {i}번" for i in range(6)]
            + [f"평가기준: 정량평가 항목 {i}번 배점" for i in range(6)]
        )
        for different_sha, omitted in ((False, 2), (True, 14)):
            with self.subTest(different_sha=different_sha):
                n = copy.deepcopy(self.notice)
                n["attachments"], n["document_evidence"] = [], []
                for index in range(2):
                    sha = (hashlib.sha256(f"synthetic-{index}".encode()).hexdigest()
                           if different_sha else self.sha)
                    name = f"가상RFP{index}.pdf"
                    url = f"https://www.g2b.go.kr/synthetic{index}.pdf"
                    ref = store_fulltext(self.root, sha, {
                        "text": text, "characters": len(text), "truncated": False,
                    })
                    n["attachments"].append({"name": name, "url": url})
                    n["document_evidence"].append({
                        "identity": hashlib.sha256((url+"\n"+name).encode()).hexdigest(),
                        "name": name, "status": "EXTRACTED", "sha256": sha,
                        "excerpt": text, **ref,
                    })
                report = structure(n, self.root)
                cats = {item["category"]: item for item in report["requirements"]}
                self.assertEqual(report["sources_used"], 2)
                self.assertEqual(cats["participation"]["count"], 5)
                self.assertEqual(cats["evaluation"]["count"], 5)
                self.assertEqual(report["omitted_candidate_count"], omitted)
                self.assertEqual(cats["participation"]["omitted_count"], omitted//2)
                self.assertEqual(cats["evaluation"]["omitted_count"], omitted//2)
                self.assertEqual(report["source_coverage"], "PARTIAL")

    def test_blocked_notice_reports_no_omitted_candidates(self):
        blocked = []
        for state in ("CANCELLED", "SUPERSEDED", "REVIEW"):
            n = copy.deepcopy(self.notice)
            n["notice_lifecycle"] = state
            blocked.append((n, "EXCLUDED_NOTICE"))
        stale = copy.deepcopy(self.notice)
        stale["rfp_review_status"] = "STALE"
        blocked.append((stale, "STALE_RFP"))
        failed = copy.deepcopy(self.notice)
        failed["document_status"] = "FAILED"
        blocked.append((failed, "NO_EXTRACTED_RFP"))
        untrusted = copy.deepcopy(self.notice)
        untrusted["document_evidence"][0]["identity"] = "0"*64
        blocked.append((untrusted, "NO_TRUSTED_EVIDENCE"))
        for n, expected in blocked:
            with self.subTest(state=expected):
                out = structure(n, self.root)
                self.assertEqual(out["state"], expected)
                self.assertEqual(out["omitted_candidate_count"], 0)
                self.assertEqual(out["candidate_display_limit_per_category"], 5)
                self.assertTrue(all(x["omitted_count"] == 0 for x in out["requirements"]))
                if expected != "NO_TRUSTED_EVIDENCE":
                    self.assertEqual(out["source_coverage"], "NONE")
                else:
                    self.assertIn(out["source_coverage"], ("NONE", "PARTIAL"))

    def test_incomplete_or_stale_rfp_does_not_analyze(self):
        for state in ("CANCELLED","SUPERSEDED","REVIEW"):
            n=copy.deepcopy(self.notice)
            n["notice_lifecycle"]=state
            self.assertEqual(structure(n,self.root)["state"],"EXCLUDED_NOTICE")
        n=copy.deepcopy(self.notice)
        n["rfp_review_status"]="STALE"
        self.assertEqual(structure(n,self.root)["state"],"STALE_RFP")
        n=copy.deepcopy(self.notice)
        n["document_status"]="FAILED"
        self.assertEqual(structure(n,self.root)["state"],"NO_EXTRACTED_RFP")

    def test_uncategorized_old_cancellation_still_blocks(self):
        n=copy.deepcopy(self.notice)
        n.pop("notice_lifecycle",None)
        n["notice_kind"]="취소공고"
        self.assertEqual(structure(n,self.root)["state"],"EXCLUDED_NOTICE")

    def test_unauthenticated_attachment_identity_never_matches_none(self):
        n=copy.deepcopy(self.notice)
        n["attachments"]=[{"name":"invalid","url":None}]
        n["document_evidence"][0]["identity"]=None
        out=structure(n,self.root)
        self.assertEqual(out["state"],"NO_TRUSTED_EVIDENCE")

    def test_spoofed_evidence_filename_is_not_reported_as_official_file(self):
        n=copy.deepcopy(self.notice)
        n["document_evidence"][0]["name"]="기타 업체 비공식자료.pdf"
        report=structure(n,self.root)
        self.assertEqual(report["state"],"NO_TRUSTED_EVIDENCE")
        self.assertEqual(report["sources_used"],0)
        self.assertTrue(any("파일명" in msg for msg in report["warnings"]))

    def test_two_failed_records_then_valid_third_is_used(self):
        n=copy.deepcopy(self.notice)
        proof=n["document_evidence"][0]
        n["document_evidence"]=[{"status":"FAILED","error":"synthetic"},
                                {"status":"FAILED","error":"synthetic"},proof]
        report=structure(n,self.root)
        self.assertEqual(report["state"],"EVIDENCE_CANDIDATES")
        self.assertEqual(report["sources_used"],1)

    def test_more_than_two_valid_documents_are_capped_with_warning(self):
        n=copy.deepcopy(self.notice)
        n["attachments"]=[]
        n["document_evidence"]=[]
        for i in range(3):
            filename=f"RFP{i}.pdf"
            url=f"https://www.g2b.go.kr/rfp{i}.pdf"
            n["attachments"].append({"name":filename,"url":url})
            proof=copy.deepcopy(self.notice["document_evidence"][0])
            proof["identity"]=hashlib.sha256((url+"\n"+filename).encode()).hexdigest()
            proof["name"]=filename
            n["document_evidence"].append(proof)
        report=structure(n,self.root)
        self.assertEqual(report["sources_used"],2)
        self.assertEqual(report["source_coverage"],"PARTIAL")
        self.assertTrue(any("상한" in msg for msg in report["warnings"]))

    def test_conflicting_raw_sha_for_same_identity_does_not_bind(self):
        n=copy.deepcopy(self.notice)
        other=copy.deepcopy(n["document_evidence"][0])
        other["sha256"]="f"*64
        n["document_evidence"].append(other)
        report=structure(n,self.root)
        self.assertEqual(report["state"],"NO_TRUSTED_EVIDENCE")
        self.assertTrue(any("충돌" in msg for msg in report["warnings"]))

    def test_duplicate_same_identity_does_not_count_twice(self):
        n=copy.deepcopy(self.notice)
        n["document_evidence"].append(copy.deepcopy(n["document_evidence"][0]))
        report=structure(n,self.root)
        self.assertEqual(report["sources_used"],1)

    def test_valid_official_attachment_at_position_121_is_detected(self):
        n=copy.deepcopy(self.notice)
        original=n["attachments"][0]
        n["attachments"]=[{"name":f"별첨{i}.pdf",
                           "url":f"https://www.g2b.go.kr/decoy{i}.pdf"}
                          for i in range(120)] + [original]
        result=structure(n,self.root)
        self.assertEqual(result["state"],"EVIDENCE_CANDIDATES")
        self.assertEqual(result["sources_used"],1)

    def test_attachment_scan_over_limit_explicitly_partial(self):
        n=copy.deepcopy(self.notice)
        original=n["attachments"][0]
        n["attachments"]=[{"name":f"별첨{i}.pdf",
                           "url":f"https://www.g2b.go.kr/decoy{i}.pdf"}
                          for i in range(400)] + [original]
        report=structure(n,self.root)
        self.assertEqual(report["state"],"NO_TRUSTED_EVIDENCE")
        self.assertEqual(report["source_coverage"],"PARTIAL")
        self.assertTrue(any("공식 첨부 탐색" in msg for msg in report["warnings"]))

    def test_wrong_source_sha_or_corrupt_chunks_fail_closed(self):
        n=copy.deepcopy(self.notice)
        n["document_evidence"][0]["sha256"]="a"*64
        with self.assertRaises(EvidenceError):
            structure(n,self.root)
        cache=self.root/"rfp_fulltext"/(self.ref["fulltext_ref"]+".json")
        cached=json.loads(cache.read_text(encoding="utf-8"))
        cached["chunks"][0]["text"]="조작 데이터"
        cache.write_text(json.dumps(cached,ensure_ascii=False),encoding="utf-8")
        with self.assertRaises(EvidenceError):
            structure(self.notice,self.root)

    def test_unknown_attachment_identity_fails_without_fake_evidence(self):
        n=copy.deepcopy(self.notice)
        n["document_evidence"][0]["identity"]="b"*64
        report=structure(n,self.root)
        self.assertEqual(report["state"],"NO_TRUSTED_EVIDENCE")
        self.assertEqual(report["requirement_count"],0)

    def test_excerpt_fallback_explicitly_marked_partial(self):
        n=copy.deepcopy(self.notice)
        n["document_evidence"][0].pop("fulltext_ref")
        report=structure(n,self.root)
        self.assertEqual(report["source_coverage"],"PARTIAL")
        self.assertTrue(report["warnings"])
        proof=report["requirements"][0]["items"][0]["evidence"]
        self.assertEqual(proof["source_mode"],"EXCERPT_ONLY")

    def test_truncated_cache_surfaces_warning(self):
        # 원문 텍스트는 그대로이며 파서 완전성을 표시하지 않는다.
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        other=Path(tmp.name)
        ref=store_fulltext(other,self.sha,{"text":TEXT,"characters":len(TEXT)+120,
                                            "truncated":True,"warnings":[]})
        n=copy.deepcopy(self.notice)
        n["document_evidence"][0].update(ref)
        report=structure(n,other)
        self.assertEqual(report["source_coverage"],"PARTIAL")
        self.assertTrue(any("절단" in v for v in report["warnings"]))

    def test_readonly_http_get_and_errors_without_data_loss(self):
        data=blank()
        data["notices"]=[self.notice]
        dashboard=self.root/"dashboard.json"
        raw=json.dumps(data,ensure_ascii=False).encode("utf-8")
        dashboard.write_bytes(raw)
        with patch.object(server,"ROOT",self.root):
            http=ThreadingHTTPServer(("127.0.0.1",0),server.Handler)
            worker=threading.Thread(target=http.serve_forever,daemon=True)
            worker.start()
            self.addCleanup(http.server_close)
            try:
                url=f"http://127.0.0.1:{http.server_port}"
                with urlopen(url+"/api/dashboard/rfp-requirements?id="+self.notice["id"],timeout=8) as res:
                    response=json.load(res)
                    self.assertEqual(res.status,200)
                self.assertEqual(response["requirements"]["sources_used"],1)
                with urlopen(url+"/rfp-evidence-summary.js",timeout=8) as script_res:
                    self.assertEqual(script_res.status,200)
                    self.assertIn("javascript",script_res.headers["Content-Type"])
                    self.assertIn(b"rfpEvidenceSummary",script_res.read())
                self.assertEqual(response["requirements"]["omitted_candidate_count"],0)
                self.assertTrue(all(x["omitted_count"]==0 for x in response["requirements"]["requirements"]))
                self.assertEqual(response["storage"],"LOCAL_READ_ONLY")
                # HTTP 게이트에서도 보류 상태의 표시 상한 생략 건수가 0으로 반환된다.
                paused=copy.deepcopy(self.notice)
                paused["rfp_review_status"]="STALE"
                data["notices"]=[paused]
                dashboard.write_text(json.dumps(data,ensure_ascii=False),encoding="utf-8")
                with urlopen(url+"/api/dashboard/rfp-requirements?id="+self.notice["id"],timeout=8) as res:
                    status=json.load(res)["requirements"]
                self.assertEqual(status["state"],"STALE_RFP")
                self.assertEqual(status["omitted_candidate_count"],0)
                dashboard.write_bytes(raw)
                for bad in ("missing","../foo"):
                    with self.assertRaises(HTTPError) as ctx:
                        urlopen(url+"/api/dashboard/rfp-requirements?id="+bad,timeout=8)
                    self.assertEqual(ctx.exception.code,400)
                cache=self.root/"rfp_fulltext"/(self.ref["fulltext_ref"]+".json")
                record=json.loads(cache.read_text(encoding="utf-8"))
                record["chunks"][0]["text"]="변조"
                cache.write_text(json.dumps(record,ensure_ascii=False),encoding="utf-8")
                with self.assertRaises(HTTPError) as err:
                    urlopen(url+"/api/dashboard/rfp-requirements?id="+self.notice["id"],timeout=8)
                self.assertEqual(err.exception.code,503)
                self.assertEqual(dashboard.read_bytes(),raw)
            finally:
                http.shutdown()
                worker.join(timeout=8)


if __name__=="__main__":
    unittest.main()
