"""Codex CLI exec/resume adapter for a previously authorized, isolated user worker.

No HTTP, Django, filesystem storage, authentication, or implicit model execution at
import time. Caller must enforce user/provider/notice session ownership and leases.
Only synthetic/approved data may be provided after provider policy approval.

Verified against codex-cli 0.166.0 on Windows 2026-11-20:
  start: codex exec --skip-git-repo-check --sandbox read-only --json -C DIR -
  resume: codex --sandbox read-only exec resume --skip-git-repo-check --json UUID -
The sandbox flag is global for resume (not a resume subcommand option).
"""
from __future__ import annotations

import json
import re
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class CodexAdapterError(Exception):
    """Error code only. Never wrap stderr, full prompt or credential material."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class CodexResult:
    session_id: str
    response: dict[str, Any]
    event_count: int


@dataclass(frozen=True)
class CodexRunPolicy:
    """Derived by the *trusted* backend, never populated from user-supplied JSON."""

    provider_contract_approved: bool = False
    isolated_os_identity_verified: bool = False
    data_export_approved: bool = False
    user_requested_this_run: bool = False
    invocation_limit_approved: bool = False

    @property
    def allowed(self) -> bool:
        return all(
            type(flag) is bool and flag
            for flag in (
                self.provider_contract_approved,
                self.isolated_os_identity_verified,
                self.data_export_approved,
                self.user_requested_this_run,
                self.invocation_limit_approved,
            )
        )


def _session_uuid(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", value
    ):
        raise CodexAdapterError("INVALID_SESSION_ID")
    return str(uuid.UUID(value))


def build_codex_command(
    *,
    cli_binary: str,
    workspace: Path,
    session_id: str | None = None,
) -> tuple[str, ...]:
    """Build fixed argv, not shell fragments; prompts travel through stdin."""
    if not isinstance(cli_binary, str) or not cli_binary or any(
        ch in cli_binary for ch in ("\n", "\r", "\x00")
    ):
        raise CodexAdapterError("INVALID_CLI_BINARY")
    if not isinstance(workspace, Path) or not workspace.is_absolute() or not workspace.is_dir():
        raise CodexAdapterError("INVALID_ISOLATED_WORKSPACE")
    old = _session_uuid(session_id)
    if old:
        # 0.166.0: resume inherits the global sandbox policy, NOT --sandbox on resume.
        return (
            cli_binary, "--sandbox", "read-only", "exec", "resume",
            "--skip-git-repo-check", "--json", old, "-",
        )
    return (
        cli_binary, "exec", "--skip-git-repo-check", "--sandbox", "read-only",
        "--json", "-C", str(workspace), "-",
    )


def parse_codex_jsonl(
    output: str,
    *,
    expected_session_id: str | None = None,
    max_output_bytes: int = 1_000_000,
) -> CodexResult:
    """Accept a single completed turn and a JSON-object final agent message."""
    if not isinstance(output, str):
        raise CodexAdapterError("INVALID_CLI_OUTPUT")
    if len(output.encode("utf-8")) > max_output_bytes:
        raise CodexAdapterError("CLI_OUTPUT_TOO_LARGE")
    expected = _session_uuid(expected_session_id)
    seen_thread: str | None = None
    final_message: str | None = None
    completed = False
    count = 0
    for line in output.splitlines():
        if not line or len(line) > 300_000:
            raise CodexAdapterError("INVALID_CLI_EVENT")
        count += 1
        if count > 2000:
            raise CodexAdapterError("TOO_MANY_CLI_EVENTS")
        try:
            event = json.loads(line)
        except (ValueError, TypeError) as exc:
            raise CodexAdapterError("INVALID_CLI_EVENT") from exc
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            raise CodexAdapterError("INVALID_CLI_EVENT")
        kind = event["type"]
        if kind in {"error", "turn.failed"}:
            raise CodexAdapterError("CODEX_TURN_FAILED")
        if kind == "thread.started":
            if seen_thread is not None:
                raise CodexAdapterError("MULTIPLE_SESSION_STARTS")
            seen_thread = _session_uuid(event.get("thread_id"))
            if seen_thread is None:
                raise CodexAdapterError("MISSING_SESSION_ID")
        elif kind == "item.completed":
            item = event.get("item")
            if isinstance(item, dict) and item.get("type") == "agent_message":
                if not isinstance(item.get("text"), str):
                    raise CodexAdapterError("INVALID_AGENT_MESSAGE")
                final_message = item["text"]
        elif kind == "turn.completed":
            completed = True
        if completed and kind not in {"turn.completed"}:
            raise CodexAdapterError("TRAILING_CLI_EVENT")
    if seen_thread is None:
        raise CodexAdapterError("MISSING_SESSION_ID")
    if expected is not None and seen_thread != expected:
        raise CodexAdapterError("SESSION_MISMATCH")
    if not completed or final_message is None:
        raise CodexAdapterError("INCOMPLETE_CLI_TURN")
    try:
        response = json.loads(final_message)
    except (ValueError, TypeError) as exc:
        raise CodexAdapterError("INVALID_RESULT_JSON") from exc
    if not isinstance(response, dict):
        raise CodexAdapterError("INVALID_RESULT_JSON")
    return CodexResult(session_id=seen_thread, response=response, event_count=count)


def run_codex(
    *,
    prompt: str,
    workspace: Path,
    policy: CodexRunPolicy,
    cli_binary: str,
    session_id: str | None = None,
    timeout_seconds: int = 90,
) -> CodexResult:
    """One bounded invocation, no automatic retry, no stdout/stderr logging.

    This is a low-level worker adapter, not a web endpoint. Callers MUST also
    enforce OS isolation, user-specific HOME/CODEX_HOME, ACL, session lease,
    prompt classification, and external-usage policy. This function cannot
    make an ordinary shared OS process into a secure multi-tenant container.
    """
    if type(policy) is not CodexRunPolicy or not policy.allowed:
        raise CodexAdapterError("PROVIDER_EXECUTION_NOT_APPROVED")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt.encode("utf-8")) > 100_000:
        raise CodexAdapterError("INVALID_PROMPT")
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 180:
        raise CodexAdapterError("INVALID_TIMEOUT")
    args = build_codex_command(
        cli_binary=cli_binary, workspace=workspace, session_id=session_id
    )
    try:
        process = subprocess.run(
            args,
            input=prompt,
            cwd=str(workspace),
            encoding="utf-8",
            errors="replace",
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            shell=False,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise CodexAdapterError("CODEX_TIMEOUT") from exc
    except OSError as exc:
        raise CodexAdapterError("CODEX_BINARY_UNAVAILABLE") from exc
    if process.returncode != 0:
        # stderr can include sensitive prompts/paths: do not relay or persist.
        raise CodexAdapterError("CODEX_PROCESS_FAILED")
    return parse_codex_jsonl(process.stdout, expected_session_id=session_id)
