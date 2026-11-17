"""조달 공고 API 뷰 계약.
목적: 공고 목록 검색/필터링, 상세 조회, 버전 이력 조회 및 대시보드 통계 집계 엔드포인트를 제공한다.
경계: 세션 인증된 사용자만 접근 가능(ClosedUntilAuthentication). 원문 임의 수정 금지.
관련: docs/server-migration/18-screen-api-contract.md §31-35.
"""
from datetime import timedelta
import hashlib
from django.db import connection
from django.db.models import Count, Q, F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from bid_server.core.permissions import ClosedUntilAuthentication
from bid_server.core.responses import PageResponse
from .models import (
    Notice,
    NoticeVersion,
    Document,
    DocumentVersion,
    Proposal,
    ProposalRevision,
    ProposalSection,
    DocumentStructure,
    ExportArtifact,
)
from .serializers import (
    NoticeSummarySerializer,
    NoticeDetailSerializer,
    NoticeVersionHistorySerializer,
    ProposalSerializer,
    ProposalRevisionSerializer,
    DocumentStructureSerializer,
)
from .proposal_service import ProposalService, RevisionConflictError, PayloadTooLargeError
from .generator import ProposalExportService
from .extractor_service import ExtractionService
from bid_server.jobs.models import JobKind
from bid_server.jobs.service import JobService


class NoticeListAPIView(APIView):
    permission_classes = [ClosedUntilAuthentication]

    def get(self, request):
        q = request.query_params.get("q", "").strip()
        field = request.query_params.get("field", "").strip().upper()
        status_filter = request.query_params.get("status", "").strip().lower()
        buyer = request.query_params.get("buyer", "").strip()
        deadline_from = request.query_params.get("deadline_from", "").strip()
        deadline_to = request.query_params.get("deadline_to", "").strip()
        sort = request.query_params.get("sort", "deadline").strip().lower()

        limit_str = request.query_params.get("limit", "20")
        try:
            limit = min(max(int(limit_str), 1), 100)
        except ValueError:
            limit = 20

        offset_str = request.query_params.get("offset", "0")
        try:
            offset = max(int(offset_str), 0)
        except ValueError:
            offset = 0

        qs = Notice.objects.select_related("current_version").annotate(
            document_count=Count("documents")
        )

        now = timezone.now()

        # 1. 키워드 검색
        if q:
            qs = qs.filter(
                Q(current_version__title__icontains=q)
                | Q(current_version__buyer__icontains=q)
                | Q(notice_number__icontains=q)
            )

        # 2. 발주기관 검색
        if buyer:
            qs = qs.filter(current_version__buyer__icontains=buyer)

        # 3. 도메인 분류 필터 (AI, DATA, SW 등)
        if field:
            if connection.vendor == "sqlite":
                qs = qs.filter(current_version__department_categories__icontains=f'"{field}"')
            else:
                qs = qs.filter(current_version__department_categories__contains=[field])

        # 4. 상태 필터 (open, closed, cancelled)
        if status_filter == "open":
            qs = qs.filter(
                current_version__cancellation=False,
                current_version__deadline_at__gte=now,
            )
        elif status_filter in ("closed", "expired"):
            qs = qs.filter(
                current_version__cancellation=False,
                current_version__deadline_at__lt=now,
            )
        elif status_filter == "cancelled":
            qs = qs.filter(current_version__cancellation=True)

        # 5. 마감일 범위 필터
        if deadline_from:
            qs = qs.filter(current_version__deadline_at__gte=deadline_from)
        if deadline_to:
            qs = qs.filter(current_version__deadline_at__lte=deadline_to)

        # 5-1. 잔여 일수(D-Day) 최소 기준 필터
        days_left_min_str = (
            request.query_params.get("days_left_min", "")
            or request.query_params.get("d_day_min", "")
        ).strip()
        if days_left_min_str.isdigit():
            min_deadline = now + timedelta(days=int(days_left_min_str))
            qs = qs.filter(current_version__deadline_at__gte=min_deadline)

        # 5-2. 배정예산 범위 필터 (원 단위)
        budget_min_str = request.query_params.get("budget_min", "").strip()
        budget_max_str = request.query_params.get("budget_max", "").strip()
        if budget_min_str.isdigit():
            qs = qs.filter(current_version__budget_amount__gte=int(budget_min_str))
        if budget_max_str.isdigit():
            qs = qs.filter(current_version__budget_amount__lte=int(budget_max_str))

        # 6. 정렬
        if sort == "deadline":
            qs = qs.order_by(
                F("current_version__deadline_at").asc(nulls_last=True),
                "-created_at",
            )
        elif sort == "budget":
            qs = qs.order_by(
                F("current_version__budget_amount").desc(nulls_last=True),
                "-created_at",
            )
        elif sort == "observed" or sort == "newest":
            qs = qs.order_by("-current_version__observed_at", "-created_at")
        else:
            qs = qs.order_by("-created_at")

        total = qs.count()
        notices = list(qs[offset : offset + limit])

        next_cursor = None
        if offset + limit < total:
            next_cursor = str(offset + limit)

        serializer = NoticeSummarySerializer(notices, many=True)
        return PageResponse(serializer.data, next_cursor=next_cursor, total=total)


class NoticeDetailAPIView(APIView):
    permission_classes = [ClosedUntilAuthentication]

    def get(self, request, notice_id):
        notice = get_object_or_404(
            Notice.objects.select_related("current_version")
            .prefetch_related("documents__versions", "versions")
            .annotate(total_versions=Count("versions", distinct=True)),
            id=notice_id,
        )
        serializer = NoticeDetailSerializer(notice)
        return Response(serializer.data)


class NoticeVersionsAPIView(APIView):
    permission_classes = [ClosedUntilAuthentication]

    def get(self, request, notice_id):
        notice = get_object_or_404(Notice, id=notice_id)
        versions = notice.versions.order_by("-version_seq")
        serializer = NoticeVersionHistorySerializer(versions, many=True)
        return Response(serializer.data)


class DashboardAPIView(APIView):
    permission_classes = [ClosedUntilAuthentication]

    def get(self, request):
        now = timezone.now()
        urgent_window = now + timedelta(days=3)

        total_notices = Notice.objects.count()
        open_notices = Notice.objects.filter(
            current_version__cancellation=False,
            current_version__deadline_at__gte=now,
        ).count()
        cancelled_notices = Notice.objects.filter(
            current_version__cancellation=True
        ).count()

        if connection.vendor == "sqlite":
            ai_count = Notice.objects.filter(
                current_version__cancellation=False,
                current_version__department_categories__icontains='"AI"',
            ).count()
            data_count = Notice.objects.filter(
                current_version__cancellation=False,
                current_version__department_categories__icontains='"DATA"',
            ).count()
            sw_count = Notice.objects.filter(
                current_version__cancellation=False,
                current_version__department_categories__icontains='"SW"',
            ).count()
        else:
            ai_count = Notice.objects.filter(
                current_version__cancellation=False,
                current_version__department_categories__contains=["AI"],
            ).count()
            data_count = Notice.objects.filter(
                current_version__cancellation=False,
                current_version__department_categories__contains=["DATA"],
            ).count()
            sw_count = Notice.objects.filter(
                current_version__cancellation=False,
                current_version__department_categories__contains=["SW"],
            ).count()

        urgent_count = Notice.objects.filter(
            current_version__cancellation=False,
            current_version__deadline_at__gte=now,
            current_version__deadline_at__lte=urgent_window,
        ).count()

        latest_version = (
            NoticeVersion.objects.order_by("-observed_at").first()
        )
        last_sync = latest_version.observed_at.isoformat() if latest_version else None

        data = {
            "counts": {
                "total_notices": total_notices,
                "open_notices": open_notices,
                "cancelled_notices": cancelled_notices,
                "ai_candidates": ai_count,
                "data_candidates": data_count,
                "sw_candidates": sw_count,
                "urgent_deadline_3d": urgent_count,
            },
            "collection_health": {
                "status": "ONLINE",
                "source": "G2B_OFFICIAL_API",
                "last_sync_at": last_sync,
            },
            "as_of": now.isoformat(),
        }
        return Response(data)


class ProposalListAPIView(APIView):
    """제안서 목록 조회 API."""
    permission_classes = [ClosedUntilAuthentication]

    def get(self, request):
        notice_id = request.query_params.get("notice_id", "").strip()
        qs = Proposal.objects.select_related("notice", "current_revision").all()
        if notice_id:
            qs = qs.filter(notice_id=notice_id)
        serializer = ProposalSerializer(qs, many=True)
        return Response(serializer.data)


class ProposalDetailAPIView(APIView):
    """제안서 상세 및 리비전 조회 API."""
    permission_classes = [ClosedUntilAuthentication]

    def get(self, request, pk):
        proposal = get_object_or_404(
            Proposal.objects.select_related("notice", "current_revision"), pk=pk
        )
        serializer = ProposalSerializer(proposal)
        return Response(serializer.data)


class ProposalRevisionCreateAPIView(APIView):
    """DEF-02: 제안서 신규 리비전 및 전체 절 원자적 커밋 API."""
    permission_classes = [ClosedUntilAuthentication]

    def post(self, request, pk):
        proposal = get_object_or_404(Proposal, pk=pk)
        data = request.data or {}

        title = data.get("title", "")
        sections = data.get("sections", [])
        expected_parent_seq = data.get("expected_parent_seq")
        summary = data.get("summary", "")

        try:
            new_rev = ProposalService.create_atomic_revision(
                proposal=proposal,
                title=title,
                sections=sections,
                author=request.user,
                expected_parent_seq=expected_parent_seq,
                summary=summary,
                provenance="HUMAN",
                status="EDITED",
            )
            serializer = ProposalRevisionSerializer(new_rev)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except PayloadTooLargeError as p_err:
            return Response(
                {"error": "PAYLOAD_TOO_LARGE", "detail": str(p_err)},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
        except RevisionConflictError as c_err:
            return Response(
                {"error": "REVISION_CONFLICT", "detail": str(c_err)},
                status=status.HTTP_409_CONFLICT,
            )


class ProposalExportAPIView(APIView):
    """A29: 제안서 HWPX/DOCX 산출물 생성 및 바이너리 다운로드 API."""
    permission_classes = [ClosedUntilAuthentication]

    def perform_content_negotiation(self, request, force=False):
        # DRF 기본 컨텐트 협상은 '?format=' 쿼리를 포맷 접미사 필터로 취급하여 404를 발생시킴.
        # 파일 다운로드 및 JSON 오류 응답을 안전하게 처리하기 위해 기본 렌더러를 직접 반환.
        renderers = self.get_renderers()
        return (renderers[0], renderers[0].media_type)

    def get(self, request, pk):
        try:
            proposal = Proposal.objects.select_related("current_revision", "notice").get(pk=pk)
        except Proposal.DoesNotExist:
            return Response({"error": "PROPOSAL_NOT_FOUND"}, status=status.HTTP_404_NOT_FOUND)

        rev = proposal.current_revision
        if not rev:
            return Response(
                {"error": "NO_REVISION", "detail": "제안서 리비전이 존재하지 않습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        fmt = request.query_params.get("format", "hwpx").strip().lower()
        try:
            raw_bytes, file_name, sha256_hash, size_bytes = ProposalExportService.export_proposal_revision(
                rev, fmt
            )
        except ValueError as v_err:
            return Response(
                {"error": "INVALID_FORMAT", "detail": str(v_err)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # GET is a read-only, on-demand download. Do not persist an artifact
        # record for bytes that are not actually stored at storage_path.
        # A future persisted export must use a separately authorized POST.

        content_type = (
            "application/x-hwp" if fmt == "hwpx"
            else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        response = HttpResponse(raw_bytes, content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{file_name}"'
        response["X-Artifact-SHA256"] = sha256_hash
        return response


class DocumentExtractAPIView(APIView):
    """DEF-03: 첨부문서 파싱 및 구조 추출 실행 API."""
    permission_classes = [ClosedUntilAuthentication]

    def post(self, request, pk):
        doc_version = get_object_or_404(
            DocumentVersion.objects.select_related("document"), pk=pk
        )
        # No synthetic fallback: only explicitly supplied source bytes may be parsed.
        # This endpoint currently accepts plain-text payloads only; binary document
        # formats require a separately validated upload/storage contract.
        if request.content_type not in ("text/plain", "application/octet-stream"):
            return Response(
                {"error": "UNSUPPORTED_MEDIA_TYPE"},
                status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            )
        raw_bytes = request.body
        if len(raw_bytes) < 4:
            return Response(
                {"error": "DOCUMENT_BODY_REQUIRED"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(raw_bytes) > 10 * 1024 * 1024:
            return Response(
                {"error": "DOCUMENT_TOO_LARGE"},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

        # The extraction must be bound to the immutable source document version.
        # A valid-looking arbitrary payload is not evidence of the stored RFP.
        if (
            len(raw_bytes) != doc_version.size_bytes
            or hashlib.sha256(raw_bytes).hexdigest() != doc_version.sha256.lower()
        ):
            return Response(
                {"error": "DOCUMENT_SOURCE_MISMATCH"},
                status=status.HTTP_409_CONFLICT,
            )

        run = ExtractionService.extract_and_persist(
            document_version=doc_version,
            raw_bytes=raw_bytes,
            file_name=doc_version.document.logical_key + ".txt",
        )
        return Response({
            "extraction_run_id": str(run.id),
            "state": run.state,
            "coverage": run.coverage,
            "warnings": run.warnings,
        }, status=status.HTTP_201_CREATED)


class DocumentStructureAPIView(APIView):
    """DEF-03: 추출된 문서 구조(표/각주 포함) 조회 API."""
    permission_classes = [ClosedUntilAuthentication]

    def get(self, request, pk):
        doc_version = get_object_or_404(DocumentVersion, pk=pk)
        structures = DocumentStructure.objects.filter(document_version=doc_version)
        serializer = DocumentStructureSerializer(structures, many=True)
        return Response(serializer.data)
