"""MCP 공고 공개 범위/기본 차단 회귀 — 실제 DB 및 mcp SDK 설치 없이 실행."""
import os
import unittest
from unittest.mock import patch

from bid_mcp.scope import (
    PUBLIC_SOURCE, approved_public_rfp_enabled, require_enabled,
    validate_limit, validate_notice_number, validate_query,
)


class McpPublicScopeTests(unittest.TestCase):
    def test_disabled_by_default_and_requires_two_flags(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(PermissionError, "MCP_DISABLED"):
                require_enabled()
        with patch.dict(os.environ, {"BID_MCP_ENABLED": "1"}, clear=True):
            with self.assertRaises(PermissionError):
                require_enabled()
        with patch.dict(os.environ, {"BID_MCP_ENABLED": "1", "BID_MCP_PUBLIC_ONLY": "1"}, clear=True):
            require_enabled()
            self.assertFalse(approved_public_rfp_enabled())

    def test_rfp_is_separately_off_by_default(self):
        with patch.dict(os.environ, {"BID_MCP_ENABLED": "1", "BID_MCP_PUBLIC_ONLY": "1", "BID_MCP_PUBLIC_RFP_ENABLED": "1"}, clear=True):
            self.assertTrue(approved_public_rfp_enabled())

    def test_query_requires_bounded_printable_text(self):
        self.assertEqual(validate_query("  AI 활용  "), "AI 활용")
        for value in ("", "x", "x" * 81, "\nAA", "\x7fAA", None, 123):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_query(value)

    def test_notice_number_is_strict(self):
        self.assertEqual(validate_notice_number("R26BK01838997"), "R26BK01838997")
        for value in ("abc; SELECT *", "../etc", "a", "", None, "한글 01"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_notice_number(value)

    def test_limit_bounded_and_bool_rejected(self):
        self.assertEqual(validate_limit(10), 10)
        for value in (0, 11, 10000, -1, True, 4.0, "5"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_limit(value)

    def test_source_constant_must_not_expand_to_user_data(self):
        self.assertEqual(PUBLIC_SOURCE, "G2B_OFFICIAL_API")
