"""AGW-05 official capture: synthetic HTTP fixtures only, no real G2B or paid calls."""
import io
import contextlib
import importlib.util
from unittest import mock
import json
import os
import tempfile
from pathlib import Path
import unittest
import zipfile
from urllib.parse import parse_qs, urlsplit

from ai_gateway_core.official_g2b_capture import CaptureError, capture, persist, persist_notice_for_existing_document

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

    def test_decoded_and_percent_encoded_portal_keys_have_identical_wire_value(self):
        for key in ("synthetic/+key", "synthetic%2F%2Bkey"):
            with self.subTest(portal_format="encoded" if "%" in key else "decoded"):
                opener = FakeOpener()
                captured = self.run_capture(service_key=key, opener=opener)
                requested = parse_qs(urlsplit(opener.calls[0]).query)
                self.assertEqual(requested["serviceKey"], ["synthetic/+key"])
                self.assertEqual(captured.summary()["status"], "UNATTESTED_RAW_CAPTURE")
                self.assertNotIn(key, json.dumps(captured.summary()))

    def test_reject_broken_key_encoding_and_encoded_controls_before_network(self):
        for key in ("synthetic%ZZ", "synthetic%", "synthetic%0Akey", "synthetic%00key"):
            with self.subTest(format_only=True):
                opener = FakeOpener()
                with self.assertRaisesRegex(CaptureError, "MISSING_SERVICE_KEY"):
                    self.run_capture(service_key=key, opener=opener)
                self.assertEqual(opener.calls, [])

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

    @unittest.skipIf(os.name == 'nt', 'POSIX private storage only')
    def test_existing_document_reference_persists_only_raw_notice_and_manifest(self):
        captured = self.run_capture()
        document_key = "public-rfp/" + captured.summary()["document_sha256"] + ".hwpx"
        with tempfile.TemporaryDirectory() as private:
            first = persist_notice_for_existing_document(
                captured, private, document_storage_key=document_key,
            )
            self.assertEqual(first, persist_notice_for_existing_document(
                captured, private, document_storage_key=document_key,
            ))
            self.assertFalse(first["document_bytes_copied"])
            stored = Path(private) / "official-g2b-capture"
            files = list(stored.iterdir())
            self.assertEqual(len(files), 2)
            self.assertFalse(any(p.suffix == ".hwpx" for p in files))
            details = json.loads((Path(private) / first["manifest_key"]).read_text())
            self.assertEqual(details["document_storage_key"], document_key)
            self.assertEqual(details["document_storage_scope"], "EXISTING_PRIVATE_MEDIA")
            self.assertEqual(details["document_reference_validation"], "HASH_AND_KEY_ONLY")
            self.assertEqual(details["attestation_state"], "UNREVIEWED")
            self.assertNotIn("synthetic-key-not-real", json.dumps(details))
            self.assertTrue(all((p.stat().st_mode & 0o777) == 0o600 for p in files))
            raw_file = Path(private) / details["notice_storage_key"]
            self.assertEqual(raw_file.read_bytes(), captured.raw_notice)
            raw_file.write_bytes(b"corrupted")
            with self.assertRaisesRegex(CaptureError, "STORAGE_CONFLICT"):
                persist_notice_for_existing_document(
                    captured, private, document_storage_key=document_key,
                )

    def test_existing_document_reference_rejects_bad_storage_keys(self):
        captured = self.run_capture()
        valid_key = "public-rfp/" + captured.summary()["document_sha256"] + ".hwpx"
        invalid = ["", "../" + valid_key, valid_key.replace(".hwpx", ".pdf"),
                   valid_key.replace("public-rfp/", "outside/"),
                   "public-rfp/" + "0" * 64 + ".hwpx", True, None]
        for key in invalid:
            with self.subTest(key_type=type(key).__name__):
                with self.assertRaisesRegex(CaptureError, "EXISTING_DOCUMENT_KEY_DENIED"):
                    persist_notice_for_existing_document(
                        captured, "unused-private-root", document_storage_key=key,
                    )


    def test_cli_existing_document_mode_does_not_duplicate_hwpx(self):
        script = Path(__file__).resolve().parents[2] / "scripts" / "capture_official_g2b.py"
        spec = importlib.util.spec_from_file_location("g2b_capture_cli_test", script)
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        captured = self.run_capture()
        key = "public-rfp/" + captured.summary()["document_sha256"] + ".hwpx"
        argv = [
            "--notice-number", NUMBER, "--source-revision", REV,
            "--attachment-url", URL, "--attachment-name", "test.hwpx",
            "--private-root", "/private-unrelated-to-git", "--apply",
            "--existing-document-storage-key", key,
        ]
        result = {**captured.summary(), "document_bytes_copied": False}
        with mock.patch.object(cli, "capture", return_value=captured) as getter, \
             mock.patch.object(cli, "persist", side_effect=AssertionError("duplicates raw HWPX")) as duplicate, \
             mock.patch.object(cli, "persist_notice_for_existing_document", return_value=result) as store, \
             mock.patch.dict(os.environ, {"G2B_SERVICE_KEY": "synthetic-cli-key"}, clear=False), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(cli.main(argv), 0)
            self.assertEqual(json.loads(output.getvalue())["document_bytes_copied"], False)
            self.assertEqual(getter.call_args.kwargs["service_key"], "synthetic-cli-key")
            store.assert_called_once_with(
                captured, "/private-unrelated-to-git", document_storage_key=key,
            )
            duplicate.assert_not_called()

        with mock.patch.object(cli, "capture", side_effect=AssertionError("network called")) as getter, \
             contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(cli.main(argv[:-3] + ["--existing-document-storage-key", key]), 2)
            self.assertEqual(json.loads(errors.getvalue())["code"], "EXISTING_DOCUMENT_REQUIRES_APPLY")
            getter.assert_not_called()

    def test_refuse_relative_root_and_repo_storage(self):
        expected = 'STORAGE_PLATFORM_UNVERIFIED' if os.name == 'nt' else 'STORAGE_ROOT_DENIED'
        with self.assertRaisesRegex(CaptureError, expected):
            persist(self.run_capture(), "relative/untrusted")
        with self.assertRaisesRegex(CaptureError, expected):
            persist(self.run_capture(), Path(__file__).resolve().parents[2])


if __name__ == "__main__":
    unittest.main()
