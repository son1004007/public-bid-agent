"""로컬 문서 추출기: 별도 Python 프로세스에서 문서 형식 검증과 읽기 수행.

입력: stdin 파일 원본(bytes) + 확장자 인자. 출력: stdout JSON(text, method, warning...).
신뢰 경계: ZIP 폭탄·대형 문서/페이지·OCR 시간 제한. 원문 내 명령을 실행하지 않음.
부작용: 타사 모델/API 호출 금지; HWP 라이브러리용 임시파일은 자동 삭제.
실패: 텍스트가 없거나 언어팩/라이브러리 미설치면 명확한 오류로 중단.
제한: 단일 파일 10MB, 텍스트 44,000자, 가상 샌드박스가 아닌 OS subprocess 격리.
"""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

MAX_RAW = 10 * 1024 * 1024
MAX_ARCHIVE = 35 * 1024 * 1024
MAX_FILES = 750
MAX_TEXT = 44_000
MAX_PDF_PAGES = 40
MAX_OCR_PAGES = 12
MAX_EXCEL_SHEETS = 24
MAX_EXCEL_ROWS = 2500
MAX_EXCEL_COLS = 90


class ExtractionError(ValueError):
    pass


def _assert_format(ext: str, raw: bytes) -> None:
    if not raw or len(raw) > MAX_RAW:
        raise ExtractionError("파일은 1바이트 이상 10MiB 이하여야 합니다")
    if ext in {".pdf"} and not raw.startswith(b"%PDF-"):
        raise ExtractionError("PDF 파일 시그니처가 일치하지 않습니다")
    if ext in {".hwp", ".xls"} and not raw.startswith(bytes.fromhex("D0 CF 11 E0 A1 B1 1A E1")):
        raise ExtractionError("HWP/XLS OLE 파일 시그니처가 일치하지 않습니다")
    if ext in {".hwpx", ".xlsx", ".xlsm", ".docx"}:
        if not zipfile.is_zipfile(io.BytesIO(raw)):
            raise ExtractionError("문서가 유효한 ZIP 기반 형식이 아닙니다")
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            members = z.infolist()
            if len(members) > MAX_FILES or sum(e.file_size for e in members) > MAX_ARCHIVE:
                raise ExtractionError("압축 해제 크기/파일 수 제한을 초과했습니다")
            if any(e.file_size > MAX_ARCHIVE or e.compress_size and e.file_size/e.compress_size > 500 for e in members):
                raise ExtractionError("압축 비율이 비정상적으로 높습니다")
            names = set(z.namelist())
            expected = {".hwpx": "Contents/", ".xlsx": "xl/workbook.xml", ".xlsm": "xl/workbook.xml", ".docx": "word/document.xml"}[ext]
            if not (any(n.lower().startswith("contents/section") and n.endswith(".xml") for n in names)
                    if ext == ".hwpx" else expected in names):
                raise ExtractionError("확장자와 내부 문서 구조가 일치하지 않습니다")


def _plain(raw: bytes) -> tuple[str, str, list[str]]:
    try:
        return raw.decode("utf-8-sig"), "utf-8", []
    except UnicodeDecodeError as e:
        raise ExtractionError("텍스트 파일은 UTF-8 인코딩으로 저장해 주세요") from e


def _pdf(raw: bytes) -> tuple[str, str, list[str]]:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(raw), strict=False)
    if reader.is_encrypted:
        raise ExtractionError("암호화 PDF는 지원하지 않습니다")
    if len(reader.pages) > MAX_PDF_PAGES:
        raise ExtractionError("PDF 최대 40페이지까지만 지원합니다")
    segments: list[str] = []
    sparse: list[int] = []
    warnings: list[str] = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        segments.append(text)
        if len(text.strip()) < 30:
            sparse.append(i)
    if not sparse:
        return "\n".join(segments), "PDF 텍스트 추출", warnings
    if len(sparse) > MAX_OCR_PAGES:
        raise ExtractionError("이미지 PDF OCR은 12페이지까지만 가능합니다. 파일을 나눠 업로드해 주세요")
    if shutil.which("tesseract") is None:
        raise ExtractionError("이미지 PDF를 OCR 처리하려면 Tesseract OCR과 한국어 kor 언어팩을 설치해 주세요")
    import pytesseract
    import pypdfium2 as pdfium
    # OCR 없는 페이지는 렌더하지 않음. 한국어+영어 인식은 기기 내에서만 처리.
    available = set(pytesseract.get_languages(config=""))
    if "kor" not in available:
        raise ExtractionError("Tesseract 한국어 kor.traineddata가 없습니다. 한국어 언어팩을 설치해 주세요")
    lang = "kor+eng" if "eng" in available else "kor"
    document = pdfium.PdfDocument(raw)
    for i in sparse:
        bitmap = document[i].render(scale=1.8)
        image = bitmap.to_pil()
        if image.width*image.height > 16_000_000:
            raise ExtractionError("OCR 이미지 크기가 지나치게 큽니다")
        content = pytesseract.image_to_string(image, lang=lang, config="--psm 3", timeout=8).strip()
        if not content:
            warnings.append(f"{i+1}페이지 OCR에서 문자를 찾지 못했습니다")
        segments[i] = content
        bitmap.close()
    if not any(t.strip() for t in segments):
        raise ExtractionError("OCR 후에도 판독된 텍스트가 없습니다. 스캔 품질을 확인해 주세요")
    return "\n".join(segments), f"PDF 텍스트+OCR({len(sparse)}페이지)", warnings


def _excel_xlsx(raw: bytes) -> tuple[str, str, list[str]]:
    from openpyxl import load_workbook
    workbook = load_workbook(io.BytesIO(raw), read_only=True, data_only=True, keep_links=False)
    output = []
    warnings = []
    size_count = 0
    try:
        sheets = workbook.worksheets
        if len(sheets) > MAX_EXCEL_SHEETS:
            warnings.append(f"{MAX_EXCEL_SHEETS}개 시트까지만 읽었습니다")
        for ws in sheets[:MAX_EXCEL_SHEETS]:
            output.append(f"[시트: {ws.title}]")
            for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row or 0, MAX_EXCEL_ROWS), max_col=min(ws.max_column or 0, MAX_EXCEL_COLS), values_only=True):
                columns = [str(val).replace("\n", " ").strip() if val is not None else "" for val in row]
                if any(columns):
                    content = "\t".join(columns)
                    output.append(content)
                    size_count += len(content)
                if size_count > MAX_TEXT*2:
                    warnings.append("Excel 처리 가능한 텍스트 상한에 도달했습니다")
                    return "\n".join(output), "Excel 셀 값 (수식의 저장된 계산값)", warnings
            if (ws.max_row or 0)>MAX_EXCEL_ROWS or (ws.max_column or 0)>MAX_EXCEL_COLS:
                warnings.append(f"시트 {ws.title}의 일부 행·열만 추출했습니다")
    finally:
        workbook.close()
    return "\n".join(output), "Excel 셀 값 (수식의 저장된 계산값)", warnings


def _excel_xls(raw: bytes) -> tuple[str, str, list[str]]:
    import xlrd
    wb = xlrd.open_workbook(file_contents=raw, on_demand=True)
    output = []
    warnings = []
    size_count = 0
    try:
        for sh in wb.sheets()[:MAX_EXCEL_SHEETS]:
            output.append(f"[시트: {sh.name}]")
            for row in range(min(sh.nrows, MAX_EXCEL_ROWS)):
                cols = [str(sh.cell_value(row, col)).strip() for col in range(min(sh.ncols,MAX_EXCEL_COLS))]
                if any(cols):
                    content = "\t".join(cols)
                    output.append(content)
                    size_count += len(content)
                if size_count > MAX_TEXT*2:
                    warnings.append("Excel 텍스트 상한에 도달했습니다")
                    return "\n".join(output), "구형 XLS 셀 값", warnings
            if sh.nrows>MAX_EXCEL_ROWS or sh.ncols>MAX_EXCEL_COLS:
                warnings.append(f"시트 {sh.name}의 일부 행·열만 추출했습니다")
    finally:
        wb.release_resources()
    return "\n".join(output), "구형 XLS 셀 값", warnings


def _hwpx(raw: bytes) -> tuple[str, str, list[str]]:
    # 한컴 설치 없이 정적 HWPX XML에서 hp:t를 읽는다. 외부 엔터티/DTD는 차단.
    output = []
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        sections = [n for n in z.namelist() if re.fullmatch(r"Contents/section\d+\.xml", n, re.I)]
        sections.sort(key=lambda n:int(re.search(r"section(\d+)\.xml",n,re.I).group(1)))
        for path in sections:
            raw_xml=z.read(path)
            if b"<!DOCTYPE" in raw_xml.upper() or b"<!ENTITY" in raw_xml.upper():
                raise ExtractionError("DTD/ENTITY가 포함된 HWPX를 거부합니다")
            root=ET.fromstring(raw_xml)
            for node in root.iter():
                if node.tag.rsplit("}",1)[-1]=="p":
                    values=[tag.text or "" for tag in node.iter() if tag.tag.rsplit("}",1)[-1]=="t"]
                    if any(values):
                        output.append("".join(values))
    return "\n".join(output), "HWPX 문단/표 XML", []


def _hwp(raw: bytes) -> tuple[str, str, list[str]]:
    # Apache-2.0 python-hwpx. legacy AGPL pyhwp를 묶어 배포하지 않음.
    try:
        from hwpx import HwpxDocument
    except ImportError as e:
        raise ExtractionError("HWP를 읽으려면 pip install python-hwpx가 필요합니다") from e
    with tempfile.TemporaryDirectory(prefix="local-bid-hwp-") as tmp:
        path = Path(tmp)/"input.hwp"
        path.write_bytes(raw)
        with HwpxDocument.open(path) as document:
            paragraphs = [paragraph.text for paragraph in document.paragraphs]
            return "\n".join(paragraphs), "HWP 5.x 한컴 바이너리 파서", []


def extract_document(name: str, raw: bytes) -> dict:
    ext = Path(name).suffix.lower()
    if ext not in {".txt", ".md", ".csv", ".json", ".pdf", ".docx", ".xlsx", ".xlsm", ".xls", ".hwpx", ".hwp"}:
        raise ExtractionError("지원 형식: txt, md, csv, json, pdf, docx, xlsx, xlsm, xls, hwp, hwpx")
    _assert_format(ext, raw)
    try:
        if ext in {".txt", ".md", ".csv", ".json"}:
            text,method,warnings = _plain(raw)
        elif ext==".pdf":
            text,method,warnings = _pdf(raw)
        elif ext==".docx":
            from docx import Document
            doc = Document(io.BytesIO(raw))
            para=[p.text for p in doc.paragraphs]
            # 표 본문 누락 방지
            for table in doc.tables:
                for row in table.rows:
                    para.append("\t".join(cell.text for cell in row.cells))
            text,method,warnings = "\n".join(para),"DOCX 문단+표",[]
        elif ext in {".xlsx", ".xlsm"}:
            text,method,warnings = _excel_xlsx(raw)
        elif ext==".xls":
            text,method,warnings = _excel_xls(raw)
        elif ext==".hwpx":
            text,method,warnings = _hwpx(raw)
        else:
            text,method,warnings = _hwp(raw)
    except ExtractionError:
        raise
    except Exception as e:
        raise ExtractionError(f"{ext} 문서 파싱 실패: {type(e).__name__}. 비암호화/정상 파일인지 확인하세요") from e
    if not text.strip():
        raise ExtractionError("문서에서 추출된 텍스트가 없습니다. OCR 언어팩/파일 상태를 확인하세요")
    truncated = len(text)>MAX_TEXT
    if truncated:
        warnings.append(f"추출 텍스트 {len(text):,}자 중 {MAX_TEXT:,}자만 보관. 일부 근거 누락 가능")
    return {"text":text[:MAX_TEXT],"method":method,"warnings":warnings,"truncated":truncated,"characters":len(text)}


def main() -> None:
    try:
        name = sys.argv[1]
        raw = sys.stdin.buffer.read(MAX_RAW+1)
        result = extract_document(name,raw)
        print(json.dumps({"ok":True,**result},ensure_ascii=False))
    except (ExtractionError, IndexError) as e:
        print(json.dumps({"ok":False,"error":str(e)},ensure_ascii=False))
    except Exception:
        print(json.dumps({"ok":False,"error":"문서 파서 내부 오류"},ensure_ascii=False))


if __name__=="__main__":
    main()