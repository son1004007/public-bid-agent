"""Public HWPX fallback is explicitly text-only, with bounded safe XML and no duplicate nested text."""
import io,zipfile
from django.test import SimpleTestCase
from unittest.mock import patch
from bid_server.procurement.parser import parse_public_hwpx_text,parse_document_bytes,ParserError


def archive(xml):
    b=io.BytesIO()
    with zipfile.ZipFile(b,"w",compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("Contents/section0.xml",xml)
    return b.getvalue()


class PublicHwpxTextTests(SimpleTestCase):
    def test_nested_text_once(self):
        raw=archive("<sec><p><t>outer</t><tbl><tr><tc><p><t>inner</t></p></tc></tr></tbl><t>end</t></p></sec>")
        r=parse_public_hwpx_text(raw)
        self.assertEqual(r["full_text"],"outerend\ninner")
        self.assertEqual(r["tables"],[])
        self.assertTrue(r["warnings"])
        self.assertEqual([b["locator"]["p_index"] for b in r["blocks"]],[1,2])
    def test_large_realistic_shape_default_unchanged(self):
        raw=archive("<sec>"+"<p><r><t>요구사항</t></r></p>"*8000+"</sec>")
        with self.assertRaises(ParserError):
            parse_document_bytes("x.hwpx",raw)
        self.assertEqual(len(parse_public_hwpx_text(raw)["blocks"]),8000)
    def test_fail_closed(self):
        for xml in ("<!DOCTYPE sec [<!ENTITY x 'bad'>]><sec><p><t>&x;</t></p></sec>",
                    "<sec>"+"<p>"*50+"<t>a</t>"+"</p>"*50+"</sec>"):
            with self.assertRaises(ParserError):
                parse_public_hwpx_text(archive(xml))
        with patch("bid_server.procurement.parser.MAX_RFP_TEXT",3):
            with self.assertRaises(ParserError):
                parse_public_hwpx_text(archive("<sec><p><t>abcd</t></p></sec>"))
