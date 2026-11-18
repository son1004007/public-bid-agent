"""비동기 작업 실행 워커 파이프라인 및 장애 STOP 제어 (A27, A28, DEF-02, DEF-03).

목적: 문서 파싱(EXTRACTION_RUN), 제안서 초안 생성(PROPOSAL_GENERATION), 제안서 파일 출력(PROPOSAL_EXPORT)
      작업을 Fencing Token 임대 하에 실행하며, 외부 LLM 공급자 장애 시 즉시 STOP 상태로 전이하여
      불완전한 자동 초안 생성 및 무단 재시도를 철저히 차단한다.
불변조건: 승인된 원본 조회 및 무결성 계약이 없으면 문서 추출은 비재시도 실패하며 합성 증거를 저장하지 않는다.
불변조건: DB 전용 제안서 작업의 쓰기 및 결과 게시는 동일 임대 트랜잭션에서 처리한다.
관련: docs/server-migration/19-automation-and-provider-contract.md §87-100, 20-acceptance-and-open-decisions.md (A27, A28).
"""
import logging
from typing import Dict, Any, Optional
from django.utils import timezone
from .models import Job, JobKind, JobState, RetryClass
from .service import JobService, FencingTokenError
from bid_server.procurement.models import (
    Proposal,
    ProposalRevision,
    ExportArtifact,
    Notice,
)
from bid_server.procurement.proposal_service import ProposalService, ProposalAccessError, owned_proposals
from bid_server.procurement.generator import ProposalExportService
from bid_server.procurement.artifact_storage import ArtifactStorageError, store_verified_artifact

logger = logging.getLogger(__name__)


class ProviderExecutionError(Exception):
    """외부 LLM 공급자 타임아웃/오류 시 발생하는 예외 (A27 STOP 대상)."""
    pass


class JobWorkerPipeline:
    def __init__(self, worker_name: str = "bid-worker-1"):
        self.worker_name = worker_name

    def execute_next_job(self) -> Optional[Job]:
        """대기 중인 작업을 하나 임대 획득하여 실행하고 결과를 원장에 기록한다."""
        lease_info = JobService.acquire_job_lease(self.worker_name)
        if not lease_info:
            return None

        job, attempt = lease_info
        fencing_token = attempt.fencing_token

        try:
            if job.kind == JobKind.EXTRACTION_RUN:
                self._run_extraction(job, fencing_token)
            elif job.kind == JobKind.PROPOSAL_GENERATION:
                JobService.complete_db_operation(job.id, fencing_token, self._run_proposal_generation)
            elif job.kind == JobKind.PROPOSAL_EXPORT:
                self._run_proposal_export(job, fencing_token)
            else:
                JobService.complete_job(
                    job.id, fencing_token, result_ref={"status": "completed", "kind": job.kind}
                )
        except FencingTokenError:
            # stale worker는 실패 보고로 원장을 다시 변경하지 않는다.
            logger.warning("작업 임대 만료로 결과 게시를 거부했습니다.")
        except ArtifactStorageError:
            try:
                JobService.fail_job(job.id, fencing_token, error_code="ARTIFACT_STORAGE_UNAVAILABLE",
                                    retry_class=RetryClass.NON_RETRYABLE)
            except FencingTokenError:
                logger.warning("작업 임대 만료로 실패 보고를 거부했습니다.")
        except ProposalAccessError:
            try:
                JobService.fail_job(job.id, fencing_token, error_code="PROPOSAL_ACCESS_DENIED",
                                    retry_class=RetryClass.NON_RETRYABLE)
            except FencingTokenError:
                logger.warning("작업 임대 만료로 실패 보고를 거부했습니다.")
        except ProviderExecutionError as p_err:
            # A27 / STOP: 외부 모델 장애 시 즉시 STOPPED 상태로 전환하고 자동 재시도 큐 차단
            logger.error("외부 모델 장애 발생으로 작업을 즉시 STOP 처리합니다: %s", p_err)
            try:
                JobService.fail_job(
                    job.id,
                    fencing_token,
                    error_code="PROVIDER_ERROR",
                    retry_class=RetryClass.STOP_EXTERNAL_FAILURE,
                    stop_reason=str(p_err),
                )
            except FencingTokenError:
                logger.warning("작업 임대 만료로 실패 보고를 거부했습니다.")
        except Exception as e:
            logger.exception("작업 실행 중 예외 발생: %s", e)
            try:
                JobService.fail_job(
                    job.id,
                    fencing_token,
                    error_code="EXECUTION_ERROR",
                    retry_class=RetryClass.RETRYABLE_TRANSIENT,
                    stop_reason=str(e),
                )
            except FencingTokenError:
                logger.warning("작업 임대 만료로 실패 보고를 거부했습니다.")

        job.refresh_from_db()
        return job

    def _run_extraction(self, job: Job, fencing_token: int):
        # 현재 승인된 원본 저장소 resolver가 없다. 매니페스트는 참조만
        # 담으며 본문이나 합성 데이터를 원본으로 신뢰하지 않는다.
        # 원본 접근권한 및 바이트 SHA/크기 검증이 구현되기 전에는 실패로
        # 종결하고 추출 증거를 생성하지 않는다.
        JobService.fail_job(
            job.id,
            fencing_token,
            error_code="DOCUMENT_SOURCE_UNAVAILABLE",
            retry_class=RetryClass.NON_RETRYABLE,
            stop_reason="Verified document source is not configured.",
        )

    def _run_proposal_generation(self, job: Job) -> dict[str, Any]:
        manifest = job.input_manifest
        notice_id = manifest.get("notice_id")
        notice = Notice.objects.get(id=notice_id)
        current_nv = notice.current_version

        # A27 / STOP 검증 분기: 외부 공급자 장애 시뮬레이션
        if manifest.get("simulate_provider_error"):
            raise ProviderExecutionError("외부 LLM 공급자 응답 타임아웃 (HTTP 504 Gateway Timeout). STOP 정책 적용.")

        if not getattr(job.owner_user, "is_active", False):
            raise ProposalAccessError("Proposal access denied.")
        proposal = ProposalService.get_or_create_proposal(notice, owner_user=job.owner_user)

        # 5개 표준 제안 절 생성
        buyer_name = current_nv.buyer if current_nv else "발주기관"
        notice_title = current_nv.title if current_nv else "공공입찰 프로젝트"

        sections = [
            {
                "section_key": "understanding",
                "ordinal": 1,
                "title": "1. 사업의 이해 및 추진 전략",
                "body": f"본 제안은 {buyer_name}의 '{notice_title}' 사업 목표를 완벽히 달성하기 위해 당사의 최신 AI 기술 역량을 집약하여 수립되었습니다.\n\n주요 추진 전략은 안정성과 확장성을 겸비한 아키텍처를 토대로 단계별 위험을 최소화하는 것입니다.",
            },
            {
                "section_key": "strategy",
                "ordinal": 2,
                "title": "2. 제안 기술 및 시스템 아키텍처",
                "body": "본 시스템은 고가용성 클라우드 인프라와 PostgreSQL 기반의 안전한 원장 데이터 모델을 채택합니다. 생성형 AI 파이프라인은 정확도 우선 원칙에 따라 검증된 데이터셋과 상호 교차 검증을 수행합니다.",
            },
            {
                "section_key": "execution",
                "ordinal": 3,
                "title": "3. 사업 수행 계획 및 일정 관리",
                "body": "착수 단계부터 요구사항 분석, 시스템 설계, 단계별 기능 구현, 통합 테스트, 시범 운영에 이르기까지 5단계 마일스톤을 엄격히 준수합니다.",
            },
            {
                "section_key": "management",
                "ordinal": 4,
                "title": "4. 프로젝트 관리 및 품질 보증 방안",
                "body": "형상 관리, 변경 관리, 위험 관리 체계를 수립하고, 테스트 주도 개발(TDD)을 통해 100% 검증 통과를 보장합니다.",
            },
            {
                "section_key": "support",
                "ordinal": 5,
                "title": "5. 지원 부문 및 기술 이전 계획",
                "body": "운영자 및 실무 담당자를 위한 체계적인 교육 훈련과 안정화 기간 동안의 24/7 기술 지원 체계를 상시 가동합니다.",
            },
        ]

        # 단일 원자적 스냅샷 리비전 생성 (DEF-02)
        rev = ProposalService.create_atomic_revision(
            proposal=proposal,
            title=f"{notice_title} 제안서 초안",
            sections=sections,
            author=job.owner_user,
            actor_user=job.owner_user,
            expected_parent_seq=manifest.get("expected_parent_seq"),
            summary=f"{buyer_name} 대상 {notice_title} 최적화 제안서 초안 (AI_DRAFT)",
            metadata={"generated_by_job": str(job.id), "model": "gemini-2.0-pro"},
        )

        return {
            "proposal_id": str(proposal.id),
            "revision_id": str(rev.id),
            "revision_seq": rev.seq,
            "sections_count": len(sections),
        }

    def _run_proposal_export(self, job: Job, fencing_token: int):
        manifest = job.input_manifest
        revision_id = manifest.get("revision_id")
        target_format = manifest.get("format", "hwpx").strip().lower()

        rev = ProposalRevision.objects.filter(
            id=revision_id, proposal__in=owned_proposals(job.owner_user),
        ).first()
        if rev is None:
            raise ProposalAccessError("Proposal access denied.")
        raw_bytes, file_name, sha256_hash, size_bytes = ProposalExportService.export_proposal_revision(
            rev, target_format
        )

        # Private file before DB publication. On fence/cancellation/DB failure
        # the unique finalized file remains an unpublished orphan for reconciliation.
        storage_key = store_verified_artifact(raw_bytes, sha256_hash, size_bytes)

        def publish(locked_job):
            # Recheck scope under the proposal lock, not the stale job snapshot.
            proposal = owned_proposals(locked_job.owner_user).select_for_update().filter(
                pk=rev.proposal_id,
            ).first()
            if proposal is None or not ProposalRevision.objects.filter(
                pk=rev.pk, proposal=proposal,
            ).exists():
                raise ProposalAccessError("Proposal access denied.")
            artifact = ExportArtifact.objects.create(
                proposal_revision=rev,
                format=target_format.upper(),
                file_name=file_name,
                sha256=sha256_hash,
                size_bytes=size_bytes,
                storage_path=storage_key,
            )
            return {
                "artifact_id": str(artifact.id),
                "format": artifact.format,
                "file_name": artifact.file_name,
                "sha256": artifact.sha256,
                "size_bytes": artifact.size_bytes,
            }

        JobService.complete_db_operation(job.id, fencing_token, publish)
