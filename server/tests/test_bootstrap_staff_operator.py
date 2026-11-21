"""Safe stdin credential bootstrap tests; never use a live account or service."""
import io
import secrets

from django.core.management.base import CommandError
from django.test import SimpleTestCase

from bid_server.accounts.management.commands.bootstrap_staff_operator import (
    _initial_password,
)


class StaffBootstrapCredentialContractTests(SimpleTestCase):
    def test_generated_private_password_is_accepted(self):
        password = secrets.token_urlsafe(32)
        self.assertEqual(_initial_password(io.BytesIO(password.encode("ascii"))), password)

    def test_rejects_short_long_whitespace_and_newline(self):
        for value in (
            b"short",
            b"A" * 129,
            b"A" * 30 + b"\n",
            b"A" * 29 + b" ",
            b"A" * 25 + b"\x00",
        ):
            with self.subTest(length=len(value)):
                with self.assertRaises(ValueError):
                    _initial_password(io.BytesIO(value))

    def test_rejects_non_ascii(self):
        with self.assertRaises(ValueError):
            _initial_password(io.BytesIO(b"A" * 24 + "\uac00".encode("utf-8")))
