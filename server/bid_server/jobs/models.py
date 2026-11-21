"""작업 원장 및 실행 상태 저장 계약.
목적: Job 원장, JobAttempt(시도 이력), Outbox 및 AutomationPolicy 모델을 통해 유한 재시도(상한 3회), fencing token 기반 lease, 외부 모델 장애 시 STOP 정책 및 트랜잭션 outbox 패턴을 영속화한다.
경계: Celery 브로커 또는 외부 LLM API와 직접 결속하지 않으며, PostgreSQL 비즈니스 트랜잭션과 원자성을 보장한다.
부작용: Job 상태 변경 시 행 잠금(select_for_update) 하에 revision/lease_epoch 단조 증가.
실패: 동시성 경합/토큰 불일치 시 트랜잭션 롤백 및 거부.
관련: docs/server-migration/19-automation-and-provider-contract.md, 17-domain-and-postgresql-contract.md §3, 20-acceptance-and-open-decisions.md (A08, A09, A10, A27, A28).
"""
import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


class JobKind(models.TextChoices):
    COLLECTION_RUN = "COLLECTION_RUN", "공고 수집 작업"
    EXTRACTION_RUN = "EXTRACTION_RUN", "문서 추출 작업"
    CLASSIFICATION_RUN = "CLASSIFICATION_RUN", "공고 분류 작업"
    EVALUATION_RUN = "EVALUATION_RUN", "정답 평가 작업"
    PROPOSAL_GENERATION = "PROPOSAL_GENERATION", "제안서 초안 생성 작업"
    PROPOSAL_EXPORT = "PROPOSAL_EXPORT", "제안서 파일 출력 작업"
    CONNECTION_CHECK = "CONNECTION_CHECK", "공급자 연결 점검 작업"


class JobState(models.TextChoices):
    QUEUED = "QUEUED", "대기 중"
    RUNNING = "RUNNING", "실행 중"
    SUCCEEDED = "SUCCEEDED", "성공 완료"
    FAILED = "FAILED", "실패"
    CANCEL_REQUESTED = "CANCEL_REQUESTED", "취소 요청됨"
    CANCELLED = "CANCELLED", "취소 완료"
    REVIEW_REQUIRED = "REVIEW_REQUIRED", "사람 검토 필요"
    STOPPED = "STOPPED", "장애 중지 (STOP)"


class RetryClass(models.TextChoices):
    RETRYABLE_TRANSIENT = "RETRYABLE_TRANSIENT", "일시적 네트워크/서버 오류 (재시도 가능)"
    NON_RETRYABLE = "NON_RETRYABLE", "비일시적 입력/인증 오류 (재시도 불가)"
    STOP_EXTERNAL_FAILURE = "STOP_EXTERNAL_FAILURE", "외부 모델 장애/타임아웃 (즉시 STOP)"


class Job(models.Model):
    """비동기 작업 실행 원장 엔터티."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=50, choices=JobKind.choices)
    owner_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="jobs",
        help_text="작업 실행 주체 사용자",
    )
    policy_version_id = models.UUIDField(null=True, blank=True, help_text="실행 승인 정책 버전 ID")
    input_manifest = models.JSONField(default=dict, help_text="버전 참조 및 파라미터 매니페스트 (비밀/전문 제외)")
    input_digest = models.CharField(max_length=64, help_text="input_manifest의 canonical SHA-256")
    business_key = models.CharField(max_length=200, db_index=True, help_text="업무 멱등키 (kind+input_digest)")
    state = models.CharField(max_length=30, choices=JobState.choices, default=JobState.QUEUED)
    current_attempt = models.PositiveIntegerField(default=0, help_text="현재 시도 차수")
    max_attempts = models.PositiveIntegerField(default=3, help_text="최대 허용 재시도 상한 (기본 3회)")
    deadline_at = models.DateTimeField(null=True, blank=True, help_text="작업 전체 만료 마감시각")
    lease_owner = models.CharField(max_length=150, blank=True, default="", help_text="현재 점유 중인 워커 ID")
    lease_epoch = models.PositiveBigIntegerField(default=1, help_text="단조 증가 펜싱 토큰")
    lease_expires_at = models.DateTimeField(null=True, blank=True, help_text="현재 점유 임대 만료시각")
    revision = models.PositiveBigIntegerField(default=1, help_text="낙관적 락 revision")
    cancellation_requested_at = models.DateTimeField(null=True, blank=True)
    result_ref = models.JSONField(default=dict, help_text="작업 산출물 불변 참조 (ID, SHA 등)")
    stop_reason = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="장애 중지 사유 (PROVIDER_ERROR, PROVIDER_TIMEOUT, BUDGET_EXCEEDED 등)",
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["business_key"],
                condition=models.Q(state__in=["QUEUED", "RUNNING"]),
                name="unique_active_job_business_key",
            )
        ]
        indexes = [
            models.Index(fields=["state", "created_at"]),
            models.Index(fields=["kind", "state"]),
            models.Index(fields=["business_key"]),
        ]

    def __str__(self):
        return f"Job {self.id} [{self.kind}/{self.state}] (attempt={self.current_attempt}/{self.max_attempts})"


class JobAttempt(models.Model):
    """작업 시도 이력 및 펜싱 토큰 엔터티."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="attempts")
    attempt_no = models.PositiveIntegerField(help_text="시도 순번 (1부터 시작)")
    lease_owner = models.CharField(max_length=150, help_text="시도한 워커 ID")
    fencing_token = models.PositiveBigIntegerField(help_text="시도 당시 발급된 fencing token")
    heartbeat_at = models.DateTimeField(default=timezone.now, help_text="최근 하트비트 시각")
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    error_code = models.CharField(max_length=100, blank=True, default="")
    retry_class = models.CharField(max_length=50, blank=True, default="")
    result_ref = models.JSONField(default=dict)
    external_request_reference = models.CharField(
        max_length=200, blank=True, default="", help_text="외부 공급자 request_id 등 식별자"
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["job", "attempt_no"], name="unique_job_attempt_no")
        ]
        indexes = [
            models.Index(fields=["job", "-attempt_no"]),
        ]

    def __str__(self):
        return f"JobAttempt {self.job_id} #{self.attempt_no} [token={self.fencing_token}]"


class Outbox(models.Model):
    """트랜잭셔널 아웃박스 엔터티 (브로커 전달 및 이벤트 보존)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(
        Job, null=True, blank=True, on_delete=models.CASCADE, related_name="outbox_messages"
    )
    message_kind = models.CharField(max_length=100, help_text="JOB_QUEUED, JOB_SUCCEEDED, JOB_STOPPED 등")
    payload_reference = models.JSONField(default=dict, help_text="이벤트 참조 데이터")
    published_at = models.DateTimeField(null=True, blank=True, help_text="브로커/외부 전달 완료 시각")
    dispatch_attempts = models.PositiveIntegerField(default=0)
    last_attempted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=["published_at", "created_at"]),
        ]

    def __str__(self):
        return f"Outbox {self.id} [{self.message_kind}] published={self.published_at is not None}"


class AutomationPolicy(models.Model):
    """자동화 정책 논리 엔터티."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150, unique=True)
    enabled = models.BooleanField(default=False, help_text="기본값 비활성(disabled)")
    current_version = models.ForeignKey(
        "AutomationPolicyVersion",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="current_for_policy",
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"AutomationPolicy {self.name} (enabled={self.enabled})"


class AutomationPolicyVersion(models.Model):
    """자동화 정책 불변 버전 엔터티."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    policy = models.ForeignKey(AutomationPolicy, on_delete=models.CASCADE, related_name="versions")
    version_seq = models.PositiveIntegerField(default=1)
    enabled = models.BooleanField(default=False)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, help_text="승인 관리자"
    )
    allowed_actions = models.JSONField(default=list, help_text="허용된 동작 목록")
    schedule_cron = models.CharField(max_length=100, blank=True, default="")
    tz_name = models.CharField(max_length=50, default="Asia/Seoul", help_text="기준 타임존")
    job_limit = models.PositiveIntegerField(default=10)
    monetary_limit = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    transfer_scope = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["policy", "version_seq"], name="unique_policy_version_seq")
        ]

    def __str__(self):
        return f"{self.policy.name} v{self.version_seq} (enabled={self.enabled})"
