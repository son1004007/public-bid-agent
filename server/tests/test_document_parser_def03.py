"""DEF-03 문서 구조 보존 파서 및 추출 서비스 인수 테스트.
목적: HWPX/DOCX 문서의 표(병합 셀/좌표), 각주(앵커 결속) 추출 및 DB 영속화 무결성을 검증한다.
관련: docs/server-migration/17-domain-and-postgresql-contract.md §16, 27-html-defects-and-stop-verification.md (DEF-03).
"""
import io
import zipfile
from django.test import TestCase
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
from bid_server.procurement.extractor_service import ExtractionService


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
        self.doc_version = DocumentVersion.objects.create(
            document=self.document,
            notice_version=self.notice_version,
            version_seq=1,
            sha256="b" * 64,
            size_bytes=1024,
            media_type="application/x-hwp+zip",
        )

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

    def test_extraction_service_persists_full_def03_hierarchy(self):
        """ExtractionService가 DB에 DocumentStructure/Blocks/Tables/Cells/Footnotes/Chunks를 완전 영속화함을 검증."""
        raw_hwpx = create_sample_hwpx_bytes()
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
