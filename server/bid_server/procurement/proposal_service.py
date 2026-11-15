"""DEF-02 제안서 리비전 및 전체 절 원자적 트랜잭션 관리 서비스.

목적: 제안서 절을 쪼개어 부분 저장하지 않고, 5개 표준 제안 절을 단일 트랜잭션 스냅샷으로 원자적 커밋한다.
      절별 최대 50,000자 초과 시 413 Validation 에러를 발생시키며 이전 리비전을 100% 보존한다.
관련: docs/server-migration/17-domain-and-postgresql-contract.md §99, 24-gemini-design-review-report.md (DEF-02).
"""
from typing import List, Dict, Any, Optional
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import (
    Proposal,
    ProposalRevision,
    ProposalSection,
    ProposalStatus,
    ProposalProvenance,
    RequirementMapping,
    EvidenceReference,
    Notice,
)


class RevisionConflictError(Exception):
    pass


class PayloadTooLargeError(ValueError):
    pass


class ProposalService:
    @staticmethod
    def get_or_create_proposal(notice: Notice) -> Proposal:
        """공고에 대한 제안서 작업 공간을 조회하거나 없으면 생성한다."""
        proposal, _ = Proposal.objects.get_or_create(notice=notice)
        return proposal

    @staticmethod
    def create_atomic_revision(
        proposal: Proposal,
        title: str,
        sections: List[Dict[str, Any]],
        author=None,
        status: str = ProposalStatus.AI_DRAFT,
        provenance: str = ProposalProvenance.AI_DRAFT,
        expected_parent_seq: Optional[int] = None,
        summary: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        requirement_mappings: Optional[List[Dict[str, Any]]] = None,
        evidence_references: Optional[List[Dict[str, Any]]] = None,
    ) -> ProposalRevision:
        """제안서 전체 리비전과 하위 모든 절을 단일 원자적 DB 트랜잭션으로 생성한다 (DEF-02)."""
        # 1. Validation: 절별 50,000자 상한 및 필수 필드 검사
        for sec in sections:
            body = sec.get("body", "")
            if len(body) > 50000:
                raise PayloadTooLargeError(
                    f"절 '{sec.get('title')}'의 본문 길이({len(body):,}자)가 제한(50,000자)을 초과했습니다."
                )

        with transaction.atomic():
            # 부모 Proposal 잠금 획득 (동시성 경합 방지)
            locked_proposal = Proposal.objects.select_for_update().get(id=proposal.id)

            current_rev = locked_proposal.current_revision
            current_seq = current_rev.seq if current_rev else 0

            # Expected parent seq 검증 (A03, DEF-04)
            if expected_parent_seq is not None and expected_parent_seq != current_seq:
                raise RevisionConflictError(
                    f"제안서 리비전 충돌: 최신 차수는 v{current_seq}이나, 요청은 v{expected_parent_seq}를 기준으로 생성되었습니다."
                )

            next_seq = current_seq + 1

            # 2. ProposalRevision 생성
            new_rev = ProposalRevision.objects.create(
                proposal=locked_proposal,
                seq=next_seq,
                parent_revision=current_rev,
                notice_version=locked_proposal.notice.current_version,
                status=status,
                provenance=provenance,
                author=author,
                title=title or locked_proposal.notice.notice_number + " 제안서",
                summary=summary,
                metadata=metadata or {},
            )

            # 3. ProposalSections 생성
            for idx, sec in enumerate(sections):
                ProposalSection.objects.create(
                    proposal_revision=new_rev,
                    section_key=sec.get("section_key") or f"section_{idx+1}",
                    ordinal=sec.get("ordinal", idx + 1),
                    title=sec.get("title", f"제 {idx+1} 절"),
                    body=sec.get("body", ""),
                )

            # 4. RequirementMappings 생성 (옵션)
            if requirement_mappings:
                for req in requirement_mappings:
                    RequirementMapping.objects.create(
                        proposal_revision=new_rev,
                        requirement_text=req.get("requirement_text", ""),
                        section_key=req.get("section_key", ""),
                        coverage=req.get("coverage", "FULL"),
                        locator=req.get("locator", {}),
                    )

            # 5. EvidenceReferences 생성 (옵션)
            if evidence_references:
                for ev in evidence_references:
                    EvidenceReference.objects.create(
                        proposal_revision=new_rev,
                        section_key=ev.get("section_key", ""),
                        claim_text=ev.get("claim_text", ""),
                        locator=ev.get("locator", {}),
                    )

            # 6. Proposal current_revision 갱신
            locked_proposal.current_revision = new_rev
            locked_proposal.save(update_fields=["current_revision", "updated_at"])

            return new_rev
