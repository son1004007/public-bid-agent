"""AGW-02/06 Synology Docker *prototype* for approved own-user Codex sessions.

This is a bounded worker-side adapter, NOT a public endpoint, login proxy, or
production-approved multitenant runtime. It reuses the existing Synology Docker
external isolation instead of bypassing sandbox restrictions on the NAS host.
No auth material is copied: user must have authenticated their private CLI HOME.
"""
from __future__ import annotations

import os
import stat
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from .codex_cli import (
    CodexAdapterError, CodexRunPolicy, CodexResult, _session_uuid,
    parse_codex_jsonl,
)

# Installed/inspected with Synology Container Manager; do not silently upgrade.
NAS_CODEX_IMAGE = "device-control/codex-runtime:0.163.0"
NAS_MODEL = "gpt-6.1-sol"


@dataclass(frozen=True)
class NasCodexConfig:
    web_user_id: uuid.UUID
    os_uid: int
    os_gid: int
    identity_root: Path
    workspace: Path
    docker_binary: str = "/usr/local/bin/docker"


def _private_dir(path: Path, *, uid: int | None = None) -> Path:
    if type(path) is not Path or not path.is_absolute() or path.is_symlink():
        raise CodexAdapterError("INVALID_PRIVATE_DIRECTORY")
    if not path.exists() or not path.is_dir():
        raise CodexAdapterError("PRIVATE_DIRECTORY_MISSING")
    st = path.stat()
    if st.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise CodexAdapterError("UNSAFE_DIRECTORY_PERMISSIONS")
    if uid is not None and st.st_uid != uid:
        raise CodexAdapterError("DIRECTORY_OWNER_MISMATCH")
    return path.resolve(strict=True)


def _check_environment(config: NasCodexConfig) -> tuple[Path, Path]:
    if type(config) is not NasCodexConfig:
        raise CodexAdapterError("INVALID_DOCKER_CONFIG")
    if type(config.web_user_id) is not uuid.UUID:
        raise CodexAdapterError("INVALID_USER_ID")
    if type(config.os_uid) is not int or config.os_uid < 1:
        raise CodexAdapterError("INVALID_OS_IDENTITY")
    if type(config.os_gid) is not int or config.os_gid < 1:
        raise CodexAdapterError("INVALID_OS_IDENTITY")
    if config.docker_binary != "/usr/local/bin/docker":
        raise CodexAdapterError("UNAPPROVED_DOCKER_BINARY")
    base = _private_dir(config.identity_root)
    user_dir = _private_dir(base / str(config.web_user_id), uid=config.os_uid)
    home = _private_dir(user_dir / "codex", uid=config.os_uid)
    if not isinstance(config.workspace, Path) or not config.workspace.is_absolute():
        raise CodexAdapterError("INVALID_WORKSPACE")
    if config.workspace.is_symlink() or not config.workspace.is_dir():
        raise CodexAdapterError("INVALID_WORKSPACE")
    workspace = config.workspace.resolve(strict=True)
    if workspace == home or workspace.is_relative_to(base):
        # Evidence files may not be in or beneath credential/session storage.
        raise CodexAdapterError("WORKSPACE_OVERLAPS_IDENTITY")
    for path in (base, user_dir, home, workspace):
        if any(c in str(path) for c in (":", "\n", "\r", "\x00")):
            raise CodexAdapterError("INVALID_MOUNT_PATH")
    auth = home / ".codex" / "auth.json"
    if not auth.is_file() or auth.is_symlink():
        raise CodexAdapterError("AUTH_REQUIRED")
    metadata = auth.stat()
    if metadata.st_uid != config.os_uid or metadata.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise CodexAdapterError("UNSAFE_AUTH_PERMISSIONS")
    return home, workspace


def build_nas_docker_codex_argv(
    *,
    config: NasCodexConfig,
    session_id: str | None = None,
) -> tuple[str, ...]:
    """Build immutable Docker flags. No Docker socket, broad HOME or production mounts."""
    home, workspace = _check_environment(config)
    # Inside the READ-ONLY externally isolated container only, Codex native
    # Bubblewrap/Landlock sandbox is bypassed due to DSM kernel limitations.
    fixed = (
        config.docker_binary, "run", "--rm", "-i",
        "--read-only", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges:true",
        "--memory", "1g",
        "--tmpfs", "/tmp:rw,nosuid,nodev,size=256m",
        "--user", f"{config.os_uid}:{config.os_gid}",
        "-e", "HOME=/home/codex", "-e", "CODEX_HOME=/home/codex/.codex",
        "-v", f"{workspace}:/workspace:ro",
        "-v", f"{home}:/home/codex:rw",
        "-w", "/workspace",
        NAS_CODEX_IMAGE,
        "codex", "--dangerously-bypass-approvals-and-sandbox",
        "exec",
    )
    flags = (
        "--json", "--skip-git-repo-check", "--ignore-user-config",
        "--ignore-rules", "--model", NAS_MODEL,
        "--config", "model_reasoning_effort=medium",
    )
    prior = _session_uuid(session_id)
    return fixed + (("resume",) if prior else ()) + flags + ((prior,) if prior else ()) + ("-",)


def run_nas_docker_codex(
    *,
    config: NasCodexConfig,
    policy: CodexRunPolicy,
    prompt: str,
    session_id: str | None = None,
    timeout_seconds: int = 150,
) -> CodexResult:
    """One authorized, bounded invocation. NEVER performs automatic paid retries.

    Caller must independently enforce immutable notice snapshot, evidence ACL,
    per-user provider agreement, session DB lease/fence and egress restrictions.
    DSM may ignore PID and CPU CFS limits: never claim those controls are active.
    """
    if type(policy) is not CodexRunPolicy or not policy.allowed:
        raise CodexAdapterError("PROVIDER_EXECUTION_NOT_APPROVED")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt.encode("utf-8")) > 100_000:
        raise CodexAdapterError("INVALID_PROMPT")
    if type(timeout_seconds) is not int or not 15 <= timeout_seconds <= 180:
        raise CodexAdapterError("INVALID_TIMEOUT")
    argv = build_nas_docker_codex_argv(config=config, session_id=session_id)
    try:
        result = subprocess.run(
            argv,
            input=prompt,
            cwd=str(config.workspace),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
            text=True, shell=False, check=False,
            timeout=timeout_seconds,
            env={**os.environ, "PATH": "/usr/local/bin:/usr/bin:/bin"},
        )
    except subprocess.TimeoutExpired as exc:
        raise CodexAdapterError("CODEX_TIMEOUT") from exc
    except OSError as exc:
        raise CodexAdapterError("DOCKER_UNAVAILABLE") from exc
    if result.returncode != 0:
        # stderr can contain raw prompt, private home paths and authentication.
        raise CodexAdapterError("DOCKER_CODEX_FAILED")
    return parse_codex_jsonl(result.stdout, expected_session_id=session_id)
