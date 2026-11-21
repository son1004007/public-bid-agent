"""Interactive first-password change for the NAS owner-operated staff account.

Requires a real TTY. Never prints password, hashes, session material, or user
identity. This exists because the old NAS preview HTTP server does not expose
the new Django login/change-password API yet.
"""
import getpass
import re
import sys
import warnings
from uuid import uuid4

from django.contrib.auth.hashers import check_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from bid_server.accounts.models import AuthEvent, User


class Command(BaseCommand):
    help = "Trusted local TTY first-password change for a provisioned staff account."
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--expected-db-name", required=True)
        parser.add_argument("--username", required=True)

    def handle(self, *args, **options):
        username = options["username"]
        expected = options["expected_db_name"]
        if (
            not sys.stdin.isatty() or not sys.stderr.isatty()
            or type(username) is not str
            or not re.fullmatch(r"[a-z][a-z0-9_.-]{2,79}", username)
            or type(expected) is not str
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,63}", expected)
            or connection.vendor != "postgresql"
        ):
            raise CommandError("INTERACTIVE_STAFF_PASSWORD_CHANGE_REQUIRED")
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database()")
            if cursor.fetchone()[0] != expected:
                raise CommandError("WRONG_DATABASE")
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            try:
                old = getpass.getpass("Current temporary password: ")
                new = getpass.getpass("New permanent password: ")
                confirmation = getpass.getpass("Confirm new password: ")
            except (EOFError, OSError, getpass.GetPassWarning):
                raise CommandError("SECURE_TERMINAL_REQUIRED") from None
        if new != confirmation or not 12 <= len(new) <= 128:
            raise CommandError("PASSWORD_CHANGE_REJECTED")
        with transaction.atomic():
            user = User.objects.select_for_update().filter(username=username).first()
            now = timezone.now()
            if (
                user is None or not user.is_active or not user.is_staff
                or not user.must_change_password
                or user.temporary_expires_at is None
                or user.temporary_expires_at <= now
                or (user.locked_until is not None and user.locked_until > now)
                or not check_password(old, user.password)
                or check_password(new, user.password)
            ):
                raise CommandError("PASSWORD_CHANGE_REJECTED")
            try:
                validate_password(new, user)
            except ValidationError:
                raise CommandError("PASSWORD_CHANGE_REJECTED") from None
            user.set_password(new)
            user.must_change_password = False
            user.temporary_expires_at = None
            user.password_changed_at = now
            user.save(update_fields=[
                "password", "must_change_password",
                "temporary_expires_at", "password_changed_at",
            ])
            AuthEvent.objects.create(
                actor=user, kind="first_password_changed",
                request_id=uuid4(),
            )
        self.stdout.write("FIRST_PASSWORD_CHANGE_COMMITTED_RELOGIN_REQUIRED")
