"""MCP 공개 공고/RFP DB 스코프 테스트 — 외부 API·실제 데이터 접근 없음."""
import os
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from bid_mcp.service import get_public_notice, search_public_notices, search_public_rfp_passages
from bid_server.procurement.models import (
    Notice, NoticeVersion, Document, DocumentVersion, ExtractionRun, Chunk,
)


def make_notice(number, *, source="G2B_OFFICIAL_API", title="정보보안 AI 시스템"):
    n = Notice.objects.create(source=source, notice_number=number)
    v = NoticeVersion.objects.create(
        notice=n, version_seq=1, observed_at=timezone.now(),
        title=title, buyer="Synthetic Buyer", source_payload_digest="a" * 64,
    )
    n.current_version = v
    n.save(update_fields=["current_version"])
    return n, v


class PublicMcpDatabaseScopeTests(TestCase):
    def setUp(self):
        flags = patch.dict(os.environ, {
            "BID_MCP_ENABLED": "1", "BID_MCP_PUBLIC_ONLY": "1",
            "BID_MCP_PUBLIC_RFP_ENABLED": "0",
        })
        flags.start()
        self.addCleanup(flags.stop)

        self.public, self.v1 = make_notice("R26BK01838997")
        self.private, self.pv = make_notice("PRIVATE-00001", source="SYNTHETIC_FIXTURE")
        self.document = Document.objects.create(notice=self.public, logical_key="RFP")
        self.dv = DocumentVersion.objects.create(
            document=self.document, notice_version=self.v1, version_seq=1,
            sha256="b" * 64, size_bytes=10, shared_read_approved=False,
        )
        self.run = ExtractionRun.objects.create(
            document_version=self.dv, extractor_version="synthetic", state="PARSED",
        )
        Chunk.objects.create(extraction_run=self.run, ordinal=1, text="정보보안 요건", locator={})

    def test_search_is_official_current_only(self):
        result = search_public_notices("정보보안", limit=10)
        self.assertEqual(result["status"], "OK")
        self.assertEqual([x["notice_number"] for x in result["items"]], ["R26BK01838997"])
        self.assertEqual(result["items"][0]["evidence_state"], "PUBLIC_NOTICE_METADATA_ONLY")
        self.assertNotIn("storage_key", result["items"][0])
        self.assertEqual(get_public_notice("PRIVATE-00001")["status"], "NOT_FOUND")

    def test_rfp_needs_explicit_gate_and_document_approval(self):
        self.assertEqual(search_public_rfp_passages("R26BK01838997", "정보보안")["status"], "NOT_ENABLED")
        with patch.dict(os.environ, {"BID_MCP_PUBLIC_RFP_ENABLED": "1"}):
            self.assertEqual(search_public_rfp_passages("R26BK01838997", "정보보안")["items"], [])
            self.dv.shared_read_approved = True
            self.dv.save(update_fields=["shared_read_approved"])
            items = search_public_rfp_passages("R26BK01838997", "정보보안")["items"]
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["text_excerpt"], "정보보안 요건")
            self.assertNotIn("storage_key", items[0])
            # A newer failed extraction invalidates old parsed evidence.
            ExtractionRun.objects.create(
                document_version=self.dv, extractor_version="synthetic-v2",
                state="FAILED", created_at=timezone.now() + timedelta(seconds=1),
            )
            self.assertEqual(search_public_rfp_passages("R26BK01838997", "정보보안")["items"], [])

    def test_old_notice_version_and_unapproved_owner_never_leak(self):
        self.dv.shared_read_approved = True
        self.dv.save(update_fields=["shared_read_approved"])
        with patch.dict(os.environ, {"BID_MCP_PUBLIC_RFP_ENABLED": "1"}):
            v2 = NoticeVersion.objects.create(
                notice=self.public, version_seq=2, observed_at=timezone.now() + timedelta(seconds=2),
                title="정정된 공고", buyer="Synthetic Buyer", source_payload_digest="c" * 64,
            )
            self.public.current_version = v2
            self.public.save(update_fields=["current_version"])
            self.assertEqual(search_public_rfp_passages("R26BK01838997", "정보보안")["items"], [])
