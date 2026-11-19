"""Real PostgreSQL nonempty MVP DB+storage restore in Django's isolated test database."""
import json
import os
import tempfile
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TransactionTestCase
from django.utils import timezone
from bid_server.procurement.models import (
    CostDepartment, CostMembership, DepartmentCostBasis, SharedBidReviewEvent, Notice, NoticeVersion,
)
from scripts.backup_system import create_backup, sha256_file, MVP_FINGERPRINT_TABLES, MVP_TABLES
from scripts.restore_rehearsal import run_rehearsal


class MVPRecoveryTests(TransactionTestCase):
    def test_nonempty_mvp_restore_and_content_parity(self):
        if connection.vendor != "postgresql" or os.environ.get("DJANGO_SETTINGS_MODULE") != "bid_server.settings.test_postgres":
            self.skipTest("Isolated PostgreSQL fixture required")
        cfg = json.loads(Path(os.environ["SM03_TEST_DB_CONFIG_FILE"]).read_text(encoding="utf-8"))
        # Refuse the source/provisioned database; only Django's disposable test DB.
        self.assertEqual(connection.settings_dict["NAME"], "test_" + cfg["NAME"])
        self.assertEqual(cfg["HOST"], "127.0.0.1")
        self.assertTrue(cfg["NAME"].startswith("sm03_"))
        cfg["NAME"] = connection.settings_dict["NAME"]
        user = get_user_model().objects.create_user(username="synthetic-recovery-owner", must_change_password=False)
        department = CostDepartment.objects.create(active=True)
        CostMembership.objects.create(department=department,user=user,active=True,can_decide=True,can_manage_cost=True)
        today = timezone.localdate()
        basis = DepartmentCostBasis.objects.create(department=department,revision=1,period_start=today,
            period_end=today+timedelta(days=30),valid_until=today+timedelta(days=10),
            labor_total_krw=60000000,allocation_mm=Decimal("12"),available_mm=Decimal("10"),
            headcount=12,minimum_headcount=10,rate_rounding_krw=1000000,capacity_rounding_mm=2,
            approved_by=user,approved=True,current=True)
        notice = Notice.objects.create(source="G2B_OFFICIAL_API",notice_number="SYNTHETIC-RESTORE-MVP")
        version = NoticeVersion.objects.create(notice=notice,version_seq=1,observed_at=timezone.now(),
            title="Synthetic restore",buyer="Synthetic",source_payload_digest="a"*64)
        notice.current_version=version
        notice.save()
        SharedBidReviewEvent.objects.create(department=department,notice_version=version,actor=user,
            revision=1,kind="ESTIMATE",basis=basis,payload={"synthetic_profit":"23000000"})
        SharedBidReviewEvent.objects.create(department=department,notice_version=version,actor=user,
            revision=2,kind="DECISION",payload={"decision":"HOLD","reason":"EVIDENCE_PENDING"})
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            config=root/"fixture.json"
            config.write_text(json.dumps(cfg),encoding="utf-8")
            config.chmod(0o600)
            storage=root/"source"
            storage.mkdir()
            artifact=storage/"synthetic-rfp.txt"
            artifact.write_bytes(b"synthetic MVP recovery")
            bundle=create_backup(root/"backup",config,storage)
            manifest=json.loads((bundle/"manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(set(manifest["database"]["table_counts"]),set(MVP_TABLES))
            for table in MVP_FINGERPRINT_TABLES:
                self.assertGreater(manifest["database"]["table_counts"][table],0)
            report=run_rehearsal(bundle,"sm03_test_mvp_rehearsal_"+uuid4().hex[:8],config,
                trusted_dump_sha256=sha256_file(bundle/"db_dump.sql"),
                trusted_manifest_sha256=sha256_file(bundle/"manifest.json"))
            self.assertEqual(report["status"],"SUCCESS")
            self.assertEqual(report["mvp_content_verification"],"PASS")
            self.assertEqual(report["storage_recovery_verification"],"PASS")
            self.assertEqual(report["new_write_verification"],"PASS")
            self.assertEqual(SharedBidReviewEvent.objects.count(),2)
            self.assertEqual(artifact.read_bytes(),b"synthetic MVP recovery")
            print("MVP_DB_STORAGE_RESTORE_CONTENT_PASS")
