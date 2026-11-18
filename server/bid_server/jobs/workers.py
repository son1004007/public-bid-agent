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
                JobService.fail_job(
                    job.id, fencing_token, error_code="JOB_KIND_NOT_IMPLEMENTED",
                    retry_class=RetryClass.NON_RETRYABLE,
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
            logger.error("외부 모델 실행을 STOP 처리합니다.")
            try:
                JobService.fail_job(
                    job.id,
                    fencing_token,
                    error_code="PROVIDER_NOT_CONFIGURED" if str(p_err) == "PROVIDER_NOT_CONFIGURED" else "PROVIDER_ERROR",
                    retry_class=RetryClass.STOP_EXTERNAL_FAILURE,
                    stop_reason=str(p_err),
                )
            except FencingTokenError:
                logger.warning("작업 임대 만료로 실패 보고를 거부했습니다.")
        except Exception as e:
            logger.error("작업 실행 중 예외 발생.")
            try:
                JobService.fail_job(
                    job.id,
                    fencing_token,
                    error_code="EXECUTION_ERROR",
                    retry_class=RetryClass.RETRYABLE_TRANSIENT,
                    stop_reason="EXECUTION_ERROR",
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

        if not getattr(job.owner_user, "is_active", False) or job.owner_user.must_change_password:
            raise ProposalAccessError("Proposal access denied.")
        existing = Proposal.objects.filter(notice=notice).first()
        if existing is not None and existing.owner_user_id != job.owner_user_id:
            raise ProposalAccessError("Proposal access denied.")

        # No provider adapter/approved egress exists yet. Never claim a model
        # call from a static string or a caller-supplied simulation flag.
        if manifest.get("draft_mode") != "template":
            raise ProviderExecutionError("PROVIDER_NOT_CONFIGURED")

        proposal = ProposalService.get_or_create_proposal(notice, owner_user=job.owner_user)
        notice_title = current_nv.title if current_nv else notice.notice_number
        sections = [
            {"section_key": key, "ordinal": ordinal, "title": title,
             "body": "[미검증 템플릿] " + instruction}
            for ordinal, (key, title, instruction) in enumerate([
                ("understanding", "사업 이해", "공식 요구사항 및 사업 목표를 확인하여 작성하십시오."),
                ("strategy", "기술 및 아키텍처", "검증된 기술 역량과 요구사항 매핑을 작성하십시오."),
                ("execution", "수행 일정", "승인된 인력 및 일정 근거를 작성하십시오."),
                ("management", "품질 및 위험 관리", "검증 기준 및 위험 대응 방안을 작성하십시오."),
                ("support", "지원 및 기술 이전", "계약상 지원 범위와 수행 가능 여부를 확인하십시오."),
            ], 1)
        ]
        rev = ProposalService.create_atomic_revision(
            proposal=proposal,
            title=f"[미검증 템플릿] {notice_title}",
            sections=sections,
            author=job.owner_user,
            actor_user=job.owner_user,
            status="TEMPLATE_DRAFT",
            provenance="TEMPLATE",
            expected_parent_seq=manifest.get("expected_parent_seq"),
            summary="정적 템플릿입니다. AI 생성 및 요구사항 검증을 수행하지 않았습니다.",
            metadata={"generated_by_job": str(job.id), "source": "static_template", "verified": False},
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
