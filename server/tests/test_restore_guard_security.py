from django.test import SimpleTestCase
from pathlib import Path
import sys
import json
import tempfile
from unittest.mock import MagicMock, patch
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from scripts.restore_rehearsal import validate_rehearsal_target
from scripts.backup_system import create_backup

class RestoreGuardSecurityTests(SimpleTestCase):
    def test_reject_bad_names_and_remote_hosts(self):
        cfg = {"HOST":"127.0.0.1","NAME":"sm03_live"}
        for name in ("sm03_live","postgres","template1","public_bid","SM03_test_x_rehearsal"):
            with self.assertRaises(ValueError):
                validate_rehearsal_target(name,cfg)
        with self.assertRaises(ValueError):
            validate_rehearsal_target("sm03_restore_rehearsal",{"HOST":"elsewhere","NAME":"sm03_live"})
        validate_rehearsal_target("sm03_test_a16_rehearsal",cfg)

    def test_disallow_repo_backup(self):
        with self.assertRaises(ValueError):
            create_backup(output_dir=Path(__file__).resolve().parents[2]/"backups")

    def test_existing_rehearsal_database_is_never_dropped(self):
        # An existing reserved-name database may contain data from a previous run.
        # CREATE must fail closed rather than silently destroying that database.
        from scripts.restore_rehearsal import run_rehearsal
        with tempfile.TemporaryDirectory() as temp:
            bundle = Path(temp)
            (bundle / "fixture.sql").write_text("-- synthetic fixture", encoding="utf-8")
            import hashlib
            digest = hashlib.sha256((bundle / "fixture.sql").read_bytes()).hexdigest()
            (bundle / "manifest.json").write_text(json.dumps({
                "backup_id": "synthetic",
                "database": {"dump_file": "fixture.sql", "dump_sha256": digest, "table_counts": {"accounts_user": 0, "procurement_notice": 0, "procurement_noticeversion": 0, "procurement_document": 0, "procurement_documentversion": 0, "procurement_proposal": 0, "procurement_proposalrevision": 0, "procurement_proposalsection": 0, "jobs_job": 0, "jobs_jobattempt": 0}},
                "storage": {"files": []},
            }), encoding="utf-8")
            cursor = MagicMock()
            cursor.execute.side_effect = RuntimeError("duplicate_database")
            conn = MagicMock()
            conn.cursor.return_value.__enter__.return_value = cursor
            with patch("scripts.restore_rehearsal.load_db_config", return_value={
                "HOST": "127.0.0.1", "PORT": 5432, "NAME": "source_db",
                "USER": "synthetic", "PASSWORD": "synthetic",
            }), patch("scripts.restore_rehearsal.psycopg.connect", return_value=conn):
                with self.assertRaisesRegex(RuntimeError, "duplicate_database"):
                    run_rehearsal(bundle, rehearsal_db_name="sm03_test_guard_rehearsal", trusted_dump_sha256=digest)
            self.assertEqual(cursor.execute.call_count, 1)
            statement = str(cursor.execute.call_args.args[0])
            self.assertIn("CREATE DATABASE", statement)
            self.assertNotIn("DROP DATABASE", statement)
            conn.close.assert_called_once()

    def test_manifest_dump_path_cannot_escape_bundle(self):
        from scripts.restore_rehearsal import run_rehearsal
        with tempfile.TemporaryDirectory() as temp:
            bundle = Path(temp) / "bundle"
            bundle.mkdir()
            (bundle / "manifest.json").write_text(json.dumps({
                "backup_id": "synthetic",
                "database": {"dump_file": "../outside.sql", "dump_sha256": "0" * 64, "table_counts": {"accounts_user": 0, "procurement_notice": 0, "procurement_noticeversion": 0, "procurement_document": 0, "procurement_documentversion": 0, "procurement_proposal": 0, "procurement_proposalrevision": 0, "procurement_proposalsection": 0, "jobs_job": 0, "jobs_jobattempt": 0}},
                "storage": {"files": []},
            }), encoding="utf-8")
            with patch("scripts.restore_rehearsal.psycopg.connect") as connect:
                with self.assertRaisesRegex(ValueError, "escapes backup directory"):
                    run_rehearsal(bundle, rehearsal_db_name="sm03_test_guard_rehearsal")
                connect.assert_not_called()

    def test_manifest_storage_path_cannot_escape_bundle(self):
        from scripts.restore_rehearsal import run_rehearsal
        import hashlib
        with tempfile.TemporaryDirectory() as temp:
            bundle = Path(temp)
            (bundle / "fixture.sql").write_bytes(b"-- synthetic fixture")
            digest = hashlib.sha256((bundle / "fixture.sql").read_bytes()).hexdigest()
            (bundle / "manifest.json").write_text(json.dumps({
                "backup_id": "synthetic",
                "database": {"dump_file": "fixture.sql", "dump_sha256": digest, "table_counts": {"accounts_user": 0, "procurement_notice": 0, "procurement_noticeversion": 0, "procurement_document": 0, "procurement_documentversion": 0, "procurement_proposal": 0, "procurement_proposalrevision": 0, "procurement_proposalsection": 0, "jobs_job": 0, "jobs_jobattempt": 0}},
                "storage": {"files": [{"relative_path": "../fixture.sql", "sha256": digest}]},
            }), encoding="utf-8")
            with patch("scripts.restore_rehearsal.psycopg.connect") as connect:
                with self.assertRaisesRegex(ValueError, "escapes backup directory"):
                    run_rehearsal(bundle, rehearsal_db_name="sm03_test_guard_rehearsal")
                connect.assert_not_called()

    def test_symlinked_storage_directory_cannot_escape_bundle(self):
        from scripts.restore_rehearsal import run_rehearsal
        import hashlib
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bundle = root / "bundle"
            outside = root / "outside"
            bundle.mkdir()
            outside.mkdir()
            (bundle / "fixture.sql").write_bytes(b"-- synthetic fixture")
            (outside / "private.txt").write_bytes(b"synthetic private data")
            try:
                (bundle / "storage").symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("directory symlinks unavailable on this platform")
            digest = hashlib.sha256((bundle / "fixture.sql").read_bytes()).hexdigest()
            outside_digest = hashlib.sha256((outside / "private.txt").read_bytes()).hexdigest()
            (bundle / "manifest.json").write_text(json.dumps({
                "backup_id": "synthetic",
                "database": {"dump_file": "fixture.sql", "dump_sha256": digest, "table_counts": {"accounts_user": 0, "procurement_notice": 0, "procurement_noticeversion": 0, "procurement_document": 0, "procurement_documentversion": 0, "procurement_proposal": 0, "procurement_proposalrevision": 0, "procurement_proposalsection": 0, "jobs_job": 0, "jobs_jobattempt": 0}},
                "storage": {"files": [{"relative_path": "private.txt", "sha256": outside_digest}]},
            }), encoding="utf-8")
            with patch("scripts.restore_rehearsal.psycopg.connect") as connect:
                with self.assertRaisesRegex(ValueError, "escapes backup directory"):
                    run_rehearsal(bundle, rehearsal_db_name="sm03_test_guard_rehearsal")
                connect.assert_not_called()

    def test_incomplete_table_counts_rejected_before_database_connection(self):
        from scripts.restore_rehearsal import run_rehearsal
        for invalid_counts in ({}, {"procurement_notice": 1}, {"accounts_user": -1}):
            with self.subTest(invalid_counts=invalid_counts), tempfile.TemporaryDirectory() as temp:
                bundle = Path(temp)
                (bundle / "manifest.json").write_text(json.dumps({
                    "backup_id": "synthetic",
                    "database": {"dump_file": "missing.sql", "dump_sha256": "0" * 64,
                                 "table_counts": invalid_counts},
                }), encoding="utf-8")
                with patch("scripts.restore_rehearsal.psycopg.connect") as connect:
                    with self.assertRaisesRegex(ValueError, "table_counts"):
                        run_rehearsal(bundle)
                    connect.assert_not_called()

    def test_restore_requires_independent_dump_digest_before_connecting(self):
        from scripts.restore_rehearsal import run_rehearsal
        from scripts.backup_system import sha256_file
        with tempfile.TemporaryDirectory() as temp:
            bundle = Path(temp)
            dump = bundle / "db_dump.sql"
            dump.write_bytes(b"-- synthetic fixture")
            digest = sha256_file(dump)
            tables = ("accounts_user", "procurement_notice", "procurement_noticeversion",
                      "procurement_document", "procurement_documentversion",
                      "procurement_proposal", "procurement_proposalrevision", "procurement_proposalsection",
                      "jobs_job", "jobs_jobattempt")
            (bundle / "manifest.json").write_text(json.dumps({
                "backup_id": "synthetic", "database": {
                    "dump_file": dump.name, "dump_sha256": digest,
                    "table_counts": dict.fromkeys(tables, 0),
                }, "storage": {"files": []}
            }), encoding="utf-8")
            with patch("scripts.restore_rehearsal.psycopg.connect") as connect:
                for expected in (None, "0" * 64):
                    with self.assertRaisesRegex(ValueError, "Trusted dump SHA-256"):
                        run_rehearsal(bundle, trusted_dump_sha256=expected)
                connect.assert_not_called()

    def test_configured_media_cannot_be_silently_omitted_or_replaced(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.dict("os.environ", {"BID_LOCAL_PRIVATE_MEDIA_ROOT": str(root / "selected")}):
                with patch("scripts.backup_system.load_db_config") as config:
                    for storage in (None, root / "other"):
                        with self.assertRaisesRegex(ValueError, "selected private media root"):
                            create_backup(root / "backup", storage_dir=storage)
                    config.assert_not_called()

    def test_combined_backup_inventory_rejects_missing_or_unlisted_files(self):
        from scripts.restore_rehearsal import run_rehearsal
        from scripts.backup_system import sha256_file
        tables = ("accounts_user", "procurement_notice", "procurement_noticeversion",
                  "procurement_document", "procurement_documentversion", "procurement_proposal",
                  "procurement_proposalrevision", "procurement_proposalsection", "jobs_job", "jobs_jobattempt")
        with tempfile.TemporaryDirectory() as temp:
            bundle = Path(temp)
            dump = bundle / "db_dump.sql"
            dump.write_bytes(b"-- synthetic fixture")
            digest = sha256_file(dump)
            storage = bundle / "storage"
            storage.mkdir()
            member = storage / "fixture.txt"
            member.write_bytes(b"fixture")
            row = {"relative_path": member.name, "sha256": sha256_file(member), "size_bytes": 7}
            manifest = {"backup_id": "synthetic", "coverage": "DB_AND_STORAGE", "database": {
                "dump_file": dump.name, "dump_sha256": digest, "table_counts": dict.fromkeys(tables, 0),
            }, "storage": {"files": [row], "files_count": 1}}
            (bundle / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            with patch("scripts.restore_rehearsal.psycopg.connect") as connect:
                extra = storage / "unlisted.txt"
                extra.write_bytes(b"unlisted")
                with self.assertRaisesRegex(ValueError, "Storage inventory mismatch"):
                    run_rehearsal(bundle, trusted_dump_sha256=digest)
                extra.unlink()
                member.unlink()
                with self.assertRaisesRegex(ValueError, "Storage verification errors"):
                    run_rehearsal(bundle, trusted_dump_sha256=digest)
                connect.assert_not_called()

    def test_backup_rejects_overlapping_and_symlinked_storage(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            storage = root / "storage"
            storage.mkdir()
            with self.assertRaisesRegex(ValueError, "overlapping"):
                create_backup(storage / "backup", storage_dir=storage)
            source = root / "private.txt"
            source.write_bytes(b"synthetic private content")
            try:
                (storage / "file.txt").symlink_to(source)
            except (OSError, NotImplementedError):
                self.skipTest("symlink unsupported")
            with self.assertRaisesRegex(ValueError, "unsafe link"):
                create_backup(root / "backup", storage_dir=storage)
