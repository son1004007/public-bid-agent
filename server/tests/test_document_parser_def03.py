"""DEF-03 문서 구조 보존 파서 및 추출 서비스 인수 테스트.
목적: HWPX/DOCX 문서의 표(병합 셀/좌표), 각주(앵커 결속) 추출 및 DB 영속화 무결성을 검증한다.
관련: docs/server-migration/17-domain-and-postgresql-contract.md §16, 27-html-defects-and-stop-verification.md (DEF-03).
"""
import hashlib
import io
import zipfile
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from unittest.mock import patch
from django.utils import timezone
from bid_server.procurement.models import (
    Notice,
    NoticeVersion,
    Document,
    DocumentVersion,
    ExtractionState,
    ChunkPath,
)
from bid_server.procurement.parser import parse_hwpx, parse_docx, parse_document_bytes
from bid_server.procurement.extractor_service import ExtractionService, DocumentSourceMismatchError


def create_sample_hwpx_bytes() -> bytes:
    """합성 HWPX (표 병합 셀 및 각주 포함) 바이트를 생성한다."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("mimetype", b"application/hwp+zip")
        sec_xml = """<?xml version="1.0" encoding="UTF-8"?>
<hp:sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">
  <hp:p id="p1">
    <hp:run><hp:t>제안요청서 1. 사업 개요 본문입니다.</hp:t></hp:run>
  </hp:p>
  <hp:tbl id="tbl1">
    <hp:tr id="r0">
      <hp:tc id="c0_0"><hp:cellSpan colSpan="2" rowSpan="1"/><hp:p><hp:run><hp:t>통합 머리글 (2열 병합)</hp:t></hp:run></hp:p></hp:tc>
    </hp:tr>
    <hp:tr id="r1">
      <hp:tc id="c1_0"><hp:cellSpan colSpan="1" rowSpan="1"/><hp:p><hp:run><hp:t>데이터 A</hp:t></hp:run></hp:p></hp:tc>
      <hp:tc id="c1_1"><hp:cellSpan colSpan="1" rowSpan="1"/><hp:p><hp:run><hp:t>데이터 B</hp:t></hp:run></hp:p></hp:tc>
    </hp:tr>
  </hp:tbl>
  <hp:p id="p2">
    <hp:run><hp:t>과업 세부 요구사항 본문입니다.</hp:t></hp:run>
    <hp:footnote id="fn1">
      <hp:p><hp:run><hp:t>각주 설명: 필수 인프라 요구사항 기준 참조</hp:t></hp:run></hp:p>
    </hp:footnote>
  </hp:p>
</hp:sec>"""
        z.writestr("Contents/section0.xml", sec_xml.encode("utf-8"))
    return buf.getvalue()


def create_sample_docx_bytes() -> bytes:
    """합성 DOCX (표 및 본문 포함) 바이트를 생성한다."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        doc_xml = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>DOCX 제안요청서 과업 내용</w:t></w:r></w:p>
    <w:tbl>
      <w:tr>
        <w:tc><w:p><w:r><w:t>평가항목</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>배점</w:t></w:r></w:p></w:tc>
      </w:tr>
      <w:tr>
        <w:tc><w:p><w:r><w:t>기술 역량</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>80점</w:t></w:r></w:p></w:tc>
      </w:tr>
    </w:tbl>
  </w:body>
</w:document>"""
        z.writestr("word/document.xml", doc_xml.encode("utf-8"))
    return buf.getvalue()


class DocumentParserAcceptanceTests(TestCase):
    def setUp(self):
        self.notice = Notice.objects.create(
            source="G2B_OFFICIAL_API",
            notice_number="TEST-RFP-DEF03-001",
        )
        self.notice_version = NoticeVersion.objects.create(
            notice=self.notice,
            version_seq=1,
            observed_at=timezone.now(),
            title="인공지능 기반 통합 검증 시스템 구축 용역",
            buyer="한국지능정보사회진흥원",
            source_payload_digest="a" * 64,
        )
        self.document = Document.objects.create(
            notice=self.notice,
            logical_key="RFP",
        )
        self.raw_hwpx = create_sample_hwpx_bytes()
        self.doc_version = DocumentVersion.objects.create(
            document=self.document,
            notice_version=self.notice_version,
            version_seq=1,
            sha256=hashlib.sha256(self.raw_hwpx).hexdigest(),
            size_bytes=len(self.raw_hwpx),
            media_type="application/x-hwp+zip",
        )

    def test_worker_rejects_unverified_document_sources_without_writes(self):
        """검증된 저장소 원본이 없으면 합성/클라이언트 본문을 쓰지 않고 실패한다."""
        from bid_server.jobs.models import JobAttempt, JobKind, JobState, RetryClass
        from bid_server.jobs.service import JobService
        from bid_server.jobs.workers import JobWorkerPipeline
        from bid_server.procurement.models import ExtractionRun, DocumentStructure

        for extra in ({}, {"raw_bytes_simulated": "untrusted synthetic text"}):
            with self.subTest(has_manifest_body=bool(extra)):
                job, _ = JobService.create_job(
                    kind=JobKind.EXTRACTION_RUN,
                    input_manifest={"document_version_id": str(self.doc_version.pk), **extra},
                )
                executed = JobWorkerPipeline().execute_next_job()
                self.assertEqual(executed.pk, job.pk)
                self.assertEqual(executed.state, JobState.FAILED)
                self.assertEqual(executed.current_attempt, 1)
                self.assertEqual(executed.result_ref, {})
                attempt = JobAttempt.objects.get(job=job, attempt_no=1)
                self.assertEqual(attempt.error_code, "DOCUMENT_SOURCE_UNAVAILABLE")
                self.assertEqual(attempt.retry_class, RetryClass.NON_RETRYABLE)
                self.assertEqual(ExtractionRun.objects.count(), 0)
                self.assertEqual(DocumentStructure.objects.count(), 0)

    def test_parser_rejects_oversized_xml_dtd_and_unsupported_formats(self):
        from bid_server.procurement.parser import ParserError, MAX_XML_BYTES
        cases = (
            ("rfp.docx", b"<document>" + b"A" * MAX_XML_BYTES + b"</document>"),
            ("rfp.docx", b"<!DOCTYPE document [<!ENTITY x 'sample'>]><document>&x;</document>"),
            ("rfp.docx", "<!DOCTYPE document><document/>".encode("utf-16")),
            ("rfp.hwpx", b"<sec>" + b"<p>" * 50 + b"</p>" * 50 + b"</sec>"),
        )
        for name, content in cases:
            with self.subTest(name=name, size=len(content)):
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                    member = "word/document.xml" if name.endswith("docx") else "Contents/section0.xml"
                    archive.writestr(member, content)
                with self.assertRaises(ParserError):
                    parse_document_bytes(name, buf.getvalue())

        for name, content in (
            ("rfp.pdf", b"%PDF-1.7 fixture"),
            ("rfp.txt", b"%PDF-1.7 fixture"),
            ("rfp.txt", create_sample_hwpx_bytes()),
            ("rfp.txt", bytes([0, 1, 2, 3])),
        ):
            with self.subTest(name=name):
                with self.assertRaises(ParserError):
                    parse_document_bytes(name, content)

    def test_service_rejects_registered_media_mismatch(self):
        from bid_server.procurement.parser import ParserError
        from bid_server.procurement.models import ExtractionRun
        DocumentVersion.objects.filter(pk=self.doc_version.pk).update(media_type="text/plain")
        with self.assertRaises(ParserError):
            ExtractionService.extract_and_persist(self.doc_version, self.raw_hwpx, "rfp.hwpx")
        self.assertFalse(ExtractionRun.objects.exists())

    def test_unimplemented_job_kind_does_not_report_success(self):
        from bid_server.jobs.models import JobKind, JobState, Outbox
        from bid_server.jobs.service import JobService
        from bid_server.jobs.workers import JobWorkerPipeline
        for kind in (JobKind.COLLECTION_RUN, JobKind.CLASSIFICATION_RUN,
                     JobKind.EVALUATION_RUN, JobKind.CONNECTION_CHECK):
            job, _ = JobService.create_job(kind, {"fixture": True})
            result = JobWorkerPipeline().execute_next_job()
            self.assertEqual(result.pk, job.pk)
            self.assertEqual(result.state, JobState.FAILED)
            self.assertEqual(result.attempts.last().error_code, "JOB_KIND_NOT_IMPLEMENTED")
            self.assertFalse(Outbox.objects.filter(job=job, message_kind="JOB_SUCCEEDED").exists())

    def test_hwpx_parser_extracts_table_grid_and_footnotes(self):
        """HWPX 파서가 표의 병합 span 및 각주 앵커를 정확히 추출함을 검증 (DEF-03)."""
        raw_hwpx = create_sample_hwpx_bytes()
        res = parse_hwpx(raw_hwpx)

        self.assertEqual(res["format"], "HWPX")
        self.assertIn("제안요청서 1. 사업 개요", res["full_text"])

        # Tables 검증
        self.assertEqual(len(res["tables"]), 1)
        tbl = res["tables"][0]
        self.assertEqual(tbl["row_count"], 2)
        self.assertEqual(tbl["column_count"], 2)

        # 병합 셀 검증 (colSpan=2)
        c0_0 = [c for c in tbl["cells"] if c["row_index"] == 0 and c["column_index"] == 0][0]
        self.assertEqual(c0_0["colspan"], 2)
        self.assertIn("통합 머리글", c0_0["text"])

        # Footnotes 검증
        self.assertEqual(len(res["footnotes"]), 1)
        fn = res["footnotes"][0]
        self.assertIn("각주 설명", fn["text"])
        self.assertTrue(len(fn["anchor_refs"]) > 0)

    def test_docx_parser_extracts_table_and_paragraphs(self):
        """DOCX 파서가 문단 및 표 구조를 정상 추출함을 검증."""
        raw_docx = create_sample_docx_bytes()
        res = parse_docx(raw_docx)

        self.assertEqual(res["format"], "DOCX")
        self.assertIn("DOCX 제안요청서", res["full_text"])
        self.assertEqual(len(res["tables"]), 1)
        tbl = res["tables"][0]
        self.assertEqual(tbl["row_count"], 2)
        self.assertEqual(tbl["column_count"], 2)

    def test_service_rejects_mismatched_source_even_without_http(self):
        """길이/해시 불일치 및 호출자 모델 조작은 파싱 전에 차단한다."""
        from unittest.mock import patch
        from bid_server.procurement.models import ExtractionRun, DocumentStructure, Chunk

        bad = bytes([self.raw_hwpx[0] ^ 1]) + self.raw_hwpx[1:]
        with patch("bid_server.procurement.extractor_service.parse_document_bytes") as parser:
            for payload in (bad, self.raw_hwpx + b"extra"):
                with self.subTest(size=len(payload)):
                    with self.assertRaises(DocumentSourceMismatchError):
                        ExtractionService.extract_and_persist(self.doc_version, payload, "rfp.hwpx")
            # 메모리상의 메타데이터를 조작해도 DB 원본과 일치해야 한다.
            self.doc_version.sha256 = hashlib.sha256(bad).hexdigest()
            with self.assertRaises(DocumentSourceMismatchError):
                ExtractionService.extract_and_persist(self.doc_version, bad, "rfp.hwpx")
            parser.assert_not_called()
        self.assertEqual(ExtractionRun.objects.count(), 0)
        self.assertEqual(DocumentStructure.objects.count(), 0)
        self.assertEqual(Chunk.objects.count(), 0)

    def test_service_rechecks_source_before_persistence(self):
        """파싱 중 등록 원본이 바뀌면 추출 결과를 저장하지 않는다."""
        from unittest.mock import patch
        from bid_server.procurement.models import ExtractionRun, DocumentStructure, Chunk

        def changed_source(file_name, raw_bytes):
            parsed = parse_document_bytes(file_name, raw_bytes)
            DocumentVersion.objects.filter(pk=self.doc_version.pk).update(sha256="0" * 64)
            return parsed

        with patch(
            "bid_server.procurement.extractor_service.parse_document_bytes",
            side_effect=changed_source,
        ):
            with self.assertRaises(DocumentSourceMismatchError):
                ExtractionService.extract_and_persist(self.doc_version, self.raw_hwpx, "rfp.hwpx")
        self.assertEqual(ExtractionRun.objects.count(), 0)
        self.assertEqual(DocumentStructure.objects.count(), 0)
        self.assertEqual(Chunk.objects.count(), 0)

    def test_extraction_service_persists_full_def03_hierarchy(self):
        """ExtractionService가 DB에 DocumentStructure/Blocks/Tables/Cells/Footnotes/Chunks를 완전 영속화함을 검증."""
        raw_hwpx = self.raw_hwpx
        run = ExtractionService.extract_and_persist(
            document_version=self.doc_version,
            raw_bytes=raw_hwpx,
            file_name="rfp.hwpx",
        )

        self.assertEqual(run.state, ExtractionState.PARSED)
        self.assertEqual(run.coverage["format"], "HWPX")

        # Structure 확인
        structure = run.structures.first()
        self.assertIsNotNone(structure)
        self.assertTrue(structure.blocks.count() >= 3)

        # Table & Cells 확인
        tbl_block = structure.blocks.filter(kind="table").first()
        self.assertIsNotNone(tbl_block)
        t_block = tbl_block.table_block
        self.assertEqual(t_block.row_count, 2)
        self.assertEqual(t_block.cells.count(), 3)  # c0_0 (colspan 2), c1_0, c1_1

        # Footnote 확인
        fn_block = structure.blocks.filter(kind="footnote").first()
        self.assertIsNotNone(fn_block)
        f_block = fn_block.footnote_block
        self.assertIn("각주 설명", f_block.text)

        # Chunks 확인 (본문 및 표 구절)
        chunks = list(run.chunks.all())
        self.assertTrue(len(chunks) >= 2)
        text_chunks = [c for c in chunks if c.path == ChunkPath.TEXT]
        tbl_chunks = [c for c in chunks if c.path == ChunkPath.TABLE]
        self.assertTrue(len(text_chunks) >= 1)
        self.assertTrue(len(tbl_chunks) >= 1)

class DocumentExtractHTTPIntegrityTests(TestCase):
    """Missing/short/unsupported input must never create synthetic extraction evidence."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        self.user = get_user_model().objects.create_user(
            username="extract-integrity-user",
            password="SyntheticTestPassword123!",
            must_change_password=False,
        )
        self.client = APIClient()
        # Establish the actual session/epoch expected by AuthGateMiddleware.
        csrf = self.client.get("/api/v1/auth/csrf", secure=True)
        self.assertEqual(csrf.status_code, 200)
        token = csrf.json()["data"]["csrf_token"]
        login = self.client.post(
            "/api/v1/auth/login",
            {"username": self.user.username, "password": "SyntheticTestPassword123!"},
            format="json", secure=True, HTTP_X_CSRFTOKEN=token,
            HTTP_ORIGIN="https://testserver",
        )
        self.assertEqual(login.status_code, 200)
        self.csrf_token = self.client.get(
            "/api/v1/auth/csrf", secure=True
        ).json()["data"]["csrf_token"]
        notice = Notice.objects.create(source="G2B_OFFICIAL_API", notice_number="SYNTH-EXTRACT-01")
        nv = NoticeVersion.objects.create(
            notice=notice, version_seq=1, observed_at=timezone.now(),
            title="Synthetic test notice", buyer="Synthetic agency",
            source_payload_digest="f" * 64,
        )
        doc = Document.objects.create(notice=notice, logical_key="synthetic-rfp")
        import hashlib
        self.valid_payload = b"Synthetic RFP requirements for a test only."
        self.version = DocumentVersion.objects.create(
            document=doc, notice_version=nv, version_seq=1,
            owner_user=self.user,
            sha256=hashlib.sha256(self.valid_payload).hexdigest(),
            size_bytes=len(self.valid_payload), media_type="text/plain",
        )
        self.url = f"/api/v1/documents/{self.version.pk}/extract"

    def test_missing_and_short_payloads_do_not_persist(self):
        from bid_server.procurement.models import ExtractionRun, DocumentStructure
        for payload in (b"", b"abc"):
            with self.subTest(payload=payload):
                res = self.client.post(
                    self.url, data=payload, content_type="text/plain", secure=True,
                    HTTP_X_CSRFTOKEN=self.csrf_token,
                    HTTP_ORIGIN="https://testserver",
                )
                self.assertEqual(res.status_code, 411 if not payload else 400)
                self.assertEqual(ExtractionRun.objects.count(), 0)
                self.assertEqual(DocumentStructure.objects.count(), 0)

    def test_unsupported_media_type_does_not_persist(self):
        from bid_server.procurement.models import ExtractionRun
        res = self.client.post(
            self.url, data=b'{"fake":"source"}', content_type="application/json",
            secure=True, HTTP_X_CSRFTOKEN=self.csrf_token,
            HTTP_ORIGIN="https://testserver",
        )
        self.assertEqual(res.status_code, 415)
        self.assertEqual(ExtractionRun.objects.count(), 0)

    def test_valid_synthetic_plain_text_is_persisted(self):
        from bid_server.procurement.models import ExtractionRun, DocumentStructure
        res = self.client.post(
            self.url, data=self.valid_payload,
            content_type="text/plain", secure=True,
            HTTP_X_CSRFTOKEN=self.csrf_token, HTTP_ORIGIN="https://testserver",
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(ExtractionRun.objects.count(), 1)
        self.assertEqual(DocumentStructure.objects.count(), 1)

    def test_different_source_bytes_rejected_without_persistence(self):
        from bid_server.procurement.models import ExtractionRun, DocumentStructure
        # Same size but different digest must not create extracted evidence.
        bad_payload = b"X" + self.valid_payload[1:]
        for payload in (bad_payload, self.valid_payload + b"extra"):
            with self.subTest(length=len(payload)):
                res = self.client.post(
                    self.url, data=payload, content_type="text/plain", secure=True,
                    HTTP_X_CSRFTOKEN=self.csrf_token, HTTP_ORIGIN="https://testserver",
                )
                self.assertEqual(res.status_code, 409)
                self.assertEqual(res.json()["data"]["error"], "DOCUMENT_SOURCE_MISMATCH")
                self.assertEqual(ExtractionRun.objects.count(), 0)
                self.assertEqual(DocumentStructure.objects.count(), 0)

    def test_document_scope_denies_unclassified_and_other_owner_writes(self):
        from django.contrib.auth import get_user_model
        from bid_server.procurement.models import ExtractionRun, DocumentStructure
        other = get_user_model().objects.create_user(
            username="other-document-owner", password="SyntheticTestPassword123!",
            must_change_password=False, role="director",
        )
        structure_url = f"/api/v1/documents/{self.version.pk}/structures"
        for owner, shared, expected_read in (
            (None, False, 404), (other, False, 404), (other, True, 200),
        ):
            with self.subTest(shared=shared, owner=owner):
                DocumentVersion.objects.filter(pk=self.version.pk).update(
                    owner_user=owner, shared_read_approved=shared,
                )
                self.assertEqual(self.client.get(structure_url, secure=True).status_code, expected_read)
                res = self.client.post(
                    self.url, data=self.valid_payload, content_type="text/plain",
                    secure=True, HTTP_X_CSRFTOKEN=self.csrf_token,
                    HTTP_ORIGIN="https://testserver",
                )
                self.assertEqual(res.status_code, 404)
                self.assertFalse(ExtractionRun.objects.exists())
                self.assertFalse(DocumentStructure.objects.exists())

    def test_service_rejects_unauthorized_actor(self):
        from bid_server.procurement.extractor_service import DocumentAccessError
        from bid_server.procurement.models import ExtractionRun
        DocumentVersion.objects.filter(pk=self.version.pk).update(owner_user=None)
        with self.assertRaises(DocumentAccessError):
            ExtractionService.extract_and_persist(
                self.version, self.valid_payload, "rfp.txt", actor_user=self.user,
            )
        self.assertFalse(ExtractionRun.objects.exists())

    def _assert_no_extraction(self):
        from bid_server.procurement.models import ExtractionRun, DocumentStructure, Chunk
        self.assertFalse(ExtractionRun.objects.exists())
        self.assertFalse(DocumentStructure.objects.exists())
        self.assertFalse(Chunk.objects.exists())

    def _assert_mid_parse_denied(self, change):
        def parse_then_change(filename, raw):
            result = parse_document_bytes(filename, raw)
            change()
            return result
        with patch("bid_server.procurement.extractor_service.parse_document_bytes", side_effect=parse_then_change):
            res = self.client.post(
                self.url, data=self.valid_payload, content_type="text/plain", secure=True,
                HTTP_X_CSRFTOKEN=self.csrf_token, HTTP_ORIGIN="https://testserver",
            )
        self.assertEqual(res.status_code, 404)
        self._assert_no_extraction()

    def test_epoch_revoked_during_parse_rejects_write(self):
        def revoke():
            current = type(self.user).objects.get(pk=self.user.pk)
            current.auth_epoch += 1
            current.save(update_fields=["auth_epoch"])
        self._assert_mid_parse_denied(revoke)

    def test_account_disabled_during_parse_rejects_write(self):
        def disable():
            current = type(self.user).objects.get(pk=self.user.pk)
            current.is_active = False
            current.save(update_fields=["is_active"])
        self._assert_mid_parse_denied(disable)

    def test_owner_removed_during_parse_rejects_write(self):
        self._assert_mid_parse_denied(
            lambda: DocumentVersion.objects.filter(pk=self.version.pk).update(owner_user=None)
        )

    def test_stale_actor_cannot_read_or_begin_parse(self):
        from bid_server.procurement.extractor_service import DocumentAccessError, scoped_document_versions
        visible = scoped_document_versions(self.user)
        current = type(self.user).objects.get(pk=self.user.pk)
        current.auth_epoch += 1
        current.save(update_fields=["auth_epoch"])
        self.assertFalse(visible.exists())
        with patch("bid_server.procurement.extractor_service.parse_document_bytes") as parser:
            with self.assertRaises(DocumentAccessError):
                ExtractionService.extract_and_persist(
                    self.version, self.valid_payload, "rfp.txt", actor_user=self.user,
                )
            parser.assert_not_called()
        self._assert_no_extraction()

    def test_http_rejects_registered_binary_and_invalid_text(self):
        from bid_server.procurement.models import ExtractionRun, DocumentStructure
        for payload, media, sent_media, expected in (
            (b"%PDF-1.7 fixture", "application/pdf", "text/plain", 415),
            (create_sample_hwpx_bytes(), "application/x-hwp+zip", "application/octet-stream", 415),
            (bytes([0, 1, 2, 3]), "text/plain", "text/plain", 422),
        ):
            with self.subTest(media=media):
                DocumentVersion.objects.filter(pk=self.version.pk).update(
                    sha256=hashlib.sha256(payload).hexdigest(), size_bytes=len(payload), media_type=media,
                )
                res = self.client.post(
                    self.url, data=payload, content_type=sent_media, secure=True,
                    HTTP_X_CSRFTOKEN=self.csrf_token, HTTP_ORIGIN="https://testserver",
                )
                self.assertEqual(res.status_code, expected)
                self.assertFalse(ExtractionRun.objects.exists())
                self.assertFalse(DocumentStructure.objects.exists())

class ExtractionPostgresConcurrencyTests(TransactionTestCase):
    """Separate DB connections; a committed revocation must win over later persistence."""

    @skipUnlessDBFeature("has_select_for_update")
    def test_revocation_committed_while_parser_runs(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        from django.db import connections
        from bid_server.accounts.models import User
        from bid_server.procurement.extractor_service import DocumentAccessError
        from bid_server.procurement.models import ExtractionRun, DocumentStructure, Chunk

        user = User.objects.create_user(
            username="synthetic-extraction-race", password="SyntheticTestPassword123!",
            must_change_password=False,
        )
        notice = Notice.objects.create(source="G2B_OFFICIAL_API", notice_number="SYNTH-EXTRACT-RACE")
        nv = NoticeVersion.objects.create(
            notice=notice, version_seq=1, observed_at=timezone.now(),
            title="Synthetic", buyer="Synthetic", source_payload_digest="f" * 64,
        )
        doc = Document.objects.create(notice=notice, logical_key="synthetic-rfp")
        raw = b"Synthetic document requirements."
        version = DocumentVersion.objects.create(
            document=doc, notice_version=nv, version_seq=1, owner_user=user,
            sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw), media_type="text/plain",
        )
        parsed, resume = Event(), Event()

        def paused_parser(filename, payload):
            result = parse_document_bytes(filename, payload)
            parsed.set()
            if not resume.wait(10):
                raise AssertionError("test synchronization timeout")
            return result

        def extraction():
            try:
                actor = User.objects.get(pk=user.pk)
                ExtractionService.extract_and_persist(version, raw, "rfp.txt", actor_user=actor)
            finally:
                connections.close_all()

        with patch("bid_server.procurement.extractor_service.parse_document_bytes", side_effect=paused_parser):
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(extraction)
                try:
                    self.assertTrue(parsed.wait(10))
                    current = User.objects.get(pk=user.pk)
                    current.auth_epoch += 1
                    current.save(update_fields=["auth_epoch"])
                finally:
                    resume.set()
                with self.assertRaises(DocumentAccessError):
                    future.result(timeout=15)

        self.assertFalse(ExtractionRun.objects.exists())
        self.assertFalse(DocumentStructure.objects.exists())
        self.assertFalse(Chunk.objects.exists())
