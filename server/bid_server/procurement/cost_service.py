"""Aggregate-only cost simulation. No raw cost inputs or persistence via HTTP."""
from decimal import Decimal, InvalidOperation, ROUND_FLOOR, ROUND_HALF_UP
import re
from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from bid_server.accounts.models import User
from bid_server.core.permissions import ClosedUntilAuthentication
from .models import CostMembership, DepartmentCostBasis, CostDepartment, Notice, DeadlineStatus

FORMULA = "AGGREGATE_MM_V1"
MONEY_LIMIT = 10 ** 13
FIELDS = {"basis_id", "notice_version_id", "required_mm", "revenue_krw", "external_krw", "direct_krw", "overhead_krw", "reserve_krw"}


class CostUnavailable(Exception):
    pass


def _number(value, *, money=False):
    # Exact decimal strings or integers only; reject bool, floats, and excess precision.
    if type(value) not in (str, int):
        raise ValueError()
    raw = str(value)
    if not re.fullmatch(r"[0-9]{1,13}" if money else r"[0-9]{1,8}(?:\.[0-9]{1,2})?", raw):
        raise ValueError()
    result = Decimal(raw)
    if money and result > MONEY_LIMIT:
        raise ValueError()
    return result


def _basis(actor):
    # Resolve the original request epoch under the same account lock for read and write.
    if User.objects.select_for_update().filter(pk=actor.pk, auth_epoch=actor.auth_epoch, is_active=True,
                                must_change_password=False).filter(
        Q(locked_until__isnull=True) | Q(locked_until__lte=timezone.now())
    ).first() is None:
        raise CostUnavailable()
    memberships = list(CostMembership.objects.filter(
        user_id=actor.pk, active=True, department__active=True,
    ).values_list("department_id", flat=True)[:2])
    if len(memberships) != 1:
        raise CostUnavailable()
    if CostDepartment.objects.select_for_update().filter(pk=memberships[0], active=True).first() is None:
        raise CostUnavailable()
    if CostMembership.objects.select_for_update().filter(
        department_id=memberships[0], user_id=actor.pk, active=True
    ).first() is None:
        raise CostUnavailable()
    today = timezone.localdate()
    basis = DepartmentCostBasis.objects.select_for_update().filter(
        department_id=memberships[0], current=True, approved=True,
        valid_until__gte=today, period_start__lte=today, period_end__gte=today,
    ).first()
    if basis is None or basis.headcount < basis.minimum_headcount:
        raise CostUnavailable()
    # No new approval may be inferred from system role. The current approver
    # must still have an active account and explicit cost membership.
    if CostMembership.objects.select_for_update(of=("self",)).filter(
        department_id=memberships[0], user_id=basis.approved_by_id,
        can_manage_cost=True, active=True, user__is_active=True,
        user__must_change_password=False,
    ).filter(Q(user__locked_until__isnull=True) | Q(user__locked_until__lte=timezone.now())).first() is None:
        raise CostUnavailable()
    _published(basis)
    return basis


def _published(basis):
    # Use exactly the approved coarse rate for all derived results, never the hidden exact rate.
    step = Decimal(basis.rate_rounding_krw)
    rate = ((Decimal(basis.labor_total_krw) / basis.allocation_mm) / step).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP) * step
    mm_step = Decimal(basis.capacity_rounding_mm)
    capacity = (basis.available_mm / mm_step).quantize(Decimal("1"), rounding=ROUND_FLOOR) * mm_step
    if rate <= 0:
        raise CostUnavailable()
    return rate, capacity


def calculate(basis, payload):
    if not isinstance(payload, dict) or set(payload) != FIELDS:
        raise ValueError()
    mm = _number(payload["required_mm"])
    revenue = _number(payload["revenue_krw"], money=True)
    if mm <= 0 or revenue <= 0:
        raise ValueError()
    other = sum(_number(payload[k], money=True) for k in ("external_krw", "direct_krw", "overhead_krw", "reserve_krw"))
    rate, capacity = _published(basis)
    labor = (rate * mm).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    cost = labor + other
    profit = revenue - cost
    margin = (profit / revenue * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {
        "state": "SCENARIO_NOT_APPROVED", "formula": FORMULA,
        "basis_id": str(basis.pk), "basis_revision": basis.revision,
        "notice_version_id": str(payload["notice_version_id"]),
        "labor_krw": str(labor), "total_cost_krw": str(cost),
        "profit_krw": str(profit), "margin_percent": str(margin),
        "capacity": "REVIEW_REQUIRED" if mm > capacity else "WITHIN_PUBLISHED_CAPACITY",
    }


def _notice(notice_id):
    return get_object_or_404(Notice.objects.select_related("current_version"), pk=notice_id)


def _eligible_notice(notice):
    version = notice.current_version
    return bool(version and version.notice_id == notice.pk and not version.cancellation
                and not version.correction and version.deadline_status == DeadlineStatus.PARSED
                and version.deadline_at and version.deadline_at > timezone.now())


class CostScenarioAPIView(APIView):
    permission_classes = [ClosedUntilAuthentication]

    def get(self, request, notice_id):
        try:
            with transaction.atomic():
                basis = _basis(request.user)
                notice = get_object_or_404(Notice.objects.select_for_update(), pk=notice_id)
                if not _eligible_notice(notice):
                    raise CostUnavailable()
                return Response({"state": "READY", "basis_id": str(basis.pk), "basis_revision": basis.revision,
                                 "notice_version_id": str(notice.current_version_id),
                                 "period_start": basis.period_start.isoformat(), "period_end": basis.period_end.isoformat()})
        except CostUnavailable:
            return Response({"state": "UNVERIFIED"})

    def post(self, request, notice_id):
        try:
            with transaction.atomic():
                actor = User.objects.select_for_update().filter(pk=request.user.pk).first()
                if actor is None or actor.auth_epoch != request.user.auth_epoch:
                    raise CostUnavailable()
                basis = _basis(request.user)
                notice = get_object_or_404(Notice.objects.select_for_update(), pk=notice_id)
                if not _eligible_notice(notice):
                    raise CostUnavailable()
                payload = request.data
                if not isinstance(payload, dict) or set(payload) != FIELDS:
                    raise ValueError()
                if payload["basis_id"] != str(basis.pk) or payload["notice_version_id"] != str(notice.current_version_id):
                    return Response({"error": "SCENARIO_VERSION_CHANGED"}, status=409)
                return Response(calculate(basis, payload))
        except CostUnavailable:
            return Response({"error": "COST_BASIS_UNAVAILABLE"}, status=409)
        except (ValueError, InvalidOperation):
            return Response({"error": "INVALID_SCENARIO"}, status=400)
