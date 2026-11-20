"""AGW-05/09 DB-backed synthetic evidence and immutable result persistence.

These tests use synthetic data and an ephemeral DB; no provider calls or auth
tokens are needed. They exercise both SQLite CI and the existing PostgreSQL CI.
"""
import json
import uuid

from django.test import TestCase
from django.utils import timezone

from bid_server.accounts.models import User
from bid_server.procurement.models import (
    Chunk, ChunkCategory, Document, DocumentFreshness, DocumentVersion,
    ExtractionRun, ExtractionState, Notice, NoticeVersion,
)
from bid_server.ai_gateway.models import AnalysisRevision, AnalysisRun
from bid_server.ai_gateway.analysis_service import (
    AnalysisServiceError, create_synthetic_analysis_run, append_validated_result,
)

PASSWORD = "SyntheticOnly!Sample9876"


class SyntheticAnalysisStorageTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_user(
            username="agw-evidence-a", password=PASSWORD, must_change_password=False
        )
        self.other = User.objects.create_user(
            username="agw-evidence-b", password=PASSWORD, must_change_password=False
        )
        self.notice = Notice.objects.create(
            source="SYNTHETIC_FIXTURE", notice_number="AGW-ANALYSIS-1",
        )
        self.version = NoticeVersion.objects.create(
            notice=self.notice, version_seq=1, observed_at=timezone.now(),
            title="Synthetic RFP", buyer="Synthetic Office",
            source_payload_digest="f" * 64,
        )
        self.notice.current_version = self.version
        self.notice.save(update_fields=["current_version"])
        self.document = Document.objects.create(notice=self.notice, logical_key="RFP")
        self.document_version = DocumentVersion.objects.create(
            document=self.document, notice_version=self.version, version_seq=1,
            sha256="a" * 64, size_bytes=150,
            owner_user=self.actor, shared_read_approved=False,
            freshness=DocumentFreshness.CURRENT,
        )
        self.extraction = ExtractionRun.objects.create(
            document_version=self.document_version, extractor_version="synthetic-v1",
            state=ExtractionState.PARSED,
        )
        self.req = Chunk.objects.create(
            extraction_run=self.extraction, ordinal=1,
            category=ChunkCategory.QUALIFICATION,
            text="A synthetic RFP requires 3 recent projects.",
        )
        self.evidence = Chunk.objects.create(
            extraction_run=self.extraction, ordinal=2,
            category=ChunkCategory.QUALIFICATION,
            text="A synthetic procurement document explains the 3 projects requirement.",
        )
        self.replay_key = uuid.uuid4()

    def create_run(self, **overrides):
        args = {
            "actor": self.actor,
            "notice_version_id": self.version.id,
            "request_key": self.replay_key,
            "requirement_chunk_ids": [self.req.pk],
            "evidence_chunk_ids": [self.evidence.pk],
        }
        args.update(overrides)
        return create_synthetic_analysis_run(**args)

    def response(self, run, assessment="UNKNOWN", **overrides):
        packet = run.snapshot_payload
        row = {
            "requirement_id": packet["requirements"][0]["requirement_id"],
            "assessment": assessment,
            "evidence_ids": [packet["evidence"][0]["evidence_id"]],
            "missing_evidence_ids": (["NEEDS_COMPANY_PROOF"] if assessment == "UNKNOWN" else []),
            "rationale_short": "RFP specifies requirement; company eligibility remains unverified.",
        }
        row.update(overrides)
        return {
            "schema_version": "bid_analysis_v1",
            "run_id": str(run.id),
            "provider": "CODEX",
            "notice_version_id": str(run.notice_version_id),
            "corpus_snapshot_id": str(run.corpus_snapshot_id),
            "snapshot_sha256": run.snapshot_sha256,
            "prompt_version": run.prompt_version,
            "requirements": [row],
            "risks": [], "scenarios": [], "unknowns": [],
        }

    def append(self, run, **kwargs):
        payload = kwargs.pop("result", self.response(run))
        return append_validated_result(
            actor=kwargs.pop("actor", self.actor), run_id=run.id,
            provider=kwargs.pop("provider", "CODEX"),
            raw_json=json.dumps(payload, ensure_ascii=False), **kwargs
        )

    def test_snapshot_pins_db_chunk_provenance(self):
        run = self.create_run()
        self.assertEqual(run.notice_version_id, self.version.pk)
        self.assertEqual(run.snapshot_payload["requirements"][0]["source_span_id"],
                         str(self.req.pk))
        self.assertEqual(run.snapshot_payload["evidence"][0]["classification"], "SYNTHETIC")
        self.assertEqual(run.snapshot_payload["company_facts"], [])
        self.assertEqual(AnalysisRun.objects.count(), 1)

    def test_same_request_key_is_idempotent(self):
        first = self.create_run()
        second = self.create_run()
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(AnalysisRun.objects.count(), 1)

    def test_request_key_reused_with_other_source_is_rejected(self):
        self.create_run()
        with self.assertRaisesRegex(AnalysisServiceError, "REQUEST_KEY_REUSED"):
            self.create_run(evidence_chunk_ids=[self.req.pk])

    def test_other_user_cannot_use_owned_documents(self):
        with self.assertRaisesRegex(AnalysisServiceError, "UNAPPROVED_OR_STALE_SOURCE"):
            self.create_run(actor=self.other)

    def test_unparsed_extract_rejected(self):
        self.extraction.state = ExtractionState.FAILED
        self.extraction.save(update_fields=["state"])
        with self.assertRaisesRegex(AnalysisServiceError, "UNAPPROVED_OR_STALE_SOURCE"):
            self.create_run()

    def test_stale_document_version_rejected(self):
        self.document_version.freshness = DocumentFreshness.STALE
        self.document_version.save(update_fields=["freshness"])
        with self.assertRaisesRegex(AnalysisServiceError, "UNAPPROVED_OR_STALE_SOURCE"):
            self.create_run()

    def test_corrected_notice_rejected(self):
        next_version = NoticeVersion.objects.create(
            notice=self.notice, version_seq=2, observed_at=timezone.now(),
            title="Corrected synthetic RFP", buyer="Synthetic Office",
            source_payload_digest="c" * 64,
        )
        self.notice.current_version = next_version
        self.notice.save(update_fields=["current_version"])
        with self.assertRaisesRegex(AnalysisServiceError, "STALE_OR_UNAPPROVED_NOTICE"):
            self.create_run()

    def test_model_result_add_and_idempotent_replay(self):
        run = self.create_run()
        first = self.append(run)
        again = self.append(run)
        self.assertEqual(first.pk, again.pk)
        self.assertEqual(first.revision_seq, 1)
        self.assertEqual(AnalysisRevision.objects.count(), 1)

    def test_divergent_revision_needs_explicit_authorization(self):
        run = self.create_run()
        first = self.append(run)
        payload = self.response(run)
        payload["requirements"][0]["rationale_short"] = "Different corrected analysis"
        with self.assertRaisesRegex(AnalysisServiceError, "REVISION_APPROVAL_REQUIRED"):
            self.append(run, result=payload)
        second = self.append(run, result=payload, authorize_additional_revision=True)
        self.assertEqual(second.revision_seq, 2)
        self.assertNotEqual(second.result_sha256, first.result_sha256)
        self.assertEqual(AnalysisRevision.objects.count(), 2)

    def test_fake_evidence_rejected_without_database_write(self):
        run = self.create_run()
        payload = self.response(run, evidence_ids=["FAKE"])
        with self.assertRaisesRegex(AnalysisServiceError, "RESULT_NOT_VALIDATED"):
            self.append(run, result=payload)
        self.assertFalse(AnalysisRevision.objects.exists())

    def test_model_cannot_assert_definitive_eligibility_from_rfp_only(self):
        run = self.create_run()
        for decision in ("MET", "NOT_MET"):
            with self.subTest(decision=decision):
                with self.assertRaisesRegex(AnalysisServiceError, "RESULT_NOT_VALIDATED"):
                    self.append(run, result=self.response(run, assessment=decision))
        self.assertFalse(AnalysisRevision.objects.exists())

    def test_other_user_cannot_append_or_read_as_owner(self):
        run = self.create_run()
        with self.assertRaisesRegex(AnalysisServiceError, "UNAUTHORIZED_USER"):
            self.append(run, actor=self.other)
        self.assertFalse(AnalysisRevision.objects.exists())

    def test_source_acl_revocation_blocks_append(self):
        run = self.create_run()
        self.document_version.owner_user = self.other
        self.document_version.save(update_fields=["owner_user"])
        with self.assertRaisesRegex(AnalysisServiceError, "UNAPPROVED_OR_STALE_SOURCE"):
            self.append(run)

    def test_original_chunk_change_blocks_append(self):
        run = self.create_run()
        self.evidence.text = "Tampered synthetic text"
        self.evidence.save(update_fields=["text"])
        with self.assertRaisesRegex(AnalysisServiceError, "STALE_OR_TAMPERED_SOURCE"):
            self.append(run)

    def test_provider_spoof_rejected(self):
        run = self.create_run()
        with self.assertRaisesRegex(AnalysisServiceError, "RESULT_NOT_VALIDATED"):
            self.append(run, provider="CLAUDE")
        self.assertFalse(AnalysisRevision.objects.exists())

    def test_snapshot_tampered_in_db_rejected(self):
        run = self.create_run()
        # Raw DB mutation simulates a privileged storage compromise.
        # Model.save itself is append-only and cannot perform this.
        from django.db import connection
        with connection.cursor() as cursor:
            # QuerySet.update is intentionally disabled; direct SQL can bypass
            # this until production DB triggers/grants are deployed.
            payload = dict(run.snapshot_payload)
            payload["prompt_version"] = "modified"
            from django.core.serializers.json import DjangoJSONEncoder
            cursor.execute(
                "UPDATE ai_gateway_analysisrun SET snapshot_payload=%s WHERE id=%s",
                [json.dumps(payload, cls=DjangoJSONEncoder), str(run.id).replace("-", "")],
            )
        run.refresh_from_db()
        with self.assertRaisesRegex(AnalysisServiceError, "RESULT_NOT_VALIDATED"):
            self.append(run)

    def test_model_and_queryset_updates_are_blocked(self):
        run = self.create_run()
        run.prompt_version = "tamper"
        with self.assertRaisesRegex(ValueError, "IMMUTABLE_ANALYSIS_HISTORY"):
            run.save()
        with self.assertRaisesRegex(ValueError, "IMMUTABLE_ANALYSIS_HISTORY"):
            AnalysisRun.objects.filter(pk=run.pk).update(prompt_version="evil")
        with self.assertRaisesRegex(ValueError, "IMMUTABLE_ANALYSIS_HISTORY"):
            AnalysisRun.objects.filter(pk=run.pk).delete()
        revision = self.append(run)
        revision.revision_seq = 999
        with self.assertRaisesRegex(ValueError, "IMMUTABLE_ANALYSIS_HISTORY"):
            revision.save()
        with self.assertRaisesRegex(ValueError, "IMMUTABLE_ANALYSIS_HISTORY"):
            AnalysisRevision.objects.filter(pk=revision.pk).update(revision_seq=999)
