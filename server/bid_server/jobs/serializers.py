"""작업 원장 직렬화 계약.
목적: Job 및 JobAttempt 데이터를 안전한 공통 API 규격으로 직렬화하고, 취소/재시도 입력의 유효성을 검증한다.
경계: 원본 전문, 비공개 비밀, 내부 워커 스택트레이스를 노출하지 않고 정제된 필드만 반환한다.
부작용: 없음.
실패: expected_revision 누락 또는 형식 오류 시 422 ValidationError 반환.
관련: docs/server-migration/18-screen-api-contract.md §50-51, 19-automation-and-provider-contract.md.
"""
from rest_framework import serializers
from .models import Job, JobAttempt


class JobAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobAttempt
        fields = [
            "attempt_no",
            "lease_owner",
            "fencing_token",
            "started_at",
            "ended_at",
            "error_code",
            "retry_class",
            "external_request_reference",
            "result_ref",
        ]


class JobSerializer(serializers.ModelSerializer):
    attempts = JobAttemptSerializer(many=True, read_only=True)

    class Meta:
        model = Job
        fields = [
            "id",
            "kind",
            "state",
            "current_attempt",
            "max_attempts",
            "stop_reason",
            "deadline_at",
            "revision",
            "result_ref",
            "cancellation_requested_at",
            "created_at",
            "updated_at",
            "attempts",
        ]


class JobControlInputSerializer(serializers.Serializer):
    expected_revision = serializers.IntegerField(min_value=1, required=True)
