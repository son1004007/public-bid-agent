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
                "database": {"dump_file": "fixture.sql", "dump_sha256": digest, "table_counts": {}},
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
                    run_rehearsal(bundle, rehearsal_db_name="sm03_test_guard_rehearsal")
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
                "database": {"dump_file": "../outside.sql", "dump_sha256": "0" * 64, "table_counts": {}},
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
                "database": {"dump_file": "fixture.sql", "dump_sha256": digest, "table_counts": {}},
                "storage": {"files": [{"relative_path": "../fixture.sql", "sha256": digest}]},
            }), encoding="utf-8")
            with patch("scripts.restore_rehearsal.psycopg.connect") as connect:
                with self.assertRaisesRegex(ValueError, "escapes backup directory"):
                    run_rehearsal(bundle, rehearsal_db_name="sm03_test_guard_rehearsal")
                connect.assert_not_called()
