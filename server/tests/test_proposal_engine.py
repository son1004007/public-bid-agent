"""DEF-02 및 A29 제안서 생성 엔진, HWPX/DOCX 어댑터 및 장애 STOP 인수 테스트.
목적: 제안서 단일 트랜잭션 스냅샷 리비전(DEF-02), HWPX/DOCX 공식 어댑터(A29),
      외부 LLM 장애 시 STOP 제어(A27, A28) 및 REST API 엔드포인트를 검증한다.
관련: docs/server-migration/17-domain-and-postgresql-contract.md §99, 19-automation-and-provider-contract.md, 20-acceptance-and-open-decisions.md (A27, A28, A29).
"""
import io
import zipfile
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from bid_server.procurement.models import (
    Notice,
    NoticeVersion,
    Proposal,
    ProposalRevision,
    ProposalSection,
    ProposalStatus,
    ExportArtifact,
)
from bid_server.procurement.proposal_service import (
    ProposalService,
    RevisionConflictError,
    PayloadTooLargeError,
)
from bid_server.procurement.generator import ProposalExportService
from bid_server.jobs.models import Job, JobKind, JobState
from bid_server.jobs.service import JobService, FencingTokenError
from bid_server.jobs.workers import JobWorkerPipeline

User = get_user_model()
PASSWORD_FIXTURE = "TestSecurePassword123!@#"


class ProposalEngineAcceptanceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="proposal-author",
            password=PASSWORD_FIXTURE,
            must_change_password=False,
            role="lead",
        )
        self.client = APIClient(enforce_csrf_checks=True)
        # Login and obtain session
        token_res = self.client.get("/api/v1/auth/csrf", secure=True)
        self.csrf_token = token_res.json()["data"]["csrf_token"]
        self.client.post(
            "/api/v1/auth/login",
            {"username": "proposal-author", "password": PASSWORD_FIXTURE},
            format="json",
            secure=True,
            HTTP_X_CSRFTOKEN=self.csrf_token,
            HTTP_ORIGIN="https://testserver",
        )
        # Post-login CSRF token refresh (CSRF rotation on login)
        post_csrf = self.client.get("/api/v1/auth/csrf", secure=True)
        self.csrf_token = post_csrf.json()["data"]["csrf_token"]

        self.notice = Notice.objects.create(
            source="G2B_OFFICIAL_API",
            notice_number="PROP-TEST-001",
        )
        self.notice_version = NoticeVersion.objects.create(
            notice=self.notice,
            version_seq=1,
            observed_at=timezone.now(),
            title="차세대 AI 기반 국방 교육훈련 체계 개발",
            buyer="국방부 국군재정관리단",
            budget_amount=799000000,
            source_payload_digest="c" * 64,
        )

    def test_atomic_proposal_revision_creation(self):
        """제안서 전체 절이 단일 트랜잭션으로 원자적 커밋되고 seq가 1만 증가함을 검증 (DEF-02)."""
        proposal = ProposalService.get_or_create_proposal(self.notice)
        self.assertIsNone(proposal.current_revision)

        sections = [
            {"section_key": "sec1", "ordinal": 1, "title": "사업 이해", "body": "본 사업의 목적과 배경입니다."},
            {"section_key": "sec2", "ordinal": 2, "title": "기술 방안", "body": "클라우드 및 생성형 AI 아키텍처입니다."},
            {"section_key": "sec3", "ordinal": 3, "title": "수행 일정", "body": "3단계 마일스톤 계획입니다."},
        ]

        rev1 = ProposalService.create_atomic_revision(
            proposal=proposal,
            title="국방 AI 교육훈련 제안서 v1",
            sections=sections,
            author=self.user,
        )

        self.assertEqual(rev1.seq, 1)
        self.assertEqual(rev1.sections.count(), 3)
        proposal.refresh_from_db()
        self.assertEqual(proposal.current_revision, rev1)

        # 2차 리비전 생성 검증 (seq가 2로 증가)
        rev2 = ProposalService.create_atomic_revision(
            proposal=proposal,
            title="국방 AI 교육훈련 제안서 v2",
            sections=sections,
            author=self.user,
            expected_parent_seq=1,
        )
        self.assertEqual(rev2.seq, 2)
        self.assertEqual(rev2.parent_revision, rev1)
        proposal.refresh_from_db()
        self.assertEqual(proposal.current_revision, rev2)

    def test_payload_too_large_rejection_leaves_previous_intact(self):
        """절 본문 50,000자 초과 시 롤백되고 이전 리비전이 불변 보존됨을 검증 (DEF-02)."""
        proposal = ProposalService.get_or_create_proposal(self.notice)
        valid_sections = [
            {"section_key": "sec1", "ordinal": 1, "title": "정상 절", "body": "정상적인 본문 내용입니다."}
        ]
        rev1 = ProposalService.create_atomic_revision(
            proposal=proposal,
            title="제안서 v1",
            sections=valid_sections,
        )
        proposal.refresh_from_db()
        self.assertEqual(proposal.current_revision.seq, 1)

        oversized_sections = [
            {"section_key": "sec1", "ordinal": 1, "title": "초대형 절", "body": "A" * 50001}
        ]
        with self.assertRaises(PayloadTooLargeError):
            ProposalService.create_atomic_revision(
                proposal=proposal,
                title="제안서 v2 (초과)",
                sections=oversized_sections,
                expected_parent_seq=1,
            )

        proposal.refresh_from_db()
        self.assertEqual(proposal.current_revision.seq, 1)  # 여전히 v1 유지

    def test_revision_conflict_rejection(self):
        """부모 차수 불일치 시 RevisionConflictError 발생 및 커밋 거부 검증 (A03, DEF-04)."""
        proposal = ProposalService.get_or_create_proposal(self.notice)
        sections = [{"section_key": "s1", "ordinal": 1, "title": "절", "body": "본문"}]
        ProposalService.create_atomic_revision(proposal=proposal, title="v1", sections=sections)

        # 현재 v1인데 expected_parent_seq=999 요청 시 충돌 거부
        with self.assertRaises(RevisionConflictError):
            ProposalService.create_atomic_revision(
                proposal=proposal,
                title="v2 충돌",
                sections=sections,
                expected_parent_seq=999,
            )

    def test_hwpx_and_docx_export_adapters(self):
        """HWPX 및 DOCX 어댑터가 유효한 압축 패키지와 SHA-256을 생성함을 검증 (A29)."""
        proposal = ProposalService.get_or_create_proposal(self.notice)
        sections = [
            {"section_key": "sec1", "ordinal": 1, "title": "1. 사업 개요", "body": "국방 AI 훈련 체계 구축."},
            {"section_key": "sec2", "ordinal": 2, "title": "2. 기술 아키텍처", "body": "SLLM 및 온디바이스 에이전트 연계."},
        ]
        rev = ProposalService.create_atomic_revision(proposal=proposal, title="제안서", sections=sections)

        # 1. HWPX Export 검증
        hwpx_bytes, hwpx_name, hwpx_sha, hwpx_sz = ProposalExportService.export_proposal_revision(rev, "hwpx")
        self.assertTrue(hwpx_name.endswith(".hwpx"))
        self.assertTrue(len(hwpx_sha) == 64)
        self.assertTrue(hwpx_sz > 0)
        # Verify it is a valid zip with mimetype and section0.xml
        with zipfile.ZipFile(io.BytesIO(hwpx_bytes)) as z:
            self.assertIn("mimetype", z.namelist())
            self.assertIn("Contents/section0.xml", z.namelist())
            sec_xml = z.read("Contents/section0.xml").decode("utf-8")
            self.assertIn("1. 사업 개요", sec_xml)

        # 2. DOCX Export 검증
        docx_bytes, docx_name, docx_sha, docx_sz = ProposalExportService.export_proposal_revision(rev, "docx")
        self.assertTrue(docx_name.endswith(".docx"))
        self.assertTrue(len(docx_sha) == 64)
        self.assertTrue(docx_sz > 0)
        with zipfile.ZipFile(io.BytesIO(docx_bytes)) as z:
            self.assertIn("[Content_Types].xml", z.namelist())
            self.assertIn("word/document.xml", z.namelist())
            doc_xml = z.read("word/document.xml").decode("utf-8")
            self.assertIn("2. 기술 아키텍처", doc_xml)

    def test_job_worker_proposal_generation_and_stop_on_failure(self):
        """워커 파이프라인이 정상 생성과 모델 장애 시 STOP 상태 전이를 올바르게 제어함을 검증 (A27, A28)."""
        pipeline = JobWorkerPipeline(worker_name="test-worker")

        # 1. 정상 제안서 생성 작업
        job1, _ = JobService.create_job(
            kind=JobKind.PROPOSAL_GENERATION,
            owner_user=self.user,
            input_manifest={"notice_id": str(self.notice.id)},
        )
        executed1 = pipeline.execute_next_job()
        self.assertEqual(executed1.id, job1.id)
        self.assertEqual(executed1.state, JobState.SUCCEEDED)
        self.assertIn("revision_id", executed1.result_ref)

        # 2. 외부 LLM 모델 장애 발생 시 STOP 처리 검증 (A27)
        job2, _ = JobService.create_job(
            kind=JobKind.PROPOSAL_GENERATION,
            owner_user=self.user,
            input_manifest={"notice_id": str(self.notice.id), "simulate_provider_error": True},
        )
        executed2 = pipeline.execute_next_job()
        self.assertEqual(executed2.id, job2.id)
        self.assertEqual(executed2.state, JobState.STOPPED)
        self.assertIn("STOP 정책 적용", executed2.stop_reason)
        # Attempt error code 확인
        last_attempt = executed2.attempts.last()
        self.assertEqual(last_attempt.error_code, "PROVIDER_ERROR")

    def test_expired_worker_cannot_start_proposal_writes(self):
        from datetime import timedelta
        from unittest.mock import patch

        job, _ = JobService.create_job(
            JobKind.PROPOSAL_GENERATION, {"notice_id": str(self.notice.id)}, self.user,
        )
        leased, attempt = JobService.acquire_job_lease("stale-worker")
        Job.objects.filter(pk=job.pk).update(lease_expires_at=timezone.now() - timedelta(seconds=1))
        with patch.object(JobService, "acquire_job_lease", return_value=(leased, attempt)):
            executed = JobWorkerPipeline().execute_next_job()
        self.assertEqual(executed.state, JobState.RUNNING)
        self.assertEqual(executed.result_ref, {})
        self.assertFalse(Proposal.objects.exists())
        self.assertFalse(ProposalRevision.objects.exists())

    def test_cancelled_worker_does_not_create_proposal(self):
        from unittest.mock import patch

        job, _ = JobService.create_job(
            JobKind.PROPOSAL_GENERATION, {"notice_id": str(self.notice.id)}, self.user,
        )
        leased, attempt = JobService.acquire_job_lease("cancelled-worker")
        JobService.cancel_job(job.pk)
        with patch.object(JobService, "acquire_job_lease", return_value=(leased, attempt)):
            executed = JobWorkerPipeline().execute_next_job()
        self.assertEqual(executed.state, JobState.CANCELLED)
        self.assertEqual(executed.result_ref, {})
        self.assertFalse(Proposal.objects.exists())
        self.assertFalse(ProposalRevision.objects.exists())

    def test_failed_fence_rolls_back_proposal_and_export_writes(self):
        from unittest.mock import patch

        job, _ = JobService.create_job(
            JobKind.PROPOSAL_GENERATION, {"notice_id": str(self.notice.id)}, self.user,
        )
        with patch.object(JobService, "complete_job", side_effect=FencingTokenError("expired")):
            executed = JobWorkerPipeline().execute_next_job()
        self.assertEqual(executed.pk, job.pk)
        self.assertEqual(executed.state, JobState.RUNNING)
        self.assertEqual(executed.result_ref, {})
        self.assertFalse(Proposal.objects.exists())
        self.assertFalse(ProposalRevision.objects.exists())
        self.assertFalse(ProposalSection.objects.exists())

        proposal = ProposalService.get_or_create_proposal(self.notice)
        rev = ProposalService.create_atomic_revision(
            proposal=proposal, title="synthetic export",
            sections=[{"section_key": "s1", "ordinal": 1, "title": "section", "body": "fixture"}],
        )
        export_job, _ = JobService.create_job(
            JobKind.PROPOSAL_EXPORT, {"revision_id": str(rev.pk), "format": "hwpx"}, self.user,
        )
        with patch.object(JobService, "complete_job", side_effect=FencingTokenError("expired")):
            executed = JobWorkerPipeline().execute_next_job()
        self.assertEqual(executed.pk, export_job.pk)
        self.assertEqual(executed.state, JobState.RUNNING)
        self.assertEqual(executed.result_ref, {})
        self.assertFalse(ExportArtifact.objects.exists())
        proposal.refresh_from_db()
        self.assertEqual(proposal.current_revision_id, rev.pk)

    def test_proposal_rest_api_endpoints(self):
        """제안서 목록, 신규 리비전 커밋(DEF-02) 및 파일 다운로드(A29) REST API 검증."""
        proposal = ProposalService.get_or_create_proposal(self.notice)

        # 1. GET /api/v1/proposals
        list_res = self.client.get(f"/api/v1/proposals?notice_id={self.notice.id}", secure=True)
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        res_data = list_res.json()
        items = res_data.get("data", res_data)
        self.assertEqual(len(items), 1)

        # 2. POST /api/v1/proposals/{id}/revisions
        rev_payload = {
            "title": "API 테스트 제안서 v1",
            "sections": [
                {"section_key": "sec1", "ordinal": 1, "title": "개요", "body": "API를 통한 제안서 절 커밋."},
                {"section_key": "sec2", "ordinal": 2, "title": "상세", "body": "두 번째 절 내용."},
            ],
            "summary": "API 커밋 요약",
        }
        create_res = self.client.post(
            f"/api/v1/proposals/{proposal.id}/revisions",
            rev_payload,
            format="json",
            secure=True,
            HTTP_X_CSRFTOKEN=self.csrf_token,
            HTTP_ORIGIN="https://testserver",
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        created_data = create_res.json()
        seq_val = created_data.get("data", created_data)["seq"]
        self.assertEqual(seq_val, 1)

        # 3. GET /api/v1/proposals/{id}/export?format=hwpx
        export_url = f"/api/v1/proposals/{proposal.id}/export"
        export_res = self.client.get(
            f"{export_url}?format=hwpx",
            secure=True,
        )
        self.assertEqual(export_res.status_code, status.HTTP_200_OK)
        self.assertEqual(export_res["Content-Type"], "application/x-hwp")
        self.assertTrue(len(export_res.content) > 100)
        self.assertIn("X-Artifact-SHA256", export_res)
        self.assertEqual(ExportArtifact.objects.count(), 0)
        repeat_res = self.client.get(f"{export_url}?format=hwpx", secure=True)
        self.assertEqual(repeat_res.status_code, status.HTTP_200_OK)
        self.assertEqual(ExportArtifact.objects.count(), 0)

