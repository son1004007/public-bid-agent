"""Real loopback HTTP acceptance, independent of Chrome or a real DB.

Run explicitly under the synthetic settings on Linux and Windows. The ephemeral
LiveServer and private temporary static/media roots are cleaned by Django.
"""
import json
import os
import tempfile
from pathlib import Path
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.request import Request, build_opener, ProxyHandler, HTTPCookieProcessor
from unittest import skipUnless

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import LiveServerTestCase, override_settings


@skipUnless(os.environ.get("BID_WORKSPACE_HTTP") == "1", "Explicit synthetic HTTP acceptance required")
@override_settings(SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class WorkspaceHttpTest(LiveServerTestCase):
    host = "127.0.0.1"

    @classmethod
    def setUpClass(cls):
        if (os.environ.get("DJANGO_SETTINGS_MODULE") != "bid_server.settings.test"
                or settings.DATABASES["default"]["ENGINE"] != "django.db.backends.sqlite3"):
            raise RuntimeError("Synthetic SQLite settings required")
        root = Path(cls.enterClassContext(tempfile.TemporaryDirectory()))
        for name in ("static", "media"):
            (root / name).mkdir()
        cls.enterClassContext(override_settings(
            STATIC_URL="/__test_static__/", MEDIA_URL="/__test_media__/",
            STATIC_ROOT=str(root / "static"), MEDIA_ROOT=str(root / "media"),
        ))
        super().setUpClass()

    def test_http_authentication_boundary_and_workspace(self):
        username, old, new = "http-synthetic", "Synthetic!Initial39Blue", "Changed!Independent74Green"
        get_user_model().objects.create_user(username=username, password=old)
        client = build_opener(ProxyHandler({}), HTTPCookieProcessor(CookieJar()))

        def req(path, payload=None, csrf=None):
            headers = {"Accept": "application/json"}
            data = None
            if payload is not None:
                data = json.dumps(payload).encode()
                headers.update({"Content-Type": "application/json", "Origin": self.live_server_url})
                if csrf:
                    headers["X-CSRFToken"] = csrf
            try:
                with client.open(Request(self.live_server_url + path, data=data,
                                         headers=headers), timeout=8) as response:
                    return response.status, response.headers, response.read()
            except HTTPError as error:
                return error.code, error.headers, error.read()

        def token():
            code, _, body = req("/api/v1/auth/csrf")
            self.assertEqual(code, 200)
            return json.loads(body)["data"]["csrf_token"]

        def shell():
            code, headers, body = req("/workspace")
            self.assertEqual(code, 200)
            self.assertIn(b'id="loginForm"', body)
            self.assertIn("script-src-attr 'none'", headers["Content-Security-Policy"])
            self.assertEqual(headers["Cache-Control"], "no-store")

        shell()
        self.assertEqual(req("/api/v1/notices")[0], 401)
        payload = {"username": username, "password": old}
        self.assertEqual(req("/api/v1/auth/login", payload)[0], 403)
        code, _, body = req("/api/v1/auth/login", payload, token())
        self.assertEqual(code, 200)
        data = json.loads(body)["data"]
        self.assertEqual(data["access"], "PASSWORD_CHANGE_REQUIRED")
        shell()
        self.assertEqual(req("/api/v1/notices")[0], 403)
        self.assertEqual(req("/api/v1/auth/change-password", {
            "current_password": old, "new_password": new,
            "expected_auth_epoch": data["auth_epoch"],
        }, token())[0], 204)
        self.assertEqual(req("/api/v1/notices")[0], 401)
        code, _, body = req("/api/v1/auth/login", {"username": username, "password": new}, token())
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)["data"]["access"], "FULL")
        self.assertEqual(req("/api/v1/notices")[0], 200)
        self.assertEqual(req("/api/v1/auth/logout", {}, token())[0], 204)
        shell()
        self.assertEqual(req("/api/v1/notices")[0], 401)
        for prefix in ("__test_static__", "__test_media__"):
            self.assertEqual(req("/" + prefix + "/manage.py")[0], 404)
