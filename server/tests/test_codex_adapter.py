"""AGW-06 guarded native Codex CLI adapter: no network/model calls in CI."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_gateway_core.codex_cli import (
    CodexAdapterError, CodexRunPolicy, build_codex_command,
    parse_codex_jsonl, run_codex,
)

SESSION = "01a1f6a7-9dd4-7843-99bb-bca6bf1d73ca"


def event_stream(*, session=SESSION, result=None, completed=True):
    result = result if result is not None else {"assessment": "NOT_MET", "evidence_ids": ["E1"]}
    items = [
        {"type": "thread.started", "thread_id": session},
        {"type": "turn.started"},
        {"type": "item.completed", "item": {
            "type": "agent_message", "text": json.dumps(result, ensure_ascii=False)}},
    ]
    if completed:
        items.append({"type": "turn.completed", "usage": {"input_tokens": 5}})
    return "\n".join(json.dumps(item, ensure_ascii=False) for item in items) + "\n"


def policy(**kwargs):
    enabled = dict(provider_contract_approved=True, isolated_os_identity_verified=True,
                   data_export_approved=True, user_requested_this_run=True,
                   invocation_limit_approved=True)
    enabled.update(kwargs)
    return CodexRunPolicy(**enabled)


class AdapterParsingTests(unittest.TestCase):
    def test_parse_completed_realistic_jsonl(self):
        parsed = parse_codex_jsonl(event_stream())
        self.assertEqual(parsed.session_id, SESSION)
        self.assertEqual(parsed.response["assessment"], "NOT_MET")
        self.assertEqual(parsed.event_count, 4)

    def test_parse_verified_resume(self):
        self.assertEqual(parse_codex_jsonl(event_stream(), expected_session_id=SESSION).session_id, SESSION)

    def test_resume_wrong_thread_rejected(self):
        with self.assertRaisesRegex(CodexAdapterError, "SESSION_MISMATCH"):
            parse_codex_jsonl(event_stream(), expected_session_id="11111111-1111-1111-1111-111111111111")

    def test_duplicate_thread_rejected(self):
        with self.assertRaisesRegex(CodexAdapterError, "MULTIPLE_SESSION_STARTS"):
            parse_codex_jsonl(event_stream() + event_stream())

    def test_uncompleted_turn_rejected(self):
        with self.assertRaisesRegex(CodexAdapterError, "INCOMPLETE_CLI_TURN"):
            parse_codex_jsonl(event_stream(completed=False))

    def test_failure_event_rejected(self):
        stream = event_stream(completed=False) + json.dumps({"type": "turn.failed"}) + "\n"
        with self.assertRaisesRegex(CodexAdapterError, "CODEX_TURN_FAILED"):
            parse_codex_jsonl(stream)

    def test_non_json_event_rejected(self):
        with self.assertRaisesRegex(CodexAdapterError, "INVALID_CLI_EVENT"):
            parse_codex_jsonl("not json\n")

    def test_non_json_final_message_rejected(self):
        s = event_stream().replace('"{\\"assessment', '"not json \\{\\"assessment')
        # Direct constructed event ensures the final assistant message isn't valid JSON.
        s = "\n".join(json.dumps(v) for v in [
            {"type": "thread.started", "thread_id": SESSION},
            {"type": "item.completed", "item": {"type": "agent_message", "text": "NOT JSON"}},
            {"type": "turn.completed"},
        ])
        with self.assertRaisesRegex(CodexAdapterError, "INVALID_RESULT_JSON"):
            parse_codex_jsonl(s)

    def test_output_size_limit(self):
        with self.assertRaisesRegex(CodexAdapterError, "CLI_OUTPUT_TOO_LARGE"):
            parse_codex_jsonl(event_stream(), max_output_bytes=10)

    def test_trailing_event_after_turn_is_rejected(self):
        s = event_stream() + json.dumps({"type": "turn.started"}) + "\n"
        with self.assertRaisesRegex(CodexAdapterError, "TRAILING_CLI_EVENT"):
            parse_codex_jsonl(s)


class InvocationTests(unittest.TestCase):
    def test_start_uses_readonly_sandbox_stdin_and_pinned_workspace(self):
        with tempfile.TemporaryDirectory() as d:
            args = build_codex_command(cli_binary="codex", workspace=Path(d))
        self.assertEqual(args[:2], ("codex", "exec"))
        self.assertIn("--sandbox", args)
        self.assertIn("read-only", args)
        self.assertEqual(args[-1], "-")
        self.assertEqual(args[args.index("-C") + 1], d)

    def test_resume_uses_global_sandbox_verified_from_cli(self):
        with tempfile.TemporaryDirectory() as d:
            args = build_codex_command(cli_binary="codex.cmd", workspace=Path(d), session_id=SESSION)
        self.assertEqual(args[:4], ("codex.cmd", "--sandbox", "read-only", "exec"))
        self.assertEqual(args[-2:], (SESSION, "-"))

    def test_invalid_resume_id_does_not_execute(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(CodexAdapterError, "INVALID_SESSION_ID"):
                build_codex_command(cli_binary="codex", workspace=Path(d), session_id="--dangerously-bypass-approvals-and-sandbox")

    def test_missing_workspace_rejected(self):
        with self.assertRaisesRegex(CodexAdapterError, "INVALID_ISOLATED_WORKSPACE"):
            build_codex_command(cli_binary="codex", workspace=Path("/a/nonexistent/absolute/path"))

    @patch("ai_gateway_core.codex_cli.subprocess.run")
    def test_default_deny_makes_zero_subprocess_calls(self, process):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(CodexAdapterError, "NOT_APPROVED"):
                run_codex(prompt="synthetic", workspace=Path(d), policy=CodexRunPolicy(), cli_binary="codex")
        process.assert_not_called()

    @patch("ai_gateway_core.codex_cli.subprocess.run")
    def test_truthy_string_cannot_approve_call(self, process):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(CodexAdapterError, "NOT_APPROVED"):
                run_codex(prompt="synthetic", workspace=Path(d),
                          policy=policy(user_requested_this_run="true"), cli_binary="codex")
        process.assert_not_called()

    @patch("ai_gateway_core.codex_cli.subprocess.run")
    def test_mocked_real_output_parses_and_is_not_logged(self, process):
        process.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=event_stream(), stderr="hidden-token"
        )
        with tempfile.TemporaryDirectory() as d:
            result = run_codex(prompt="synthetic", workspace=Path(d),
                               policy=policy(), cli_binary="codex", session_id=SESSION)
        self.assertEqual(result.session_id, SESSION)
        self.assertEqual(result.response["assessment"], "NOT_MET")
        _, kwargs = process.call_args
        self.assertFalse(kwargs["shell"])
        self.assertEqual(kwargs["input"], "synthetic")
        self.assertEqual(kwargs["timeout"], 90)

    @patch("ai_gateway_core.codex_cli.subprocess.run")
    def test_error_does_not_reveal_stderr(self, process):
        process.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="SECRET_FROM_PROVIDER"
        )
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(CodexAdapterError) as context:
                run_codex(prompt="synthetic", workspace=Path(d), policy=policy(), cli_binary="codex")
        self.assertEqual(context.exception.code, "CODEX_PROCESS_FAILED")
        self.assertNotIn("SECRET_FROM_PROVIDER", str(context.exception))

    @patch("ai_gateway_core.codex_cli.subprocess.run")
    def test_timeout_no_unbounded_retry(self, process):
        process.side_effect = subprocess.TimeoutExpired(cmd=["codex"], timeout=5)
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(CodexAdapterError, "CODEX_TIMEOUT"):
                run_codex(prompt="synthetic", workspace=Path(d), policy=policy(), cli_binary="codex")
        process.assert_called_once()


if __name__ == "__main__":
    unittest.main()
