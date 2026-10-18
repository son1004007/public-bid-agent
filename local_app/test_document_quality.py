"""PDF/HWPX 구조 위험 진단 합성 문서 테스트: 실제 원본/네트워크 미사용."""
import io
import json
import tempfile
import unittest
import zipfile
from unittest.mock import patch
from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from document_quality import inspect
from extractors import ExtractionError
import server

class QualityDiagnosticsTests(unittest.TestCase):
    def test_pdf_page_sparse_vs_text_and_no_original_content(self):
        buffer=io.BytesIO()
        pdf=canvas.Canvas(buffer)
        pdf.drawString(30,700,"Synthetic qualification and score reference text")
        pdf.showPage()
        pdf.showPage()
        pdf.save()
        out=inspect("synthetic.pdf",buffer.getvalue())
        self.assertEqual(out["file_type"],"PDF")
        self.assertEqual(out["page_count"],2)
        self.assertEqual(out["pages"][0]["page"],1)
        self.assertFalse(out["pages"][0]["sparse_text"])
        self.assertTrue(out["pages"][1]["sparse_text"])
        self.assertIn("SPARSE_OR_SCANNED_PAGES_POSSIBLE",out["flags"])
        self.assertEqual(out["ocr_accuracy"],"NOT_VERIFIED")
        self.assertNotIn("Synthetic qualification",json.dumps(out))
        self.assertIn("OCR_VISUAL_REVIEW_REQUIRED",out["pages"][1]["flags"])
        self.assertNotIn("OCR_VISUAL_REVIEW_REQUIRED",out["pages"][0]["flags"])
        self.assertIn("TABLE_STRUCTURE_NOT_VERIFIED",out["flags"])
        self.assertIn("FOOTNOTE_STRUCTURE_NOT_VERIFIED",out["flags"])

    def test_text_layer_over_image_still_needs_ocr_visual_review(self):
        buffer=io.BytesIO();pdf=canvas.Canvas(buffer)
        pdf.drawImage(ImageReader(Image.new("RGB",(10,10),"white")),20,400,100,100)
        pdf.drawString(30,700,"Synthetic OCR layer: qualification 100 vs 1000 requires review")
        pdf.save()
        out=inspect("synthetic.pdf",buffer.getvalue())
        self.assertFalse(out["pages"][0]["sparse_text"])
        self.assertEqual(out["pages"][0]["image_object_count"],1)
        self.assertIn("OCR_VISUAL_REVIEW_REQUIRED",out["pages"][0]["flags"])
        self.assertEqual(out["ocr_accuracy"],"NOT_VERIFIED")

    def test_unknown_image_metadata_is_not_zero(self):
        class Page:
            def extract_text(self):return "SYNTHETIC "*8
            def get(self,key):raise ValueError("PRIVATE_PARSER_DETAIL")
        class Reader:
            is_encrypted=False
            pages=[Page()]
        with patch("pypdf.PdfReader",return_value=Reader()):
            out=inspect("synthetic.pdf",b"%PDF-1.4\n")
        self.assertIsNone(out["image_object_count"])
        self.assertIsNone(out["pages"][0]["image_object_count"])
        self.assertIn("IMAGE_METADATA_UNAVAILABLE",out["pages"][0]["flags"])
        self.assertNotIn("PRIVATE_PARSER_DETAIL",repr(out))

    def test_hwpx_section_locations_and_merged_cells_are_not_page_numbers(self):
        raw=io.BytesIO()
        with zipfile.ZipFile(raw,"w") as z:
            z.writestr("Contents/section10.xml",'<section><tbl><cellSpan colSpan="2" rowSpan="1"/></tbl><footNote>SECRET</footNote></section>')
            z.writestr("Contents/section2.xml",'<section><tbl><cellSpan colSpan="1" rowSpan="1"/><cellSpacing value="2"/></tbl></section>')
        out=inspect("synthetic.hwpx",raw.getvalue())
        self.assertEqual(out["merged_cell_markers"],1)
        self.assertEqual(out["table_elements"],2)
        self.assertEqual([s["section"] for s in out["section_details"]],[2,10])
        self.assertTrue(all(s["page"] is None for s in out["section_details"]))
        self.assertEqual(out["section_details"][0]["merged_cell_markers"],0)
        self.assertIn("FOOTNOTE_REVIEW_REQUIRED",out["section_details"][1]["flags"])
        self.assertIn("MERGED_CELL_REVIEW_REQUIRED",out["flags"])
        self.assertNotIn("SECRET",repr(out))

    def test_hwpx_without_numeric_body_section_is_rejected(self):
        raw=io.BytesIO()
        with zipfile.ZipFile(raw,"w") as z:z.writestr("Contents/sectionOther.xml","<section/>")
        with self.assertRaises(ExtractionError):inspect("synthetic.hwpx",raw.getvalue())

    def test_resource_limits_and_entity_input_remain_rejected(self):
        from extractors import MAX_RAW, MAX_PDF_PAGES
        with self.assertRaises(ExtractionError):inspect("synthetic.txt",b"x"*(MAX_RAW+1))
        buffer=io.BytesIO();pdf=canvas.Canvas(buffer)
        for _ in range(MAX_PDF_PAGES+1):pdf.showPage()
        pdf.save()
        with self.assertRaises(ExtractionError):inspect("synthetic.pdf",buffer.getvalue())
        raw=io.BytesIO()
        with zipfile.ZipFile(raw,"w") as z:
            z.writestr("Contents/section0.xml",'<!DOCTYPE x [<!ENTITY x "SECRET">]><section>&x;</section>')
        with self.assertRaises(ExtractionError):inspect("synthetic.hwpx",raw.getvalue())
    def test_hwpx_table_and_footnote_markers_do_not_imply_coverage(self):
        raw=io.BytesIO()
        with zipfile.ZipFile(raw,"w",zipfile.ZIP_DEFLATED) as z:
            z.writestr("Contents/section0.xml",
              '<hp:section xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">'
              '<hp:tbl><hp:tc><hp:p><hp:t>SECRET_EVIDENCE</hp:t></hp:p></hp:tc></hp:tbl>'
              '<hp:footNote/><hp:p><hp:t>입찰 자격</hp:t></hp:p></hp:section>')
        out=inspect("synthetic.hwpx",raw.getvalue())
        self.assertEqual(out["table_elements"],1)
        self.assertEqual(out["footnote_markers"],1)
        self.assertIn("TABLE_LAYOUT_REVIEW_REQUIRED",out["flags"])
        self.assertIn("FOOTNOTE_REVIEW_REQUIRED",out["flags"])
        self.assertEqual(out["original_completeness"],"NOT_VERIFIED")
        self.assertNotIn("SECRET_EVIDENCE",repr(out))
    def test_unsupported_file_and_spoofed_signature_rejected(self):
        with self.assertRaises(ExtractionError):
            inspect("synthetic.exe",b"ABC")
        with self.assertRaises(ExtractionError):
            inspect("synthetic.pdf",b"not-pdf")
    def test_quality_subprocess_memory_only_fixed_metadata(self):
        raw=b"CONFIDENTIAL_SYNTHETIC_TEXT"
        result=server.quality_in_subprocess("test.txt",raw)
        self.assertEqual(result["mode"],"STRUCTURAL_RISK_HINTS_ONLY")
        self.assertNotIn("CONFIDENTIAL_SYNTHETIC_TEXT",repr(result))
        self.assertEqual(result["original_completeness"],"NOT_VERIFIED")
        self.assertEqual(server.quality_in_subprocess("test.exe",raw)["mode"],"UNAVAILABLE")

if __name__=="__main__":unittest.main()
