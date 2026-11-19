"""Interactive, authorized local operator containment; never an HTTP endpoint."""
import getpass
import sys
import warnings
from uuid import uuid4

from django.contrib.auth.hashers import check_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from bid_server.accounts.models import AuthEvent, User, temporary_deadline


class Command(BaseCommand):
    help = "Rotate one existing account to a temporary password, or disable it. Interactive operator only."

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument("--rotate", action="store_true")
        mode.add_argument("--disable", action="store_true")

    def handle(self, *args, **options):
        if not sys.stdin.isatty() or not sys.stderr.isatty():
            raise CommandError("Interactive local terminal required")
        username = input("Existing account username: ").strip()
        if not username or len(username) > 150:
            raise CommandError("Invalid account selector")
        action = "ROTATE" if options["rotate"] else "DISABLE"
        if input("Type " + action + " to confirm: ") != action:
            raise CommandError("Operation cancelled")
        new = None
        if options["rotate"]:
            with warnings.catch_warnings():
                warnings.simplefilter("error", getpass.GetPassWarning)
                try:
                    new = getpass.getpass("New temporary password: ")
                    repeated = getpass.getpass("Repeat temporary password: ")
                except (getpass.GetPassWarning, EOFError, OSError):
                    raise CommandError("Secure password entry unavailable") from None
            if new != repeated:
                raise CommandError("Passwords do not match")
            if not 12 <= len(new) <= 128:
                raise CommandError("Password does not satisfy policy")
        with transaction.atomic():
            user = User.objects.select_for_update().filter(username=username).first()
            if user is None:
                raise CommandError("Account not found")
            if options["rotate"]:
                if not user.is_active:
                    raise CommandError("Inactive account; rotation cannot enable it")
                try:
                    validate_password(new, user)
                except ValidationError:
                    raise CommandError("Password does not satisfy policy") from None
                if check_password(new, user.password):
                    raise CommandError("Password reuse prohibited")
                user.set_password(new)
                user.must_change_password = True
                user.temporary_expires_at = temporary_deadline()
                user.password_changed_at = timezone.now()
                fields = ["password", "must_change_password", "temporary_expires_at", "password_changed_at"]
                kind = "operator_password_reset"
            else:
                user.is_active = False
                user.set_unusable_password()
                user.must_change_password = True
                user.temporary_expires_at = None
                fields = ["is_active", "password", "must_change_password", "temporary_expires_at"]
                kind = "operator_account_disabled"
            # Preserve role, staff/superuser flags and rate-limit state. A fresh
            # epoch revokes previous sessions even if other fields were unchanged.
            user.auth_epoch += 1
            user.save(update_fields=fields + ["auth_epoch"])
            # No authenticated HTTP actor exists for this local operator action.
            AuthEvent.objects.create(actor=None, kind=kind, request_id=uuid4())
        self.stdout.write("Account security action committed; prior session epoch revoked.")
