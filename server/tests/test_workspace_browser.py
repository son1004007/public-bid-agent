"""Opt-in real Chrome + loopback Django HTTP acceptance using only synthetic data.

No new Python dependencies, private configuration, real account or database.
ChromeDriver is provided by the hosted runner or an explicitly selected local binary.
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
from decimal import Decimal
import hashlib
from unittest import skipUnless
from urllib.request import Request, build_opener, ProxyHandler

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import LiveServerTestCase, override_settings
from django.utils import timezone
from bid_server.procurement.models import (Notice, NoticeVersion, DeadlineStatus, Document, DocumentVersion,
    CostDepartment, CostMembership, DepartmentCostBasis, DocumentFreshness, SharedBidReviewEvent)
from bid_server.procurement.extractor_service import ExtractionService


@skipUnless(os.environ.get("BID_WORKSPACE_BROWSER") == "1", "Explicit synthetic browser test required")
@override_settings(SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class WorkspaceBrowserTest(LiveServerTestCase):
    host = "127.0.0.1"

    @classmethod
    def setUpClass(cls):
        if (os.environ.get("DJANGO_SETTINGS_MODULE") != "bid_server.settings.test"
                or settings.DATABASES["default"]["ENGINE"] != "django.db.backends.sqlite3"):
            raise RuntimeError("Synthetic SQLite settings required")
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
        user = get_user_model().objects.create_user(username=username, password=old_password)
        department = CostDepartment.objects.create(active=True)
        CostMembership.objects.create(department=department,user=user,active=True,can_manage_cost=True,can_decide=True)
        today = timezone.localdate()
        DepartmentCostBasis.objects.create(department=department, revision=1,
            period_start=today-timedelta(days=1),period_end=today+timedelta(days=30),valid_until=today+timedelta(days=10),
            labor_total_krw=60100000,allocation_mm=Decimal('12'),available_mm=Decimal('8.75'),headcount=12,
            minimum_headcount=10,rate_rounding_krw=1000000,capacity_rounding_mm=2,approved_by=user,approved=True,current=True)
        title = '<img src=x onerror="alert(1)"> Synthetic notice'
        notice = Notice.objects.create(source="G2B_OFFICIAL_API", notice_number="BROWSER-001")
        version = NoticeVersion.objects.create(
            notice=notice, version_seq=1, observed_at=timezone.now(), title=title,
            buyer="Synthetic buyer", deadline_at=timezone.now() + timedelta(days=5),
            deadline_status=DeadlineStatus.PARSED, budget_amount=300000000,
            department_categories=["AI"], source_payload_digest="fixture", source_url="https://g2b.go.kr/synthetic-browser-notice",
        )
        notice.current_version = version
        notice.save()
        raw = "입찰 참가자격 확인\nJava 기반 시스템 구축\n투입 인력 5 M/M".encode("utf-8")
        doc = Document.objects.create(notice=notice, logical_key="Synthetic RFP")
        dv = DocumentVersion.objects.create(document=doc,notice_version=version,version_seq=1,
            owner_user=user,sha256=hashlib.sha256(raw).hexdigest(),size_bytes=len(raw),media_type="text/plain",
            freshness=DocumentFreshness.CURRENT,source_url="https://g2b.go.kr/synthetic-browser-rfp")
        ExtractionService.extract_and_persist(dv,raw)

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

        chrome = os.environ.get("BID_CHROME_BINARY")
        if not chrome and os.name == "nt":
            candidate = Path(os.environ.get("ProgramFiles", "")) / "Google/Chrome/Application/chrome.exe"
            chrome = str(candidate) if candidate.is_absolute() and candidate.is_file() else None
        elif not chrome:
            chrome = shutil.which("google-chrome") or shutil.which("chromium")
        self.assertTrue(chrome and Path(chrome).is_absolute() and Path(chrome).is_file(),
                        "Installed Chrome binary is required")
        # Windows Chrome can open a window instead of returning --version.
        if os.name != "nt":
            print(subprocess.check_output([chrome, "--version"], text=True, timeout=10).strip(), flush=True)

        if os.environ.get("BID_WORKSPACE_CDP") == "1":
            node = shutil.which("node")
            self.assertTrue(node and Path(node).is_absolute(), "Installed Node.js 22+ required")
            runner = Path(__file__).resolve().parents[2] / "scripts" / "test_workspace_cdp.cjs"
            subprocess.run([node, str(runner), chrome, self.live_server_url], check=True, timeout=150)
            self.assertEqual(list(SharedBidReviewEvent.objects.order_by('revision').values_list('kind',flat=True)), ['ESTIMATE','OPINION','DECISION'])
            self.assertEqual(SharedBidReviewEvent.objects.get(kind='DECISION').payload['decision'],'BID')
            return

        driver = os.environ.get("BID_CHROMEDRIVER_BINARY") or shutil.which("chromedriver")
        if not driver:
            name = "chromedriver.exe" if os.name == "nt" else "chromedriver"
            directory = os.environ.get("CHROMEWEBDRIVER")
            if directory:
                candidate = Path(directory) / name
                if candidate.is_absolute() and candidate.is_file():
                    driver = str(candidate)
        self.assertTrue(driver and Path(driver).is_absolute() and Path(driver).is_file(),
                        "Compatible installed ChromeDriver is required for the browser gate")
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
        print("Chrome session version: " + str(session.get("capabilities", {}).get("browserVersion", "unreported")), flush=True)

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
        wait_for("document.querySelector('#dShared button') && document.querySelector('#dCost form')", "Detail business panels unavailable")
        self.assertIn('Java 기반 시스템 구축', js("return document.getElementById('dReview').textContent"))
        js("document.getElementById('logoutBtn').click()")
        wait_for("document.getElementById('authStatus').textContent === '로그아웃되었습니다.'",
                 "Logout did not complete")
        wait_for(visible("loginForm"), "Logout did not restore login form")
        call("POST", base + "/refresh", {})
        wait_for(visible("loginForm"), "Logged-out session was not cleared on reload")
        self.assertTrue(js("return document.getElementById('businessContent').hidden"))
        self.assertEqual(js("return document.getElementById('noticeTableBody').textContent"), "")
