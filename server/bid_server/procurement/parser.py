"""DEF-03 구조 보존 문서 파서 (HWPX, DOCX, PDF, TXT).

목적: HWPX/DOCX 등 조달 첨부 문서로부터 단순 텍스트뿐만 아니라 표(병합 셀 rowspan/colspan,
      머리글 참조) 및 각주(앵커 결속) 구조를 무결하게 보존하여 추출한다.
경계: 외부 타사 라이브러리(한컴 오피스, MS Word 등) 의존 없이 순수 Python 표준 라이브러리(zipfile,
      xml.etree.ElementTree)를 사용하여 결정론적이고 안전하게 실행한다.
관련: docs/server-migration/17-domain-and-postgresql-contract.md §16, 27-html-defects-and-stop-verification.md (DEF-03).
"""
import io
import re
import zipfile
from xml.etree import ElementTree as ET
from typing import Any, Dict, List, Tuple


class ParserError(ValueError):
    """문서 파싱 실패 시 발생하는 표준 예외."""
    pass


# Conservative parser limits until large-document workload is measured.
MAX_INPUT_BYTES = 10 * 1024 * 1024
MAX_XML_BYTES = 2 * 1024 * 1024
MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 512
MAX_XML_NODES = 20000
MAX_XML_DEPTH = 48
MAX_OUTPUT_BLOCKS = 4000


def _check_input(raw):
    if not raw or len(raw) > MAX_INPUT_BYTES:
        raise ParserError("Document size exceeds parser limit or is empty.")


def _check_zip(z):
    entries = z.infolist()
    if (len(entries) > MAX_ARCHIVE_ENTRIES
            or sum(info.file_size for info in entries) > MAX_ARCHIVE_BYTES
            or len({info.filename.casefold() for info in entries}) != len(entries)
            or any(info.flag_bits & 1 for info in entries)):
        raise ParserError("Unsupported archive structure or size.")


def _read_xml(z, name):
    info = z.getinfo(name)
    if info.file_size > MAX_XML_BYTES:
        raise ParserError("XML size exceeds parser limit.")
    with z.open(info) as stream:
        data = stream.read(MAX_XML_BYTES + 1)
    if len(data) != info.file_size or len(data) > MAX_XML_BYTES:
        raise ParserError("XML size exceeds parser limit.")
    # Only UTF-8 XML is accepted at this boundary. Reject alternate encodings
    # and DTD/entity declarations before handing data to ElementTree.
    decoded = data.decode("utf-8-sig", errors="strict")
    if "\\x00" in decoded or re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", decoded, re.I):
        raise ParserError("Forbidden XML declaration.")
    declaration = re.match(r"\s*<\?xml\s+([^?]*)\?>", decoded, re.I)
    if declaration:
        encoding = re.search(r"""encoding\s*=\s*['"]([^'"]+)['"]""", declaration.group(1), re.I)
        if encoding and encoding.group(1).lower() not in ("utf-8", "utf8"):
            raise ParserError("Unsupported XML encoding.")
    parser = ET.XMLPullParser(events=("start", "end"))
    root = None
    depth = count = 0
    for start in range(0, len(data), 4096):
        parser.feed(data[start:start + 4096])
        for event, node in parser.read_events():
            if event == "start":
                if root is None:
                    root = node
                depth += 1
                count += 1
                if depth > MAX_XML_DEPTH or count > MAX_XML_NODES:
                    raise ParserError("XML structure exceeds parser limit.")
            else:
                depth -= 1
    parser.close()
    if root is None or depth != 0:
        raise ParserError("Invalid XML document.")
    return root


def _local_tag(elem: ET.Element) -> str:
    """XML 네임스페이스를 제외한 로컬 태그 이름을 반환한다."""
    tag = elem.tag
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def parse_hwpx(raw_bytes: bytes) -> Dict[str, Any]:
    """HWPX (OWPML) 문서에서 본문, 표(병합/좌표), 각주(앵커)를 파싱한다."""
    _check_input(raw_bytes)
    if not zipfile.is_zipfile(io.BytesIO(raw_bytes)):
        raise ParserError("유효한 HWPX (ZIP) 파일이 아닙니다.")

    blocks: List[Dict[str, Any]] = []
    tables: List[Dict[str, Any]] = []
    footnotes: List[Dict[str, Any]] = []
    full_text_parts: List[str] = []
    warnings: List[str] = []

    block_counter = 0

    with zipfile.ZipFile(io.BytesIO(raw_bytes)) as z:
        _check_zip(z)
        names = z.namelist()
        section_names = [n for n in names if re.fullmatch(r"Contents/section\d+\.xml", n, re.I)]
        section_names.sort(key=lambda n: int(re.search(r"section(\d+)\.xml", n, re.I).group(1)))

        if not section_names or len(section_names) > 32:
            raise ParserError("Missing or excessive HWPX sections.")

        for s_idx, sec_path in enumerate(section_names):
            root = _read_xml(z, sec_path)
            if _local_tag(root) != "sec":
                raise ParserError("Invalid HWPX section.")

            # Traverse elements
            for elem in root.iter():
                tag = _local_tag(elem)

                # 1. Table parsing (<hp:tbl>)
                if tag == "tbl":
                    block_counter += 1
                    t_block_id = f"sec{s_idx}_tbl{len(tables)+1}"

                    rows = []
                    for row_elem in elem.findall(".//{*}tr"):
                        rows.append(row_elem)
                    if not rows:
                        rows = [r for r in elem.iter() if _local_tag(r) == "tr"]

                    row_count = len(rows)
                    col_count = 0
                    cells_data: List[Dict[str, Any]] = []

                    for r_idx, r_elem in enumerate(rows):
                        # extract cells in row
                        c_elems = [c for c in r_elem.iter() if _local_tag(c) == "tc"]
                        if len(c_elems) > col_count:
                            col_count = len(c_elems)

                        for c_idx, c_elem in enumerate(c_elems):
                            # Check cellSpan / cellAddr attributes
                            colspan = 1
                            rowspan = 1
                            for child in c_elem.iter():
                                c_tag = _local_tag(child)
                                if c_tag in ("cellSpan", "cellAddr"):
                                    colspan = int(child.attrib.get("colSpan") or child.attrib.get("colspan") or 1)
                                    rowspan = int(child.attrib.get("rowSpan") or child.attrib.get("rowspan") or 1)

                            # Cell text
                            cell_texts = []
                            for p in c_elem.iter():
                                if _local_tag(p) == "t" and p.text:
                                    cell_texts.append(p.text.strip())
                            c_text = " ".join(cell_texts)

                            cell_id = f"{t_block_id}_c{r_idx}_{c_idx}"
                            header_refs = [f"{t_block_id}_c0_{c_idx}"] if r_idx > 0 else []

                            cells_data.append({
                                "cell_id": cell_id,
                                "row_index": r_idx,
                                "column_index": c_idx,
                                "rowspan": max(rowspan, 1),
                                "colspan": max(colspan, 1),
                                "header_refs": header_refs,
                                "text": c_text,
                                "locator": {"section": s_idx, "row": r_idx, "col": c_idx},
                            })

                    if col_count == 0:
                        col_count = 1
                    if row_count == 0:
                        row_count = 1

                    tbl_info = {
                        "block_id": t_block_id,
                        "kind": "table",
                        "row_count": row_count,
                        "column_count": col_count,
                        "cells": cells_data,
                        "page_spans": [s_idx + 1],
                        "locator": {"section": s_idx, "table_index": len(tables)},
                    }
                    tables.append(tbl_info)
                    blocks.append({
                        "block_id": t_block_id,
                        "kind": "table",
                        "table": tbl_info,
                        "locator": tbl_info["locator"],
                    })

                # 2. Paragraph parsing (<hp:p>)
                elif tag == "p":
                    # Extract text directly inside paragraph (outside tables)
                    # Check if inside tbl
                    p_texts = []
                    for t in elem.findall(".//{*}t"):
                        if t.text:
                            p_texts.append(t.text)
                    if not p_texts:
                        for child in elem.iter():
                            if _local_tag(child) == "t" and child.text:
                                p_texts.append(child.text)

                    p_str = "".join(p_texts).strip()
                    if p_str:
                        block_counter += 1
                        b_id = f"sec{s_idx}_p{block_counter}"
                        blocks.append({
                            "block_id": b_id,
                            "kind": "text",
                            "text": p_str,
                            "locator": {"section": s_idx, "p_index": block_counter},
                        })
                        full_text_parts.append(p_str)

                # 3. Footnote parsing (<hp:footnote>)
                elif tag in ("footnote", "fn"):
                    block_counter += 1
                    fn_id = f"sec{s_idx}_fn{len(footnotes)+1}"
                    fn_texts = [t.text for t in elem.iter() if _local_tag(t) == "t" and t.text]
                    fn_text = " ".join(fn_texts).strip()
                    last_block_id = blocks[-1]["block_id"] if blocks else f"sec{s_idx}_p1"

                    fn_info = {
                        "footnote_id": fn_id,
                        "text": fn_text or "각주 내용 없음",
                        "locator": {"section": s_idx, "footnote_index": len(footnotes) + 1},
                        "anchor_refs": [last_block_id],
                    }
                    footnotes.append(fn_info)
                    blocks.append({
                        "block_id": fn_id,
                        "kind": "footnote",
                        "footnote": fn_info,
                        "locator": fn_info["locator"],
                    })

    return {
        "format": "HWPX",
        "full_text": "\n".join(full_text_parts),
        "blocks": blocks,
        "tables": tables,
        "footnotes": footnotes,
        "warnings": warnings,
    }


def parse_docx(raw_bytes: bytes) -> Dict[str, Any]:
    """DOCX 문서에서 본문, 표(병합/좌표), 각주를 파싱한다."""
    _check_input(raw_bytes)
    if not zipfile.is_zipfile(io.BytesIO(raw_bytes)):
        raise ParserError("유효한 DOCX (ZIP) 파일이 아닙니다.")

    blocks: List[Dict[str, Any]] = []
    tables: List[Dict[str, Any]] = []
    footnotes: List[Dict[str, Any]] = []
    full_text_parts: List[str] = []
    warnings: List[str] = []

    block_counter = 0

    with zipfile.ZipFile(io.BytesIO(raw_bytes)) as z:
        _check_zip(z)
        if "word/document.xml" not in z.namelist():
            raise ParserError("word/document.xml이 누락된 비정상 DOCX 문서입니다.")

        root = _read_xml(z, "word/document.xml")
        if _local_tag(root) != "document":
            raise ParserError("Invalid DOCX document.")

        # 1. Parse footnotes.xml if present
        if "word/footnotes.xml" in z.namelist():
            try:
                fn_root = _read_xml(z, "word/footnotes.xml")
                for fn_elem in fn_root.iter():
                    if _local_tag(fn_elem) == "footnote":
                        fn_num = fn_elem.attrib.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}id") or fn_elem.attrib.get("id") or "1"
                        if int(fn_num) > 0:
                            fn_texts = [t.text for t in fn_elem.iter() if _local_tag(t) == "t" and t.text]
                            if fn_texts:
                                footnotes.append({
                                    "footnote_id": f"fn_{fn_num}",
                                    "text": "".join(fn_texts).strip(),
                                    "locator": {"footnote_num": fn_num},
                                    "anchor_refs": [],
                                })
            except (ParserError, ET.ParseError, UnicodeError, ValueError):
                raise ParserError("Invalid DOCX footnotes.") from None

        # 2. Iterate elements in body
        body = root.find(".//{*}body")
        if body is None:
            body = root

        for elem in body:
            tag = _local_tag(elem)

            if tag == "p":
                # Paragraph
                p_texts = [t.text for t in elem.iter() if _local_tag(t) == "t" and t.text]
                p_str = "".join(p_texts).strip()
                if p_str:
                    block_counter += 1
                    b_id = f"p_{block_counter}"
                    blocks.append({
                        "block_id": b_id,
                        "kind": "text",
                        "text": p_str,
                        "locator": {"p_index": block_counter},
                    })
                    full_text_parts.append(p_str)

                    # Check for footnoteReference
                    for fn_ref in elem.iter():
                        if _local_tag(fn_ref) == "footnoteReference":
                            ref_id = fn_ref.attrib.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}id") or fn_ref.attrib.get("id")
                            if ref_id:
                                for fn in footnotes:
                                    if fn["footnote_id"] == f"fn_{ref_id}":
                                        fn["anchor_refs"].append(b_id)

            elif tag == "tbl":
                # Table
                block_counter += 1
                t_block_id = f"tbl_{len(tables)+1}"

                rows = [r for r in elem if _local_tag(r) == "tr"]
                row_count = len(rows)
                col_count = 0
                cells_data: List[Dict[str, Any]] = []

                for r_idx, r_elem in enumerate(rows):
                    cells = [c for c in r_elem if _local_tag(c) == "tc"]
                    if len(cells) > col_count:
                        col_count = len(cells)

                    for c_idx, c_elem in enumerate(cells):
                        colspan = 1
                        rowspan = 1
                        # check tcPr
                        tc_pr = c_elem.find(".//{*}tcPr")
                        if tc_pr is not None:
                            grid_span = tc_pr.find(".//{*}gridSpan")
                            if grid_span is not None:
                                colspan = int(grid_span.attrib.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val") or grid_span.attrib.get("val") or 1)

                        c_texts = [t.text for t in c_elem.iter() if _local_tag(t) == "t" and t.text]
                        c_str = "".join(c_texts).strip()

                        cell_id = f"{t_block_id}_c{r_idx}_{c_idx}"
                        header_refs = [f"{t_block_id}_c0_{c_idx}"] if r_idx > 0 else []

                        cells_data.append({
                            "cell_id": cell_id,
                            "row_index": r_idx,
                            "column_index": c_idx,
                            "rowspan": max(rowspan, 1),
                            "colspan": max(colspan, 1),
                            "header_refs": header_refs,
                            "text": c_str,
                            "locator": {"row": r_idx, "col": c_idx},
                        })

                if col_count == 0:
                    col_count = 1
                if row_count == 0:
                    row_count = 1

                tbl_info = {
                    "block_id": t_block_id,
                    "kind": "table",
                    "row_count": row_count,
                    "column_count": col_count,
                    "cells": cells_data,
                    "page_spans": [1],
                    "locator": {"table_index": len(tables)},
                }
                tables.append(tbl_info)
                blocks.append({
                    "block_id": t_block_id,
                    "kind": "table",
                    "table": tbl_info,
                    "locator": tbl_info["locator"],
                })

    return {
        "format": "DOCX",
        "full_text": "\n".join(full_text_parts),
        "blocks": blocks,
        "tables": tables,
        "footnotes": footnotes,
        "warnings": warnings,
    }


def parse_plain(raw_bytes: bytes) -> Dict[str, Any]:
    """일반 텍스트/마크다운 문서를 파싱한다."""
    _check_input(raw_bytes)
    try:
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = raw_bytes.decode("cp949")
        except UnicodeDecodeError:
            raise ParserError("Unsupported text encoding.") from None

    if any(ord(c) < 32 and c not in "\\n\\r\\t" for c in text):
        raise ParserError("Invalid text document.")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines or len(lines) > MAX_OUTPUT_BLOCKS:
        raise ParserError("Empty or excessive text blocks.")
    blocks = []
    for idx, ln in enumerate(lines):
        blocks.append({
            "block_id": f"line_{idx+1}",
            "kind": "text",
            "text": ln,
            "locator": {"line": idx + 1},
        })

    return {
        "format": "PLAIN",
        "full_text": text,
        "blocks": blocks,
        "tables": [],
        "footnotes": [],
        "warnings": [],
    }


def parse_document_bytes(file_name: str, raw_bytes: bytes) -> Dict[str, Any]:
    """확장자 및 매직 바이트에 따라 적합한 파서를 호출한다."""
    ext = file_name.lower().split(".")[-1] if "." in file_name else ""

    _check_input(raw_bytes)
    try:
        if ext == "hwpx":
            result = parse_hwpx(raw_bytes)
        elif ext == "docx":
            result = parse_docx(raw_bytes)
        elif ext in ("txt", "md") and not raw_bytes.startswith((b"PK", b"%PDF-")):
            result = parse_plain(raw_bytes)
        else:
            raise ParserError("Unsupported document format.")
    except (ET.ParseError, UnicodeError, zipfile.BadZipFile, RuntimeError, ValueError, OSError) as exc:
        if isinstance(exc, ParserError):
            raise
        raise ParserError("Invalid document content.") from None
    if not result["blocks"] or len(result["blocks"]) > MAX_OUTPUT_BLOCKS:
        raise ParserError("Empty or excessive document blocks.")
    if sum(len(t["cells"]) for t in result["tables"]) > MAX_OUTPUT_BLOCKS:
        raise ParserError("Excessive document table cells.")
    return result
