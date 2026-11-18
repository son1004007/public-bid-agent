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

        driver = shutil.which("chromedriver")
        if not driver:
            candidate = Path(os.environ.get("CHROMEWEBDRIVER", "/nonexistent")) / "chromedriver"
            if candidate.is_file():
                driver = str(candidate)
        self.assertTrue(driver, "ChromeDriver is required for the browser gate")
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
        opener = build_opener(ProxyHandler({}))

        def call(method, path, body=None):
            req = Request(endpoint + path, method=method,
                          data=None if body is None else json.dumps(body).encode(),
                          headers={"Content-Type": "application/json"})
            with opener.open(req, timeout=15) as response:
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
            "goog:chromeOptions": {"args": [
                "--headless", "--disable-background-networking", "--disable-sync",
                "--no-first-run", "--window-size=1280,900",
            ]},
            "timeouts": {"pageLoad": 15000, "script": 10000, "implicit": 0},
        }}})
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
            return f"!document.getElementById('{element}').hidden"

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
        wait_for(visible("loginForm"), "Logout did not restore login form")
        self.assertTrue(js("return document.getElementById('businessContent').hidden"))
        self.assertEqual(js("return document.getElementById('noticeTableBody').textContent"), "")
