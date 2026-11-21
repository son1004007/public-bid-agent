"""Operator-only, aggregate-only, initial pilot scope and append-only basis provisioning."""
import hashlib
import json
import os
import re
import stat
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.models import Q, Max
from django.utils import timezone

from bid_server.accounts.models import User
from bid_server.config import REPOSITORY_ROOT
from bid_server.procurement.models import CostDepartment, CostMembership, DepartmentCostBasis
from bid_server.procurement.cost_service import _published, CostUnavailable

MAX_BYTES = 65536
TOP = {"department_id", "expected_revision", "members", "basis"}
MEMBER = {"user_id", "can_manage_cost", "can_decide"}
BASIS = {"period_start", "period_end", "valid_until", "labor_total_krw", "allocation_mm",
         "available_mm", "headcount", "minimum_headcount", "rate_rounding_krw",
         "capacity_rounding_mm", "approved_by_id"}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError()
        result[key] = value
    return result


def identifier(value):
    if not isinstance(value, str):
        raise ValueError()
    result = UUID(value)
    if str(result) != value:
        raise ValueError()
    return result


def integer(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError()
    return value


def mm(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,10}(?:\.[0-9]{1,2})?", value):
        raise ValueError()
    return Decimal(value)


def day(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError()
    return date.fromisoformat(value)


def read_plan(path, digest):
    path = Path(path)
    if not path.is_absolute() or not re.fullmatch(r"[a-f0-9]{64}", digest or ""):
        raise ValueError()
    if path.resolve().is_relative_to(REPOSITORY_ROOT):
        raise ValueError()
    for component in (path, *path.parents):
        meta = component.lstat()
        if stat.S_ISLNK(meta.st_mode) or getattr(meta, "st_file_attributes", 0) & 1024:
            raise ValueError()
    with os.fdopen(os.open(path, os.O_RDONLY | getattr(os,"O_NOFOLLOW",0) | getattr(os,"O_NONBLOCK",0)), "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or (os.name != "nt" and info.st_mode & 0o077):
            raise ValueError()
        raw = stream.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES or hashlib.sha256(raw).hexdigest()!=digest:
        raise ValueError()
    plan=json.loads(raw,object_pairs_hook=unique_object)
    if not isinstance(plan,dict) or set(plan)!=TOP:
        raise ValueError()
    department_id=identifier(plan["department_id"])
    revision=integer(plan["expected_revision"],0,2147483646)
    rows=plan["members"]
    if not isinstance(rows,list) or not 1<=len(rows)<=200:
        raise ValueError()
    members={}
    for row in rows:
        if not isinstance(row,dict) or set(row)!=MEMBER:
            raise ValueError()
        uid=identifier(row["user_id"])
        if uid in members or any(type(row[k]) is not bool for k in ("can_manage_cost","can_decide")):
            raise ValueError()
        members[uid]=(row["can_manage_cost"],row["can_decide"])
    if not any(v[0] for v in members.values()) or not any(v[1] for v in members.values()):
        raise ValueError()
    raw_basis=plan["basis"]
    if not isinstance(raw_basis,dict) or set(raw_basis)!=BASIS:
        raise ValueError()
    basis={k:day(raw_basis[k]) for k in ("period_start","period_end","valid_until")}
    basis.update({k:mm(raw_basis[k]) for k in ("allocation_mm","available_mm")})
    basis.update({k:integer(raw_basis[k],1,2147483647) for k in
                  ("headcount","minimum_headcount","rate_rounding_krw","capacity_rounding_mm")})
    basis["labor_total_krw"]=integer(raw_basis["labor_total_krw"],1,10**13-1)
    basis["approved_by_id"]=identifier(raw_basis["approved_by_id"])
    today=timezone.localdate()
    if (basis["minimum_headcount"]<2 or basis["headcount"]<basis["minimum_headcount"]
        or not basis["period_start"]<=today<=basis["period_end"]
        or not today<=basis["valid_until"]<=basis["period_end"]
        or not 0<basis["allocation_mm"] or not 0<=basis["available_mm"]<=basis["allocation_mm"]
        or not members.get(basis["approved_by_id"],(False,False))[0]):
        raise ValueError()
    _published(DepartmentCostBasis(**basis))
    return department_id,revision,members,basis


def provision(plan, apply):
    department_id,expected,members,basis=plan
    with transaction.atomic():
        # Account locks precede department locks, consistent with cost and review APIs.
        users=list(User.objects.select_for_update().filter(pk__in=members,is_active=True,
            must_change_password=False).filter(Q(locked_until__isnull=True)|Q(locked_until__lte=timezone.now())).order_by("pk"))
        if {u.pk for u in users}!=set(members):
            raise ValueError()
        department=CostDepartment.objects.select_for_update().filter(pk=department_id).first()
        if CostMembership.objects.filter(user_id__in=members,active=True,department__active=True).exclude(department_id=department_id).exists():
            raise ValueError()
        if department is None:
            if expected!=0:
                raise ValueError()
            if apply:
                department=CostDepartment.objects.create(pk=department_id,active=True)
                CostMembership.objects.bulk_create([CostMembership(department=department,user_id=uid,active=True,
                    can_manage_cost=flags[0],can_decide=flags[1]) for uid,flags in members.items()])
        else:
            if not department.active or expected==0:
                raise ValueError()
            existing={row.user_id:(row.can_manage_cost,row.can_decide) for row in
                CostMembership.objects.select_for_update().filter(department=department,active=True)}
            # Initial provisioning or basis replacement only. Roles are not changed by rotation.
            if existing!=members:
                raise ValueError()
            current=DepartmentCostBasis.objects.select_for_update().filter(department=department,current=True).first()
            maximum=DepartmentCostBasis.objects.filter(department=department).aggregate(n=Max("revision"))["n"]
            if current is None or current.revision!=expected or maximum!=expected:
                raise ValueError()
            if apply:
                current.current=False
                current.save(update_fields=["current"])
        if apply:
            DepartmentCostBasis.objects.create(department=department,revision=expected+1,
                approved=True,current=True,**basis)


class Command(BaseCommand):
    help="Validate or provision approved aggregate-only pilot plan; never creates accounts or changes existing membership."
    requires_system_checks=[]

    def add_arguments(self,parser):
        parser.add_argument("--plan",required=True)
        parser.add_argument("--trusted-plan-sha256",required=True)
        parser.add_argument("--synthetic",action="store_true")
        parser.add_argument("--apply",action="store_true")

    def handle(self,*args,**options):
        module=settings.SETTINGS_MODULE
        synthetic=options["synthetic"]
        if synthetic:
            if module not in {"bid_server.settings.test","bid_server.settings.test_postgres"}:
                raise CommandError("Synthetic test settings required.")
            name=str(connection.settings_dict["NAME"])
            if ((connection.vendor=="postgresql" and not name.startswith("test_sm03_"))
                or (connection.vendor=="sqlite" and not (name==":memory:" or name.startswith("file:memorydb_")))
                or connection.vendor not in {"sqlite","postgresql"}):
                raise CommandError("Disposable test database required.")
        elif (module!="bid_server.settings.base" or connection.vendor!="postgresql"
              or getattr(getattr(settings,"CONFIG",None),"environment",None)!="production"):
            raise CommandError("Approved production base settings required.")
        if options["apply"] and not synthetic:
            if not sys.stdin.isatty() or not sys.stderr.isatty() or input("Type APPROVED PILOT APPLY: ")!="APPROVED PILOT APPLY":
                raise CommandError("Interactive operator confirmation required.")
        try:
            plan=read_plan(options["plan"],options["trusted_plan_sha256"])
            provision(plan,options["apply"])
        except Exception:
            # Input values and database exception details are intentionally omitted.
            raise CommandError("Pilot plan rejected; no changes committed.") from None
        self.stdout.write(json.dumps({"status":"APPLIED" if options["apply"] else "VALIDATED",
            "mode":"SYNTHETIC" if synthetic else "OPERATOR","release":"NOT_AUTHORIZED_BY_PROVISIONING"}))
