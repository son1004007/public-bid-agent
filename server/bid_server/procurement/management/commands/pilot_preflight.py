"""Read-only pilot preflight. No account changes, migrations, starts, or deployment."""
import json
import os
import stat
from pathlib import Path

from django.conf import settings
from django.core import checks
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.models import Q
from django.utils import timezone

from bid_server.procurement.cost_service import CostUnavailable, _published
from bid_server.procurement.models import CostDepartment, CostMembership, DepartmentCostBasis, Notice, DeadlineStatus

TEST_SETTINGS = {"bid_server.settings.test", "bid_server.settings.test_postgres"}


def business_checks():
    now = timezone.now()
    today = timezone.localdate()
    members = CostMembership.objects.filter(active=True, department__active=True,
                user__is_active=True, user__must_change_password=False).filter(
                Q(user__locked_until__isnull=True) | Q(user__locked_until__lte=now))
    # An account with multiple active department memberships is not usable in MVP.
    usable = set()
    ambiguous = False
    for user_id, department_id in members.values_list("user_id", "department_id"):
        if CostMembership.objects.filter(user_id=user_id,active=True,department__active=True).count() == 1:
            usable.add((user_id,department_id))
        else:
            ambiguous = True
    found = False
    incomplete = ambiguous
    for department in CostDepartment.objects.filter(active=True).iterator():
        current_members = members.filter(department=department)
        manager_ids = {x for x in current_members.filter(can_manage_cost=True).values_list("user_id",flat=True)
                       if (x,department.pk) in usable}
        decider = any((x,department.pk) in usable for x in current_members.filter(can_decide=True).values_list("user_id",flat=True))
        basis = DepartmentCostBasis.objects.filter(department=department,current=True,approved=True,
                       period_start__lte=today,period_end__gte=today,valid_until__gte=today).first()
        valid = False
        if basis is not None and basis.headcount >= basis.minimum_headcount and basis.approved_by_id in manager_ids:
            try:
                _published(basis)
                valid = True
            except CostUnavailable:
                pass
        if manager_ids and decider and valid:
            found = True
        else:
            incomplete = True
    return {
        "business_scope": "PASS" if found and not incomplete else "BLOCKED",
        "notice_presence": "PASS" if Notice.objects.filter(current_version__cancellation=False,
             current_version__correction=False, current_version__deadline_status=DeadlineStatus.PARSED,
             current_version__deadline_at__gt=now).exists() else "BLOCKED",
    }


class Command(BaseCommand):
    help = "Read-only local pilot preflight; reports fixed statuses only, never release approval."
    requires_system_checks = []

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--synthetic", action="store_true", help="Only dedicated test settings")
        group.add_argument("--approved-read-only", action="store_true", help="Only after target/config read-only authorization")

    def handle(self, *args, **options):
        module = settings.SETTINGS_MODULE
        synthetic = options["synthetic"]
        if synthetic and module not in TEST_SETTINGS:
            raise CommandError("Synthetic preflight requires dedicated test settings.")
        if synthetic:
            name = str(connection.settings_dict["NAME"])
            if connection.vendor == "postgresql" and not name.startswith("test_sm03_"):
                raise CommandError("Synthetic PostgreSQL preflight requires Django disposable test DB.")
            if connection.vendor == "sqlite" and not (name == ":memory:" or name.startswith("file:memorydb_")):
                raise CommandError("Synthetic SQLite preflight requires in-memory DB.")
        elif (module != "bid_server.settings.base" or getattr(getattr(settings,"CONFIG",None),"environment",None) != "production"
                or connection.vendor != "postgresql"):
            raise CommandError("Approved preflight requires production base settings and PostgreSQL.")
        result = {"mode": "SYNTHETIC" if synthetic else "APPROVED_READ_ONLY",
                  "release": "NOT_AUTHORIZED_BY_PREFLIGHT"}
        try:
            if not synthetic:
                security = (
                    not settings.DEBUG and settings.SECURE_SSL_REDIRECT and settings.SESSION_COOKIE_SECURE
                    and settings.CSRF_COOKIE_SECURE and settings.SESSION_COOKIE_HTTPONLY
                    and connection.settings_dict["OPTIONS"].get("sslmode") == "verify-full"
                )
                result["transport_settings"] = "PASS" if security else "BLOCKED"
                result["django_deployment_checks"] = "REVIEW_REQUIRED" if checks.run_checks(include_deployment_checks=True) else "PASS"
                root = Path(settings.PRIVATE_MEDIA_ROOT)
                def safe_dir(path):
                    meta = path.lstat()
                    return stat.S_ISDIR(meta.st_mode) and not getattr(meta,"st_file_attributes",0) & 1024
                media = root.exists() and all(safe_dir(p) for p in (root,*root.parents))
                # Platform ACLs and ownership must still be confirmed externally.
                result["media_root"] = "PASS" if media and (os.name == "nt" or not root.stat().st_mode & 0o077) else "BLOCKED"
                result["policy_reference"] = "REVIEW_REQUIRED" if getattr(settings,"PUBLIC_BID_POLICY_SOURCE_FILE",None) else "BLOCKED"
            with transaction.atomic():
                if not synthetic:
                    with connection.cursor() as cur:
                        cur.execute("SET TRANSACTION READ ONLY")
                        cur.execute("SELECT rolsuper, rolcreaterole, rolcreatedb, rolreplication, rolbypassrls FROM pg_roles WHERE rolname=current_user")
                        role = cur.fetchone()
                    result["runtime_db_role"] = "PASS" if role is not None and not any(role) else "BLOCKED"
                executor = MigrationExecutor(connection)
                pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
                result["schema"] = "BLOCKED" if pending else "PASS"
                if not pending:
                    result.update(business_checks())
                else:
                    result.update(business_scope="NOT_CHECKED",notice_presence="NOT_CHECKED")
        except Exception:
            # Do not echo paths, DSNs, SQL, identities or private table contents.
            self.stdout.write(json.dumps({**result,"status":"BLOCKED","error":"PREFLIGHT_CHECK_FAILED"}))
            raise CommandError("Pilot preflight failed; inspect protected operator diagnostics.") from None
        status = "BLOCKED" if any(v in ("BLOCKED","NOT_CHECKED") for v in result.values()) else "CHECKS_PASS"
        self.stdout.write(json.dumps({**result,"status":status}))
        if status == "BLOCKED":
            raise CommandError("Pilot preflight blocked.")
