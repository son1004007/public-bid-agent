"""작업 API 뷰 계약.
목적: 작업 목록/상세 조회, 명시 취소(/cancel), 명시 재시도(/retry) 엔드포인트를 제공한다.
경계: 세션 인증된 사용자만 접근 가능(ClosedUntilAuthentication). 원문 전문과 내부 스택트레이스를 반환하지 않는다.
부작용: /cancel 및 /retry 요청 시 JobService를 통한 원자적 상태 변경 및 Outbox 이벤트 생성.
실패: revision 불일치 시 409 Conflict, 부적절한 상태 전이 시 422 ValidationError, 미인증 시 401.
관련: docs/server-migration/18-screen-api-contract.md §50-51, 19-automation-and-provider-contract.md.
"""
import uuid
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from bid_server.core.permissions import ClosedUntilAuthentication
from bid_server.core.responses import PageResponse
from .models import Job, JobState, JobKind
from .serializers import JobSerializer, JobControlInputSerializer
from .service import (
    JobService,
    RevisionConflictError,
    InvalidStateTransitionError,
)


class Conflict(APIException):
    status_code = 409
    default_code = "REVISION_CONFLICT"


class JobListAPIView(APIView):
    permission_classes = [ClosedUntilAuthentication]

    def get(self, request):
        state = request.query_params.get("state")
        kind = request.query_params.get("kind")
        limit_str = request.query_params.get("limit", "20")

        try:
            limit = min(max(int(limit_str), 1), 100)
        except ValueError:
            limit = 20

        qs = Job.objects.all().order_by("-created_at")
        if state:
            qs = qs.filter(state=state)
        if kind:
            qs = qs.filter(kind=kind)

        total = qs.count()
        jobs = list(qs[:limit])
        serializer = JobSerializer(jobs, many=True)
        return PageResponse(serializer.data, total=total)


class JobDetailAPIView(APIView):
    permission_classes = [ClosedUntilAuthentication]

    def get(self, request, job_id):
        job = get_object_or_404(Job.objects.prefetch_related("attempts"), id=job_id)
        serializer = JobSerializer(job)
        return Response(serializer.data)


class JobCancelAPIView(APIView):
    permission_classes = [ClosedUntilAuthentication]

    def post(self, request, job_id):
        input_serializer = JobControlInputSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        expected_revision = input_serializer.validated_data["expected_revision"]

        try:
            job = JobService.cancel_job(
                job_id=job_id,
                expected_revision=expected_revision,
                actor_user=request.user,
            )
        except RevisionConflictError as exc:
            raise Conflict(str(exc))
        except InvalidStateTransitionError as exc:
            raise ValidationError({"state": [str(exc)]})

        return Response(JobSerializer(job).data, status=status.HTTP_200_OK)


class JobRetryAPIView(APIView):
    permission_classes = [ClosedUntilAuthentication]

    def post(self, request, job_id):
        input_serializer = JobControlInputSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        expected_revision = input_serializer.validated_data["expected_revision"]

        try:
            job = JobService.retry_job(
                job_id=job_id,
                expected_revision=expected_revision,
                actor_user=request.user,
            )
        except RevisionConflictError as exc:
            raise Conflict(str(exc))
        except InvalidStateTransitionError as exc:
            raise ValidationError({"state": [str(exc)]})

        return Response(JobSerializer(job).data, status=status.HTTP_200_OK)
