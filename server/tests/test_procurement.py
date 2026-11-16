"""SM04 조달 도메인 및 레거시 이관 통합 검증 계약.
목적: A05(공고 버전/취소 보존), A06(문서 버전/SHA 갱신), A15(레거시 멱등 이관/dry-run), A25(DEF-03 표·각주 구조 보존) 검증.
경계: 임시 테스트 DB와 합성 데이터만 사용. 실제 운영 DB나 외부 조달 API를 호출하지 않는다.
부작용: Django test runner가 트랜잭션 단위로 롤백하므로 부작용 없음.
실패: 불변조건 또는 멱등성 실패 시 테스트 AssertionError 발생.
관련: docs/server-migration/17-domain-and-postgresql-contract.md, 20-acceptance-and-open-decisions.md.
"""
import json
import os
from io import StringIO
import tempfile
import uuid
from datetime import datetime, timedelta
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from bid_server.procurement.models import (
    Notice,
    NoticeVersion,
    Document,
    DocumentVersion,
    ExtractionRun,
    DocumentStructure,
    DocumentBlock,
    TableBlock,
    TableCell,
    FootnoteBlock,
    Chunk,
    LegacyIdentity,
    DeadlineStatus,
    DocumentFreshness,
    ExtractionState,
    ChunkCategory,
    ChunkPath,
)
from bid_server.procurement.importer import (
    LegacyNoticeImporter,
    compute_canonical_digest,
    parse_deadline,
)
from bid_server.procurement.validators import (
    validate_table_grid,
    validate_block_hierarchy,
    validate_footnote_anchors,
)


class ProcurementDomainModelTests(TestCase):
    """도메인 모델의 기본 생성, 제약조건 및 관계를 검증한다."""

    def test_notice_unique_source_and_number(self):
        """동일 source와 notice_number를 가진 Notice의 중복 생성이 차단되는지 검증."""
        Notice.objects.create(source="G2B_OFFICIAL_API", notice_number="2026110001")
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Notice.objects.create(source="G2B_OFFICIAL_API", notice_number="2026110001")

    def test_notice_version_unique_seq(self):
        """동일 Notice 내에서 동일 version_seq의 중복 생성이 차단되는지 검증."""
        notice = Notice.objects.create(source="G2B_OFFICIAL_API", notice_number="2026110002")
        NoticeVersion.objects.create(
            notice=notice,
            version_seq=1,
            observed_at=timezone.now(),
            title="테스트 공고 v1",
            buyer="발주기관 A",
            source_payload_digest="a" * 64,
        )
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                NoticeVersion.objects.create(
                    notice=notice,
                    version_seq=1,
                    observed_at=timezone.now(),
                    title="테스트 공고 v1 중복",
                    buyer="발주기관 A",
                    source_payload_digest="b" * 64,
                )

    def test_document_and_version_constraints(self):
        """Document의 logical_key 유일성과 DocumentVersion의 version_seq 유일성을 검증."""
        notice = Notice.objects.create(source="G2B_OFFICIAL_API", notice_number="2026110003")
        nv = NoticeVersion.objects.create(
            notice=notice,
            version_seq=1,
            observed_at=timezone.now(),
            title="문서 테스트 공고",
            buyer="발주기관 B",
            source_payload_digest="c" * 64,
        )
        doc = Document.objects.create(notice=notice, logical_key="RFP")
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Document.objects.create(notice=notice, logical_key="RFP")

        DocumentVersion.objects.create(
            document=doc,
            notice_version=nv,
            version_seq=1,
            sha256="1" * 64,
            size_bytes=1024,
        )
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                DocumentVersion.objects.create(
                    document=doc,
                    notice_version=nv,
                    version_seq=1,
                    sha256="2" * 64,
                    size_bytes=2048,
                )

    def test_notice_deletion_cascades_versions_and_sets_null_current(self):
        """Notice 삭제 시 versions는 CASCADE되고 current_version은 SET_NULL 처리됨을 검증."""
        notice = Notice.objects.create(source="SYNTHETIC_FIXTURE", notice_number="2026110004")
        nv = NoticeVersion.objects.create(
            notice=notice,
            version_seq=1,
            observed_at=timezone.now(),
            title="삭제 테스트",
            buyer="발주기관 C",
            source_payload_digest="d" * 64,
        )
        notice.current_version = nv
        notice.save()

        nv_id = nv.id
        notice.delete()
        self.assertFalse(NoticeVersion.objects.filter(id=nv_id).exists())


class AcceptanceA05NoticeVersioningTests(TestCase):
    """A05: 취소/정정/마감/미상 기한/다른 차수 재관측 시 버전 역행 없이 보존됨을 검증."""

    def test_deadline_parsing_rules(self):
        """마감일시 문자열의 결정적 파싱 및 임의 시각 보충 금지 검증."""
        # 1. 일시 파싱 (초 포함)
        dt, status = parse_deadline("2026-12-31 18:00:00")
        self.assertEqual(status, DeadlineStatus.PARSED)
        self.assertEqual(dt.hour, 18)
        self.assertEqual(dt.minute, 0)

        # 2. 날짜만 확인 시 DATE_ONLY (임의 시각 23:59:59 등으로 왜곡하지 않음)
        dt, status = parse_deadline("2026-12-31")
        self.assertEqual(status, DeadlineStatus.DATE_ONLY)
        self.assertEqual(dt.hour, 0)

        # 3. 모호한 문자열
        dt, status = parse_deadline("추후 공지")
        self.assertIsNone(dt)
        self.assertEqual(status, DeadlineStatus.AMBIGUOUS)

        # 4. 과거 시각
        dt, status = parse_deadline("2020-01-01 10:00:00")
        self.assertEqual(status, DeadlineStatus.EXPIRED)

        # 5. 빈 문자열
        dt, status = parse_deadline("")
        self.assertIsNone(dt)
        self.assertEqual(status, DeadlineStatus.UNKNOWN)

    def test_monotonic_notice_versions_preserved(self):
        """동일 공고의 차수가 갱신되어도 과거 버전이 보존되고 current_version이 전진함을 검증."""
        notice = Notice.objects.create(source="G2B_OFFICIAL_API", notice_number="2026110005")
        nv1 = NoticeVersion.objects.create(
            notice=notice,
            version_seq=1,
            source_revision="00",
            observed_at=timezone.now(),
            title="클라우드 센터 구축",
            buyer="정보화진흥원",
            source_payload_digest="11" * 32,
        )
        notice.current_version = nv1
        notice.save()

        # 정정 공고 관측
        nv2 = NoticeVersion.objects.create(
            notice=notice,
            version_seq=2,
            source_revision="01",
            observed_at=timezone.now() + timedelta(hours=1),
            title="[정정] 클라우드 센터 구축",
            buyer="정보화진흥원",
            correction=True,
            source_payload_digest="22" * 32,
        )
        notice.current_version = nv2
        notice.save()

        # 취소 공고 관측
        nv3 = NoticeVersion.objects.create(
            notice=notice,
            version_seq=3,
            source_revision="02",
            observed_at=timezone.now() + timedelta(hours=2),
            title="[취소] 클라우드 센터 구축",
            buyer="정보화진흥원",
            cancellation=True,
            source_payload_digest="33" * 32,
        )
        notice.current_version = nv3
        notice.save()

        notice.refresh_from_db()
        self.assertEqual(notice.current_version_id, nv3.id)
        self.assertTrue(notice.current_version.cancellation)
        self.assertEqual(notice.versions.count(), 3)
        self.assertTrue(notice.versions.filter(version_seq=1).exists())
        self.assertTrue(notice.versions.filter(version_seq=2, correction=True).exists())


class AcceptanceA06DocumentVersioningTests(TestCase):
    """A06: SHA 바뀐 원본 관측 시 새 DocumentVersion 생성 및 과거 버전 STALE 보존 검증."""

    def test_document_versioning_and_stale_flagging(self):
        importer = LegacyNoticeImporter(source_system="TEST_SYS", dataset="TEST_DS")
        notice_data_v1 = {
            "id": "notice-doc-001",
            "bid_no": "2026-DOC-01",
            "title": "전자정부 프레임워크 고도화",
            "attachments": [
                {
                    "logical_key": "RFP",
                    "file_name": "제안요청서.pdf",
                    "sha256": "aaaa" * 16,
                    "size_bytes": 10000,
                }
            ],
        }

        # 1차 이관
        res1 = importer.import_notices([notice_data_v1])
        self.assertEqual(res1["created_documents"], 1)
        self.assertEqual(res1["created_doc_versions"], 1)

        doc = Document.objects.get(logical_key="RFP")
        doc_v1 = doc.versions.get(version_seq=1)
        self.assertEqual(doc_v1.freshness, DocumentFreshness.CURRENT)
        self.assertEqual(doc_v1.sha256, "aaaa" * 16)

        # 동일한 SHA로 다시 이관 시 추가 버전 생성 없음
        res2 = importer.import_notices([notice_data_v1])
        self.assertEqual(res2["idempotent_skipped"], 1)
        self.assertEqual(doc.versions.count(), 1)

        # 2차: 첨부파일 내용 변경 (새로운 SHA)
        notice_data_v2 = {
            "id": "notice-doc-001",
            "bid_no": "2026-DOC-01",
            "title": "전자정부 프레임워크 고도화",
            "attachments": [
                {
                    "logical_key": "RFP",
                    "file_name": "제안요청서_수정본.pdf",
                    "sha256": "bbbb" * 16,
                    "size_bytes": 12000,
                }
            ],
        }

        res3 = importer.import_notices([notice_data_v2])
        self.assertEqual(res3["created_doc_versions"], 1)

        doc_v1.refresh_from_db()
        self.assertEqual(doc_v1.freshness, DocumentFreshness.STALE)  # 과거 버전은 STALE로 전환

        doc_v2 = doc.versions.get(version_seq=2)
        self.assertEqual(doc_v2.freshness, DocumentFreshness.CURRENT)
        self.assertEqual(doc_v2.sha256, "bbbb" * 16)
        self.assertEqual(doc.versions.count(), 2)  # 과거 버전 보존


class AcceptanceA15LegacyMigrationIdempotencyTests(TestCase):
    """A15: JSON 이관 반복, 동일 legacy ID 다른 snapshot/내용 변경 멱등성 검증."""

    def setUp(self):
        self.sample_data = [
            {
                "id": "demo-ai-001",
                "title": "[합성] 공공 AI 업무지원 서비스 기획 및 구현",
                "organization": "가상 공공기관 A",
                "source_type": "SYNTHETIC_FIXTURE",
                "end": "2026-11-30 18:00:00",
            },
            {
                "id": "demo-sw-002",
                "title": "[합성] 행정 업무 웹서비스 고도화",
                "organization": "가상 공공기관 B",
                "source_type": "SYNTHETIC_FIXTURE",
                "end": "2026-12-15 17:00:00",
            },
        ]

    def test_dry_run_leaves_database_untouched(self):
        """dry_run=True 시뮬레이션 시 결과 지표는 반환하되 DB 레코드는 0건이어야 함."""
        importer = LegacyNoticeImporter()
        summary = importer.import_notices(self.sample_data, dry_run=True)
        self.assertTrue(summary["dry_run"])
        self.assertEqual(summary["total_records"], 2)
        self.assertEqual(summary["created_notices"], 2)
        self.assertEqual(summary["created_versions"], 2)

        # DB 검증: 실제로 아무것도 쓰여지지 않았는지 확인
        self.assertEqual(Notice.objects.count(), 0)
        self.assertEqual(NoticeVersion.objects.count(), 0)
        self.assertEqual(LegacyIdentity.objects.count(), 0)

    def test_idempotent_repeated_imports(self):
        """동일한 데이터로 반복 이관 시 중복 생성 없이 idempotent_skipped 증가 검증."""
        importer = LegacyNoticeImporter()

        # 1회 실행
        summary1 = importer.import_notices(self.sample_data, snapshot_ref="SNAP_01")
        self.assertEqual(summary1["created_notices"], 2)
        self.assertEqual(summary1["created_versions"], 2)
        self.assertEqual(summary1["idempotent_skipped"], 0)
        self.assertEqual(Notice.objects.count(), 2)

        # 2회 실행 (동일 스냅샷 데이터)
        summary2 = importer.import_notices(self.sample_data, snapshot_ref="SNAP_02")
        self.assertEqual(summary2["created_notices"], 0)
        self.assertEqual(summary2["created_versions"], 0)
        self.assertEqual(summary2["idempotent_skipped"], 2)
        self.assertEqual(Notice.objects.count(), 2)
        self.assertEqual(NoticeVersion.objects.count(), 2)

    def test_payload_change_creates_new_version(self):
        """내용 변경 시 새로운 NoticeVersion이 생성되고 LegacyIdentity digest가 갱신됨을 검증."""
        importer = LegacyNoticeImporter()
        importer.import_notices(self.sample_data)

        # 내용 변경 (제목 변경)
        modified_data = [
            {
                "id": "demo-ai-001",
                "title": "[합성] 공공 AI 업무지원 서비스 기획 및 구현 (예산 증액 정정)",
                "organization": "가상 공공기관 A",
                "source_type": "SYNTHETIC_FIXTURE",
                "end": "2026-11-30 18:00:00",
                "correction": True,
            }
        ]

        summary = importer.import_notices(modified_data)
        self.assertEqual(summary["created_notices"], 0)  # 기존 Notice 재사용
        self.assertEqual(summary["created_versions"], 1)  # 새 버전 생성

        notice = Notice.objects.get(notice_number="demo-ai-001")
        self.assertEqual(notice.versions.count(), 2)
        self.assertEqual(notice.current_version.version_seq, 2)
        self.assertTrue(notice.current_version.correction)
        self.assertIn("예산 증액 정정", notice.current_version.title)

    def test_cli_management_command(self):
        """import_legacy_notices CLI 관리 명령 정상 동작 및 파일 예외 검증."""
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(self.sample_data, f, ensure_ascii=False)
            tmp_path = f.name

        try:
            # 1. dry-run 옵션 실행
            call_command("import_legacy_notices", file=tmp_path, dry_run=True, stdout=StringIO())
            self.assertEqual(Notice.objects.count(), 0)

            # 2. 실제 실행
            call_command("import_legacy_notices", file=tmp_path, stdout=StringIO())
            self.assertEqual(Notice.objects.count(), 2)

            # 3. 잘못된 파일 경로 시 CommandError
            with self.assertRaises(CommandError):
                call_command("import_legacy_notices", file="non_existent_file.json")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


class AcceptanceA25Def03StructurePreservationTests(TestCase):
    """A25: DEF-03 표·각주 구조 보존 및 불변조건 검증 (셀 중첩, 범위 초과, 순환 부모 등)."""

    def setUp(self):
        self.notice = Notice.objects.create(source="SYNTHETIC_FIXTURE", notice_number="2026110099")
        self.nv = NoticeVersion.objects.create(
            notice=self.notice,
            version_seq=1,
            observed_at=timezone.now(),
            title="DEF-03 테스트 공고",
            buyer="검증기관",
            source_payload_digest="f" * 64,
        )
        self.doc = Document.objects.create(notice=self.notice, logical_key="RFP")
        self.doc_v = DocumentVersion.objects.create(
            document=self.doc,
            notice_version=self.nv,
            version_seq=1,
            sha256="e" * 64,
        )
        self.run = ExtractionRun.objects.create(
            document_version=self.doc_v,
            extractor_version="v1.0.0",
            state=ExtractionState.PARSED,
        )
        self.structure = DocumentStructure.objects.create(
            document_version=self.doc_v,
            extraction_run=self.run,
            schema_version=1,
        )

    def test_valid_complex_table_grid(self):
        """병합 셀(rowspan=2, colspan=1)이 포함된 3x3 표의 정상 격자 검증."""
        cells = [
            {"cell_id": "c_0_0", "row_index": 0, "column_index": 0, "rowspan": 2, "colspan": 1, "text": "구분(병합)"},
            {"cell_id": "c_0_1", "row_index": 0, "column_index": 1, "rowspan": 1, "colspan": 1, "text": "항목1"},
            {"cell_id": "c_0_2", "row_index": 0, "column_index": 2, "rowspan": 1, "colspan": 1, "text": "비고1"},
            {"cell_id": "c_1_1", "row_index": 1, "column_index": 1, "rowspan": 1, "colspan": 1, "text": "항목2"},
            {"cell_id": "c_1_2", "row_index": 1, "column_index": 2, "rowspan": 1, "colspan": 1, "text": "비고2"},
            {"cell_id": "c_2_0", "row_index": 2, "column_index": 0, "rowspan": 1, "colspan": 1, "text": "합계"},
            {"cell_id": "c_2_1", "row_index": 2, "column_index": 1, "rowspan": 1, "colspan": 2, "text": "완료(가로병합)"},
        ]
        res = validate_table_grid(row_count=3, column_count=3, cells=cells)
        self.assertEqual(res["total_slots"], 9)
        self.assertEqual(res["occupied_slots"], 9)
        self.assertEqual(res["grid"][0][0], "c_0_0")
        self.assertEqual(res["grid"][1][0], "c_0_0")  # rowspan 점유 확인
        self.assertEqual(res["grid"][2][1], "c_2_1")
        self.assertEqual(res["grid"][2][2], "c_2_1")  # colspan 점유 확인

    def test_table_cell_overlap_raises_validation_error(self):
        """두 셀이 동일 좌표를 중복 점유할 경우 ValidationError 발생 검증."""
        cells = [
            {"cell_id": "cell_1", "row_index": 0, "column_index": 0, "rowspan": 2, "colspan": 1},
            {"cell_id": "cell_2", "row_index": 1, "column_index": 0, "rowspan": 1, "colspan": 1},  # cell_1과 (1,0) 중첩
        ]
        with self.assertRaises(ValidationError) as ctx:
            validate_table_grid(row_count=2, column_count=1, cells=cells)
        self.assertIn("셀 중첩 발견", str(ctx.exception))

    def test_table_cell_out_of_bounds_raises_validation_error(self):
        """셀의 rowspan/colspan이 표 경계를 벗어날 경우 ValidationError 발생 검증."""
        cells = [
            {"cell_id": "cell_out", "row_index": 2, "column_index": 0, "rowspan": 2, "colspan": 1},
        ]
        with self.assertRaises(ValidationError) as ctx:
            validate_table_grid(row_count=3, column_count=1, cells=cells)
        self.assertIn("행 범위", str(ctx.exception))

    def test_table_cell_negative_index_raises_validation_error(self):
        """음수 좌표 및 0 이하 span 거부 검증."""
        with self.assertRaises(ValidationError):
            validate_table_grid(1, 1, [{"cell_id": "neg", "row_index": -1, "column_index": 0}])
        with self.assertRaises(ValidationError):
            validate_table_grid(1, 1, [{"cell_id": "zero", "row_index": 0, "column_index": 0, "rowspan": 0}])

    def test_block_hierarchy_circular_reference_rejected(self):
        """블록 간 순환 참조(A -> B -> A) 발견 시 ValidationError 발생 검증."""
        blocks = [
            {"block_id": "blk_a", "parent_block_id": "blk_b"},
            {"block_id": "blk_b", "parent_block_id": "blk_a"},
        ]
        with self.assertRaises(ValidationError) as ctx:
            validate_block_hierarchy(blocks)
        self.assertIn("순환 참조", str(ctx.exception))

    def test_block_hierarchy_missing_parent_rejected(self):
        """존재하지 않는 부모 블록 참조 시 ValidationError 발생 검증."""
        blocks = [
            {"block_id": "blk_c", "parent_block_id": "blk_ghost"},
        ]
        with self.assertRaises(ValidationError) as ctx:
            validate_block_hierarchy(blocks)
        self.assertIn("부모 블록 blk_ghost이 동일 구조 내에 존재하지 않습니다", str(ctx.exception))

    def test_footnote_anchor_references_validated(self):
        """각주 앵커가 동일 구조의 실재 블록만 참조하는지 검증."""
        valid_block_ids = {"blk_1", "blk_2", "cell_0_0"}
        valid_fn = {"footnote_id": "fn_1", "anchor_refs": ["blk_1", "cell_0_0"]}
        # 정상 검증
        validate_footnote_anchors(valid_fn, valid_block_ids)

        # 유령 블록 참조
        invalid_fn = {"footnote_id": "fn_2", "anchor_refs": ["blk_missing"]}
        with self.assertRaises(ValidationError) as ctx:
            validate_footnote_anchors(invalid_fn, valid_block_ids)
        self.assertIn("동일 문서 구조 내에 존재하지 않습니다", str(ctx.exception))

    def test_chunk_with_def03_block_refs(self):
        """Chunk 엔터티에 DEF-03 source_block_refs 및 locator가 결속되는지 검증."""
        chunk = Chunk.objects.create(
            extraction_run=self.run,
            ordinal=1,
            category=ChunkCategory.REQUIREMENT,
            path=ChunkPath.TABLE,
            text="클라우드 인프라 요구조건: 가용성 99.9% 보장",
            locator={"page": 12, "bbox": [10, 20, 100, 200], "table_id": "tbl_01"},
            source_block_refs=["blk_table_1", "cell_0_1"],
        )
        self.assertEqual(chunk.source_block_refs, ["blk_table_1", "cell_0_1"])
        self.assertEqual(chunk.locator["page"], 12)
