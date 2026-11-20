"""AGW-02 Docker command safety: synthetic fixtures, no real CLI or billing."""
import json
import os
import subprocess
import tempfile
import unittest
import uuid
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from ai_gateway_core.codex_cli import CodexAdapterError, CodexRunPolicy
from ai_gateway_core.nas_docker_codex import (
    NasCodexConfig, NAS_CODEX_IMAGE, NAS_MODEL,
    build_nas_docker_codex_argv, run_nas_docker_codex,
)

USER_ID = uuid.UUID("44444444-5555-4666-8777-888888888888")
SESSION_ID = "11111111-2222-4333-8444-555555555555"


def valid_policy():
    return CodexRunPolicy(
        provider_contract_approved=True, isolated_os_identity_verified=True,
        data_export_approved=True, user_requested_this_run=True,
        invocation_limit_approved=True,
    )


def final_stream(thread=SESSION_ID):
    events = [
        {"type": "thread.started", "thread_id": thread},
        {"type": "turn.started"},
        {"type": "item.completed", "item": {
            "type": "agent_message", "text": json.dumps({"assessment": "NOT_MET"})}},
        {"type": "turn.completed"},
    ]
    return "\n".join(json.dumps(e) for e in events) + "\n"


@unittest.skipIf(os.name == "nt", "Synology Docker mount/UID checks are Linux-only")
class SynologyDockerCommandTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name) / "identities"
        root.mkdir(mode=0o700)
        user_dir = root / str(USER_ID)
        user_dir.mkdir(mode=0o700)
        home = user_dir / "codex"
        home.mkdir(mode=0o700)
        self.codex_dir = home / ".codex"
        self.codex_dir.mkdir(mode=0o700)
        self.auth = self.codex_dir / "auth.json"
        self.auth.write_text('{"synthetic":"not-an-auth-token"}', encoding="utf-8")
        self.auth.chmod(0o600)
        workspace = Path(self.tmp.name) / "evidence"
        workspace.mkdir(mode=0o700)
        self.config = NasCodexConfig(
            web_user_id=USER_ID, os_uid=os.getuid(), os_gid=os.getgid(),
            identity_root=root, workspace=workspace,
        )

    def reviewed_config(self):
        return replace(
            self.config, user_os_mapping_verified=True,
            egress_restricted_verified=True, model_tool_policy_verified=True,
        )

    @patch("ai_gateway_core.nas_docker_codex.subprocess.run")
    def test_provider_approval_alone_does_not_authorize_unverified_nas(self, child):
        with self.assertRaisesRegex(CodexAdapterError, "NAS_RUNTIME_GATES_NOT_APPROVED"):
            run_nas_docker_codex(config=self.config, policy=valid_policy(),
                                 prompt="synthetic")
        child.assert_not_called()

    @patch("ai_gateway_core.nas_docker_codex.subprocess.run")
    def test_each_runtime_attestation_is_required(self, child):
        for name in ("user_os_mapping_verified", "egress_restricted_verified",
                     "model_tool_policy_verified"):
            with self.subTest(name=name):
                conf = replace(self.reviewed_config(), **{name: False})
                with self.assertRaisesRegex(CodexAdapterError, "NAS_RUNTIME_GATES_NOT_APPROVED"):
                    run_nas_docker_codex(config=conf, policy=valid_policy(),
                                         prompt="synthetic")
        child.assert_not_called()

    def test_start_has_verified_synology_isolation_flags(self):
        args = build_nas_docker_codex_argv(config=self.config)
        self.assertEqual(args[:3], ("/usr/local/bin/docker", "run", "--rm"))
        for item in ("--read-only", "--cap-drop", "ALL", "--security-opt",
                     "no-new-privileges:true", "--memory", "1g", "--tmpfs",
                     "--user", "--json", "--ignore-user-config", "--ignore-rules"):
            self.assertIn(item, args)
        self.assertIn(NAS_CODEX_IMAGE, args)
        self.assertIn(NAS_MODEL, args)
        self.assertIn("--dangerously-bypass-approvals-and-sandbox", args)
        self.assertLess(args.index(NAS_CODEX_IMAGE), args.index(
            "--dangerously-bypass-approvals-and-sandbox"))
        self.assertNotIn("--privileged", args)
        self.assertNotIn("/var/run/docker.sock", " ".join(args))
        self.assertNotIn("--ephemeral", args)
        self.assertNotIn("--cpus", args)
        self.assertEqual(args[-1], "-")
        self.assertIn(str(self.config.workspace) + ":/workspace:ro", args)

    def test_resume_keeps_same_uuid_and_persisted_codex_home(self):
        args = build_nas_docker_codex_argv(config=self.config, session_id=SESSION_ID)
        self.assertEqual(args[-2:], (SESSION_ID, "-"))
        self.assertIn("resume", args)
        self.assertIn(str(self.config.identity_root / str(USER_ID) / "codex")
                      + ":/home/codex:rw", args)

    def test_path_injection_session_rejected(self):
        with self.assertRaisesRegex(CodexAdapterError, "INVALID_SESSION_ID"):
            build_nas_docker_codex_argv(
                config=self.config, session_id="--privileged")

    def test_auth_required_before_invocation(self):
        self.auth.unlink()
        with self.assertRaisesRegex(CodexAdapterError, "AUTH_REQUIRED"):
            build_nas_docker_codex_argv(config=self.config)

    def test_insecure_auth_mode_rejected(self):
        self.auth.chmod(0o644)
        with self.assertRaisesRegex(CodexAdapterError, "UNSAFE_AUTH_PERMISSIONS"):
            build_nas_docker_codex_argv(config=self.config)

    def test_symlinked_user_home_rejected(self):
        self.auth.unlink()
        self.codex_dir.rmdir()
        home = self.config.identity_root / str(USER_ID) / "codex"
        home.rmdir()
        home.symlink_to(self.config.workspace, target_is_directory=True)
        with self.assertRaisesRegex(CodexAdapterError, "INVALID_PRIVATE_DIRECTORY"):
            build_nas_docker_codex_argv(config=self.config)

    def test_other_os_uid_cannot_run_same_home(self):
        other = replace(self.config, os_uid=os.getuid() + 123)
        with self.assertRaisesRegex(CodexAdapterError, "DIRECTORY_OWNER_MISMATCH"):
            build_nas_docker_codex_argv(config=other)

    def test_workspace_cannot_be_identity_root(self):
        other = replace(self.config, workspace=self.config.identity_root)
        with self.assertRaisesRegex(CodexAdapterError, "WORKSPACE_OVERLAPS_IDENTITY"):
            build_nas_docker_codex_argv(config=other)

    def test_unapproved_binary_rejected(self):
        other = replace(self.config, docker_binary="/bin/sh")
        with self.assertRaisesRegex(CodexAdapterError, "UNAPPROVED_DOCKER_BINARY"):
            build_nas_docker_codex_argv(config=other)

    @patch("ai_gateway_core.nas_docker_codex.subprocess.run")
    def test_default_deny_never_starts_docker(self, child):
        with self.assertRaisesRegex(CodexAdapterError, "PROVIDER_EXECUTION_NOT_APPROVED"):
            run_nas_docker_codex(config=self.config, policy=CodexRunPolicy(),
                                 prompt="synthetic")
        child.assert_not_called()

    @patch("ai_gateway_core.nas_docker_codex.subprocess.run")
    def test_allowlisted_mock_exec_returns_object(self, child):
        child.return_value = subprocess.CompletedProcess([], 0, final_stream(), "")
        outcome = run_nas_docker_codex(
            config=self.reviewed_config(), policy=valid_policy(),
            prompt="synthetic", session_id=SESSION_ID,
        )
        self.assertEqual(outcome.session_id, SESSION_ID)
        self.assertEqual(outcome.response["assessment"], "NOT_MET")
        child.assert_called_once()
        _, arguments = child.call_args
        self.assertIs(arguments["shell"], False)
        self.assertEqual(arguments["input"], "synthetic")
        self.assertLessEqual(arguments["timeout"], 180)

    @patch("ai_gateway_core.nas_docker_codex.subprocess.run")
    def test_nonzero_error_does_not_echo_credentials(self, child):
        child.return_value = subprocess.CompletedProcess([], 125, "", "FAKE_SECRET")
        with self.assertRaises(CodexAdapterError) as caught:
            run_nas_docker_codex(config=self.reviewed_config(), policy=valid_policy(),
                                 prompt="synthetic")
        self.assertEqual(caught.exception.code, "DOCKER_CODEX_FAILED")
        self.assertNotIn("FAKE_SECRET", str(caught.exception))
        child.assert_called_once()

    @patch("ai_gateway_core.nas_docker_codex.subprocess.run")
    def test_timeout_does_not_retry_paid_call(self, child):
        child.side_effect = subprocess.TimeoutExpired(cmd=["docker"], timeout=150)
        with self.assertRaisesRegex(CodexAdapterError, "CODEX_TIMEOUT"):
            run_nas_docker_codex(config=self.reviewed_config(), policy=valid_policy(),
                                 prompt="synthetic")
        child.assert_called_once()


if __name__ == "__main__":
    unittest.main()
