"""작업 원장 트랜잭션 및 실행 제어 계약.
목적: Job 생성, Fencing Token 기반 워커 Lease 점유, 하트비트, 성공 완료, 외부 장애 STOP, 취소 및 명시 재시도 서비스를 원자적으로 제공한다.
경계: 외부 Celery 프로세스 및 LLM 공급자 호출의 불확실성을 격리하고, PostgreSQL select_for_update 행 잠금으로 멱등성과 상태 전이를 보장한다.
부작용: Job 상태 변경 시 revision 증가 및 Outbox 이벤트 행 동시 커밋.
실패: 만료된 펜싱 토큰(A08), 낙관적 락 충돌(409), 허용되지 않은 상태 전이 시 예외 발생 및 롤백.
관련: docs/server-migration/19-automation-and-provider-contract.md, 20-acceptance-and-open-decisions.md (A08, A09, A10, A27, A28).
"""
import hashlib
import json
import uuid
from datetime import timedelta
from typing import Any
from django.db import transaction, models
from django.utils import timezone
from .models import (
    Job,
    JobAttempt,
    Outbox,
    JobState,
    JobKind,
    RetryClass,
)


class FencingTokenError(Exception):
    """만료되었거나 유효하지 않은 펜싱 토큰으로 결과를 게시하려 할 때 발생 (A08)."""
    pass


class RevisionConflictError(Exception):
    """낙관적 락 revision 불일치 시 발생 (409 CONFLICT)."""
    pass


class InvalidStateTransitionError(Exception):
    """허용되지 않은 작업 상태 전이 시도 시 발생."""
    pass


class ActiveJobConflictError(Exception):
    """동일한 business_key를 가진 활성(QUEUED/RUNNING) 작업이 이미 존재할 때 발생."""
    pass


def compute_manifest_digest(manifest: dict[str, Any]) -> str:
    """작업 매니페스트의 canonical SHA-256 해시를 산출한다."""
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class JobService:
    """비동기 작업 원장 관리 및 상태 전이 서비스."""

    @staticmethod
    def create_job(
        kind: str,
        input_manifest: dict[str, Any],
        owner_user=None,
        policy_version_id: uuid.UUID = None,
        max_attempts: int = 3,
        business_key: str | None = None,
        deadline_at=None,
    ) -> tuple[Job, bool]:
        """새로운 작업을 생성하거나 동일한 business_key를 가진 기존 활성 작업을 반환한다 (멱등성 보장)."""
        digest = compute_manifest_digest(input_manifest)
        if not business_key:
            business_key = f"{kind}:{digest}"

        with transaction.atomic():
            # 활성 상태(QUEUED, RUNNING)의 동일 작업 확인
            existing_active = (
                Job.objects.select_for_update()
                .filter(business_key=business_key, state__in=[JobState.QUEUED, JobState.RUNNING])
                .first()
            )
            if existing_active:
                return existing_active, False

            job = Job.objects.create(
                kind=kind,
                owner_user=owner_user,
                policy_version_id=policy_version_id,
                input_manifest=input_manifest,
                input_digest=digest,
                business_key=business_key,
                state=JobState.QUEUED,
                current_attempt=0,
                max_attempts=max_attempts,
                deadline_at=deadline_at,
                revision=1,
            )

            # 트랜잭셔널 아웃박스 동시 기록
            Outbox.objects.create(
                job=job,
                message_kind="JOB_QUEUED",
                payload_reference={
                    "job_id": str(job.id),
                    "kind": kind,
                    "input_digest": digest,
                    "business_key": business_key,
                },
            )
            return job, True

    @staticmethod
    def acquire_job_lease(
        worker_id: str,
        kind: str | None = None,
        lease_duration_seconds: int = 60,
    ) -> tuple[Job, JobAttempt] | None:
        """워커가 다음 대기 작업을 안전하게 점유(Lease)하고 fencing token을 발급받는다."""
        now = timezone.now()
        with transaction.atomic():
            qs = Job.objects.select_for_update(skip_locked=True).order_by("created_at")
            if kind:
                qs = qs.filter(kind=kind)

            # 1. QUEUED 작업 우선, 또는 2. lease 만료된 RUNNING 작업(워커 장애 복구)
            candidate = qs.filter(
                models.Q(state=JobState.QUEUED)
                | (models.Q(state=JobState.RUNNING) & models.Q(lease_expires_at__lt=now))
            ).first()

            if not candidate:
                return None

            job = candidate

            # 취소 요청 여부 사전 점검
            if job.cancellation_requested_at:
                job.state = JobState.CANCELLED
                job.revision += 1
                job.save(update_fields=["state", "revision", "updated_at"])
                Outbox.objects.create(
                    job=job,
                    message_kind="JOB_CANCELLED",
                    payload_reference={"job_id": str(job.id), "reason": "CANCELLED_BEFORE_LEASE"},
                )
                return None

            next_attempt = job.current_attempt + 1
            if next_attempt > job.max_attempts:
                # 유한 재시도 상한 초과 (A09)
                job.state = JobState.FAILED
                job.stop_reason = "MAX_ATTEMPTS_EXCEEDED"
                job.revision += 1
                job.save(update_fields=["state", "stop_reason", "revision", "updated_at"])
                Outbox.objects.create(
                    job=job,
                    message_kind="JOB_FAILED",
                    payload_reference={"job_id": str(job.id), "reason": "MAX_ATTEMPTS_EXCEEDED"},
                )
                return None

            # Fencing token (단조 증가)
            job.lease_epoch += 1
            job.current_attempt = next_attempt
            job.lease_owner = worker_id
            job.lease_expires_at = now + timedelta(seconds=lease_duration_seconds)
            job.state = JobState.RUNNING
            job.revision += 1
            job.save(update_fields=[
                "lease_epoch", "current_attempt", "lease_owner", "lease_expires_at",
                "state", "revision", "updated_at"
            ])

            attempt = JobAttempt.objects.create(
                job=job,
                attempt_no=next_attempt,
                lease_owner=worker_id,
                fencing_token=job.lease_epoch,
                heartbeat_at=now,
                started_at=now,
            )

            Outbox.objects.create(
                job=job,
                message_kind="JOB_RUNNING",
                payload_reference={
                    "job_id": str(job.id),
                    "attempt_no": next_attempt,
                    "worker_id": worker_id,
                    "fencing_token": job.lease_epoch,
                },
            )

            return job, attempt

    @staticmethod
    def send_heartbeat(job_id: uuid.UUID, fencing_token: int, extend_seconds: int = 60) -> bool:
        """워커의 활성 상태를 알리고 임대(Lease) 만료를 연장한다."""
        now = timezone.now()
        with transaction.atomic():
            job = Job.objects.select_for_update().filter(id=job_id).first()
            if (not job or job.state != JobState.RUNNING or job.lease_epoch != fencing_token
                    or job.lease_expires_at is None or job.lease_expires_at <= now):
                return False

            job.lease_expires_at = now + timedelta(seconds=extend_seconds)
            job.save(update_fields=["lease_expires_at", "updated_at"])

            JobAttempt.objects.filter(job=job, attempt_no=job.current_attempt).update(
                heartbeat_at=now
            )
            return True

    @staticmethod
    def complete_job(
        job_id: uuid.UUID,
        fencing_token: int,
        result_ref: dict[str, Any],
    ) -> Job:
        """작업을 정상 완료 처리하고 산출물 참조를 원자적으로 게시한다 (A08)."""
        now = timezone.now()
        with transaction.atomic():
            job = Job.objects.select_for_update().filter(id=job_id).first()
            if not job:
                raise ValueError("작업을 찾을 수 없습니다.")

            # Stale Fencing Token 방어: 임대가 만료되었거나 다른 워커에게 넘어간 경우 게시 거부
            if (job.lease_epoch != fencing_token or job.state != JobState.RUNNING
                    or job.lease_expires_at is None or job.lease_expires_at <= now):
                raise FencingTokenError(
                    f"Fencing token 유효성 검증 실패 (job_token={job.lease_epoch}, provided={fencing_token}, state={job.state})."
                )

            # 취소 요청이 있었던 경우 완료 대신 취소로 종결
            if job.cancellation_requested_at:
                job.state = JobState.CANCELLED
                job.lease_owner = ""
                job.lease_expires_at = None
                job.revision += 1
                job.save(update_fields=["state", "lease_owner", "lease_expires_at", "revision", "updated_at"])
                Outbox.objects.create(
                    job=job,
                    message_kind="JOB_CANCELLED",
                    payload_reference={"job_id": str(job.id), "reason": "CANCEL_PREVAILS"},
                )
                return job

            job.state = JobState.SUCCEEDED
            job.result_ref = result_ref
            job.lease_owner = ""
            job.lease_expires_at = None
            job.revision += 1
            job.save(update_fields=["state", "result_ref", "lease_owner", "lease_expires_at", "revision", "updated_at"])

            JobAttempt.objects.filter(job=job, attempt_no=job.current_attempt).update(
                ended_at=now,
                result_ref=result_ref,
            )

            Outbox.objects.create(
                job=job,
                message_kind="JOB_SUCCEEDED",
                payload_reference={"job_id": str(job.id), "result_ref": result_ref},
            )
            return job

    @staticmethod
    def fail_job(
        job_id: uuid.UUID,
        fencing_token: int,
        error_code: str,
        retry_class: str = RetryClass.NON_RETRYABLE,
        stop_reason: str = "",
        external_request_reference: str = "",
    ) -> Job:
        """작업 실패 처리 및 확정 정책에 따른 즉시 STOP 또는 유한 재시도 분기 (A27)."""
        now = timezone.now()
        with transaction.atomic():
            job = Job.objects.select_for_update().filter(id=job_id).first()
            if not job:
                raise ValueError("작업을 찾을 수 없습니다.")

            if job.lease_epoch != fencing_token:
                raise FencingTokenError("Fencing token이 일치하지 않습니다.")

            JobAttempt.objects.filter(job=job, attempt_no=job.current_attempt).update(
                ended_at=now,
                error_code=error_code,
                retry_class=retry_class,
                external_request_reference=external_request_reference,
            )

            # 확정 정책: 외부 모델 장애/타임아웃 발생 시 즉시 STOP (A27)
            is_external_stop = (
                retry_class == RetryClass.STOP_EXTERNAL_FAILURE
                or stop_reason in ["PROVIDER_ERROR", "PROVIDER_TIMEOUT", "PROVIDER_RESULT_UNKNOWN", "BUDGET_EXCEEDED"]
            )

            if is_external_stop:
                job.state = JobState.STOPPED
                job.stop_reason = stop_reason or error_code
                outbox_kind = "JOB_STOPPED"
            elif retry_class == RetryClass.RETRYABLE_TRANSIENT and job.current_attempt < job.max_attempts:
                # 일시적 오류이며 재시도 한도 미만인 경우 대기열로 복귀 (A09)
                job.state = JobState.QUEUED
                job.stop_reason = ""
                outbox_kind = "JOB_QUEUED"
            else:
                job.state = JobState.FAILED
                job.stop_reason = error_code
                outbox_kind = "JOB_FAILED"

            job.lease_owner = ""
            job.lease_expires_at = None
            job.revision += 1
            job.save(update_fields=["state", "stop_reason", "lease_owner", "lease_expires_at", "revision", "updated_at"])

            Outbox.objects.create(
                job=job,
                message_kind=outbox_kind,
                payload_reference={
                    "job_id": str(job.id),
                    "error_code": error_code,
                    "stop_reason": job.stop_reason,
                    "attempt_no": job.current_attempt,
                },
            )
            return job

    @staticmethod
    def cancel_job(
        job_id: uuid.UUID,
        expected_revision: int | None = None,
        actor_user=None,
    ) -> Job:
        """작업 취소를 요청하거나 즉시 취소한다."""
        now = timezone.now()
        with transaction.atomic():
            job = Job.objects.select_for_update().filter(id=job_id).first()
            if not job:
                raise ValueError("작업을 찾을 수 없습니다.")

            if expected_revision is not None and job.revision != expected_revision:
                raise RevisionConflictError(
                    f"Job revision 충돌 (expected={expected_revision}, current={job.revision})"
                )

            if job.state == JobState.QUEUED:
                job.state = JobState.CANCELLED
                job.cancellation_requested_at = now
                outbox_kind = "JOB_CANCELLED"
            elif job.state == JobState.RUNNING:
                job.state = JobState.CANCEL_REQUESTED
                job.cancellation_requested_at = now
                outbox_kind = "JOB_CANCEL_REQUESTED"
            else:
                raise InvalidStateTransitionError(
                    f"종결된 상태({job.state})의 작업은 취소할 수 없습니다."
                )

            job.revision += 1
            job.save(update_fields=["state", "cancellation_requested_at", "revision", "updated_at"])

            Outbox.objects.create(
                job=job,
                message_kind=outbox_kind,
                payload_reference={"job_id": str(job.id), "state": job.state},
            )
            return job

    @staticmethod
    def retry_job(
        job_id: uuid.UUID,
        expected_revision: int | None = None,
        actor_user=None,
    ) -> Job:
        """사용자의 명시적 지시에 따라 실패 또는 중지된 작업을 대기열로 재개한다 (A28)."""
        with transaction.atomic():
            job = Job.objects.select_for_update().filter(id=job_id).first()
            if not job:
                raise ValueError("작업을 찾을 수 없습니다.")

            if expected_revision is not None and job.revision != expected_revision:
                raise RevisionConflictError(
                    f"Job revision 충돌 (expected={expected_revision}, current={job.revision})"
                )

            # 명시 재개 허용 상태 (FAILED, STOPPED, REVIEW_REQUIRED)
            if job.state not in [JobState.FAILED, JobState.STOPPED, JobState.REVIEW_REQUIRED]:
                raise InvalidStateTransitionError(
                    f"상태가 {job.state}인 작업은 명시 재시도할 수 없습니다 (FAILED/STOPPED/REVIEW_REQUIRED만 허용)."
                )

            job.state = JobState.QUEUED
            job.stop_reason = ""
            job.cancellation_requested_at = None
            job.revision += 1
            job.save(update_fields=["state", "stop_reason", "cancellation_requested_at", "revision", "updated_at"])

            Outbox.objects.create(
                job=job,
                message_kind="JOB_QUEUED",
                payload_reference={"job_id": str(job.id), "manual_retry": True},
            )
            return job

    @staticmethod
    def dispatch_outbox_messages(batch_size: int = 50) -> int:
        """미발행 Outbox 메시지를 원자적으로 조회하여 발행 처리한다."""
        now = timezone.now()
        with transaction.atomic():
            messages = list(
                Outbox.objects.select_for_update(skip_locked=True)
                .filter(published_at__isnull=True)
                .order_by("created_at")[:batch_size]
            )
            count = 0
            for msg in messages:
                msg.published_at = now
                msg.dispatch_attempts += 1
                msg.last_attempted_at = now
                msg.save(update_fields=["published_at", "dispatch_attempts", "last_attempted_at"])
                count += 1
            return count
