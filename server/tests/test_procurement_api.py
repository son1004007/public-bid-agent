"""SM06 조달 공고 및 대시보드 API 엔드포인트 검증 계약.
목적: /api/v1/dashboard, /api/v1/notices, /api/v1/notices/{id}, /api/v1/notices/{id}/versions 엔드포인트의 인증, 검색, 필터링, 정렬, 페이지네이션 및 무결성을 검증한다.
관련: docs/server-migration/18-screen-api-contract.md §31-35.
"""
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from bid_server.procurement.models import (
    Notice,
    NoticeVersion,
    Document,
    DocumentVersion,
    DeadlineStatus,
)

User = get_user_model()
PASSWORD_FIXTURE = "TestSecurePassword123!@#"


class ProcurementAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="procurement-officer",
            password=PASSWORD_FIXTURE,
            must_change_password=False,
            role="lead",
        )
        self.client = APIClient(enforce_csrf_checks=True)
        # Login and obtain session
        token_res = self.client.get("/api/v1/auth/csrf", secure=True)
        self.csrf_token = token_res.json()["data"]["csrf_token"]
        login_res = self.client.post(
            "/api/v1/auth/login",
            {"username": "procurement-officer", "password": PASSWORD_FIXTURE},
            format="json",
            secure=True,
            HTTP_X_CSRFTOKEN=self.csrf_token,
            HTTP_ORIGIN="https://testserver",
        )
        self.assertEqual(login_res.status_code, status.HTTP_200_OK)

        # Create test notices
        now = timezone.now()

        # 1. AI Notice (Open, D-5)
        self.notice_ai = Notice.objects.create(
            source="G2B_OFFICIAL_API",
            notice_number="202611-AI-001",
        )
        self.nv_ai_v1 = NoticeVersion.objects.create(
            notice=self.notice_ai,
            version_seq=1,
            observed_at=now,
            title="초거대 AI 기반 지능형 민원 상담 시스템 구축",
            buyer="서울특별시",
            source_url="https://g2b.go.kr/test-ai",
            deadline_raw="2026-11-20 18:00:00",
            deadline_at=now + timedelta(days=5),
            deadline_status=DeadlineStatus.PARSED,
            cancellation=False,
            budget_amount=736000000,
            department_categories=["AI", "SW"],
            source_payload_digest="digest_ai_v1",
        )
        self.notice_ai.current_version = self.nv_ai_v1
        self.notice_ai.save()

        # Attach Document to AI Notice
        self.doc_ai = Document.objects.create(
            notice=self.notice_ai,
            logical_key="RFP",
            source_attachment_id="ATT-001",
        )
        DocumentVersion.objects.create(
            document=self.doc_ai,
            notice_version=self.nv_ai_v1,
            version_seq=1,
            shared_read_approved=True,
            sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            size_bytes=1048576,
            media_type="application/pdf",
        )

        # 2. DATA Notice (Open, Urgent D-1)
        self.notice_data = Notice.objects.create(
            source="G2B_OFFICIAL_API",
            notice_number="202611-DATA-002",
        )
        self.nv_data_v1 = NoticeVersion.objects.create(
            notice=self.notice_data,
            version_seq=1,
            observed_at=now - timedelta(hours=2),
            title="바이오 빅데이터 플랫폼 스토리지 및 분석 인프라 고도화",
            buyer="조달청",
            source_url="https://g2b.go.kr/test-data",
            deadline_raw="2026-11-16 11:00:00",
            deadline_at=now + timedelta(days=1),
            deadline_status=DeadlineStatus.PARSED,
            cancellation=False,
            budget_amount=1510000000,
            department_categories=["DATA"],
            source_payload_digest="digest_data_v1",
        )
        self.notice_data.current_version = self.nv_data_v1
        self.notice_data.save()

        # 3. SW Notice (Expired / Closed)
        self.notice_sw = Notice.objects.create(
            source="G2B_OFFICIAL_API",
            notice_number="202611-SW-003",
        )
        self.nv_sw_v1 = NoticeVersion.objects.create(
            notice=self.notice_sw,
            version_seq=1,
            observed_at=now - timedelta(days=10),
            title="기초연금 개편에 따른 전산 정보시스템 기능개선",
            buyer="보건복지부",
            deadline_raw="2026-11-10 10:00:00",
            deadline_at=now - timedelta(days=2),
            deadline_status=DeadlineStatus.EXPIRED,
            cancellation=False,
            budget_amount=400000000,
            department_categories=["SW"],
            source_payload_digest="digest_sw_v1",
        )
        self.notice_sw.current_version = self.nv_sw_v1
        self.notice_sw.save()

        # 4. Cancelled Notice
        self.notice_cancel = Notice.objects.create(
            source="G2B_OFFICIAL_API",
            notice_number="202611-CANCEL-004",
        )
        self.nv_cancel_v1 = NoticeVersion.objects.create(
            notice=self.notice_cancel,
            version_seq=1,
            observed_at=now - timedelta(days=1),
            title="하수처리시설 IoT 원격 제어 통신망 구축 [취소]",
            buyer="경상남도 거창군",
            deadline_at=now + timedelta(days=3),
            cancellation=True,
            budget_amount=80000000,
            department_categories=["SW"],
            source_payload_digest="digest_cancel_v1",
        )
        self.notice_cancel.current_version = self.nv_cancel_v1
        self.notice_cancel.save()

    def test_unauthenticated_access_is_denied(self):
        anon_client = APIClient()
        res = anon_client.get("/api/v1/notices", secure=True)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

        res_dash = anon_client.get("/api/v1/dashboard", secure=True)
        self.assertEqual(res_dash.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_dashboard_api(self):
        res = self.client.get("/api/v1/dashboard", secure=True)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        body = res.json()
        self.assertIn("data", body)
        data = body["data"]

        counts = data["counts"]
        self.assertEqual(counts["total_notices"], 4)
        self.assertEqual(counts["open_notices"], 2)  # AI and DATA
        self.assertEqual(counts["cancelled_notices"], 1)
        self.assertEqual(counts["ai_candidates"], 1)
        self.assertEqual(counts["data_candidates"], 1)
        self.assertEqual(counts["urgent_deadline_3d"], 1)  # DATA notice (D-1)
        self.assertEqual(data["collection_health"]["status"], "UNVERIFIED")
        self.assertIsNone(data["collection_health"]["source"])
        self.assertEqual(counts["major_candidates"], 2)

    def test_notice_list_all(self):
        res = self.client.get("/api/v1/notices", secure=True)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        body = res.json()
        self.assertIn("data", body)
        self.assertIn("page", body)
        self.assertEqual(body["page"]["total"], 4)
        self.assertEqual(len(body["data"]), 4)

    def test_notice_keyword_search(self):
        res = self.client.get("/api/v1/notices?q=민원", secure=True)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()["data"]
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["notice_number"], "202611-AI-001")
        self.assertEqual(data[0]["buyer"], "서울특별시")

    def test_notice_field_category_filter(self):
        res = self.client.get("/api/v1/notices?field=AI", secure=True)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()["data"]
        self.assertEqual(len(data), 1)
        self.assertIn("AI", data[0]["categories"])

        res_sw = self.client.get("/api/v1/notices?field=SW", secure=True)
        self.assertEqual(res_sw.status_code, status.HTTP_200_OK)
        data_sw = res_sw.json()["data"]
        self.assertEqual(len(data_sw), 3)  # AI Notice also has SW, plus SW and Cancel

    def test_notice_status_filter(self):
        # Open
        res_open = self.client.get("/api/v1/notices?status=open", secure=True)
        self.assertEqual(res_open.status_code, status.HTTP_200_OK)
        self.assertEqual(res_open.json()["page"]["total"], 2)

        # Closed
        res_closed = self.client.get("/api/v1/notices?status=closed", secure=True)
        self.assertEqual(res_closed.status_code, status.HTTP_200_OK)
        self.assertEqual(res_closed.json()["page"]["total"], 1)

        # Cancelled
        res_cancel = self.client.get("/api/v1/notices?status=cancelled", secure=True)
        self.assertEqual(res_cancel.status_code, status.HTTP_200_OK)
        self.assertEqual(res_cancel.json()["page"]["total"], 1)

    def test_notice_sorting_by_budget(self):
        res = self.client.get("/api/v1/notices?sort=budget", secure=True)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()["data"]
        # Highest budget first (DATA 15.1억 -> AI 7.36억 -> SW 4.0억 -> Cancel 0.8억)
        self.assertEqual(data[0]["budget_amount"], 1510000000)
        self.assertEqual(data[1]["budget_amount"], 736000000)
        self.assertEqual(data[2]["budget_amount"], 400000000)

    def test_notice_detail_endpoint(self):
        res = self.client.get(f"/api/v1/notices/{self.notice_ai.id}", secure=True)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()["data"]
        self.assertEqual(data["notice_number"], "202611-AI-001")
        self.assertEqual(data["title"], "초거대 AI 기반 지능형 민원 상담 시스템 구축")
        self.assertEqual(len(data["documents"]), 1)
        doc = data["documents"][0]
        self.assertEqual(doc["logical_key"], "RFP")
        self.assertEqual(len(doc["versions"]), 1)
        self.assertEqual(doc["versions"][0]["size_bytes"], 1048576)

    def test_notice_versions_history(self):
        # Create second version for AI notice
        nv_ai_v2 = NoticeVersion.objects.create(
            notice=self.notice_ai,
            version_seq=2,
            observed_at=timezone.now(),
            title="초거대 AI 기반 지능형 민원 상담 시스템 구축 [정정공고]",
            buyer="서울특별시",
            correction=True,
            budget_amount=736000000,
            department_categories=["AI", "SW"],
            source_payload_digest="digest_ai_v2",
        )
        self.notice_ai.current_version = nv_ai_v2
        self.notice_ai.save()

        res = self.client.get(f"/api/v1/notices/{self.notice_ai.id}/versions", secure=True)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()["data"]
        self.assertEqual(len(data), 2)
        # Ordered by -version_seq
        self.assertEqual(data[0]["version_seq"], 2)
        self.assertTrue(data[0]["correction"])
        self.assertEqual(data[1]["version_seq"], 1)

    def test_notice_attachments_filter_versions_and_counts_by_access(self):
        other = User.objects.create_user(
            username="other-attachment-owner", password=PASSWORD_FIXTURE,
            must_change_password=False, role="director",
        )
        hidden_doc = Document.objects.create(
            notice=self.notice_ai, logical_key="restricted-fixture",
        )
        for doc, seq in ((self.doc_ai, 2), (hidden_doc, 1)):
            DocumentVersion.objects.create(
                document=doc, notice_version=self.nv_ai_v1, version_seq=seq,
                sha256="a" * 64, size_bytes=50, owner_user=other,
                source_url="https://example.invalid/restricted-fixture",
            )
        # Even explicitly shared rows with inconsistent notice linkage must not leak.
        invalid = DocumentVersion.objects.create(
            document=hidden_doc, notice_version=self.nv_data_v1, version_seq=2,
            sha256="b" * 64, size_bytes=50, shared_read_approved=True,
        )
        res = self.client.get(f"/api/v1/notices/{self.notice_ai.pk}", secure=True)
        self.assertEqual(res.status_code, 200)
        docs = res.json()["data"]["documents"]
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["logical_key"], "RFP")
        self.assertEqual([v["version_seq"] for v in docs[0]["versions"]], [1])
        self.assertNotIn("restricted-fixture", str(docs))
        res = self.client.get("/api/v1/notices?q=민원", secure=True)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["data"][0]["document_count"], 1)
        self.assertEqual(self.client.get(
            f"/api/v1/documents/{invalid.pk}/structures", secure=True,
        ).status_code, 404)

    def test_public_notice_does_not_expose_unapproved_metadata_or_source_secrets(self):
        self.nv_ai_v1.extra_data = {"score": 90, "final": {"private": "SENSITIVE_FIXTURE"}}
        for url in ("javascript:alert(1)", "https://g2b.go.kr/?token=SENSITIVE_FIXTURE",
                    "https://user:secret@g2b.go.kr/test", "https://g2b.go.kr.example.invalid/test",
                    "http://localhost:8080/private"):
            with self.subTest(url=url):
                self.nv_ai_v1.source_url = url
                self.nv_ai_v1.save(update_fields=["source_url", "extra_data"])
                res = self.client.get(f"/api/v1/notices/{self.notice_ai.pk}", secure=True)
                self.assertEqual(res.status_code, 200)
                self.assertEqual(res.json()["data"]["source_url"], "")
                self.assertEqual(res.json()["data"]["extra_data"], {})
                listing = self.client.get("/api/v1/notices?q=민원", secure=True)
                self.assertEqual(listing.json()["data"][0]["source_url"], "")
        self.nv_ai_v1.source_url = "https://g2b.go.kr/test-ai"
        self.nv_ai_v1.save(update_fields=["source_url"])
        res = self.client.get(f"/api/v1/notices/{self.notice_ai.pk}", secure=True)
        self.assertEqual(res.json()["data"]["source_url"], "https://g2b.go.kr/test-ai")
        self.nv_ai_v1.refresh_from_db()
        self.assertEqual(self.nv_ai_v1.extra_data["final"]["private"], "SENSITIVE_FIXTURE")

    def test_manual_snapshot_import_to_authenticated_search_and_cancel(self):
        import json
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from io import StringIO
        from django.core.management import call_command

        item = {
            "id": "SYNTH-MVP-01", "bid_no": "SYNTH-MVP-01", "bid_order": "00",
            "source_type": "SYNTHETIC_FIXTURE",
            "title": "MVP-01 AI 데이터 플랫폼", "buyer": "합성 기관",
            "source_url": "https://g2b.go.kr/synthetic-mvp-01",
            "end": (timezone.now() + timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S"),
        }
        with TemporaryDirectory() as directory:
            path = Path(directory) / "notices.json"
            path.write_text(json.dumps([item], ensure_ascii=False), encoding="utf-8")
            original = path.read_bytes()
            call_command("import_legacy_notices", file=str(path), dry_run=True, stdout=StringIO())
            self.assertFalse(Notice.objects.filter(notice_number=item["id"]).exists())
            call_command("import_legacy_notices", file=str(path), stdout=StringIO())
            call_command("import_legacy_notices", file=str(path), stdout=StringIO())
            self.assertEqual(path.read_bytes(), original)
            rows = self.client.get("/api/v1/notices?q=SYNTH-MVP-01&field=AI&status=open", secure=True).json()["data"]
            self.assertEqual(len(rows), 1)
            self.assertIn("DATA", rows[0]["categories"])
            self.assertEqual(rows[0]["source_url"], item["source_url"])
            notice_id = rows[0]["id"]
            detail = self.client.get(f"/api/v1/notices/{notice_id}", secure=True).json()["data"]
            self.assertEqual(detail["total_versions"], 1)
            cancelled = {**item, "bid_order": "01", "cancellation": True}
            path.write_text(json.dumps([cancelled], ensure_ascii=False), encoding="utf-8")
            call_command("import_legacy_notices", file=str(path), stdout=StringIO())
            path.write_bytes(original)
            call_command("import_legacy_notices", file=str(path), stdout=StringIO())

        opened = self.client.get("/api/v1/notices?q=SYNTH-MVP-01&status=open", secure=True).json()["data"]
        self.assertEqual(opened, [])
        rows = self.client.get("/api/v1/notices?q=SYNTH-MVP-01&status=cancelled", secure=True).json()["data"]
        self.assertEqual(len(rows), 1)
        history = self.client.get(f"/api/v1/notices/{notice_id}/versions", secure=True).json()["data"]
        self.assertEqual(len(history), 2)
        self.assertTrue(history[0]["cancellation"])

    def test_date_only_and_exact_deadline_status(self):
        from unittest.mock import patch
        instant = timezone.now()
        self.nv_ai_v1.deadline_status = DeadlineStatus.DATE_ONLY
        self.nv_ai_v1.save(update_fields=["deadline_status"])
        self.nv_data_v1.deadline_at = instant
        self.nv_data_v1.save(update_fields=["deadline_at"])
        with patch("bid_server.procurement.views.timezone.now", return_value=instant):
            self.assertEqual(self.client.get("/api/v1/notices?status=open", secure=True).json()["page"]["total"], 0)
            self.assertEqual(self.client.get("/api/v1/notices?status=unknown", secure=True).json()["page"]["total"], 1)
            self.assertEqual(self.client.get("/api/v1/notices?status=closed", secure=True).json()["page"]["total"], 2)
            counts = self.client.get("/api/v1/dashboard", secure=True).json()["data"]["counts"]
            self.assertEqual(counts["open_notices"], 0)
            self.assertEqual(counts["urgent_deadline_3d"], 0)
