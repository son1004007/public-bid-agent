"""로컬 나라장터 인증키 등록의 보안 경계·공식 연결 검사.

실제 발급 키를 읽거나 공공데이터포털에 요청하지 않는다. 가상 키만 사용.
"""
import json
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import server
import dashboard_backend as db
import procurement_credentials as credentials

FAKE = "FAKE-API-KEY-DO-NOT-USE-123456789"


class CredentialUnitTests(unittest.TestCase):
    def test_key_normalization_and_encoded_string(self):
        self.assertEqual(credentials.clean_key(FAKE), FAKE)
        self.assertEqual(credentials.clean_key("ABCDEFGH%2F012345678901"), "ABCDEFGH/012345678901")
        for bad in (None, "", "short", "FAKE\rKEY", "some%broken-percent-key", "x" * 601):
            with self.assertRaises(ValueError):
                credentials.clean_key(bad)

    def test_save_uses_only_opaque_encrypted_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "key.dpapi"
            def fake_dpapi(data, *, decrypt):
                if decrypt: return data.removeprefix(b"DPAPI_BINARY_TEST:")
                return b"DPAPI_BINARY_TEST:" + data
            with patch.object(credentials, "key_path", return_value=path), patch.object(
                    credentials, "_dpapi", side_effect=fake_dpapi):
                credentials.save_key(FAKE)
                self.assertTrue(path.exists())
                self.assertNotIn(FAKE.encode(), path.read_bytes()[:16])
                self.assertFalse(path.suffix == ".json")
                self.assertTrue(credentials.delete_key())
                self.assertFalse(path.exists())

    @unittest.skipUnless(os.name == "nt", "DPAPI 사용자 범위 암호화는 Windows에서 검증")
    def test_real_windows_user_dpapi_roundtrip_and_corruption(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict(os.environ, {"LOCALAPPDATA": temp}, clear=False):
                credentials.save_key(FAKE)
                path = credentials.key_path()
                self.assertNotIn(FAKE.encode(), path.read_bytes())
                self.assertEqual(credentials.active_key(), FAKE)
                self.assertEqual(credentials.status()["source"], "WINDOWS_DPAPI")
                path.write_bytes(b"corrupt")
                with self.assertRaises(credentials.CredentialError):
                    credentials.active_key()
                self.assertTrue(credentials.delete_key())

    def test_official_credential_verify_requires_body(self):
        from test_dashboard_backend import FakeTransport, response
        transport = FakeTransport([response([])])
        db.verify_key(FAKE, transport)
        self.assertIn("ServiceKey=FAKE-API-KEY-DO-NOT-USE", transport.request.full_url)
        self.assertIn("numOfRows=1", transport.request.full_url)
        for malformed in ({"response": {"header": {"resultCode": "20"}, "body": {}}},
                          {"response": {"header": {"resultCode": "00"}}}):
            with self.assertRaises(db.ProviderError):
                db.verify_key(FAKE, FakeTransport([malformed]))


class CredentialHTTPTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.patches = [
            patch.object(server, "ROOT", self.root),
            patch.object(server, "FILE", self.root / "cases.json"),
        ]
        for p in self.patches: p.start()
        server.persist({"schema_version": 1, "cases": [{"id": "existing"}]})
        self.original = (self.root / "cases.json").read_bytes()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = "http://127.0.0.1:" + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown(); self.server.server_close()
        self.thread.join(timeout=3)
        for p in reversed(self.patches): p.stop()
        self.folder.cleanup()

    def query(self, method, path, payload=None, headers=True):
        h = {"Content-Type": "application/json"}
        if headers: h.update({"Origin": self.base, "X-Local-CSRF": server.TOKEN})
        data = json.dumps(payload or {}).encode() if method == "POST" else None
        r = Request(self.base + path, data=data, headers=h, method=method)
        try:
            with urlopen(r, timeout=5) as stream:
                return stream.status, json.load(stream)
        except HTTPError as stream:
            return stream.code, json.load(stream)

    def test_public_get_contains_no_credentials(self):
        with patch.object(server, "procurement_key_status",
                          return_value={"configured": True,"can_save": True,"can_delete": True,"source":"WINDOWS_DPAPI"}):
            status, body = self.query("GET", "/api/procurement-key")
        self.assertEqual(status, 200)
        self.assertTrue(body["credential"]["configured"])
        self.assertNotIn(FAKE, json.dumps(body))

    def test_csrf_rejected_and_invalid_key_rejected(self):
        self.assertEqual(self.query("POST", "/api/procurement-key/save", {"key":FAKE}, headers=False)[0], 403)
        with patch.object(server, "procurement_key_status",
                          return_value={"can_save": True,"configured":False}):
            status, payload = self.query("POST", "/api/procurement-key/save", {"key":"short"})
            self.assertEqual(status, 400)
            self.assertNotIn("short", json.dumps(payload))

    def test_endpoints_save_verify_delete_never_echo_secret(self):
        saved = {"value":None}
        def save(v):
            credentials.clean_key(v)
            saved["value"] = v
        def key():
            return saved["value"]
        def delete():
            saved["value"] = None
        def status():
            return {"can_save":True,"can_delete":bool(saved["value"]),
                    "configured":bool(saved["value"]),"source":"WINDOWS_DPAPI" if saved["value"] else "NONE"}
        with patch.object(server, "save_procurement_key",side_effect=save), patch.object(
             server, "delete_procurement_key",side_effect=delete), patch.object(
             server, "procurement_key_status",side_effect=status), patch.object(
             server, "procurement_key",side_effect=key), patch.object(
             server, "verify_key") as verifier:
            for endpoint, payload in [
                ("save", {"key":FAKE}), ("verify", {}), ("delete", {})]:
                code, response = self.query("POST","/api/procurement-key/"+endpoint,payload)
                self.assertEqual(code, 200)
                self.assertNotIn(FAKE,json.dumps(response,ensure_ascii=False))
            verifier.assert_called_once_with(FAKE)
        self.assertEqual((self.root / "cases.json").read_bytes(),self.original)
        self.assertFalse((self.root / "dashboard.json").exists())

    def test_real_provider_failure_never_leaks_secret(self):
        with patch.object(server,"procurement_key",return_value=FAKE),patch.object(
             server,"verify_key",side_effect=db.ProviderError("NEVER LEAK "+FAKE)):
            code,data=self.query("POST","/api/procurement-key/verify")
        self.assertEqual(code,502)
        self.assertNotIn(FAKE,json.dumps(data))


if __name__ == "__main__":
    unittest.main()
