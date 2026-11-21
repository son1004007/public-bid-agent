"""DEF-03 문서 구조화 추출 서비스.

목적: DocumentVersion의 원본 바이트를 파싱하여 DocumentStructure, DocumentBlock,
      TableBlock, TableCell, FootnoteBlock, Chunk를 원자적으로 영속화한다.
불변조건: DB에 등록된 원본 SHA-256/크기와 일치하는 바이트만 파싱 및 저장한다.
호출자가 넘긴 모델 메타데이터를 신뢰하지 않으며, 불일치 시 전체 영속화 없이 실패한다.
권한: 요청의 auth_epoch와 최신 활성·잠금·강제변경 상태를 DB에서 대조한다.
저장: PostgreSQL에서 사용자 행을 먼저 잠근 뒤 문서 버전 행을 잠그고 권한을 재확인한다.
파싱 중 보안 변경이 먼저 커밋되면 저장하지 않는다. 저장이 먼저 잠금을 획득하면 변경은 저장 종료 후 진행된다.
actor_user=None은 인가된 내부 호출 전용이며 HTTP 경로는 반드시 요청 사용자를 전달한다.
관련: docs/server-migration/17-domain-and-postgresql-contract.md §16, 27-html-defects-and-stop-verification.md.
"""
import hashlib
from typing import Optional, Dict, Any
from django.db import transaction
from django.db.models import Exists, F, Q
from bid_server.accounts.models import User
from django.utils import timezone
from .models import (
    DocumentVersion,
    ExtractionRun,
    ExtractionState,
    DocumentStructure,
    DocumentBlock,
    TableBlock,
    TableCell,
    FootnoteBlock,
    Chunk,
    ChunkCategory,
    ChunkPath,
)
from .parser import parse_document_bytes, parse_public_hwpx_text, ParserError
from .source_chunking import split_source_text, SourceChunkError, MAX_CHUNK_UTF8_BYTES

MAX_CHUNKS_PER_EXTRACTION = 30000


class DocumentAccessError(ValueError):
    """Document version is not in the actor's authorized scope."""


def _eligible_actor_rows(actor):
    """Use the request epoch, never refresh it to authorize an old request."""
    epoch = getattr(actor, "auth_epoch", None)
    if not getattr(actor, "is_authenticated", False) or type(epoch) is not int:
        return User.objects.none()
    return User.objects.filter(
        pk=actor.pk, auth_epoch=epoch, is_active=True, must_change_password=False,
    ).filter(Q(locked_until__isnull=True) | Q(locked_until__lte=timezone.now()))


def scoped_document_versions(actor, *, write=False):
    qs = DocumentVersion.objects.filter(
        notice_version__notice_id=F("document__notice_id"),
    )
    if not getattr(actor, "is_authenticated", False):
        return qs.none()
    scope = Q(owner_user_id=actor.pk)
    if not write:
        scope |= Q(shared_read_approved=True)
    return qs.filter(scope).filter(Exists(_eligible_actor_rows(actor)))


def _assert_document_access(version, actor):
    if (version.owner_user_id != actor.pk
            or version.notice_version.notice_id != version.document.notice_id):
        raise DocumentAccessError("Document access denied.")


class DocumentSourceMismatchError(ValueError):
    """등록된 원본과 추출 입력이 일치하지 않는다."""


def _assert_source_matches(version: DocumentVersion, size: int, digest: str) -> None:
    if size != version.size_bytes or digest != version.sha256.lower():
        raise DocumentSourceMismatchError("Document source does not match registered version.")


class ExtractionService:
    @staticmethod
    def extract_and_persist(
        document_version: DocumentVersion,
        raw_bytes: bytes,
        file_name: Optional[str] = None,
        job_attempt_id: Optional[Any] = None,
        *, actor_user=None, public_hwpx_text_only=False,
    ) -> ExtractionRun:
        """단일 문서 버전을 파싱하고 모든 계층 구조를 단일 트랜잭션으로 저장한다."""
        size = len(raw_bytes)
        digest = hashlib.sha256(raw_bytes).hexdigest()
        # 호출자가 수정한 in-memory 모델 대신 DB에 저장된 원본 정보를 검증한다.
        document_version = DocumentVersion.objects.get(pk=document_version.pk)
        if actor_user is not None:
            if not _eligible_actor_rows(actor_user).exists():
                raise DocumentAccessError("Document access denied.")
            _assert_document_access(document_version, actor_user)
        _assert_source_matches(document_version, size, digest)
        allowed = {
            "text/plain": ("txt", "PLAIN"),
            "text/markdown": ("md", "PLAIN"),
            "application/x-hwp+zip": ("hwpx", "HWPX"),
            "application/hwp+zip": ("hwpx", "HWPX"),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ("docx", "DOCX"),
        }
        registered_media = document_version.media_type.split(";")[0].strip().lower()
        if registered_media not in allowed:
            raise ParserError("Unsupported registered document format.")
        ext, expected_format = allowed[registered_media]
        fname = file_name or f"document.{ext}"
        if fname.lower().rsplit(".", 1)[-1] != ext:
            raise ParserError("Document format mismatch.")
        if public_hwpx_text_only:
            if actor_user is not None or ext != "hwpx":
                raise ParserError("Public RFP fallback is internal HWPX only.")
            parsed = parse_public_hwpx_text(raw_bytes)
        else:
            parsed = parse_document_bytes(fname, raw_bytes)
        if parsed["format"] != expected_format:
            raise ParserError("Document format mismatch.")


        # P0-03 preflight: no database mutation until *every* extracted source
        # block/cell/footnote has been losslessly segmented. These offsets
        # refer to parser-extracted text, never claimed XML/archive positions.
        prepared_chunks = []
        footnote_missing = False

        def classify(text):
            if any(key in text for key in ("자격", "참가", "제한", "실적")):
                return ChunkCategory.QUALIFICATION
            if any(key in text for key in ("요구", "과업", "기능", "규격")):
                return ChunkCategory.REQUIREMENT
            if any(key in text for key in ("평가", "배점", "기술평가")):
                return ChunkCategory.EVALUATION
            if any(key in text for key in ("예산", "금액", "원")):
                return ChunkCategory.BUDGET
            return ChunkCategory.GENERAL

        def prepare(text, path, base_locator, refs, category):
            if type(text) is not str:
                raise ParserError("Invalid extracted source text.")
            if not text:
                return
            try:
                spans = split_source_text(text)
            except SourceChunkError:
                raise ParserError("Unsafe source chunk boundary or size.") from None
            for span in spans:
                if len(prepared_chunks) >= MAX_CHUNKS_PER_EXTRACTION:
                    raise ParserError("Extracted chunk budget exceeded.")
                prepared_chunks.append({
                    "category": category,
                    "text": span.text,
                    "locator": {
                        **base_locator, **span.locator,
                        "source_document_sha256": digest,
                    },
                    "path": path,
                    "source_block_refs": refs,
                })

        for block in parsed["blocks"]:
            if block["kind"] == "text":
                content = block.get("text", "")
                prepare(content, ChunkPath.TEXT, block.get("locator", {}),
                        [block["block_id"]], classify(content))
            elif block["kind"] == "footnote":
                foot = block.get("footnote", {})
                content = foot.get("text", "")
                # The legacy HWPX parser uses this placeholder, which is
                # fabricated and MUST NOT be represented as source evidence.
                if content == "각주 내용 없음" or not content:
                    footnote_missing = True
                else:
                    prepare(content, ChunkPath.FOOTNOTE,
                            foot.get("locator", block.get("locator", {})),
                            [block["block_id"]], classify(content))
        for table in parsed["tables"]:
            for cell in table.get("cells", []):
                # Legacy code omitted cells with <=5 characters, including
                # qualification/score tokens. Preserve every nonempty cell.
                content = cell.get("text", "")
                prepare(content, ChunkPath.TABLE, cell.get("locator", {}),
                        [table["block_id"], cell["cell_id"]], classify(content))

        # A successful text parse is not an audited guarantee that all tables,
        # spans, page anchors, footnotes and images were recovered. Until full
        # structural verification is implemented, NEVER set complete=True.
        fidelity_warnings = list(parsed["warnings"])
        if public_hwpx_text_only:
            fidelity_warnings.append("TEXT_ONLY_LAYOUT_AND_FOOTNOTES_UNVERIFIED")
        else:
            fidelity_warnings.append("STRUCTURAL_COVERAGE_NOT_VERIFIED")
        if footnote_missing:
            fidelity_warnings.append("EMPTY_FOOTNOTE_SOURCE_UNVERIFIED")
        if not prepared_chunks:
            raise ParserError("No verifiable extracted source spans.")
        chunk_bytes = sum(len(item["text"].encode("utf-8")) for item in prepared_chunks)
        coverage = {
            "format": parsed["format"],
            "block_count": len(parsed["blocks"]),
            "table_count": len(parsed["tables"]),
            "table_cell_count": sum(len(t.get("cells", [])) for t in parsed["tables"]),
            "footnote_count": len(parsed["footnotes"]),
            "character_count": len(parsed["full_text"]),
            "chunk_count": len(prepared_chunks),
            "chunk_utf8_bytes": chunk_bytes,
            "max_chunk_utf8_bytes": MAX_CHUNK_UTF8_BYTES,
            "offset_origin": "EXTRACTED_BLOCK_TEXT",
            "source_document_sha256": digest,
            "source_text_lossless_segmentation": True,
            "structure_fidelity": "UNVERIFIED",
            "status": "PARTIAL",
            "complete": False,
        }


        with transaction.atomic():
            # 사용자 행을 문서보다 먼저 잠가 보안 변경 및 저장을 직렬화한다.
            # exists()가 아닌 실제 행 조회로 잠금을 획득하고 commit까지 유지한다.
            if actor_user is not None:
                if _eligible_actor_rows(actor_user).select_for_update().first() is None:
                    raise DocumentAccessError("Document access denied.")
            # 파싱 중 원본 메타데이터가 변경되었더라도 잘못된 결속을 저장하지 않는다.
            document_version = DocumentVersion.objects.select_for_update().get(
                pk=document_version.pk,
            )
            if actor_user is not None:
                _assert_document_access(document_version, actor_user)
            _assert_source_matches(document_version, size, digest)
            if document_version.media_type.split(";")[0].strip().lower() != registered_media:
                raise DocumentSourceMismatchError("Document format changed during extraction.")
            # 1. ExtractionRun 생성
            run = ExtractionRun.objects.create(
                document_version=document_version,
                extractor_version="1.1.0-public-hwpx-text" if public_hwpx_text_only else "1.0.0-def03",
                job_attempt_id=job_attempt_id,
                state=ExtractionState.PARSED,
                coverage=coverage,
                warnings=fidelity_warnings,
                completed_at=timezone.now(),
            )

            # 2. DocumentStructure 생성
            structure = DocumentStructure.objects.create(
                document_version=document_version,
                extraction_run=run,
                schema_version=1,
                coverage=run.coverage,
            )

            created_blocks_map = {}

            # 3. DocumentBlocks & TableBlocks & FootnoteBlocks 생성
            for b_data in parsed["blocks"]:
                b_id = b_data["block_id"]
                kind = b_data["kind"]
                locator = b_data.get("locator", {})

                d_block = DocumentBlock.objects.create(
                    structure=structure,
                    block_id=b_id,
                    kind=kind,
                    locator=locator,
                    verification="UNVERIFIED",
                )
                created_blocks_map[b_id] = d_block

                # If table
                if kind == "table" and "table" in b_data:
                    tbl_info = b_data["table"]
                    t_block = TableBlock.objects.create(
                        document_block=d_block,
                        row_count=tbl_info["row_count"],
                        column_count=tbl_info["column_count"],
                        page_spans=tbl_info.get("page_spans", [1]),
                    )
                    # create table cells
                    for c in tbl_info.get("cells", []):
                        TableCell.objects.create(
                            table_block=t_block,
                            cell_id=c["cell_id"],
                            row_index=c["row_index"],
                            column_index=c["column_index"],
                            rowspan=c["rowspan"],
                            colspan=c["colspan"],
                            header_refs=c.get("header_refs", []),
                            text=c.get("text", ""),
                            locator=c.get("locator", {}),
                        )

                # If footnote
                elif kind == "footnote" and "footnote" in b_data:
                    fn_info = b_data["footnote"]
                    # Validate anchor refs against existing block IDs
                    anchors = [a for a in fn_info.get("anchor_refs", []) if a in created_blocks_map]
                    FootnoteBlock.objects.create(
                        document_block=d_block,
                        footnote_id=fn_info["footnote_id"],
                        text=fn_info["text"],
                        locator=fn_info.get("locator", {}),
                        anchor_refs=anchors,
                    )

            # 4. Preflighted, lossless spans with source-text and span SHA.
            for ordinal, chunk in enumerate(prepared_chunks, start=1):
                Chunk.objects.create(
                    extraction_run=run,
                    ordinal=ordinal,
                    **chunk,
                )

            return run
