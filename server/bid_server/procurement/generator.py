"""A29 제안서 문서 생성 어댑터 (HWPX 및 DOCX).

목적: 확정된 ProposalRevision과 해당 절(ProposalSection) 데이터를 바탕으로
      공식 조달 규격에 부합하는 HWPX(OWPML) 및 DOCX 문서를 순수 Python으로 패키징한다.
관련: docs/server-migration/19-automation-and-provider-contract.md §102, 20-acceptance-and-open-decisions.md (A29).
"""
import io
import hashlib
import zipfile
from xml.sax.saxutils import escape
from typing import Tuple, List, Dict, Any


def build_hwpx_bytes(title: str, sections: List[Dict[str, str]], notice_info: Dict[str, Any]) -> bytes:
    """OWPML 규격에 부합하는 HWPX 패키지 바이트를 생성한다."""
    buf = io.BytesIO()

    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        # 1. mimetype (MUST be first and uncompressed)
        mimetype_info = zipfile.ZipInfo("mimetype")
        mimetype_info.compress_type = zipfile.ZIP_STORED
        z.writestr(mimetype_info, b"application/hwp+zip")

        # 2. META-INF/container.xml
        container_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<ocf:container xmlns:ocf="urn:oasis:names:tc:opendocument:xmlns:container">
  <ocf:rootfiles>
    <ocf:rootfile ocf:full-path="Contents/content.hpf" ocf:media-type="application/hwp+zip"/>
  </ocf:rootfiles>
</ocf:container>"""
        z.writestr("META-INF/container.xml", container_xml.encode("utf-8"))

        # 3. Contents/content.hpf
        content_hpf = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<package xmlns="http://www.hancom.co.kr/hwpml/2011/content" unique-identifier="uid">
  <metadata>
    <title>{escape(title)}</title>
    <creator>PublicBidAgent</creator>
  </metadata>
  <manifest>
    <item id="sec0" href="section0.xml" media-type="application/xml"/>
  </manifest>
  <spine>
    <itemref idref="sec0"/>
  </spine>
</package>"""
        z.writestr("Contents/content.hpf", content_hpf.encode("utf-8"))

        # 4. Contents/section0.xml
        sec_paras = []
        # Title paragraph
        sec_paras.append(f"""    <hp:p id="0">
      <hp:run>
        <hp:secPr/>
        <hp:t>{escape(title)}</hp:t>
      </hp:run>
    </hp:p>""")

        # Metadata info
        buyer = notice_info.get("buyer", "공공 발주기관")
        n_no = notice_info.get("notice_number", "")
        sec_paras.append(f"""    <hp:p id="1">
      <hp:run>
        <hp:t>[공고번호: {escape(n_no)}] 발주기관: {escape(buyer)}</hp:t>
      </hp:run>
    </hp:p>""")
        sec_paras.append("""    <hp:p id="2"><hp:run><hp:t>====================================================</hp:t></hp:run></hp:p>""")

        p_idx = 3
        for sec in sections:
            sec_title = f"{sec.get('ordinal', 1)}. {sec.get('title', '제안 절')}"
            sec_paras.append(f"""    <hp:p id="{p_idx}">
      <hp:run>
        <hp:t>{escape(sec_title)}</hp:t>
      </hp:run>
    </hp:p>""")
            p_idx += 1

            body_lines = (sec.get("body") or "").splitlines()
            for line in body_lines:
                if not line.strip():
                    continue
                sec_paras.append(f"""    <hp:p id="{p_idx}">
      <hp:run>
        <hp:t>{escape(line.strip())}</hp:t>
      </hp:run>
    </hp:p>""")
                p_idx += 1

        section0_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<hp:sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">
{chr(10).join(sec_paras)}
</hp:sec>"""
        z.writestr("Contents/section0.xml", section0_xml.encode("utf-8"))

    return buf.getvalue()


def build_docx_bytes(title: str, sections: List[Dict[str, str]], notice_info: Dict[str, Any]) -> bytes:
    """Office Open XML 규격에 부합하는 DOCX 패키지 바이트를 생성한다."""
    buf = io.BytesIO()

    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        # 1. [Content_Types].xml
        content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""
        z.writestr("[Content_Types].xml", content_types.encode("utf-8"))

        # 2. _rels/.rels
        rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
        z.writestr("_rels/.rels", rels.encode("utf-8"))

        # 3. word/document.xml
        w_paras = []
        # Title
        w_paras.append(f"""    <w:p>
      <w:pPr><w:pStyle w:val="Title"/><w:jc w:val="center"/></w:pPr>
      <w:r><w:rPr><w:b/><w:sz w:val="48"/></w:rPr><w:t>{escape(title)}</w:t></w:r>
    </w:p>""")

        buyer = notice_info.get("buyer", "공공 발주기관")
        n_no = notice_info.get("notice_number", "")
        w_paras.append(f"""    <w:p>
      <w:pPr><w:jc w:val="center"/></w:pPr>
      <w:r><w:rPr><w:color w:val="555555"/><w:sz w:val="24"/></w:rPr><w:t>[공고번호: {escape(n_no)}] 발주기관: {escape(buyer)}</w:t></w:r>
    </w:p>""")

        for sec in sections:
            sec_title = f"{sec.get('ordinal', 1)}. {sec.get('title', '제안 절')}"
            w_paras.append(f"""    <w:p>
      <w:pPr><w:pStyle w:val="Heading1"/></w:pPr>
      <w:r><w:rPr><w:b/><w:sz w:val="32"/></w:rPr><w:t>{escape(sec_title)}</w:t></w:r>
    </w:p>""")

            body_lines = (sec.get("body") or "").splitlines()
            for line in body_lines:
                if not line.strip():
                    continue
                w_paras.append(f"""    <w:p>
      <w:r><w:sz w:val="22"/><w:t>{escape(line.strip())}</w:t></w:r>
    </w:p>""")

        doc_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
{chr(10).join(w_paras)}
  </w:body>
</w:document>"""
        z.writestr("word/document.xml", doc_xml.encode("utf-8"))

    return buf.getvalue()


class ProposalExportService:
    @staticmethod
    def export_proposal_revision(revision, target_format: str) -> Tuple[bytes, str, str, int]:
        """ProposalRevision을 HWPX 또는 DOCX 바이트로 빌드하고 (bytes, filename, sha256, size)를 반환한다."""
        fmt = target_format.strip().lower()
        if fmt not in ("hwpx", "docx"):
            raise ValueError(f"지원하지 않는 제안서 출력 서식입니다: {target_format} (지원: hwpx, docx)")

        notice = revision.proposal.notice
        current_nv = revision.notice_version
        notice_info = {
            "notice_number": notice.notice_number,
            "buyer": current_nv.buyer if current_nv else "공공 발주처",
            "title": current_nv.title if current_nv else revision.title,
        }

        sections_qs = revision.sections.all().order_by("ordinal")
        sections_data = [
            {"ordinal": s.ordinal, "title": s.title, "body": s.body}
            for s in sections_qs
        ]

        if not sections_data:
            raise ValueError("Proposal revision has no sections.")

        safe_title = revision.title or "제안서_초안"
        safe_name = "".join(c for c in safe_title if c.isalnum() or c in (" ", "_", "-")).strip()[:80] or "proposal"

        if fmt == "hwpx":
            raw_bytes = build_hwpx_bytes(revision.title, sections_data, notice_info)
            file_name = f"{safe_name}_v{revision.seq}.hwpx"
        else:
            raw_bytes = build_docx_bytes(revision.title, sections_data, notice_info)
            file_name = f"{safe_name}_v{revision.seq}.docx"

        sha256_hash = hashlib.sha256(raw_bytes).hexdigest()
        size_bytes = len(raw_bytes)

        return raw_bytes, file_name, sha256_hash, size_bytes
