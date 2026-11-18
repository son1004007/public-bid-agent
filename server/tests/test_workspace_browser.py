"""Opt-in real Chrome + loopback Django HTTP acceptance using only synthetic data.

No new Python dependencies, private configuration, real account or database.
ChromeDriver is provided by the GitHub-hosted Ubuntu test image.
"""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
from datetime import timedelta
from unittest import skipUnless
from urllib.request import Request, build_opener, ProxyHandler

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import LiveServerTestCase, override_settings
from django.utils import timezone
from bid_server.procurement.models import Notice, NoticeVersion, DeadlineStatus


@skipUnless(os.environ.get("BID_WORKSPACE_BROWSER") == "1", "Explicit synthetic browser test required")
@override_settings(SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class WorkspaceBrowserTest(LiveServerTestCase):
    host = "127.0.0.1"

    @classmethod
    def setUpClass(cls):
        # LiveServerTestCase wraps the app in static/media WSGI handlers.
        # Use isolated empty roots, never the working directory or private files.
        root = Path(cls.enterClassContext(tempfile.TemporaryDirectory()))
        static_root = root / "static"
        media_root = root / "media"
        static_root.mkdir()
        media_root.mkdir()
        cls.enterClassContext(override_settings(
            STATIC_URL="/__test_static__/", MEDIA_URL="/__test_media__/",
            STATIC_ROOT=str(static_root), MEDIA_ROOT=str(media_root),
        ))
        super().setUpClass()

    def test_password_change_reload_and_notice_then_logout(self):
        self.assertEqual(os.environ.get("DJANGO_SETTINGS_MODULE"), "bid_server.settings.test")
        self.assertEqual(settings.DATABASES["default"]["ENGINE"], "django.db.backends.sqlite3")
        username = "browser-synthetic"
        old_password = "Synthetic!Initial39Blue"
        new_password = "Changed!Independent74Green"
        get_user_model().objects.create_user(username=username, password=old_password)
        title = '<img src=x onerror="alert(1)"> Synthetic notice'
        notice = Notice.objects.create(source="SYNTHETIC_FIXTURE", notice_number="BROWSER-001")
        version = NoticeVersion.objects.create(
            notice=notice, version_seq=1, observed_at=timezone.now(), title=title,
            buyer="Synthetic buyer", deadline_at=timezone.now() + timedelta(days=5),
            deadline_status=DeadlineStatus.PARSED, budget_amount=300000000,
            department_categories=["AI"], source_payload_digest="fixture",
        )
        notice.current_version = version
        notice.save()

        opener = build_opener(ProxyHandler({}))
        # Preflight HTTP before browser navigation.
        with opener.open(self.live_server_url + "/workspace", timeout=10) as page:
            self.assertEqual(page.status, 200)
            self.assertIn(b'id="loginForm"', page.read())
            self.assertIn("script-src-attr 'none'", page.headers["Content-Security-Policy"])
        from urllib.error import HTTPError
        for prefix in ("__test_static__", "__test_media__"):
            with self.assertRaises(HTTPError) as denied:
                opener.open(self.live_server_url + "/" + prefix + "/manage.py", timeout=5)
            self.assertEqual(denied.exception.code, 404)

        chrome = shutil.which("google-chrome") or shutil.which("chromium")
        self.assertTrue(chrome, "Installed Chrome binary is required")
        print(subprocess.check_output([chrome, "--version"], text=True, timeout=10).strip(), flush=True)

        driver = shutil.which("chromedriver")
        if not driver:
            candidate = Path(os.environ.get("CHROMEWEBDRIVER", "/nonexistent")) / "chromedriver"
            if candidate.is_file():
                driver = str(candidate)
        self.assertTrue(driver, "ChromeDriver is required for the browser gate")
        print(subprocess.check_output([driver, "--version"], text=True, timeout=10).strip(), flush=True)
        profile = self.enterContext(tempfile.TemporaryDirectory())
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        proc = subprocess.Popen(
            [driver, f"--port={port}", "--allowed-ips=127.0.0.1"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

        def close_process():
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)

        self.addCleanup(close_process)
        endpoint = f"http://127.0.0.1:{port}"
        def call(method, path, body=None, timeout=25):
            req = Request(endpoint + path, method=method,
                          data=None if body is None else json.dumps(body).encode(),
                          headers={"Content-Type": "application/json"})
            with opener.open(req, timeout=timeout) as response:
                return json.load(response)["value"]

        end = time.monotonic() + 10
        while True:
            try:
                if call("GET", "/status").get("ready"):
                    break
            except OSError:
                pass
            if proc.poll() is not None or time.monotonic() >= end:
                self.fail("ChromeDriver did not start")
            time.sleep(0.1)

        session = call("POST", "/session", {"capabilities": {"alwaysMatch": {
            "browserName": "chrome",
            "goog:chromeOptions": {"binary": chrome, "args": [
                "--user-data-dir=" + profile,
                "--headless", "--disable-background-networking", "--disable-sync",
                "--no-first-run", "--window-size=1280,900",
            ]},
            "timeouts": {"pageLoad": 15000, "script": 10000, "implicit": 0},
        }}}, timeout=65)
        base = "/session/" + session["sessionId"]

        def stop_browser():
            try:
                call("DELETE", base)
            except OSError:
                pass

        self.addCleanup(stop_browser)

        def js(script, *args):
            return call("POST", base + "/execute/sync", {"script": script, "args": list(args)})

        def wait_for(script, label):
            until = time.monotonic() + 12
            while time.monotonic() < until:
                if js("return Boolean(" + script + ");"):
                    return
                time.sleep(0.1)
            self.fail(label)

        def visible(element):
            return f"document.getElementById('{element}') && !document.getElementById('{element}').hidden"

        def fill(element, value):
            js("document.getElementById(arguments[0]).value=arguments[1];", element, value)

        def submit(form):
            js("document.querySelector('#' + arguments[0] + ' button[type=submit]').click();", form)

        def login(password):
            wait_for(visible("loginForm"), "Login form not available")
            fill("username", username)
            fill("password", password)
            submit("loginForm")

        call("POST", base + "/url", {"url": self.live_server_url + "/workspace"})
        login(old_password)
        wait_for(visible("passwordForm"), "First password change not requested")
        self.assertTrue(js("return document.getElementById('businessContent').hidden"))
        call("POST", base + "/refresh", {})
        wait_for(visible("passwordForm"), "Limited session could not reload workspace")
        self.assertTrue(js("return document.getElementById('businessContent').hidden"))
        fill("currentPassword", old_password)
        fill("newPassword", new_password)
        submit("passwordForm")
        login(new_password)
        wait_for(visible("businessContent"), "Full session not available")
        wait_for("document.querySelector('[data-notice-id]')", "Notice list not rendered")
        self.assertEqual(js("return document.querySelector('.notice-title-btn').textContent"), title)
        self.assertEqual(js("return document.querySelectorAll('#noticeTableBody img').length"), 0)
        js("document.querySelector('.notice-title-btn').click()")
        wait_for("document.querySelector('#dTitle').textContent === " + json.dumps(title), "Notice detail unavailable")
        js("document.getElementById('logoutBtn').click()")
        wait_for("document.getElementById('authStatus').textContent === '로그아웃되었습니다.'",
                 "Logout did not complete")
        wait_for(visible("loginForm"), "Logout did not restore login form")
        call("POST", base + "/refresh", {})
        wait_for(visible("loginForm"), "Logged-out session was not cleared on reload")
        self.assertTrue(js("return document.getElementById('businessContent').hidden"))
        self.assertEqual(js("return document.getElementById('noticeTableBody').textContent"), "")
