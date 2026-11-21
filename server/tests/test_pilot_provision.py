"""Initial scope and immutable aggregate revision, synthetic fixtures only."""
import hashlib
import json
import tempfile
from pathlib import Path
from io import StringIO
from uuid import uuid4
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.test import TestCase
from django.utils import timezone
from bid_server.procurement.models import CostDepartment, CostMembership, DepartmentCostBasis


class PilotProvisionTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user(username="synthetic-provision",must_change_password=False)
        today=timezone.localdate()
        self.plan={"department_id":str(uuid4()),"expected_revision":0,
            "members":[{"user_id":str(self.user.pk),"can_manage_cost":True,"can_decide":True}],
            "basis":{"period_start":today.isoformat(),"period_end":(today+timedelta(days=10)).isoformat(),
                     "valid_until":(today+timedelta(days=5)).isoformat(),"labor_total_krw":60100000,
                     "allocation_mm":"12","available_mm":"8","headcount":12,"minimum_headcount":10,
                     "rate_rounding_krw":1000000,"capacity_rounding_mm":2,"approved_by_id":str(self.user.pk)}}

    def run_plan(self,apply=False,wrong_digest=False):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"plan.json"
            raw=json.dumps(self.plan).encode()
            path.write_bytes(raw)
            path.chmod(0o600)
            output=StringIO()
            call_command("pilot_provision",plan=str(path),trusted_plan_sha256="0"*64 if wrong_digest else hashlib.sha256(raw).hexdigest(),
                         synthetic=True,apply=apply,stdout=output)
            self.assertNotIn("60100000",output.getvalue())
            self.assertNotIn(str(self.user.pk),output.getvalue())
            return json.loads(output.getvalue())

    def test_validate_apply_replay_and_append_revision(self):
        self.assertEqual(self.run_plan()["status"],"VALIDATED")
        self.assertFalse(CostDepartment.objects.exists())
        self.assertEqual(self.run_plan(True)["status"],"APPLIED")
        self.assertEqual(CostMembership.objects.count(),1)
        with self.assertRaises(CommandError):
            self.run_plan(True)
        self.plan["expected_revision"]=1
        self.plan["basis"]["labor_total_krw"]=72000000
        self.assertEqual(self.run_plan(True)["status"],"APPLIED")
        self.assertEqual(DepartmentCostBasis.objects.count(),2)
        self.assertEqual(DepartmentCostBasis.objects.get(revision=1).labor_total_krw,60100000)
        self.assertFalse(DepartmentCostBasis.objects.get(revision=1).current)
        self.assertEqual(DepartmentCostBasis.objects.get(current=True).revision,2)

    def test_reject_extra_fields_and_wrong_digest(self):
        with self.assertRaises(CommandError):
            self.run_plan(True,True)
        self.plan["basis"]["employee_salary"]=123
        with self.assertRaises(CommandError):
            self.run_plan(True)
        self.assertFalse(CostDepartment.objects.exists())

    def test_no_membership_override_or_cross_department(self):
        self.run_plan(True)
        self.plan["department_id"]=str(uuid4())
        with self.assertRaises(CommandError):
            self.run_plan(True)
        self.assertEqual(CostDepartment.objects.count(),1)
        self.plan["department_id"]=str(CostDepartment.objects.get().pk)
        self.plan["expected_revision"]=1
        self.plan["members"][0]["can_decide"]=False
        with self.assertRaises(CommandError):
            self.run_plan(True)
        self.assertEqual(DepartmentCostBasis.objects.count(),1)

    def test_inactive_account_and_small_group_blocked(self):
        self.plan["basis"]["headcount"]=1
        with self.assertRaises(CommandError):
            self.run_plan(True)
        self.plan["basis"]["headcount"]=12
        self.user.is_active=False
        self.user.save(update_fields=["is_active"])
        with self.assertRaises(CommandError):
            self.run_plan(True)
        self.assertFalse(CostDepartment.objects.exists())
