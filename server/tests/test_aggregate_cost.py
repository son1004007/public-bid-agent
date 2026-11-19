"""Synthetic aggregate scenarios, no company data or role inference."""
from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from bid_server.procurement.models import (
    CostDepartment, CostMembership, DepartmentCostBasis, Notice, NoticeVersion, DeadlineStatus,
)


class AggregateCostTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="cost-synthetic-member", password="SyntheticFixturePassword123!", must_change_password=False)
        self.approver = User.objects.create_user(username="cost-synthetic-approver", must_change_password=False)
        self.dept = CostDepartment.objects.create(active=True)
        CostMembership.objects.create(department=self.dept, user=self.user, active=True)
        CostMembership.objects.create(department=self.dept, user=self.approver, active=True, can_manage_cost=True)
        self.today = timezone.localdate()
        self.basis = DepartmentCostBasis.objects.create(
            department=self.dept, revision=1, period_start=self.today - timedelta(days=1),
            period_end=self.today + timedelta(days=30), valid_until=self.today + timedelta(days=10),
            labor_total_krw=60100000, allocation_mm=Decimal("12"), available_mm=Decimal("8.75"),
            headcount=12, minimum_headcount=10, rate_rounding_krw=1000000, capacity_rounding_mm=2,
            approved_by=self.approver, approved=True, current=True,
        )
        notice = Notice.objects.create(source="G2B_OFFICIAL_API", notice_number="COST-SYNTHETIC")
        self.version = NoticeVersion.objects.create(notice=notice, version_seq=1, observed_at=timezone.now(),
            title="Synthetic cost notice", buyer="Synthetic", deadline_status=DeadlineStatus.PARSED,
            deadline_at=timezone.now()+timedelta(days=3), source_payload_digest="a"*64)
        notice.current_version = self.version
        notice.save()
        self.url = f"/api/v1/notices/{notice.pk}/cost-scenario"
        self.client = APIClient(enforce_csrf_checks=True)
        token = self.client.get("/api/v1/auth/csrf", secure=True).json()["data"]["csrf_token"]
        self.assertEqual(self.client.post("/api/v1/auth/login",
            {"username":self.user.username,"password":"SyntheticFixturePassword123!"},
            format="json",secure=True,HTTP_X_CSRFTOKEN=token,HTTP_ORIGIN="https://testserver").status_code,200)
        self.token = self.client.get("/api/v1/auth/csrf", secure=True).json()["data"]["csrf_token"]
        self.payload = {"basis_id":str(self.basis.pk),"notice_version_id":str(self.version.pk),
                        "required_mm":"5","revenue_krw":"50000000","external_krw":"1000000",
                        "direct_krw":"1000000","overhead_krw":"0","reserve_krw":"0"}

    def post(self, payload):
        return self.client.post(self.url,payload,format="json",secure=True,
                                HTTP_X_CSRFTOKEN=self.token,HTTP_ORIGIN="https://testserver")

    def test_published_coarse_rate_only_and_no_raw_totals(self):
        data = self.client.get(self.url,secure=True).json()["data"]
        self.assertEqual(data["state"],"READY")
        self.assertNotIn("labor_total_krw",data)
        result = self.post(self.payload)
        self.assertEqual(result.status_code,200)
        result = result.json()["data"]
        self.assertEqual(result["labor_krw"],"25000000")
        self.assertEqual(result["total_cost_krw"],"27000000")
        self.assertEqual(result["profit_krw"],"23000000")
        self.assertEqual(result["margin_percent"],"46.00")
        self.assertEqual(result["state"],"SCENARIO_NOT_APPROVED")
        self.assertEqual(self.post({**self.payload,"required_mm":"8.5"}).json()["data"]["capacity"],"REVIEW_REQUIRED")
        self.assertNotIn("60100000",str(result))

    def test_membership_removed_even_director_denied(self):
        CostMembership.objects.filter(user=self.user).update(active=False)
        self.assertEqual(self.client.get(self.url,secure=True).json()["data"]["state"],"UNVERIFIED")
        self.assertEqual(self.post(self.payload).status_code,409)

    def test_no_small_group_or_expired_basis(self):
        for values in ({"headcount":3},{"headcount":12,"valid_until":self.today-timedelta(days=1)}):
            DepartmentCostBasis.objects.filter(pk=self.basis.pk).update(**values)
            self.assertEqual(self.post(self.payload).status_code,409)

    def test_inputs_and_version_conflict(self):
        for updates in ({"salary":100},{"required_mm":"0"},{"required_mm":"1.001"},{"direct_krw":"-1"},{"revenue_krw":0},{"revenue_krw":True}):
            self.assertEqual(self.post({**self.payload,**updates}).status_code,400)
        self.assertEqual(self.post({**self.payload,"basis_id":"stale"}).status_code,409)
        self.assertEqual(self.client.post(self.url,self.payload,format="json",secure=True).status_code,403)

    def test_cancelled_notice_blocks_new_scenario(self):
        NoticeVersion.objects.filter(pk=self.version.pk).update(cancellation=True)
        self.assertEqual(self.post(self.payload).status_code,409)
