"""Department-scoped versioned review. No submission or automated eligibility claim."""
from decimal import InvalidOperation
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from bid_server.accounts.models import User
from bid_server.core.permissions import ClosedUntilAuthentication
from .cost_service import _basis, _eligible_notice, calculate, CostUnavailable, FIELDS
from .models import CostDepartment, CostMembership, Notice, SharedBidReviewEvent
from .serializers import public_source_url

OPINIONS = {"REVIEW", "QUALIFICATION_RISK", "TECHNICAL_RISK", "STAFFING_RISK", "COST_RISK", "SUPPORT", "OPPOSE"}
DECISIONS = {"BID", "HOLD", "NO_BID"}
ATTESTATIONS = {"official_rfp", "qualification", "technology", "staffing", "cost"}
REASONS = {"READY", "EVIDENCE_PENDING", "QUALIFICATION_RISK", "TECHNICAL_RISK", "STAFFING_RISK", "COST_RISK", "STRATEGY"}


class ScopeDenied(Exception):
    pass


def _scope(actor):
    account = User.objects.select_for_update().filter(pk=actor.pk, auth_epoch=actor.auth_epoch,
        is_active=True, must_change_password=False).filter(
        Q(locked_until__isnull=True) | Q(locked_until__lte=timezone.now())).first()
    if account is None:
        raise ScopeDenied()
    ids = list(CostMembership.objects.filter(user=account, active=True, department__active=True)
               .values_list("department_id", flat=True)[:2])
    if len(ids) != 1:
        raise ScopeDenied()
    department = CostDepartment.objects.select_for_update().filter(pk=ids[0], active=True).first()
    if department is None:
        raise ScopeDenied()
    member = CostMembership.objects.select_for_update().filter(department=department, user=account, active=True).first()
    if member is None:
        raise ScopeDenied()
    return member


def _current_basis(actor):
    try:
        return _basis(actor)
    except CostUnavailable:
        return None


def _safe_event(event, basis):
    payload = event.payload
    if event.kind == "ESTIMATE":
        payload = payload if basis is not None and event.basis_id == basis.pk else {"state": "BASIS_REVIEW_REQUIRED"}
    elif event.kind == "DECISION":
        payload = {k: payload[k] for k in ("decision", "reason", "attestations", "estimate_revision") if k in payload}
        if payload.get("decision") == "BID" and (basis is None or event.basis_id != basis.pk):
            payload["state"] = "BASIS_REVIEW_REQUIRED"
    else:
        payload = {"opinion": payload.get("opinion")}
    return {"revision": event.revision, "kind": event.kind, "actor_id": str(event.actor_id),
            "created_at": event.created_at.isoformat(), "payload": payload}


def _active(notice):
    return _eligible_notice(notice) and notice.source == "G2B_OFFICIAL_API" and bool(public_source_url(notice.current_version.source_url))


class SharedReviewAPIView(APIView):
    permission_classes = [ClosedUntilAuthentication]

    def get(self, request, notice_id):
        try:
            with transaction.atomic():
                member = _scope(request.user)
                basis = _current_basis(request.user)
                notice = get_object_or_404(Notice.objects.select_for_update(), pk=notice_id)
                if notice.current_version is None or notice.current_version.notice_id != notice.pk:
                    return Response({"state": "UNAVAILABLE"})
                events = SharedBidReviewEvent.objects.filter(department=member.department, notice_version=notice.current_version)
                history = list(events.order_by("-revision")[:50])
                decision = events.filter(kind="DECISION").order_by("-revision").first()
                estimate = events.filter(kind="ESTIMATE").order_by("-revision").first()
                active = _active(notice)
                current_decision = _safe_event(decision, basis) if decision else None
                if current_decision and current_decision["payload"].get("decision") == "BID" and (
                    not active or estimate is None or decision.payload.get("estimate_revision") != estimate.revision
                ):
                    current_decision["payload"]["state"] = "REVIEW_REQUIRED"
                return Response({"state": "READY", "notice_version_id": str(notice.current_version_id),
                    "revision": history[0].revision if history else 0, "can_decide": member.can_decide,
                    "can_publish_estimate": member.can_manage_cost and basis is not None and active,
                    "can_bid": member.can_decide and active and basis is not None and estimate is not None and estimate.basis_id == basis.pk,
                    "current_decision": current_decision,
                    "current_estimate": _safe_event(estimate, basis) if estimate else None,
                    "history": [_safe_event(event, basis) for event in history]})
        except ScopeDenied:
            return Response({"state": "UNAVAILABLE"})

    def post(self, request, notice_id):
        try:
            with transaction.atomic():
                member = _scope(request.user)
                basis = _current_basis(request.user)
                # Actor -> department/membership/basis -> notice. Serializes revisions.
                notice = get_object_or_404(Notice.objects.select_for_update(), pk=notice_id)
                if notice.current_version is None or notice.current_version.notice_id != notice.pk:
                    return Response({"error": "CURRENT_VERSION_UNAVAILABLE"}, status=409)
                data = request.data
                if not isinstance(data, dict) or set(data) != {"kind", "notice_version_id", "expected_revision", "payload"}:
                    raise ValueError()
                if type(data["expected_revision"]) is not int or data["expected_revision"] < 0:
                    raise ValueError()
                events = SharedBidReviewEvent.objects.filter(department=member.department, notice_version=notice.current_version)
                revision = events.order_by("-revision").values_list("revision", flat=True).first() or 0
                if data["notice_version_id"] != str(notice.current_version_id) or data["expected_revision"] != revision:
                    return Response({"error": "REVIEW_VERSION_CHANGED"}, status=409)
                kind, payload = data["kind"], data["payload"]
                if not isinstance(payload, dict) or not isinstance(kind, str):
                    raise ValueError()
                event_basis = None
                if kind == "OPINION":
                    if set(payload) != {"opinion"} or not isinstance(payload["opinion"], str) or payload["opinion"] not in OPINIONS:
                        raise ValueError()
                    stored = {"opinion": payload["opinion"]}
                elif kind == "ESTIMATE":
                    if not member.can_manage_cost:
                        return Response({"error": "BUSINESS_PERMISSION_REQUIRED"}, status=403)
                    if not _active(notice) or basis is None:
                        raise CostUnavailable()
                    if set(payload) != FIELDS:
                        raise ValueError()
                    if payload["basis_id"] != str(basis.pk) or payload["notice_version_id"] != str(notice.current_version_id):
                        return Response({"error": "SCENARIO_VERSION_CHANGED"}, status=409)
                    result = calculate(basis, payload)
                    stored = {"assumptions": {k: str(payload[k]) for k in FIELDS - {"basis_id", "notice_version_id"}},
                              "result": result, "state": "PUBLISHED_ESTIMATE_NOT_FINAL_BID"}
                    event_basis = basis
                elif kind == "DECISION":
                    if not member.can_decide:
                        return Response({"error": "BUSINESS_PERMISSION_REQUIRED"}, status=403)
                    if set(payload) != {"decision", "reason", "attestations", "estimate_revision"}:
                        raise ValueError()
                    decision, reason, attestations, estimate_revision = (payload[k] for k in ("decision","reason","attestations","estimate_revision"))
                    if (not isinstance(decision, str) or decision not in DECISIONS or not isinstance(reason, str)
                        or reason not in REASONS or not isinstance(attestations, list)
                        or any(not isinstance(a, str) or a not in ATTESTATIONS for a in attestations)
                        or len(attestations) != len(set(attestations)) or type(estimate_revision) is not int or estimate_revision < 0):
                        raise ValueError()
                    estimate = events.filter(kind="ESTIMATE").order_by("-revision").first()
                    if decision == "BID":
                        if (not _active(notice) or basis is None or estimate is None or estimate.basis_id != basis.pk
                            or estimate.revision != estimate_revision or set(attestations) != ATTESTATIONS
                            or reason != "READY" or estimate.payload.get("result", {}).get("capacity") != "WITHIN_PUBLISHED_CAPACITY"):
                            return Response({"error": "DECISION_PREREQUISITES_UNVERIFIED"}, status=409)
                        event_basis = basis
                    elif reason == "READY" or attestations or estimate_revision != 0:
                        raise ValueError()
                    stored = {"decision": decision, "reason": reason, "attestations": sorted(attestations),
                              "estimate_revision": estimate_revision}
                else:
                    raise ValueError()
                event = SharedBidReviewEvent.objects.create(department=member.department,
                   notice_version=notice.current_version, actor_id=request.user.pk,
                   revision=revision + 1, kind=kind, payload=stored, basis=event_basis)
                return Response(_safe_event(event, basis), status=201)
        except ScopeDenied:
            return Response({"error": "BUSINESS_PERMISSION_REQUIRED"}, status=403)
        except CostUnavailable:
            return Response({"error":"COST_BASIS_UNAVAILABLE"}, status=409)
        except (ValueError, InvalidOperation):
            return Response({"error":"INVALID_REVIEW_EVENT"}, status=400)
