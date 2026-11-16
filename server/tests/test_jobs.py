"""SM05 작업 원장 및 워커 실행 통합 검증 계약.
목적: A08(워커 임대/펜싱 토큰/결과 게시), A09(유한 재시도 3회 상한), A10(자동화 정책), A27(외부 모델 장애 STOP), A28(명시 재시도/멱등성), 작업 API(조회/취소/재시도) 및 PostgreSQL 동시성 검증.
경계: 임시 테스트 DB와 합성 데이터만 사용. 실제 Celery 브로커나 외부 LLM API를 호출하지 않는다.
부작용: Django test runner가 트랜잭션 단위로 롤백하므로 영구 부작용 없음.
실패: 동시성 경합/토큰 불일치/재시도 상한 실패 시 AssertionError 발생.
관련: docs/server-migration/19-automation-and-provider-contract.md, 17-domain-and-postgresql-contract.md §3, 20-acceptance-and-open-decisions.md.
"""
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest import skipUnless
from django.contrib.auth import get_user_model
from django.db import connection, connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from bid_server.jobs.models import (
    Job,
    JobAttempt,
    Outbox,
    AutomationPolicy,
    AutomationPolicyVersion,
    JobKind,
    JobState,
    RetryClass,
)
from bid_server.jobs.service import (
    JobService,
    FencingTokenError,
    RevisionConflictError,
    InvalidStateTransitionError,
    compute_manifest_digest,
)

User = get_user_model()
PASSWORD_FIXTURE = "TestSecurePassword123!@#"


class JobServiceUnitAndAcceptanceTests(TestCase):
    """JobService의 핵심 비즈니스 로직 및 인수 조건을 검증한다."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="job-operator",
            password=PASSWORD_FIXTURE,
            must_change_password=False,
        )

    def test_job_creation_and_business_key_idempotency(self):
        """동일 매니페스트 작업 생성 시 중복 없이 기존 활성 작업이 반환되는지 검증."""
        manifest = {"notice_id": str(uuid.uuid4()), "extractor_version": "v1.2.0"}
        job1, created1 = JobService.create_job(
            kind=JobKind.EXTRACTION_RUN,
            input_manifest=manifest,
            owner_user=self.user,
        )
        self.assertTrue(created1)
        self.assertEqual(job1.state, JobState.QUEUED)
        self.assertEqual(job1.current_attempt, 0)
        self.assertEqual(job1.max_attempts, 3)

        # 동일 매니페스트로 재요청 -> 멱등성 유지 (A15/A28)
        job2, created2 = JobService.create_job(
            kind=JobKind.EXTRACTION_RUN,
            input_manifest=manifest,
            owner_user=self.user,
        )
        self.assertFalse(created2)
        self.assertEqual(job1.id, job2.id)
        self.assertEqual(Job.objects.count(), 1)

        # Outbox 메시지 1건 기록 확인
        self.assertEqual(Outbox.objects.filter(job=job1, message_kind="JOB_QUEUED").count(), 1)

    def test_worker_lease_and_heartbeat(self):
        """워커의 작업 임대(Lease), fencing token 발급 및 하트비트 연장 검증."""
        manifest = {"payload": "sample-1"}
        job, _ = JobService.create_job(JobKind.COLLECTION_RUN, manifest, self.user)

        # 워커가 lease 획득
        acquired = JobService.acquire_job_lease(worker_id="worker-node-1", lease_duration_seconds=30)
        self.assertIsNotNone(acquired)
        leased_job, attempt = acquired

        self.assertEqual(leased_job.id, job.id)
        self.assertEqual(leased_job.state, JobState.RUNNING)
        self.assertEqual(leased_job.current_attempt, 1)
        self.assertEqual(leased_job.lease_owner, "worker-node-1")
        self.assertEqual(attempt.attempt_no, 1)
        self.assertEqual(attempt.fencing_token, leased_job.lease_epoch)

        # 하트비트 전송
        success = JobService.send_heartbeat(job.id, fencing_token=attempt.fencing_token, extend_seconds=60)
        self.assertTrue(success)

        # 잘못된 펜싱 토큰으로 하트비트 전송 시 거부
        fail_hb = JobService.send_heartbeat(job.id, fencing_token=attempt.fencing_token + 99)
        self.assertFalse(fail_hb)

    def test_stale_fencing_token_rejection_on_complete(self):
        """A08: lease 만료 후 다른 워커가 가져간 뒤 이전 워커의 결과 게시 거부 검증."""
        manifest = {"payload": "stale-token-test"}
        job, _ = JobService.create_job(JobKind.EXTRACTION_RUN, manifest, self.user)

        # 1. 워커 1이 임대 획득 (fencing token = 2)
        res1 = JobService.acquire_job_lease(worker_id="worker-1", lease_duration_seconds=10)
        job1, attempt1 = res1
        token1 = attempt1.fencing_token

        # 워커 1의 임대를 과거로 조작 (임대 만료 상황 재현)
        job1.lease_expires_at = timezone.now() - timedelta(seconds=1)
        job1.save(update_fields=["lease_expires_at"])

        # 2. 워커 2가 만료된 작업을 새로 임대 획득 (fencing token = 3)
        res2 = JobService.acquire_job_lease(worker_id="worker-2", lease_duration_seconds=30)
        self.assertIsNotNone(res2)
        job2, attempt2 = res2
        token2 = attempt2.fencing_token
        self.assertGreater(token2, token1)

        # 3. 뒤늦게 워커 1이 오래된 token1로 완료 시도 -> FencingTokenError 발생 (A08)
        with self.assertRaises(FencingTokenError):
            JobService.complete_job(job.id, fencing_token=token1, result_ref={"data": "stale"})

        # 4. 워커 2가 유효한 token2로 완료 -> 정상 성공
        completed_job = JobService.complete_job(job.id, fencing_token=token2, result_ref={"data": "valid"})
        self.assertEqual(completed_job.state, JobState.SUCCEEDED)
        self.assertEqual(completed_job.result_ref, {"data": "valid"})

    def test_expired_lease_rejects_heartbeat_and_completion_without_reassignment(self):
        """A08: expiry itself invalidates a token, even before another worker acquires it."""
        job, _ = JobService.create_job(
            JobKind.EXTRACTION_RUN, {"payload": "expired-lease"}, self.user
        )
        leased, attempt = JobService.acquire_job_lease(
            worker_id="worker-expired", lease_duration_seconds=30
        )
        self.assertEqual(leased.id, job.id)
        Job.objects.filter(pk=job.pk).update(
            lease_expires_at=timezone.now() - timedelta(seconds=1)
        )

        self.assertFalse(JobService.send_heartbeat(job.id, attempt.fencing_token))
        with self.assertRaises(FencingTokenError):
            JobService.complete_job(
                job.id, attempt.fencing_token, {"data": "must-not-publish"}
            )

        job.refresh_from_db()
        self.assertEqual(job.state, JobState.RUNNING)
        self.assertEqual(job.result_ref, {})
        self.assertFalse(Outbox.objects.filter(
            job=job, message_kind="JOB_SUCCEEDED"
        ).exists())

    def test_finite_retry_max_three_attempts(self):
        """A09: 일시 오류 시 최대 3회 재시도 후 FAILED로 종결 검증."""
        manifest = {"query": "sample-retry"}
        job, _ = JobService.create_job(JobKind.COLLECTION_RUN, manifest, self.user, max_attempts=3)

        # 1회차 시도 및 일시 실패
        _, att1 = JobService.acquire_job_lease("worker-a")
        job = JobService.fail_job(job.id, att1.fencing_token, "TIMEOUT", RetryClass.RETRYABLE_TRANSIENT)
        self.assertEqual(job.state, JobState.QUEUED)
        self.assertEqual(job.current_attempt, 1)

        # 2회차 시도 및 일시 실패
        _, att2 = JobService.acquire_job_lease("worker-a")
        job = JobService.fail_job(job.id, att2.fencing_token, "NET_ERROR", RetryClass.RETRYABLE_TRANSIENT)
        self.assertEqual(job.state, JobState.QUEUED)
        self.assertEqual(job.current_attempt, 2)

        # 3회차 시도 및 실패 (최대 상한 3회 도달)
        _, att3 = JobService.acquire_job_lease("worker-a")
        job = JobService.fail_job(job.id, att3.fencing_token, "SERVER_503", RetryClass.RETRYABLE_TRANSIENT)
        self.assertEqual(job.state, JobState.FAILED)
        self.assertEqual(job.current_attempt, 3)

        # 4회차 시도 불가능 (큐에 없음)
        next_lease = JobService.acquire_job_lease("worker-a")
        self.assertIsNone(next_lease)

    def test_non_retryable_error_fails_immediately(self):
        """A09: 비일시적 오류는 1회 시도만으로 즉시 FAILED 종결 검증."""
        manifest = {"bad": "data"}
        job, _ = JobService.create_job(JobKind.EXTRACTION_RUN, manifest, self.user, max_attempts=3)

        _, att = JobService.acquire_job_lease("worker-b")
        job = JobService.fail_job(job.id, att.fencing_token, "INVALID_SCHEMA", RetryClass.NON_RETRYABLE)
        self.assertEqual(job.state, JobState.FAILED)
        self.assertEqual(job.current_attempt, 1)

    def test_external_provider_stop_policy(self):
        """A27: 외부 모델 장애/타임아웃 발생 시 즉시 STOP 상태 전이 및 자동 재시도 차단 검증."""
        manifest = {"model": "claude-3-5-sonnet", "action": "draft"}
        job, _ = JobService.create_job(JobKind.PROPOSAL_GENERATION, manifest, self.user)

        _, att = JobService.acquire_job_lease("worker-ai")
        # 외부 공급자 장애 보고 (stop_reason="PROVIDER_ERROR")
        job = JobService.fail_job(
            job.id,
            att.fencing_token,
            error_code="ANTHROPIC_500",
            retry_class=RetryClass.STOP_EXTERNAL_FAILURE,
            stop_reason="PROVIDER_ERROR",
            external_request_reference="req-anthropic-xyz-99",
        )

        self.assertEqual(job.state, JobState.STOPPED)
        self.assertEqual(job.stop_reason, "PROVIDER_ERROR")

        # 자동 재시도 큐에 들어가지 않음
        next_work = JobService.acquire_job_lease("worker-ai")
        self.assertIsNone(next_work)

        # Outbox에 JOB_STOPPED 기록 확인
        self.assertTrue(Outbox.objects.filter(job=job, message_kind="JOB_STOPPED").exists())

    def test_job_cancellation_queued_and_running(self):
        """작업 취소: QUEUED는 즉시 CANCELLED, RUNNING은 CANCEL_REQUESTED로 전이 검증."""
        # 1. QUEUED 취소
        job1, _ = JobService.create_job(JobKind.COLLECTION_RUN, {"k": 1}, self.user)
        c1 = JobService.cancel_job(job1.id, expected_revision=job1.revision)
        self.assertEqual(c1.state, JobState.CANCELLED)

        # 2. RUNNING 취소
        job2, _ = JobService.create_job(JobKind.COLLECTION_RUN, {"k": 2}, self.user)
        JobService.acquire_job_lease("worker-1")
        job2.refresh_from_db()
        c2 = JobService.cancel_job(job2.id, expected_revision=job2.revision)
        self.assertEqual(c2.state, JobState.CANCEL_REQUESTED)

        # revision 불일치 시 RevisionConflictError
        with self.assertRaises(RevisionConflictError):
            JobService.cancel_job(job2.id, expected_revision=999)

    def test_user_explicit_retry_from_stopped_or_failed(self):
        """A28: FAILED/STOPPED 상태에서만 명시 재시도 가능하며 QUEUED로 전이 검증."""
        manifest = {"test": "retry"}
        job, _ = JobService.create_job(JobKind.PROPOSAL_GENERATION, manifest, self.user)
        _, att = JobService.acquire_job_lease("worker-1")
        JobService.fail_job(job.id, att.fencing_token, "LLM_FAIL", RetryClass.STOP_EXTERNAL_FAILURE, stop_reason="PROVIDER_ERROR")

        job.refresh_from_db()
        self.assertEqual(job.state, JobState.STOPPED)

        # 명시 재시도 실행
        retried = JobService.retry_job(job.id, expected_revision=job.revision)
        self.assertEqual(retried.state, JobState.QUEUED)
        self.assertEqual(retried.stop_reason, "")

        # 다시 워커가 가져갈 수 있음
        res = JobService.acquire_job_lease("worker-2")
        self.assertIsNotNone(res)
        self.assertEqual(res[0].id, job.id)

    def test_outbox_dispatcher(self):
        """트랜잭셔널 아웃박스 미발행 메시지 일괄 발행 처리 검증."""
        JobService.create_job(JobKind.COLLECTION_RUN, {"o": 1}, self.user)
        JobService.create_job(JobKind.COLLECTION_RUN, {"o": 2}, self.user)

        unpub = Outbox.objects.filter(published_at__isnull=True).count()
        self.assertGreaterEqual(unpub, 2)

        dispatched = JobService.dispatch_outbox_messages(batch_size=10)
        self.assertGreaterEqual(dispatched, 2)
        self.assertEqual(Outbox.objects.filter(published_at__isnull=True).count(), 0)

    def test_automation_policy_versioning(self):
        """A10: AutomationPolicy 모델 및 불변 버전, 기본 비활성(disabled) 상태 검증."""
        policy = AutomationPolicy.objects.create(name="밤샘 공고 수집 정책", enabled=False)
        self.assertFalse(policy.enabled)

        v1 = AutomationPolicyVersion.objects.create(
            policy=policy,
            version_seq=1,
            enabled=False,
            actor=self.user,
            allowed_actions=["COLLECTION_RUN"],
            job_limit=5,
        )
        policy.current_version = v1
        policy.save()

        self.assertEqual(policy.current_version.job_limit, 5)
        self.assertFalse(policy.current_version.enabled)


class JobAPITests(TestCase):
    """작업 조회, 취소, 재시도 REST API 엔드포인트를 검증한다."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="api-reviewer",
            password=PASSWORD_FIXTURE,
            must_change_password=False,
            role="lead",
        )
        self.client = APIClient(enforce_csrf_checks=True)
        # 세션 로그인 및 CSRF 토큰 발급
        token_res = self.client.get("/api/v1/auth/csrf", secure=True)
        self.csrf_token = token_res.json()["data"]["csrf_token"]
        login_res = self.client.post(
            "/api/v1/auth/login",
            {"username": "api-reviewer", "password": PASSWORD_FIXTURE},
            format="json",
            secure=True,
            HTTP_X_CSRFTOKEN=self.csrf_token,
            HTTP_ORIGIN="https://testserver",
        )
        self.assertEqual(login_res.status_code, 200)
        self.csrf_token = self.client.get("/api/v1/auth/csrf", secure=True).json()["data"]["csrf_token"]

    def post(self, url, data):
        return self.client.post(
            url,
            data,
            format="json",
            secure=True,
            HTTP_X_CSRFTOKEN=self.csrf_token,
            HTTP_ORIGIN="https://testserver",
        )

    def test_unauthenticated_access_denied(self):
        """미인증 클라이언트는 401 반환 검증."""
        anon_client = APIClient()
        res = anon_client.get("/api/v1/jobs")
        self.assertEqual(res.status_code, 401)

    def test_must_change_password_user_denied(self):
        """암호 변경 미이행 사용자는 403 PASSWORD_CHANGE_REQUIRED 반환 검증."""
        pw_user = User.objects.create_user(
            username="temp-user",
            password=PASSWORD_FIXTURE,
            must_change_password=True,
        )
        c = APIClient(enforce_csrf_checks=True)
        tok = c.get("/api/v1/auth/csrf", secure=True).json()["data"]["csrf_token"]
        c.post(
            "/api/v1/auth/login",
            {"username": "temp-user", "password": PASSWORD_FIXTURE},
            format="json",
            secure=True,
            HTTP_X_CSRFTOKEN=tok,
            HTTP_ORIGIN="https://testserver",
        )
        res = c.get("/api/v1/jobs", secure=True)
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json()["error"]["code"], "PASSWORD_CHANGE_REQUIRED")

    def test_list_and_detail_jobs(self):
        """작업 목록 및 상세 조회가 표준 envelope로 반환되는지 검증."""
        job, _ = JobService.create_job(JobKind.COLLECTION_RUN, {"p": 1}, self.user)

        # 목록 조회
        list_res = self.client.get("/api/v1/jobs", secure=True)
        self.assertEqual(list_res.status_code, 200)
        body = list_res.json()
        self.assertIn("data", body)
        self.assertIn("page", body)
        self.assertEqual(body["page"]["total"], 1)

        # 상세 조회
        detail_res = self.client.get(f"/api/v1/jobs/{job.id}", secure=True)
        self.assertEqual(detail_res.status_code, 200)
        d_body = detail_res.json()
        self.assertEqual(d_body["data"]["id"], str(job.id))
        self.assertEqual(d_body["data"]["state"], JobState.QUEUED)

    def test_api_cancel_and_retry(self):
        """API를 통한 작업 취소 및 재시도, revision 충돌(409) 처리 검증."""
        job, _ = JobService.create_job(JobKind.COLLECTION_RUN, {"p": 2}, self.user)

        # 1. 취소 요청 (정상)
        cancel_res = self.post(f"/api/v1/jobs/{job.id}/cancel", {"expected_revision": job.revision})
        self.assertEqual(cancel_res.status_code, 200)
        self.assertEqual(cancel_res.json()["data"]["state"], JobState.CANCELLED)

        # 2. 취소된 상태에서 재취소 시도 -> 422 ValidationError
        job.refresh_from_db()
        cancel_again = self.post(f"/api/v1/jobs/{job.id}/cancel", {"expected_revision": job.revision})
        self.assertEqual(cancel_again.status_code, 422)

        # 3. 잘못된 revision으로 retry 시도 -> 409 REVISION_CONFLICT
        retry_conflict = self.post(f"/api/v1/jobs/{job.id}/retry", {"expected_revision": 999})
        self.assertEqual(retry_conflict.status_code, 409)


@skipUnless(connection.vendor == "postgresql", "requires isolated PostgreSQL")
class PostgreSQLJobConcurrencyTests(TransactionTestCase):
    """실제 PostgreSQL 17.12 클러스터 환경에서 동시 작업 점유(Lease) 경합 검증."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="concurrency-worker",
            password=PASSWORD_FIXTURE,
            must_change_password=False,
        )

    def test_concurrent_worker_lease_single_winner(self):
        """단 1개의 QUEUED 작업을 2개의 워커 스레드가 동시 점유할 때 정확히 1개 워커만 획득하는지 검증."""
        job, _ = JobService.create_job(JobKind.EXTRACTION_RUN, {"item": "race"}, self.user)

        def worker_attempt(worker_id):
            try:
                res = JobService.acquire_job_lease(worker_id=worker_id, lease_duration_seconds=30)
                return worker_id if res is not None else None
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(worker_attempt, "worker-node-alpha")
            f2 = executor.submit(worker_attempt, "worker-node-beta")
            results = [f1.result(), f2.result()]

        # 정확히 1개만 성공하고, 1개는 None이어야 함
        winners = [w for w in results if w is not None]
        self.assertEqual(len(winners), 1)

        job.refresh_from_db()
        self.assertEqual(job.state, JobState.RUNNING)
        self.assertEqual(job.lease_owner, winners[0])
        self.assertEqual(job.current_attempt, 1)
