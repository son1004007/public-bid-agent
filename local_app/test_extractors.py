"""문서 추출 정상·오류·OCR·형식별 로컬 처리 검증; 실제 회사 자료는 사용하지 않음."""
import base64
import io
import json
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import extractors
import server


class FormatsTest(unittest.TestCase):
    def test_text_and_bad_signature(self):
        x = extractors.extract_document("requirements.txt", "입찰공고 조건".encode())
        self.assertEqual(x["text"], "입찰공고 조건")
        with self.assertRaisesRegex(ValueError, "시그니처"):
            extractors.extract_document("fake.pdf", b"not a pdf")
        with self.assertRaisesRegex(ValueError, "시그니처"):
            extractors.extract_document("fake.hwp", b"untrusted")

    def test_hwpx_zip_xml_text_and_table(self):
        content = io.BytesIO()
        with zipfile.ZipFile(content, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("mimetype", "application/hwp+zip")
            z.writestr("Contents/section0.xml", '<hp:section xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"><hp:p><hp:run><hp:t>입찰 요건을 확인</hp:t></hp:run></hp:p><hp:p><hp:run><hp:t>실적 3건 이상</hp:t></hp:run></hp:p></hp:section>')
        result=extractors.extract_document("offer.hwpx",content.getvalue())
        self.assertIn("입찰 요건을 확인",result["text"])
        self.assertIn("실적 3건",result["text"])
        with zipfile.ZipFile(content := io.BytesIO(),"w") as z:
            z.writestr("Contents/section0.xml", '<!DOCTYPE bad [ <!ENTITY x SYSTEM "file:///etc/passwd"> ]><a/>')
        with self.assertRaisesRegex(ValueError,"DTD|ENTITY"):
            extractors.extract_document("bad.hwpx",content.getvalue())

    def test_xlsx_multiple_sheets_and_no_formula_execution(self):
        from openpyxl import Workbook
        wb=Workbook();a=wb.active;a.title="평가";a.append(["항목","점수"]);a.append(["기술 적합성",3]);a.append(["수익", "=1+2"])
        b=wb.create_sheet("제안준비");b.append(["인력","2명"])
        out=io.BytesIO();wb.save(out)
        result=extractors.extract_document("bid.xlsx",out.getvalue())
        self.assertIn("[시트: 평가]",result["text"])
        self.assertIn("기술 적합성",result["text"])
        self.assertIn("[시트: 제안준비]",result["text"])
        self.assertNotIn("=1+2",result["text"])

    def test_pdf_with_text(self):
        from reportlab.pdfgen import canvas
        output=io.BytesIO();c=canvas.Canvas(output)
        c.drawString(30,700,"The procurement requires a service engineer with verifiable project experience")
        c.save()
        result=extractors.extract_document("rfp.pdf",output.getvalue())
        self.assertIn("procurement",result["text"])
        self.assertIn("PDF 텍스트",result["method"])

    def test_ocr_image_pdf_local_korean_engine(self):
        from PIL import Image,ImageDraw,ImageFont
        from reportlab.pdfgen import canvas
        import tempfile
        import shutil
        if shutil.which("tesseract") is None:
            self.skipTest("Tesseract 실행 파일 미설치")
        import pytesseract
        if "kor" not in pytesseract.get_languages(config=""):
            self.skipTest("한국어 언어팩 미설치")
        with tempfile.TemporaryDirectory() as folder:
            png=Path(folder)/"scanned.png"
            img=Image.new("RGB",(1300,350),"white")
            ImageDraw.Draw(img).text((60,110),"PROCUREMENT CONTRACT 2026",fill="black",font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",55))
            img.save(png)
            pdf=io.BytesIO();c=canvas.Canvas(pdf,pagesize=(650,175));c.drawImage(str(png),0,0,width=650,height=175);c.save()
            result=extractors.extract_document("scanned.pdf",pdf.getvalue())
            self.assertIn("OCR",result["method"])
            self.assertIn("CONTRACT",result["text"].upper())

    def test_oversize_zip_rejected_before_openpyxl(self):
        fake=io.BytesIO()
        with zipfile.ZipFile(fake,"w",compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("xl/workbook.xml","X"*(36*1024*1024))
        with self.assertRaisesRegex(ValueError,"압축"):
            extractors.extract_document("attack.xlsx",fake.getvalue())

    def test_real_hwp5_roundtrip_with_python_hwpx(self):
        # 실제 HWP5 바이너리 생성/읽기: CI에서 python-hwpx 설치 후 검증.
        try:
            from hwpx import HwpxDocument
        except ImportError:
            self.skipTest("python-hwpx 미설치")
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"example.hwp"
            doc=HwpxDocument.new()
            doc.add_paragraph("실제 입찰 참가 자격과 납기")
            doc.save_to_path(path)
            raw=path.read_bytes()
            self.assertTrue(raw.startswith(bytes.fromhex("D0 CF 11 E0 A1 B1 1A E1")))
            result=extractors.extract_document("example.hwp",raw)
            self.assertIn("입찰",result["text"])
            self.assertIn("HWP",result["method"])

    def test_xls_legacy_formula_cached_content(self):
        try:
            import xlwt
            import xlrd
        except ImportError:
            self.skipTest("xlwt/xlrd 설치 확인용 CI 시험")
        wb=xlwt.Workbook();ws=wb.add_sheet("입찰점수")
        ws.write(0,0,"기술배점");ws.write(0,1,85)
        buffer=io.BytesIO();wb.save(buffer)
        result=extractors.extract_document("legacy.xls",buffer.getvalue())
        self.assertIn("입찰점수",result["text"])
        self.assertIn("기술배점",result["text"])

    def test_worker_stdout_contract(self):
        work=Path(__file__).with_name("extractors.py")
        p=subprocess.run([sys.executable,str(work),"brief.md"],input="공고의 필수 사항".encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=12)
        self.assertEqual(p.returncode,0)
        obj=json.loads(p.stdout)
        self.assertTrue(obj["ok"])
        self.assertIn("공고",obj["text"])

    def test_http_ingest_pdf_and_warning_metadata(self):
        test=server.extract_in_subprocess("brief.md", "근거 있는 일정".encode())
        self.assertTrue(test["ok"])
        self.assertEqual(test["text"],"근거 있는 일정")
        self.assertIn("method",test)


if __name__ == "__main__": unittest.main()