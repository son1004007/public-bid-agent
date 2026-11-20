"""AGW-05 official capture: synthetic HTTP fixtures only, no real G2B or paid calls."""
import io
import json
import os
import tempfile
from pathlib import Path
import unittest
import zipfile

from ai_gateway_core.official_g2b_capture import CaptureError, capture, persist

NUMBER = "R26BK00000001"
REV = "1"
URL = ("https://www.g2b.go.kr/pn/pnp/pnpe/UntyAtchFile/downloadFile.do?"
       "bidPbancNo=R26BK00000001&bidPbancOrd=001&fileSeq=1&prcmBsneSeCd=05&fileType=")


def doc_bytes():
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("Contents/section0.xml", "<sec><p><t>TEST ONLY</t></p></sec>")
    return out.getvalue()


def notice_bytes(no=NUMBER, rev=REV, title="TEST ONLY"):
    return json.dumps({"response": {"header": {"resultCode": "00"}, "body": {
        "items": {"item": [{"bidNtceNo": no, "bidNtceOrd": rev, "bidNtceNm": title}]}
    }}}).encode()


class FakeResponse:
    status = 200
    def __init__(self, url, raw, encoding="identity"):
        self.url = url
        self.stream = io.BytesIO(raw)
        self.headers = {"Content-Encoding": encoding}
    def geturl(self):
        return self.url
    def read(self, count):
        return self.stream.read(count)
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass


class FakeOpener:
    def __init__(self, notice=None, document=None, encoding="identity"):
        self.notice = notice_bytes() if notice is None else notice
        self.document = doc_bytes() if document is None else document
        self.encoding = encoding
        self.calls = []
    def open(self, req, timeout=0):
        self.calls.append(req.full_url)
        raw = self.notice if "apis.data.go.kr" in req.full_url else self.document
        return FakeResponse(req.full_url, raw, self.encoding)


class OfficialG2BCaptureTests(unittest.TestCase):
    def run_capture(self, **updates):
        params = {
            "notice_number": NUMBER, "source_revision": REV,
            "attachment_url": URL, "attachment_name": "test.hwpx",
            "service_key": "synthetic-key-not-real", "opener": FakeOpener(),
        }
        params.update(updates)
        return capture(**params)

    def test_raw_sha_and_no_key_in_summary(self):
        opener = FakeOpener()
        captured = self.run_capture(opener=opener)
        self.assertEqual(captured.summary()["status"], "UNATTESTED_RAW_CAPTURE")
        self.assertEqual(len(captured.summary()["notice_sha256"]), 64)
        self.assertEqual(len(opener.calls), 2)
        self.assertNotIn("synthetic-key-not-real", json.dumps(captured.summary()))

    def test_identity_mismatch_and_duplicate_json_are_rejected(self):
        bad = [
            notice_bytes(no="R26BK99999999"), notice_bytes(rev="3"),
            notice_bytes(title=" "),
            b'{"response":{"header":{},"header":{},"body":{}}}',
            b"<html>not JSON</html>",
        ]
        for payload in bad:
            with self.subTest(payload=payload[:30]):
                opener = FakeOpener(notice=payload)
                with self.assertRaises(CaptureError):
                    self.run_capture(opener=opener)
                self.assertEqual(len(opener.calls), 1)

    def test_attachment_identity_host_and_secret_params(self):
        invalid = [
            URL.replace("www.g2b.go.kr", "www.g2b.go.kr.evil.invalid"),
            URL.replace("fileSeq=1", "fileSeq=0"),
            URL.replace("bidPbancOrd=001", "bidPbancOrd=002"),
            URL + "&serviceKey=secret",
            URL.replace("https:", "http:"),
        ]
        for url in invalid:
            with self.subTest(url=url):
                opener = FakeOpener()
                with self.assertRaisesRegex(CaptureError, "ATTACHMENT_URL_DENIED"):
                    self.run_capture(attachment_url=url, opener=opener)
                self.assertFalse(opener.calls)
        with self.assertRaisesRegex(CaptureError, "MISSING_SERVICE_KEY"):
            self.run_capture(service_key="")

    def test_malformed_zip_and_content_encoding(self):
        with self.assertRaisesRegex(CaptureError, "INVALID_HWPX_ARCHIVE"):
            self.run_capture(opener=FakeOpener(document=b"PK bad"))
        with self.assertRaisesRegex(CaptureError, "ENCODING_DENIED"):
            self.run_capture(opener=FakeOpener(encoding="gzip"))

    @unittest.skipIf(os.name == 'nt', 'POSIX private raw storage has no Windows ACL implementation')
    def test_persistence_replay_and_tamper_detection(self):
        captured = self.run_capture()
        with tempfile.TemporaryDirectory() as private:
            first = persist(captured, private)
            self.assertEqual(first, persist(captured, private))
            manifest = Path(private, first["manifest_key"])
            details = json.loads(manifest.read_text())
            self.assertEqual(details["attestation_state"], "UNREVIEWED")
            self.assertNotIn("synthetic-key-not-real", manifest.read_text())
            document = Path(private, details["document_storage_key"])
            document.write_bytes(b"X" * len(captured.raw_document))
            with self.assertRaisesRegex(CaptureError, "STORAGE_CONFLICT"):
                persist(captured, private)

    def test_refuse_relative_root_and_repo_storage(self):
        expected = 'STORAGE_PLATFORM_UNVERIFIED' if os.name == 'nt' else 'STORAGE_ROOT_DENIED'
        with self.assertRaisesRegex(CaptureError, expected):
            persist(self.run_capture(), "relative/untrusted")
        with self.assertRaisesRegex(CaptureError, expected):
            persist(self.run_capture(), Path(__file__).resolve().parents[2])


if __name__ == "__main__":
    unittest.main()
