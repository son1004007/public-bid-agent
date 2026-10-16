"""공식 원본 메모리·subprocess의 비식별 페이지/표·각주 위험 메타데이터 진단.
기능: PDF 페이지별 문자수/이미지 XObject 수, HWPX 표·각주 XML 표식 개수만 추산.
한계: 표 셀 읽기 순서, 주석/각주 본문, OCR 정확도·RFP 필수요건 Recall 판정 불가.
보안: 입력 원문/파일명/해시를 반환하지 않으며 네트워크/LLM/영구 파일 기록 없음.
테스트: test_document_quality.py, 40 PDF 페이지/35MiB 압축 해제 제한 재사용.
"""
import io
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from extractors import _assert_format, ExtractionError, MAX_PDF_PAGES, MAX_RAW

MAX_HWPX_SECTIONS=40

def _summary(kind,pages,flags,**counts):
    return {"mode":"STRUCTURAL_RISK_HINTS_ONLY","file_type":kind,"pages":pages,
            "flags":sorted(set(flags)),"original_completeness":"NOT_VERIFIED",
            "table_cell_order":"NOT_VERIFIED","footnote_text":"NOT_VERIFIED",
            "ocr_accuracy":"NOT_VERIFIED",**counts}

def inspect(name,raw):
    ext=Path(name).suffix.lower()
    if ext not in (".pdf",".hwpx",".hwp",".docx",".txt",".md"):
        raise ExtractionError("지원하지 않는 품질 진단 파일 형식")
    _assert_format(ext,raw)
    if ext==".pdf":
        from pypdf import PdfReader
        reader=PdfReader(io.BytesIO(raw),strict=False)
        if reader.is_encrypted:raise ExtractionError("암호화 PDF")
        if len(reader.pages)>MAX_PDF_PAGES:raise ExtractionError("PDF 페이지 상한")
        flags=[];pages=[];images=0
        for i,p in enumerate(reader.pages):
            text=p.extract_text() or ""
            # XObject image는 스캔 여부 확정이 아닌 '이미지 포함' 표시.
            try:
                resources=p.get("/Resources")
                xobjects=resources.get("/XObject",{}) if resources else {}
                xobjects=xobjects.get_object() if hasattr(xobjects,"get_object") else xobjects
                image_count=sum(1 for x in xobjects.values()
                   if hasattr(x,"get_object") and x.get_object().get("/Subtype")=="/Image")
            except (ValueError,KeyError,TypeError,AttributeError):
                image_count=0;flags.append("IMAGE_METADATA_UNAVAILABLE")
            images+=image_count
            char_count=len(text.strip())
            if char_count<30:flags.append("SPARSE_OR_SCANNED_PAGES_POSSIBLE")
            if image_count:flags.append("IMAGE_OBJECTS_PRESENT")
            pages.append({"page":i+1,"extracted_chars":char_count,
                          "image_object_count":image_count,"sparse_text":char_count<30})
        return _summary("PDF",pages,flags,page_count=len(pages),
                        image_object_count=images,table_elements="NOT_IDENTIFIED")
    if ext==".hwpx":
        flags=[];counts={"sections":0,"table_elements":0,"footnote_markers":0,
                          "merged_cell_markers":0}
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            names=[n for n in z.namelist() if re.fullmatch(r"Contents/section\d+\.xml",n,re.I)]
            if len(names)>MAX_HWPX_SECTIONS:raise ExtractionError("HWPX 섹션 상한")
            for name in names:
                xml=z.read(name)
                if b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
                    raise ExtractionError("외부 엔터티 차단")
                root=ET.fromstring(xml)
                counts["sections"]+=1
                for node in root.iter():
                    tag=node.tag.rsplit("}",1)[-1].lower()
                    if tag in ("tbl","table"):counts["table_elements"]+=1
                    if tag in ("footnote","footnoteref","footnoteshape"):counts["footnote_markers"]+=1
                    if tag in ("cellspan","cellspacing") or (tag=="tc" and any("span" in str(k).lower() for k in node.attrib)):
                        counts["merged_cell_markers"]+=1
        if counts["table_elements"]:flags.append("TABLE_LAYOUT_REVIEW_REQUIRED")
        if counts["footnote_markers"]:flags.append("FOOTNOTE_REVIEW_REQUIRED")
        flags.append("PAGE_NUMBERS_UNAVAILABLE")
        return _summary("HWPX",[],flags,**counts)
    flags=["STRUCTURAL_DIAGNOSTIC_NOT_SUPPORTED"]
    return _summary(ext[1:].upper(),[],flags)

def main():
    try:
        name=sys.argv[1]
        raw=sys.stdin.buffer.read(MAX_RAW+1)
        result=inspect(name,raw)
        print(json.dumps({"ok":True,"quality":result},ensure_ascii=False))
    except Exception:
        # 파일명/바이너리/파서 내부 내용을 stdout·stderr로 노출하지 않는다.
        print(json.dumps({"ok":False,"quality":{"mode":"UNAVAILABLE","original_completeness":"NOT_VERIFIED"}}))

if __name__=="__main__":main()
