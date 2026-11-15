from django.test import SimpleTestCase
from pathlib import Path
import sys
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
