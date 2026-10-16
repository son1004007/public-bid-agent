"""PDF/HWPX 구조 위험 진단 합성 문서 테스트: 실제 원본/네트워크 미사용."""
import io
import json
import tempfile
import unittest
import zipfile
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
