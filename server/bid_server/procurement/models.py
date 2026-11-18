"""조달 도메인 저장 계약.
목적: 공고·원본 문서의 버전 이력 불변성 보존, 구조화 추출(DEF-03 표·각주) 및 레거시 데이터 이관 멱등키를 영속화한다.
경계: 외부 LLM이나 실제 공고 API와 직접 통신하지 않으며, 승인된 DB 스키마 제약과 트랜잭션을 강제한다.
부작용: 공고 버전 갱신 시 Notice 행 잠금 및 단조 증가 version_seq 할당. 기존 버전은 덮어쓰거나 삭제하지 않는다.
실패: 불변조건(유일성, FK, 표 경계, 순환 참조) 위반 시 전체 트랜잭션 rollback.
관련: docs/server-migration/17-domain-and-postgresql-contract.md, 20-acceptance-and-open-decisions.md (A05, A06, A15, A25).
"""
import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone
from .validators import validate_table_grid, validate_block_hierarchy, validate_footnote_anchors


class DeadlineStatus(models.TextChoices):
    PARSED = "PARSED", "정상 파싱"
    DATE_ONLY = "DATE_ONLY", "날짜만 확인"
    AMBIGUOUS = "AMBIGUOUS", "모호한 기한"
    EXPIRED = "EXPIRED", "기한 경과"
    UNKNOWN = "UNKNOWN", "미확인"


class DocumentFreshness(models.TextChoices):
    CURRENT = "CURRENT", "최신 유효"
    STALE = "STALE", "구버전 대체됨"
    REVIEW_REQUIRED = "REVIEW_REQUIRED", "재검토 필요"
    UNVERIFIED = "UNVERIFIED", "미확인"


class ExtractionState(models.TextChoices):
    PENDING = "PENDING", "추출 대기"
    PARSED = "PARSED", "추출 완료"
    UNKNOWN = "UNKNOWN", "추출 미확인"
    FAILED = "FAILED", "추출 실패"
    NOT_APPLICABLE = "NOT_APPLICABLE", "해당 없음"


class ChunkCategory(models.TextChoices):
    GENERAL = "GENERAL", "일반 정보"
    QUALIFICATION = "QUALIFICATION", "참가 자격"
    REQUIREMENT = "REQUIREMENT", "요구사항"
    EVALUATION = "EVALUATION", "평가 기준"
    SCHEDULE = "SCHEDULE", "추진 일정"
    SUBMISSION = "SUBMISSION", "제출 서류"
    BUDGET = "BUDGET", "사업 예산"


class ChunkPath(models.TextChoices):
    TEXT = "TEXT", "일반 본문"
    TABLE = "TABLE", "표 추출"
    FOOTNOTE = "FOOTNOTE", "각주 추출"
    OCR = "OCR", "OCR 인식"


class Notice(models.Model):
    """논리적 조달 공고 엔터티."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.CharField(max_length=40, help_text="공고 출처(예: G2B_OFFICIAL_API, SYNTHETIC_FIXTURE)")
    notice_number = models.CharField(max_length=100, help_text="공식 공고번호")
    current_version = models.ForeignKey(
        "NoticeVersion",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="current_for_notice",
        help_text="현재 최신 공고 버전 포인터",
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["source", "notice_number"], name="unique_notice_source_number")
        ]
        indexes = [
            models.Index(fields=["source", "notice_number"]),
        ]

    def __str__(self):
        return f"[{self.source}] {self.notice_number}"


class NoticeVersion(models.Model):
    """공고의 특정 관측 시점 불변 버전."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notice = models.ForeignKey(Notice, on_delete=models.CASCADE, related_name="versions")
    version_seq = models.PositiveIntegerField(help_text="공고 내 단조 증가 차수 (1부터 시작)")
    source_revision = models.CharField(max_length=100, null=True, blank=True, help_text="공식 기관 공고 차수")
    observed_at = models.DateTimeField(help_text="수집 관측 시각")
    title = models.CharField(max_length=500)
    buyer = models.CharField(max_length=300)
    source_url = models.TextField(blank=True, default="")
    deadline_raw = models.CharField(max_length=300, blank=True, default="")
    deadline_at = models.DateTimeField(null=True, blank=True)
    deadline_status = models.CharField(
        max_length=30, choices=DeadlineStatus.choices, default=DeadlineStatus.UNKNOWN
    )
    cancellation = models.BooleanField(default=False, help_text="공식 취소 공고 여부")
    correction = models.BooleanField(default=False, help_text="정정 공고 여부")
    budget_amount = models.BigIntegerField(null=True, blank=True, help_text="배정 예산(원)")
    department_categories = models.JSONField(default=list, help_text="선정 부서 카테고리 (AI, DATA, SW 등)")
    extra_data = models.JSONField(default=dict, blank=True, help_text="출처 부가 메타데이터")
    source_payload_digest = models.CharField(max_length=64, help_text="원문 페이로드 SHA-256")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["notice", "version_seq"], name="unique_notice_version_seq")
        ]
        indexes = [
            models.Index(fields=["deadline_at"]),
            models.Index(fields=["observed_at"]),
            models.Index(fields=["notice", "-version_seq"]),
        ]

    def __str__(self):
        return f"{self.notice.notice_number} v{self.version_seq} ({self.title[:30]})"


class Document(models.Model):
    """논리적 첨부 문서 엔터티 (제안요청서, 과업지시서 등)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notice = models.ForeignKey(Notice, on_delete=models.CASCADE, related_name="documents")
    source_attachment_id = models.CharField(max_length=200, null=True, blank=True)
    logical_key = models.CharField(max_length=200, help_text="문서 논리 식별자(예: RFP, ATTACHMENT_1)")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["notice", "logical_key"], name="unique_notice_document_logical_key")
        ]

    def __str__(self):
        return f"{self.notice.notice_number} - {self.logical_key}"


class DocumentVersion(models.Model):
    """특정 파일 바이트 및 해시 기반의 불변 문서 버전."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="versions")
    notice_version = models.ForeignKey(NoticeVersion, on_delete=models.CASCADE, related_name="document_versions")
    version_seq = models.PositiveIntegerField(help_text="문서 내 단조 증가 차수 (1부터 시작)")
    sha256 = models.CharField(max_length=64, help_text="문서 바이트 SHA-256")
    size_bytes = models.BigIntegerField(default=0)
    media_type = models.CharField(max_length=150, blank=True, default="application/octet-stream")
    storage_key = models.TextField(blank=True, default="", help_text="내부 보관 저장소 키")
    source_url = models.TextField(blank=True, default="")
    acquired_at = models.DateTimeField(default=timezone.now)
    freshness = models.CharField(
        max_length=30, choices=DocumentFreshness.choices, default=DocumentFreshness.CURRENT
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["document", "version_seq"], name="unique_document_version_seq")
        ]
        indexes = [
            models.Index(fields=["sha256"]),
            models.Index(fields=["document", "-version_seq"]),
        ]

    def __str__(self):
        return f"{self.document.logical_key} v{self.version_seq} ({self.sha256[:8]})"


class ExtractionRun(models.Model):
    """문서 버전에 대한 구조화/텍스트 추출 실행 이력."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document_version = models.ForeignKey(DocumentVersion, on_delete=models.CASCADE, related_name="extraction_runs")
    extractor_version = models.CharField(max_length=100)
    job_attempt_id = models.UUIDField(null=True, blank=True)
    state = models.CharField(max_length=30, choices=ExtractionState.choices, default=ExtractionState.PENDING)
    coverage = models.JSONField(default=dict)
    warnings = models.JSONField(default=list)
    created_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["document_version", "created_at"]),
        ]

    def __str__(self):
        return f"ExtractionRun {self.id} [{self.state}] for {self.document_version}"


class DocumentStructure(models.Model):
    """DEF-03: 문서의 불변 계층 및 표/각주 구조 메타데이터."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document_version = models.ForeignKey(DocumentVersion, on_delete=models.CASCADE, related_name="structures")
    extraction_run = models.ForeignKey(ExtractionRun, on_delete=models.CASCADE, related_name="structures")
    schema_version = models.PositiveIntegerField(default=1)
    coverage = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["extraction_run"], name="unique_extraction_run_structure")
        ]

    def clean(self):
        # extraction_run과 document_version 일치 검증
        if self.extraction_run and self.document_version:
            if self.extraction_run.document_version_id != self.document_version_id:
                raise ValidationError("ExtractionRun의 DocumentVersion과 구조의 DocumentVersion이 일치하지 않습니다.")

    def validate_hierarchy(self):
        """블록 간 순환 참조 및 부모 소속 검증."""
        blocks = list(self.blocks.all())
        validate_block_hierarchy(blocks)

    def __str__(self):
        return f"DocStructure v{self.schema_version} ({self.document_version})"


class DocumentBlock(models.Model):
    """DEF-03: 구조화 블록 기본 단위 (텍스트, 제목, 표, 각주 등)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    structure = models.ForeignKey(DocumentStructure, on_delete=models.CASCADE, related_name="blocks")
    block_id = models.CharField(max_length=100, help_text="구조 내 고유 블록 ID")
    kind = models.CharField(max_length=50, help_text="text, heading, table, footnote 등")
    parent_block = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="child_blocks"
    )
    locator = models.JSONField(default=dict)
    verification = models.CharField(max_length=30, default="UNVERIFIED")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["structure", "block_id"], name="unique_structure_block_id")
        ]

    def clean(self):
        if self.parent_block and self.parent_block.structure_id != self.structure_id:
            raise ValidationError("부모 블록은 동일한 DocumentStructure 소속이어야 합니다.")


class TableBlock(models.Model):
    """DEF-03: 표 전용 구조 정보 (행/열 수, 페이지 범위)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document_block = models.OneToOneField(DocumentBlock, on_delete=models.CASCADE, related_name="table_block")
    row_count = models.PositiveIntegerField()
    column_count = models.PositiveIntegerField()
    page_spans = models.JSONField(default=list)
    created_at = models.DateTimeField(default=timezone.now)

    def validate_cells_grid(self):
        cells_data = [
            {
                "cell_id": cell.cell_id,
                "row_index": cell.row_index,
                "column_index": cell.column_index,
                "rowspan": cell.rowspan,
                "colspan": cell.colspan,
                "text": cell.text,
            }
            for cell in self.cells.all()
        ]
        return validate_table_grid(self.row_count, self.column_count, cells_data)


class TableCell(models.Model):
    """DEF-03: 표 내 개별 셀 (병합 span, 좌표, 머리글 참조)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    table_block = models.ForeignKey(TableBlock, on_delete=models.CASCADE, related_name="cells")
    cell_id = models.CharField(max_length=100)
    row_index = models.PositiveIntegerField()
    column_index = models.PositiveIntegerField()
    rowspan = models.PositiveIntegerField(default=1)
    colspan = models.PositiveIntegerField(default=1)
    header_refs = models.JSONField(default=list)
    text = models.TextField(blank=True, default="")
    locator = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["table_block", "cell_id"], name="unique_table_cell_id")
        ]
        indexes = [
            models.Index(fields=["table_block", "row_index", "column_index"]),
        ]

    def clean(self):
        if self.rowspan < 1 or self.colspan < 1:
            raise ValidationError("rowspan과 colspan은 1 이상이어야 합니다.")
        if self.table_block:
            if self.row_index + self.rowspan > self.table_block.row_count:
                raise ValidationError("셀 행 범위가 표 행 수를 초과합니다.")
            if self.column_index + self.colspan > self.table_block.column_count:
                raise ValidationError("셀 열 범위가 표 열 수를 초과합니다.")


class FootnoteBlock(models.Model):
    """DEF-03: 각주 구조 정보 및 앵커 참조."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document_block = models.OneToOneField(DocumentBlock, on_delete=models.CASCADE, related_name="footnote_block")
    footnote_id = models.CharField(max_length=100)
    text = models.TextField()
    locator = models.JSONField(default=dict)
    anchor_refs = models.JSONField(default=list)
    created_at = models.DateTimeField(default=timezone.now)

    def clean(self):
        if self.document_block and self.document_block.structure:
            valid_ids = set(
                self.document_block.structure.blocks.values_list("block_id", flat=True)
            )
            validate_footnote_anchors(self, valid_ids)


class Chunk(models.Model):
    """추출 구절 엔터티 및 구조 블록 참조 결속."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    extraction_run = models.ForeignKey(ExtractionRun, on_delete=models.CASCADE, related_name="chunks")
    ordinal = models.PositiveIntegerField()
    category = models.CharField(
        max_length=50, choices=ChunkCategory.choices, default=ChunkCategory.GENERAL
    )
    text = models.TextField()
    locator = models.JSONField(default=dict)
    path = models.CharField(max_length=50, choices=ChunkPath.choices, default=ChunkPath.TEXT)
    source_block_refs = models.JSONField(default=list, help_text="DEF-03: 참조하는 DocumentBlock/TableCell ID 목록")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["extraction_run", "ordinal"], name="unique_chunk_run_ordinal")
        ]
        indexes = [
            models.Index(fields=["extraction_run", "path"]),
        ]

    def __str__(self):
        return f"Chunk #{self.ordinal} [{self.category}/{self.path}] ({self.text[:30]})"


class LegacyIdentity(models.Model):
    """레거시 시스템 데이터 이관 영속 멱등 식별자."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_system = models.CharField(max_length=60)
    dataset = models.CharField(max_length=100)
    entity_type = models.CharField(max_length=60)
    legacy_id = models.CharField(max_length=200)
    target_id = models.UUIDField()
    snapshot_ref = models.CharField(max_length=200, blank=True, default="")
    digest = models.CharField(max_length=64, help_text="수집 당시 canonical SHA-256")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source_system", "dataset", "entity_type", "legacy_id"],
                name="unique_legacy_identity",
            )
        ]
        indexes = [
            models.Index(fields=["target_id"]),
            models.Index(fields=["legacy_id"]),
        ]

    def __str__(self):
        return f"Legacy {self.source_system}:{self.entity_type}:{self.legacy_id} -> {self.target_id}"


class ProposalStatus(models.TextChoices):
    AI_DRAFT = "AI_DRAFT", "AI 초안"
    EDITED = "EDITED", "사용자 편집"
    REVIEWED = "REVIEWED", "검토 완료"
    APPROVED = "APPROVED", "승인 완료"


class ProposalProvenance(models.TextChoices):
    AI_DRAFT = "AI_DRAFT", "AI 자동 생성"
    HUMAN = "HUMAN", "사용자 수동 작성"


class Proposal(models.Model):
    """특정 공고에 대한 단일 제안서 작업 공간."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notice = models.OneToOneField(Notice, on_delete=models.CASCADE, related_name="proposal")
    owner_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="owned_proposals",
    )
    current_revision = models.ForeignKey(
        "ProposalRevision",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="current_for_proposal",
        help_text="현재 최신 확정 제안서 리비전",
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Proposal for {self.notice.notice_number}"


class ProposalRevision(models.Model):
    """DEF-02: 전체 절 묶음 단일 불변 스냅샷 리비전."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    proposal = models.ForeignKey(Proposal, on_delete=models.CASCADE, related_name="revisions")
    seq = models.PositiveIntegerField(help_text="제안서 내 단조 증가 차수 (1부터 시작)")
    parent_revision = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="child_revisions"
    )
    notice_version = models.ForeignKey(
        NoticeVersion, null=True, blank=True, on_delete=models.SET_NULL, related_name="proposal_revisions"
    )
    status = models.CharField(
        max_length=30, choices=ProposalStatus.choices, default=ProposalStatus.AI_DRAFT
    )
    provenance = models.CharField(
        max_length=30, choices=ProposalProvenance.choices, default=ProposalProvenance.AI_DRAFT
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="proposals_authored"
    )
    title = models.CharField(max_length=500)
    summary = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["proposal", "seq"], name="unique_proposal_revision_seq")
        ]
        indexes = [
            models.Index(fields=["proposal", "-seq"]),
        ]

    def __str__(self):
        return f"{self.proposal} rev #{self.seq} [{self.status}]"


class ProposalSection(models.Model):
    """DEF-02: 제안서 단일 절 (최대 50,000자, 전체 스냅샷 소속)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    proposal_revision = models.ForeignKey(
        ProposalRevision, on_delete=models.CASCADE, related_name="sections"
    )
    section_key = models.CharField(max_length=100, help_text="표준 절 키(예: understanding, strategy, execution 등)")
    ordinal = models.PositiveIntegerField()
    title = models.CharField(max_length=300)
    body = models.TextField(help_text="절 본문 텍스트 (최대 50,000자)")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["proposal_revision", "section_key"],
                name="unique_proposal_revision_section_key",
            )
        ]
        indexes = [
            models.Index(fields=["proposal_revision", "ordinal"]),
        ]

    def __str__(self):
        return f"Section #{self.ordinal} [{self.section_key}] {self.title[:30]}"


class RequirementMapping(models.Model):
    """요구사항 대응표 항목."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    proposal_revision = models.ForeignKey(
        ProposalRevision, on_delete=models.CASCADE, related_name="requirement_mappings"
    )
    source_chunk = models.ForeignKey(
        Chunk, null=True, blank=True, on_delete=models.SET_NULL, related_name="requirement_mappings"
    )
    source_document_version = models.ForeignKey(
        DocumentVersion, null=True, blank=True, on_delete=models.SET_NULL, related_name="requirement_mappings"
    )
    locator = models.JSONField(default=dict)
    requirement_text = models.TextField()
    section_key = models.CharField(max_length=100, blank=True, default="")
    coverage = models.CharField(
        max_length=50, default="FULL", help_text="FULL, PARTIAL, UNMET, UNVERIFIED"
    )
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"ReqMap [{self.coverage}] {self.requirement_text[:30]}"


class EvidenceReference(models.Model):
    """제안 주장의 근거 문서 참조."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    proposal_revision = models.ForeignKey(
        ProposalRevision, on_delete=models.CASCADE, related_name="evidence_references"
    )
    section_key = models.CharField(max_length=100, blank=True, default="")
    document_version = models.ForeignKey(
        DocumentVersion, null=True, blank=True, on_delete=models.SET_NULL, related_name="evidence_references"
    )
    claim_text = models.TextField()
    locator = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Evidence [{self.section_key}] {self.claim_text[:30]}"


class ExportArtifact(models.Model):
    """A29: 생성된 공식 제안서 산출물 아티팩트 (HWPX, DOCX)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    proposal_revision = models.ForeignKey(
        ProposalRevision, on_delete=models.CASCADE, related_name="export_artifacts"
    )
    format = models.CharField(max_length=20, help_text="HWPX 또는 DOCX")
    file_name = models.CharField(max_length=255)
    sha256 = models.CharField(max_length=64)
    size_bytes = models.BigIntegerField(default=0)
    storage_path = models.TextField(help_text="내부 보관 절대 경로 또는 스토리지 키")
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.format} Artifact: {self.file_name} ({self.size_bytes:,} bytes)"
