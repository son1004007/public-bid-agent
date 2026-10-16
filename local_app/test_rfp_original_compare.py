"""공식 원본과 RFP 캐시 재추출을 합성 문서만으로 검증."""
import hashlib
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from extractors import extract_document
from rfp_fulltext import store, load
from rfp_original_compare import compare


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def setup_fixture(root, name, raw, parser=extract_document):
    att = {"name": name, "url": "https://www.g2b.go.kr/synthetic-fixture"}
    data = parser(name, raw)
    source = digest(raw)
    meta = store(root, source, data)
    proof = {"status": "EXTRACTED", "identity": digest(
        (att["url"] + "\n" + att["name"]).encode()), "name": name,
        "sha256": source, **meta}
    return att, proof, load(root, meta["fulltext_ref"])


class CompareTests(unittest.TestCase):
    def test_synthetic_pdf_reproduces_stored_text_without_proving_layout(self):
        from reportlab.pdfgen import canvas
        stream = io.BytesIO()
        pdf = canvas.Canvas(stream)
        pdf.drawString(50, 740, "QUALIFICATION: three projects")
        pdf.drawString(50, 710, "EVALUATION: 80 points")
        pdf.save()
        raw = stream.getvalue()
        with tempfile.TemporaryDirectory() as td:
            a, proof, cache = setup_fixture(Path(td), "synthetic.pdf", raw)
            result = compare(a, proof, cache, raw, extract_document)
            self.assertEqual(result["status"], "REPRODUCED_TEXT")
            self.assertTrue(result["source_sha_matched"])
            self.assertTrue(result["text_prefix_matched"])
            self.assertEqual(result["original_page_table_ocr_coverage"], "NOT_VERIFIED")
            self.assertNotIn("QUALIFICATION", repr(result))
            self.assertNotIn("synthetic.pdf", repr(result))

    def test_hwpx_table_xml_can_reproduce_but_layout_still_unverified(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zipout:
            zipout.writestr("Contents/section0.xml",
                '<hp:section xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">'
                '<hp:p><hp:run><hp:t>입찰 참가 조건</hp:t></hp:run></hp:p>'
                '<hp:tbl><hp:tc><hp:p><hp:run><hp:t>기술 배점 80</hp:t></hp:run></hp:p></hp:tc></hp:tbl>'
                '</hp:section>')
        raw = buffer.getvalue()
        with tempfile.TemporaryDirectory() as td:
            a, proof, cache = setup_fixture(Path(td), "synthetic.hwpx", raw)
            result = compare(a, proof, cache, raw, extract_document)
            self.assertEqual(result["status"], "REPRODUCED_TEXT")
            self.assertEqual(result["original_page_table_ocr_coverage"], "NOT_VERIFIED")

    def test_source_sha_or_provenance_change_fails_before_parser(self):
        with tempfile.TemporaryDirectory() as td:
            raw = "가상 공고".encode()
            a, proof, cache = setup_fixture(Path(td), "synthetic.txt", raw)
            def forbidden(*args):
                self.fail("원본 신뢰 실패면 파서를 실행하면 안 된다")
            self.assertEqual(compare(a, proof, cache, b"altered", forbidden)["status"],
                             "ORIGINAL_SHA_MISMATCH")
            changed = {**proof, "identity": digest(b"wrong")}
            self.assertEqual(compare(a, changed, cache, raw, forbidden)["status"],
                             "INVALID_EVIDENCE")
            changed_att = {**a, "url": "https://evil.example/RFP"}
            self.assertEqual(compare(changed_att, proof, cache, raw, forbidden)["status"],
                             "INVALID_EVIDENCE")
            self.assertEqual(compare(a, proof, cache, b"", forbidden)["status"],
                             "ORIGINAL_UNAVAILABLE")

    def test_cache_tampering_blocks_and_no_private_data_output(self):
        with tempfile.TemporaryDirectory() as td:
            raw = "비공개 합성 요건과 평가점수".encode()
            a, proof, cache = setup_fixture(Path(td), "synthetic.txt", raw)
            forged = {**cache, "chunks": [{**cache["chunks"][0], "text": "위조"}]}
            self.assertEqual(compare(a, proof, forged, raw, extract_document)["status"],
                             "CACHE_MISMATCH")
            wrong = {**cache, "source_sha256": digest(b"different")}
            self.assertEqual(compare(a, proof, wrong, raw, extract_document)["status"],
                             "CACHE_MISMATCH")

    def test_all_proof_metadata_bound_to_cache_and_fail_before_parser(self):
        with tempfile.TemporaryDirectory() as td:
            raw = b"synthetic evidence record"
            a, proof, cache = setup_fixture(Path(td), "synthetic.txt", raw)
            variants = {
                "fulltext_chars": 999,
                "fulltext_reported_chars": 999,
                "fulltext_chunks": 10,
                "fulltext_truncated": True,
                "fulltext_position_basis": "ORIGINAL_PDF_PAGE",
            }
            def forbidden(*args):
                self.fail("캐시 결속 손상 시 파서는 호출하면 안 된다")
            for key, value in variants.items():
                with self.subTest(key=key):
                    damaged = {**proof, key: value}
                    self.assertEqual(compare(a, damaged, cache, raw, forbidden)["status"],
                                     "CACHE_MISMATCH")
            for key, value in (("fulltext_chars", True),
                               ("fulltext_reported_chars", True),
                               ("fulltext_chunks", True),
                               ("fulltext_truncated", 1)):
                with self.subTest(key=key, type="bool-is-not-int"):
                    damaged = {**proof, key: value}
                    self.assertEqual(compare(a, damaged, cache, raw, forbidden)["status"],
                                     "CACHE_MISMATCH")
            invalid_cache = [
                {"schema_version": True}, {"schema_version": 2},
                {"stored_chars": True}, {"reported_chars": True},
                {"truncated_by_parser": 0},
                {"position_basis": "ORIGINAL_PAGES"},
            ]
            for fields in invalid_cache:
                with self.subTest(cache_fields=fields):
                    self.assertEqual(compare(a, proof, {**cache, **fields}, raw, forbidden)["status"],
                                     "CACHE_MISMATCH")

    def test_parser_semantic_provenance_explicitly_unverified(self):
        with tempfile.TemporaryDirectory() as td:
            raw = b"reproducible extracted text"
            a, proof, cache = setup_fixture(Path(td), "synthetic.txt", raw)
            parser = lambda _name, _raw: {
                "text": "reproducible extracted text",
                "method": "DIFFERENT_OCR_IMPLEMENTATION",
                "warnings": ["SIMULATED_OCR_QUALITY_WARNING"],
            }
            result = compare(a, proof, cache, raw, parser)
            self.assertEqual(result["status"], "REPRODUCED_TEXT")
            self.assertEqual(result["length_truncation_metadata_reproducibility"], "MATCHED")
            self.assertEqual(result["parser_method_version_ocr_reproducibility"], "NOT_VERIFIED")
            self.assertEqual(result["original_page_table_ocr_coverage"], "NOT_VERIFIED")
            self.assertNotIn("SIMULATED_OCR", repr(result))

    def test_parser_failure_change_and_truncation_are_distinct(self):
        with tempfile.TemporaryDirectory() as td:
            raw = b"synthetic RFP"
            a, proof, cache = setup_fixture(Path(td), "synthetic.txt", raw)
            failure = lambda _name, _data: (_ for _ in ()).throw(ValueError("PRIVATE DETAILS"))
            self.assertEqual(compare(a, proof, cache, raw, failure)["status"],
                             "PARSER_UNAVAILABLE")
            changed = lambda _name, _data: {"text": "different"}
            self.assertEqual(compare(a, proof, cache, raw, changed)["status"],
                             "REEXTRACTED_TEXT_DIFFERS")
            changed_len = lambda _name, _data: {"text": "synthetic RFP", "characters": 15}
            self.assertEqual(compare(a, proof, cache, raw, changed_len)["status"],
                             "PARSER_METADATA_CHANGED")
            longer = lambda _name, _data: {"text": "synthetic RFP",
                                          "characters": 53000, "truncated": True}
            # 다른 원본 SHA로 fixture 생성: 기존 캐시 store()의 불변 사본 재사용 정책 보존.
            second_raw = b"synthetic source second version"
            meta = store(Path(td), digest(second_raw), longer(None, None))
            updated = {**proof, "sha256": digest(second_raw), **meta}
            truncated_cache = load(Path(td), meta["fulltext_ref"])
            result = compare(a, updated, truncated_cache, second_raw, longer)
            self.assertEqual(result["status"], "REPRODUCED_TRUNCATED_PREFIX")
            self.assertEqual(result["reported_chars"], 53000)
            self.assertEqual(result["original_page_table_ocr_coverage"], "NOT_VERIFIED")


if __name__ == "__main__":
    unittest.main()
