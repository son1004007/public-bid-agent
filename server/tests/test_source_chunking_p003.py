"""P0-03: synthetic-only byte-exact chunk integrity, source locators and partial-coverage.

No external API, real customer RFP, network access, model call or NAS database writes.
"""
import hashlib
import io
import zipfile
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from bid_server.procurement.source_chunking import (
    MAX_CHUNK_UTF8_BYTES, MAX_CHUNKS_PER_BLOCK, SourceChunkError,
    split_source_text,
)
from bid_server.procurement.extractor_service import ExtractionService
from bid_server.procurement.models import (
    ChunkPath, Document, DocumentVersion, ExtractionRun, Notice, NoticeVersion,
)
from bid_server.procurement.parser import ParserError


def _h(value):
    return hashlib.sha256(value).hexdigest()


class ExactUTF8ChunkTests(SimpleTestCase):
    def test_mixed_unicode_no_loss_at_1800_byte_boundary(self):
        text = ("가나🌏e\u0301 \n" * 500) + ("끝" * 400)
        spans = split_source_text(text)
        self.assertGreater(len(spans), 2)
        self.assertEqual("".join(part.text for part in spans), text)
        self.assertEqual(b"".join(p.text.encode("utf-8") for p in spans), text.encode("utf-8"))
        for i, part in enumerate(spans):
            self.assertGreater(len(part.text), 0)
            self.assertLessEqual(len(part.text.encode("utf-8")), MAX_CHUNK_UTF8_BYTES)
            self.assertEqual(text[part.char_start:part.char_end], part.text)
            self.assertEqual(
                text.encode("utf-8")[part.utf8_start:part.utf8_end], part.text.encode("utf-8"),
            )
            self.assertEqual(part.source_text_sha256, _h(text.encode("utf-8")))
            self.assertEqual(part.span_sha256, _h(part.text.encode("utf-8")))
            self.assertEqual(part.locator["offset_origin"], "EXTRACTED_BLOCK_TEXT")
            if i:
                previous = spans[i - 1]
                self.assertEqual(previous.char_end, part.char_start)
                self.assertEqual(previous.utf8_end, part.utf8_start)

    def test_exact_boundary_whitespace_and_one_character_cell(self):
        for text in ("a" * 1800, "a" * 1801, "한", "A \n B\n", "🌏" * 450):
            with self.subTest(size=len(text)):
                spans = split_source_text(text)
                self.assertEqual("".join(part.text for part in spans), text)
                self.assertEqual(spans[-1].char_end, len(text))
                self.assertEqual(spans[-1].utf8_end, len(text.encode("utf-8")))
        self.assertEqual(len(split_source_text("a" * 1800)), 1)
        self.assertEqual(len(split_source_text("a" * 1801)), 2)

    def test_no_invalid_unicode_null_empty_limit_or_silent_loss(self):
        for text in ("", "\x00abc", "\ud800", "\udfff", None, b"byte"):
            with self.subTest(text=repr(text)), self.assertRaises(SourceChunkError):
                split_source_text(text)
        for limit in (0, 1801, True, 1.5):
            with self.subTest(limit=limit), self.assertRaises(SourceChunkError):
                split_source_text("valid", limit=limit)
        with self.assertRaisesRegex(SourceChunkError, "CHUNK_LIMIT_BELOW_UTF8_CODEPOINT"):
            split_source_text("한", limit=2)
        with patch("bid_server.procurement.source_chunking.MAX_CHUNKS_PER_BLOCK", 2):
            with self.assertRaisesRegex(SourceChunkError, "CHUNK_BLOCK_LIMIT_EXCEEDED"):
                split_source_text("x" * 5401)


def make_hwpx(paragraph, cell_short="5", cell_long="", footnote="자격 기준 3건 필수"):
    doc = f"""<?xml version="1.0" encoding="UTF-8"?>
<hp:sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">
<hp:p><hp:run><hp:t>{paragraph}</hp:t></hp:run></hp:p>
<hp:tbl><hp:tr>
<hp:tc><hp:p><hp:run><hp:t>{cell_short}</hp:t></hp:run></hp:p></hp:tc>
<hp:tc><hp:p><hp:run><hp:t>{cell_long}</hp:t></hp:run></hp:p></hp:tc>
</hp:tr></hp:tbl>
<hp:p><hp:run><hp:t>각주 위치 본문</hp:t></hp:run>
<hp:footnote><hp:p><hp:run><hp:t>{footnote}</hp:t></hp:run></hp:p></hp:footnote>
</hp:p>
</hp:sec>"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("mimetype", b"application/hwp+zip")
        archive.writestr("Contents/section0.xml", doc.encode("utf-8"))
    return buffer.getvalue()


class PersistEvidenceChunkTests(TestCase):
    def setUp(self):
        self.notice = Notice.objects.create(
            source="SYNTHETIC_FIXTURE", notice_number="SYNTHETIC-CHUNK-P003",
        )
        self.version = NoticeVersion.objects.create(
            notice=self.notice, version_seq=1, observed_at=timezone.now(),
            title="Synthetic chunk source", buyer="Synthetic",
            source_payload_digest="a" * 64,
        )
        self.notice.current_version = self.version
        self.notice.save(update_fields=["current_version"])
        self.document = Document.objects.create(notice=self.notice, logical_key="RFP")
        self.raw = make_hwpx("요구 자격 " + "가" * 1800, cell_long="평가 " + "다" * 1350,
                             footnote="자격 " + "나" * 1600)
        self.doc = DocumentVersion.objects.create(
            document=self.document, notice_version=self.version, version_seq=1,
            sha256=_h(self.raw), size_bytes=len(self.raw),
            media_type="application/x-hwp+zip",
        )

    def test_all_text_table_short_cell_and_footnotes_persisted_with_offsets(self):
        run = ExtractionService.extract_and_persist(self.doc, self.raw, "RFP.hwpx")
        self.assertFalse(run.coverage["complete"])
        self.assertEqual(run.coverage["status"], "PARTIAL")
        self.assertEqual(run.coverage["structure_fidelity"], "UNVERIFIED")
        self.assertTrue(run.coverage["source_text_lossless_segmentation"])
        self.assertEqual(run.coverage["source_document_sha256"], self.doc.sha256)
        self.assertIn("STRUCTURAL_COVERAGE_NOT_VERIFIED", run.warnings)
        self.assertFalse(run.coverage.get("table_grid_verified", False))
        self.assertEqual(run.coverage["chunk_count"], run.chunks.count())
        self.assertEqual(
            run.coverage["chunk_utf8_bytes"],
            sum(len(c.text.encode("utf-8")) for c in run.chunks.all()),
        )
        chunks = list(run.chunks.order_by("ordinal"))
        self.assertEqual([c.ordinal for c in chunks], list(range(1, len(chunks) + 1)))
        self.assertTrue(any(c.path == ChunkPath.TABLE and c.text == "5" for c in chunks),
                        "One-character qualification/score table cell must not be dropped")
        self.assertTrue(any(c.path == ChunkPath.FOOTNOTE for c in chunks))
        self.assertTrue(any(c.path == ChunkPath.TEXT for c in chunks))
        by_source = {}
        for item in chunks:
            self.assertLessEqual(len(item.text.encode("utf-8")), 1800)
            self.assertEqual(item.locator["source_document_sha256"], self.doc.sha256)
            self.assertEqual(item.locator["span_sha256"], _h(item.text.encode("utf-8")))
            self.assertEqual(item.locator["offset_origin"], "EXTRACTED_BLOCK_TEXT")
            self.assertTrue(item.source_block_refs)
            by_source.setdefault(
                (item.path, tuple(item.source_block_refs),
                 item.locator["source_text_sha256"]), []
            ).append(item)
        self.assertTrue(any(len(s) > 1 for s in by_source.values()))
        for parts in by_source.values():
            parts.sort(key=lambda p: p.locator["char_start"])
            joined = "".join(p.text for p in parts)
            self.assertEqual(_h(joined.encode("utf-8")), parts[0].locator["source_text_sha256"])
            self.assertEqual(parts[0].locator["char_start"], 0)
            self.assertEqual(parts[-1].locator["char_end"], len(joined))
            for previous, current in zip(parts, parts[1:]):
                self.assertEqual(previous.locator["char_end"], current.locator["char_start"])
                self.assertEqual(previous.locator["utf8_end"], current.locator["utf8_start"])

    def test_fallback_text_only_reports_unverified_tables_footnotes(self):
        run = ExtractionService.extract_and_persist(
            self.doc, self.raw, "RFP.hwpx", public_hwpx_text_only=True,
        )
        self.assertFalse(run.coverage["complete"])
        self.assertEqual(run.coverage["status"], "PARTIAL")
        self.assertEqual(run.coverage["table_count"], 0)
        self.assertEqual(run.coverage["footnote_count"], 0)
        self.assertIn("TEXT_ONLY_LAYOUT_AND_FOOTNOTES_UNVERIFIED", run.warnings)
        self.assertIn("PUBLIC_RFP_TEXT_ONLY_TABLE_LAYOUT_AND_FOOTNOTE_LINKS_UNVERIFIED", run.warnings)
        self.assertEqual(run.coverage["chunk_count"], run.chunks.count())
        self.assertTrue(all(len(c.text.encode("utf-8")) <= 1800 for c in run.chunks.all()))

    def test_source_tampering_or_chunk_budget_failure_rolls_back(self):
        tampered = self.raw + b"x"
        with self.assertRaises(Exception):
            ExtractionService.extract_and_persist(self.doc, tampered, "RFP.hwpx")
        self.assertFalse(ExtractionRun.objects.exists())
        with patch("bid_server.procurement.extractor_service.MAX_CHUNKS_PER_EXTRACTION", 1):
            with self.assertRaisesRegex(ParserError, "budget"):
                ExtractionService.extract_and_persist(self.doc, self.raw, "RFP.hwpx")
        self.assertFalse(ExtractionRun.objects.exists())
