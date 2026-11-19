"""Synthetic department scope, revisions, estimate publication, human decision."""
from .test_aggregate_cost import AggregateCostTests
from bid_server.procurement.models import CostDepartment, CostMembership, DepartmentCostBasis, SharedBidReviewEvent, NoticeVersion
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient


class SharedReviewTests(AggregateCostTests):
    def setUp(self):
        super().setUp()
        self.version.source_url = "https://g2b.go.kr/synthetic-cost-review"
        self.version.save(update_fields=["source_url"])
        self.shared = self.url.replace("cost-scenario", "shared-review")
        self.approver.set_password("SyntheticFixturePassword123!")
        self.approver.save()
        CostMembership.objects.filter(user=self.approver).update(can_decide=True)
        self.approver_client = self.login(self.approver)

    def login(self, user):
        client = APIClient(enforce_csrf_checks=True)
        token = client.get("/api/v1/auth/csrf",secure=True).json()["data"]["csrf_token"]
        self.assertEqual(client.post("/api/v1/auth/login",{"username":user.username,"password":"SyntheticFixturePassword123!"},
            format="json",secure=True,HTTP_X_CSRFTOKEN=token,HTTP_ORIGIN="https://testserver").status_code,200)
        return client

    def event(self, client, kind, revision, payload):
        token = client.get("/api/v1/auth/csrf",secure=True).json()["data"]["csrf_token"]
        return client.post(self.shared, {"kind":kind,"expected_revision":revision,
            "notice_version_id":str(self.version.pk),"payload":payload},format="json",secure=True,
            HTTP_X_CSRFTOKEN=token,HTTP_ORIGIN="https://testserver")

    def review(self, client):
        return client.get(self.shared,secure=True).json()["data"]

    def test_shared_opinion_estimate_decision_and_requery(self):
        self.assertEqual(self.event(self.client,"OPINION",0,{"opinion":"SUPPORT"}).status_code,201)
        self.assertEqual(self.event(self.client,"ESTIMATE",1,self.payload).status_code,403)
        decision = {"decision":"BID","reason":"READY","attestations":["official_rfp","qualification","technology","staffing","cost"],"estimate_revision":2}
        self.assertEqual(self.event(self.client,"DECISION",1,decision).status_code,403)
        self.assertEqual(self.event(self.approver_client,"DECISION",1,decision).status_code,409)
        self.assertEqual(self.event(self.approver_client,"ESTIMATE",1,self.payload).status_code,201)
        self.assertEqual(self.event(self.approver_client,"DECISION",2,decision).status_code,201)
        self.assertEqual(self.review(self.client)["current_decision"]["payload"]["decision"],"BID")
        self.assertEqual(self.review(self.client)["current_estimate"]["payload"]["result"]["profit_krw"],"23000000")
        self.assertEqual(SharedBidReviewEvent.objects.count(),3)
        self.assertEqual(self.event(self.approver_client,"OPINION",2,{"opinion":"REVIEW"}).status_code,409)
        DepartmentCostBasis.objects.filter(pk=self.basis.pk).update(current=False)
        self.assertEqual(self.review(self.client)["current_estimate"]["payload"],{"state":"BASIS_REVIEW_REQUIRED"})
        self.assertEqual(self.review(self.client)["current_decision"]["payload"]["state"],"BASIS_REVIEW_REQUIRED")

    def test_other_department_and_revoked_member(self):
        self.assertEqual(self.event(self.client,"OPINION",0,{"opinion":"SUPPORT"}).status_code,201)
        other = get_user_model().objects.create_user(username="other-department",password="SyntheticFixturePassword123!",must_change_password=False,role="director")
        dep = CostDepartment.objects.create(active=True)
        CostMembership.objects.create(user=other,department=dep,active=True)
        client = self.login(other)
        self.assertEqual(self.review(client)["history"],[])
        CostMembership.objects.filter(user=self.user).update(active=False)
        self.assertEqual(self.review(self.client)["state"],"UNAVAILABLE")
        self.assertEqual(self.event(self.client,"OPINION",1,{"opinion":"SUPPORT"}).status_code,403)

    def test_strict_payload_and_hold(self):
        self.assertEqual(self.event(self.client,"OPINION",0,{"opinion":"SUPPORT","salary":1}).status_code,400)
        self.assertEqual(self.event(self.approver_client,"DECISION",0,{"decision":"HOLD","reason":"EVIDENCE_PENDING","attestations":[],"estimate_revision":0}).status_code,201)
        self.assertEqual(self.review(self.client)["current_decision"]["payload"]["decision"],"HOLD")
        self.assertEqual(self.client.post(self.shared,{"kind":"OPINION"},format="json",secure=True).status_code,403)
