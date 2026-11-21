"""레거시 공고 JSON 수입 CLI 관리 명령 계약.
목적: 관리자가 레거시 JSON 파일로부터 공고 및 첨부 문서를 DB로 멱등하게 이관하거나 dry-run 시뮬레이션을 수행한다.
경계: 파일은 오직 읽기 전용으로 열며, 임의 수정이나 외부 통신을 수행하지 않는다.
부작용: dry-run이 아닐 경우 Notice, NoticeVersion, Document, DocumentVersion, LegacyIdentity 레코드 생성/갱신.
실패: 파일 미존재/JSON 파싱 오류/무결성 위반 시 0이 아닌 종료 코드 반환 및 변경 롤백.
관련: docs/server-migration/17-domain-and-postgresql-contract.md §6 및 A15.
"""
import json
import os
import sys
from django.core.management.base import BaseCommand, CommandError
from bid_server.procurement.importer import LegacyNoticeImporter


class Command(BaseCommand):
    help = "레거시 공고 JSON 파일을 읽어 조달 도메인 모델로 멱등하게 이관합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            required=True,
            help="수입할 레거시 공고 JSON 파일 경로 (읽기 전용)",
        )
        parser.add_argument(
            "--source-system",
            type=str,
            default="LEGACY_BID03",
            help="출처 시스템 식별자 (기본값: LEGACY_BID03)",
        )
        parser.add_argument(
            "--dataset",
            type=str,
            default="SAMPLE_NOTICES",
            help="데이터셋 식별자 (기본값: SAMPLE_NOTICES)",
        )
        parser.add_argument(
            "--snapshot-ref",
            type=str,
            default="",
            help="수집 스냅샷 참조 해시/버전",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="DB 변경 없이 시뮬레이션만 수행하고 롤백합니다.",
        )

    def handle(self, *args, **options):
        file_path = options["file"]
        source_system = options["source_system"]
        dataset = options["dataset"]
        snapshot_ref = options["snapshot_ref"]
        dry_run = options["dry_run"]

        if not os.path.exists(file_path):
            raise CommandError(f"파일을 찾을 수 없습니다: {file_path}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            raise CommandError(f"JSON 파일 파싱 실패: {exc}")

        if isinstance(data, dict):
            if "notices" in data and isinstance(data["notices"], list):
                data = data["notices"]
            else:
                # 단일 객체인 경우 리스트로 감쌈
                data = [data]
        elif not isinstance(data, list):
            raise CommandError("JSON 최상위 항목은 배열 또는 객체여야 합니다.")

        importer = LegacyNoticeImporter(source_system=source_system, dataset=dataset)

        self.stdout.write(
            f"[{'DRY-RUN' if dry_run else 'EXECUTE'}] 공고 데이터 이관 시작: "
            f"파일={file_path}, 총 {len(data)}건, source={source_system}, dataset={dataset}"
        )

        try:
            summary = importer.import_notices(
                notices_data=data,
                snapshot_ref=snapshot_ref,
                dry_run=dry_run,
            )
        except Exception as exc:
            raise CommandError(f"이관 작업 실패: {exc}")

        self.stdout.write(self.style.SUCCESS(
            f"이관 결과 요약:\n"
            f"  - 총 레코드 수: {summary['total_records']}\n"
            f"  - 신규 생성 Notice: {summary['created_notices']}\n"
            f"  - 신규 생성 NoticeVersion: {summary['created_versions']}\n"
            f"  - 신규 생성 Document: {summary['created_documents']}\n"
            f"  - 신규 생성 DocumentVersion: {summary['created_doc_versions']}\n"
            f"  - 멱등 스킵(동일 해시): {summary['idempotent_skipped']}\n"
            f"  - dry_run 여부: {summary['dry_run']}"
        ))
