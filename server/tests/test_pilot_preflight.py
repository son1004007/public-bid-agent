"""No real environment access: fixed-status output and fail-closed synthetic preflight."""
import json
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.test import TestCase
from django.utils import timezone

from bid_server.procurement.models import CostDepartment, CostMembership, DepartmentCostBasis, Notice, NoticeVersion, DeadlineStatus


class PilotPreflightTests(TestCase):
    def test_empty_scope_blocks_without_disclosure(self):
        output = StringIO()
        with self.assertRaisesMessage(CommandError,"Pilot preflight blocked."):
            call_command("pilot_preflight",synthetic=True,stdout=output)
        result=json.loads(output.getvalue())
        self.assertEqual(result["schema"],"PASS")
        self.assertEqual(result["business_scope"],"BLOCKED")
        self.assertEqual(result["release"],"NOT_AUTHORIZED_BY_PREFLIGHT")

    def test_approved_mode_rejects_test_settings_before_db_probe(self):
        with patch("bid_server.procurement.management.commands.pilot_preflight.MigrationExecutor") as executor:
            with self.assertRaises(CommandError):
                call_command("pilot_preflight",approved_read_only=True,stdout=StringIO())
            executor.assert_not_called()

    def test_complete_synthetic_scope_read_only_then_revoked(self):
        user = get_user_model().objects.create_user(username="synthetic-private-name",must_change_password=False)
        department=CostDepartment.objects.create(active=True)
        CostMembership.objects.create(department=department,user=user,active=True,can_manage_cost=True,can_decide=True)
        today=timezone.localdate()
        basis=DepartmentCostBasis.objects.create(department=department,revision=1,period_start=today,
            period_end=today+timedelta(days=10),valid_until=today+timedelta(days=5),
            labor_total_krw=60100000,allocation_mm=Decimal("12"),available_mm=Decimal("8"),
            headcount=12,minimum_headcount=10,rate_rounding_krw=1000000,capacity_rounding_mm=2,
            approved_by=user,approved=True,current=True)
        notice=Notice.objects.create(source="G2B_OFFICIAL_API",notice_number="SYNTHETIC-PREFLIGHT")
        ver=NoticeVersion.objects.create(notice=notice,version_seq=1,observed_at=timezone.now(),
             source_payload_digest="a"*64,title="Synthetic",buyer="Synthetic",
             deadline_status=DeadlineStatus.PARSED,deadline_at=timezone.now()+timedelta(days=3))
        notice.current_version=ver
        notice.save()
        output=StringIO()
        call_command("pilot_preflight",synthetic=True,stdout=output)
        result=json.loads(output.getvalue())
        self.assertEqual(result["status"],"CHECKS_PASS")
        self.assertEqual(result["release"],"NOT_AUTHORIZED_BY_PREFLIGHT")
        for private in (user.username,str(user.pk),str(department.pk),str(basis.pk),"60100000"):
            self.assertNotIn(private,output.getvalue())
        basis.refresh_from_db()
        self.assertEqual(basis.labor_total_krw,60100000)
        CostMembership.objects.filter(user=user).update(can_decide=False)
        output=StringIO()
        with self.assertRaises(CommandError):
            call_command("pilot_preflight",synthetic=True,stdout=output)
        self.assertEqual(json.loads(output.getvalue())["business_scope"],"BLOCKED")
