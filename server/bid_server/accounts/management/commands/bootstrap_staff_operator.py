"""First staff reviewer bootstrap for a trusted, explicitly authorized NAS operator.

One-time bootstrap only. The password is read from stdin (a trusted private
credential channel), is never accepted as an argument/environment variable and
is never echoed. New accounts MUST complete their own password change through
the authenticated API before source-link review is permitted.
"""
from datetime import timedelta
import re
import sys
from uuid import uuid4

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from bid_server.accounts.models import AuthEvent, User


def _initial_password(stream):
    raw = stream.read(129)
    if not 24 <= len(raw) <= 128 or not re.fullmatch(rb"[A-Za-z0-9_-]+", raw):
        raise ValueError("invalid private credential")
    return raw.decode("ascii")


class Command(BaseCommand):
    help = "Create the first restricted staff reviewer with mandatory first password change."
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--expected-db-name", required=True)
        parser.add_argument("--username", required=True)
        parser.add_argument("--password-stdin", action="store_true", required=True)
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        try:
            name = options["username"]
            db_name = options["expected_db_name"]
            if (
                type(name) is not str
                or not re.fullmatch(r"[a-z][a-z0-9_.-]{2,79}", name)
                or type(db_name) is not str
                or not re.fullmatch(r"[A-Za-z0-9_-]{1,63}", db_name)
                or connection.vendor != "postgresql"
                or sys.stdin.isatty()
            ):
                raise ValueError("untrusted invocation")
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_database()")
                if cursor.fetchone()[0] != db_name:
                    raise ValueError("wrong database")
            new_password = _initial_password(sys.stdin.buffer)
            proposed = User(
                username=name, is_staff=True, is_superuser=False,
                is_active=True, role="lead", must_change_password=True,
            )
            validate_password(new_password, proposed)
            with transaction.atomic():
                # Serialize one-time bootstrap attempts across sessions, not
                # across unrelated business data/notice/importer workflows.
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_xact_lock(%s)", [17300202])
                if User.objects.filter(is_staff=True).exists():
                    raise ValueError("staff already provisioned")
                if User.objects.filter(username=name).exists():
                    raise ValueError("username exists")
                if options["apply"]:
                    proposed.temporary_expires_at = timezone.now() + timedelta(hours=24)
                    proposed.password_changed_at = None
                    proposed.set_password(new_password)
                    proposed.save(force_insert=True)
                    AuthEvent.objects.create(
                        actor=None, kind="staff_operator_bootstrapped",
                        request_id=uuid4(),
                    )
            self.stdout.write(
                "STAFF_OPERATOR_CREATED_PASSWORD_CHANGE_REQUIRED"
                if options["apply"] else "STAFF_OPERATOR_DRY_RUN_VALID"
            )
        except (ValueError, ValidationError, UnicodeError, TypeError, OSError):
            raise CommandError("STAFF_OPERATOR_BOOTSTRAP_REJECTED") from None
