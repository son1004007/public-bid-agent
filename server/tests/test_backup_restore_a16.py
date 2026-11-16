"""A16 백업 및 복원 리허설 인수 테스트.

목적: docs/server-migration/20-acceptance-and-open-decisions.md (A16)
      "DB+파일 백업 복원, 전환 후 새 쓰기와 rollback: 같은 manifest 세대 복구,
       SHA/FK 대조, 새 데이터 유실 없이 계획대로 복구" 계약을 검증한다.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from django.test import TestCase
from scripts.backup_system import create_backup, sha256_file
from scripts.restore_rehearsal import run_rehearsal


class BackupRestoreA16Tests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_backup_and_restore_rehearsal_against_live_postgres(self):
        """PostgreSQL 환경이 주어졌을 때 완전한 백업 생성 및 복구 리허설 무결성을 검증 (A16)."""
        cfg_env = os.environ.get("SM03_TEST_DB_CONFIG_FILE")
        if not cfg_env or not Path(cfg_env).exists():
            default_cfg = Path(os.environ.get("LOCALAPPDATA", "")) / "PublicBidAgent" / "sm03-postgres" / "connection.private.json"
            if not default_cfg.exists():
                self.skipTest("PostgreSQL configuration not found, skipping live rehearsal.")
            cfg_path = default_cfg
        else:
            cfg_path = Path(cfg_env)

        # 1. 백업 생성
        bundle_dir = create_backup(
            output_dir=self.output_dir,
            config_path=cfg_path,
        )
        self.assertTrue(bundle_dir.exists())
        manifest_path = bundle_dir / "manifest.json"
        self.assertTrue(manifest_path.exists())

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        self.assertEqual(manifest["manifest_version"], "1.0")
        self.assertTrue(manifest["database"]["dump_size_bytes"] > 0)
        self.assertEqual(len(manifest["database"]["dump_sha256"]), 64)

        # 2. 복구 리허설 실행
        report = run_rehearsal(
            bundle_dir=bundle_dir,
            rehearsal_db_name="sm03_test_a16_rehearsal",
            config_path=cfg_path,
            keep_db=False,
        )

        self.assertEqual(report["status"], "SUCCESS")
        self.assertEqual(report["rpo_status"], "DB_COUNT_PARITY_ONLY")
        self.assertEqual(report["new_write_verification"], "PASS")
        self.assertEqual(len(report["fk_integrity_errors"]), 0)
        self.assertEqual(len(report["storage_integrity_errors"]), 0)
        self.assertTrue(report["rto_seconds"] < 30.0)

    def test_rehearsal_detects_corrupted_dump_sha256(self):
        """덤프 파일 위변조 시 복구 리허설이 즉시 중단되고 예외를 발생시킴을 검증."""
        fake_bundle = self.output_dir / "corrupted_bundle"
        fake_bundle.mkdir()
        fake_dump = fake_bundle / "db_dump.sql"
        fake_dump.write_text("corrupted content", encoding="utf-8")

        fake_manifest = {
            "manifest_version": "1.0",
            "backup_id": "test_corrupt",
            "database": {
                "name": "fake_db",
                "dump_file": "db_dump.sql",
                "dump_sha256": "0" * 64,  # mismatched SHA
                "table_counts": {},
            },
            "storage": {"files": []},
        }
        (fake_bundle / "manifest.json").write_text(json.dumps(fake_manifest), encoding="utf-8")

        with self.assertRaises(ValueError) as ctx:
            run_rehearsal(bundle_dir=fake_bundle)
        self.assertIn("Dump SHA-256 mismatch", str(ctx.exception))

    def test_failed_psql_restore_cleans_only_newly_created_rehearsal_db(self):
        """A failed restore must clean its newly created isolated DB, without touching the source."""
        from unittest.mock import MagicMock, patch
        from scripts import restore_rehearsal

        bundle = self.output_dir / "restore_failure"
        bundle.mkdir()
        dump = bundle / "db_dump.sql"
        dump.write_text("-- synthetic fixture", encoding="utf-8")
        manifest = {
            "backup_id": "synthetic-failed-restore",
            "database": {
                "dump_file": "db_dump.sql",
                "dump_sha256": sha256_file(dump),
                "table_counts": {},
            },
            "storage": {"files": []},
        }
        (bundle / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        cfg = {"HOST": "127.0.0.1", "PORT": 5432, "NAME": "source_db",
               "USER": "synthetic", "PASSWORD": "synthetic"}
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value

        with (
            patch.object(restore_rehearsal, "load_db_config", return_value=cfg),
            patch.object(restore_rehearsal.psycopg, "connect", return_value=connection) as connect,
            patch.object(restore_rehearsal.subprocess, "run") as run,
        ):
            run.return_value.returncode = 1
            run.return_value.stderr = "synthetic failure"
            with self.assertRaisesRegex(RuntimeError, "psql restore failed"):
                restore_rehearsal.run_rehearsal(
                    bundle, rehearsal_db_name="sm03_test_failure_rehearsal"
                )

        self.assertEqual(connect.call_count, 2)
        statements = [str(call.args[0]) for call in cursor.execute.call_args_list]
        self.assertEqual(len(statements), 2)
        self.assertIn("CREATE DATABASE", statements[0])
        self.assertIn("DROP DATABASE", statements[1])
        self.assertNotIn("source_db", " ".join(statements))
