"""AGW-05: reviewed PUBLIC provenance is opt-in; all fixtures are synthetic.

No downloads, supplier authentication, actual public document, model call or
production migration. Public-looking URL alone never authorizes transmission.
"""
import hashlib
import json
import uuid

from django.test import TestCase
from django.utils import timezone

from bid_server.accounts.models import User
from bid_server.procurement.models import (
    Chunk, ChunkCategory, Document, DocumentVersion, ExtractionRun,
    ExtractionState, Notice, NoticeVersion,
)
from bid_server.ai_gateway.models import PublicRfpAttestation, AnalysisRun, AnalysisRevision
from bid_server.ai_gateway.analysis_service import (
    AnalysisServiceError, create_attested_public_analysis_run,
    create_synthetic_analysis_run, append_validated_result,
)
from bid_server.ai_gateway.public_source import (
    PublicSourceError, approve_official_public_document, official_source_url,
)

PWD = "SyntheticOnlyNotACredential!2396"


class AttestedPublicSourceTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_user(
            username="agw-public-reader", password=PWD, must_change_password=False
        )
        self.reviewer = User.objects.create_user(
            username="agw-public-reviewer", password=PWD,
            must_change_password=False, is_staff=True,
        )
        self.raw_notice = b'{"sample":"not-real-government-data","version":1}'
        self.raw_doc = b"%PDF-1.4 fully synthetic fixture (not a real PDF)"
        self.notice = Notice.objects.create(
            source="G2B_OFFICIAL_API", notice_number="SYNTHETIC-PUBLIC-TEST-1",
        )
        self.version = NoticeVersion.objects.create(
            notice=self.notice, version_seq=1, observed_at=timezone.now(),
            title="Synthetic official-looking sample", buyer="Synthetic Office",
            source_payload_digest=hashlib.sha256(self.raw_notice).hexdigest(),
            source_url="https://www.g2b.go.kr/pn/pnp/test/notice",
        )
        self.notice.current_version = self.version
        self.notice.save(update_fields=["current_version"])
        self.document = Document.objects.create(notice=self.notice, logical_key="RFP")
        self.doc = DocumentVersion.objects.create(
            document=self.document, notice_version=self.version, version_seq=1,
            sha256=hashlib.sha256(self.raw_doc).hexdigest(),
            size_bytes=len(self.raw_doc),
            source_url="https://www.g2b.go.kr/pn/pnp/file/download",
            shared_read_approved=True,
        )
        self.extraction = ExtractionRun.objects.create(
            document_version=self.doc, extractor_version="synthetic-only-v1",
            state=ExtractionState.PARSED,
            coverage={"complete": True}, warnings=[],
        )
        self.requirement = Chunk.objects.create(
            extraction_run=self.extraction, ordinal=1,
            category=ChunkCategory.QUALIFICATION,
            text="Official-looking synthetic RFP needs 3 references.",
        )
        self.evidence = Chunk.objects.create(
            extraction_run=self.extraction, ordinal=2,
            category=ChunkCategory.QUALIFICATION,
            text="Synthetic public notice evidence; no company facts.",
        )

    def approve(self, **kwargs):
        args = dict(
            reviewer=self.reviewer, document_version_id=self.doc.pk,
            raw_document_bytes=self.raw_doc, raw_notice_payload_bytes=self.raw_notice,
            provider_export_approved=True,
        )
        args.update(kwargs)
        return approve_official_public_document(**args)

    def make_run(self, **kwargs):
        args = dict(
            actor=self.actor, notice_version_id=self.version.pk,
            request_key=uuid.uuid4(),
            requirement_chunk_ids=[self.requirement.pk],
            evidence_chunk_ids=[self.evidence.pk],
        )
        args.update(kwargs)
        return create_attested_public_analysis_run(**args)

    def result(self, run):
        return {
            "schema_version": "bid_analysis_v1",
            "run_id": str(run.pk), "provider": "CODEX",
            "notice_version_id": str(run.notice_version_id),
            "corpus_snapshot_id": str(run.corpus_snapshot_id),
            "snapshot_sha256": run.snapshot_sha256,
            "prompt_version": run.prompt_version,
            "requirements": [{
                "requirement_id": run.snapshot_payload["requirements"][0]["requirement_id"],
                "assessment": "UNKNOWN",
                "evidence_ids": [run.snapshot_payload["evidence"][0]["evidence_id"]],
                "missing_evidence_ids": ["NO_VERIFIED_COMPANY_RECORD"],
                "rationale_short": "Official RFP requirement known, supplier proof unknown.",
            }],
            "risks": [], "scenarios": [], "unknowns": [],
        }

    def test_official_url_exact_host_only(self):
        self.assertTrue(official_source_url("https://www.g2b.go.kr/pn/pnp/file"))
        self.assertTrue(official_source_url("https://apis.data.go.kr/1230000/ad/BidPublicInfoService02"))
        for url in (
            "https://www.g2b.go.kr.evil.example/notice",
            "https://www.g2b.go.kr@evil.example/file",
            "http://www.g2b.go.kr/notice",
            "https://www.g2b.go.kr:8888/notice",
            "https://www.g2b.go.kr/notice?serviceKey=secret",
            "file:///etc/passwd",
        ):
            with self.subTest(url=url):
                self.assertFalse(official_source_url(url))

    def test_unreviewed_public_document_is_denied(self):
        with self.assertRaisesRegex(AnalysisServiceError, "PUBLIC_SOURCE_NOT_APPROVED"):
            self.make_run()
        self.assertFalse(AnalysisRun.objects.exists())

    def test_nonstaff_cannot_approve(self):
        with self.assertRaisesRegex(PublicSourceError, "REVIEWER_NOT_AUTHORIZED"):
            self.approve(reviewer=self.actor)
        self.assertFalse(PublicRfpAttestation.objects.exists())

    def test_document_byte_mismatch_denied(self):
        with self.assertRaisesRegex(PublicSourceError, "PUBLIC_SOURCE_BYTES_MISMATCH"):
            self.approve(raw_document_bytes=b"X" * len(self.raw_doc))
        self.assertFalse(PublicRfpAttestation.objects.exists())

    def test_notice_byte_mismatch_denied(self):
        with self.assertRaisesRegex(PublicSourceError, "PUBLIC_SOURCE_BYTES_MISMATCH"):
            self.approve(raw_notice_payload_bytes=b"X" * len(self.raw_notice))

    def test_export_not_approved_denies_packet(self):
        self.approve(provider_export_approved=False)
        with self.assertRaisesRegex(AnalysisServiceError, "PUBLIC_SOURCE_NOT_APPROVED"):
            self.make_run()

    def test_public_only_snapshot_and_replay(self):
        att = self.approve()
        self.assertEqual(att.document_sha256, self.doc.sha256)
        key = uuid.uuid4()
        run = self.make_run(request_key=key)
        replay = self.make_run(request_key=key)
        self.assertEqual(run.pk, replay.pk)
        self.assertEqual(run.snapshot_payload["policy"]["classification_allowlist"], ["PUBLIC"])
        self.assertEqual(run.snapshot_payload["company_facts"], [])
        self.assertEqual(run.snapshot_payload["requirements"][0]["document_sha256"], self.doc.sha256)
        self.assertEqual(run.snapshot_payload["requirements"][0]["extraction_run_id"],
                         str(self.extraction.pk))
        self.assertEqual(AnalysisRun.objects.count(), 1)

    def test_synthetic_entrypoint_cannot_reclassify_public(self):
        self.approve()
        with self.assertRaisesRegex(AnalysisServiceError, "STALE_OR_UNAPPROVED_NOTICE"):
            create_synthetic_analysis_run(
                actor=self.actor, notice_version_id=self.version.pk,
                request_key=uuid.uuid4(),
                requirement_chunk_ids=[self.requirement.pk],
                evidence_chunk_ids=[self.evidence.pk],
            )

    def test_incomplete_public_coverage_denied(self):
        self.approve()
        self.extraction.coverage = {"complete": False}
        self.extraction.save(update_fields=["coverage"])
        with self.assertRaisesRegex(AnalysisServiceError, "PUBLIC_SOURCE_NOT_APPROVED"):
            self.make_run()

    def test_extraction_warning_denied(self):
        self.approve()
        self.extraction.warnings = ["TABLE_MISSING"]
        self.extraction.save(update_fields=["warnings"])
        with self.assertRaisesRegex(AnalysisServiceError, "PUBLIC_SOURCE_NOT_APPROVED"):
            self.make_run()

    def test_revoke_after_snapshot_blocks_result(self):
        approval = self.approve()
        run = self.make_run()
        approval.revoked = True
        approval.save(update_fields=["revoked"])
        with self.assertRaisesRegex(AnalysisServiceError, "PUBLIC_SOURCE_NOT_APPROVED"):
            append_validated_result(
                actor=self.actor, run_id=run.pk, provider="CODEX",
                raw_json=json.dumps(self.result(run)),
            )
        self.assertFalse(AnalysisRevision.objects.exists())

    def test_source_url_modified_after_approval_denied(self):
        self.approve()
        self.doc.source_url = "https://www.g2b.go.kr/pn/pnp/another-file"
        self.doc.save(update_fields=["source_url"])
        with self.assertRaisesRegex(AnalysisServiceError, "PUBLIC_SOURCE_NOT_APPROVED"):
            self.make_run()

    def test_private_notice_source_not_automatically_public(self):
        self.notice.source = "PRIVATE_UPLOAD"
        self.notice.save(update_fields=["source"])
        with self.assertRaisesRegex(PublicSourceError, "PUBLIC_SOURCE_NOT_VERIFIED"):
            self.approve()

    def test_staff_approval_does_not_make_met_true(self):
        self.approve()
        run = self.make_run()
        result = self.result(run)
        result["requirements"][0]["assessment"] = "MET"
        result["requirements"][0]["missing_evidence_ids"] = []
        with self.assertRaisesRegex(AnalysisServiceError, "RESULT_NOT_VALIDATED"):
            append_validated_result(
                actor=self.actor, run_id=run.pk, provider="CODEX",
                raw_json=json.dumps(result),
            )

    def test_public_same_snapshot_codex_and_claude_results(self):
        self.approve()
        run = self.make_run()
        codex = append_validated_result(
            actor=self.actor, run_id=run.id, provider="CODEX",
            raw_json=json.dumps(self.result(run)),
        )
        claude_data = self.result(run)
        claude_data["provider"] = "CLAUDE"
        claude = append_validated_result(
            actor=self.actor, run_id=run.id, provider="CLAUDE",
            raw_json=json.dumps(claude_data),
        )
        self.assertEqual(codex.run_id, claude.run_id)
        self.assertEqual(
            codex.validated_payload["snapshot_sha256"],
            claude.validated_payload["snapshot_sha256"],
        )
