"""가상 프로필 API 검증: 입력 계약, 이력, CSRF, 동시 변경, 기존 데이터 격리."""

import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import server
from decision_profiles import (
    FACTOR_DEFAULTS, POLICY_DEFAULT, ProfileConflict, clean_policy,
    clean_weights, default_state, load_state, next_state,
)


class ProfileContractTests(unittest.TestCase):
    def test_default_is_not_shared(self):
        a, b = default_state(), default_state()
        a["weights"]["technical"] = 0
        self.assertEqual(b["weights"]["technical"], 15)

    def test_bad_policy_and_weights_are_rejected(self):
        for bad in [
            {**POLICY_DEFAULT, "require": "true"},
            {**POLICY_DEFAULT, "minFit": True},
            {**POLICY_DEFAULT, "minMargin": float("nan")},
            {**POLICY_DEFAULT, "name": ""},
            {**POLICY_DEFAULT, "hidden_field": "ignored"},
        ]:
            with self.assertRaises(ValueError):
                clean_policy(bad)
        for bad in [
            {**FACTOR_DEFAULTS, "technical": -1},
            {**FACTOR_DEFAULTS, "technical": 14},
            {**FACTOR_DEFAULTS, "risk": 1.0},
            {**FACTOR_DEFAULTS, "rogue": 1},
        ]:
            with self.assertRaises(ValueError):
                clean_weights(bad)

    def test_immutable_versions_and_conflict(self):
        state = default_state()
        changed = next_state(state, {
            "expected_revision": 0, "kind": "policy",
            "profile": {**POLICY_DEFAULT, "minFit": 80}
        }, "2026-10-10T00:00:00Z")
        self.assertEqual(state["policy_version"], 1)
        self.assertEqual(changed["policy_version"], 2)
        self.assertEqual(changed["versions"][0]["value"]["minFit"], 65)
        self.assertEqual(changed["versions"][-1]["value"]["minFit"], 80)
        with self.assertRaises(ProfileConflict):
            next_state(changed, {"expected_revision": 0, "kind": "factors", "weights": FACTOR_DEFAULTS}, "")
        other = next_state(changed, {
            "expected_revision": 1, "kind": "factors", "weights": FACTOR_DEFAULTS
        }, "2026-10-10T00:00:01Z")
        self.assertEqual(other["revision"], 2)
        self.assertEqual(other["factor_version"], 2)


class ProfileHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.root_patch = patch.object(server, "ROOT", self.root)
        self.file_patch = patch.object(server, "FILE", self.root / "cases.json")
        self.root_patch.start()
        self.file_patch.start()
        server.persist({"schema_version": 1, "cases": [{"id": "existing", "title": "keep"}]})
        self.http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.base = "http://127.0.0.1:" + str(self.http.server_port)

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(timeout=3)
        self.file_patch.stop()
        self.root_patch.stop()
        self.tmp.cleanup()

    def get(self):
        try:
            with urlopen(self.base + "/api/decision-profiles", timeout=4) as resp:
                return resp.status, json.load(resp)
        except HTTPError as error:
            return error.code, json.load(error)

    def post(self, body, headers=None):
        request = Request(
            self.base + "/api/decision-profiles/save",
            data=json.dumps(body).encode(),
            headers=headers if headers is not None else {
                "Content-Type": "application/json", "Origin": self.base,
                "X-Local-CSRF": server.TOKEN,
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=4) as resp:
                return resp.status, json.load(resp)
        except HTTPError as error:
            return error.code, json.load(error)

    def test_roundtrip_conflict_and_isolation(self):
        status, response = self.get()
        self.assertEqual(status, 200)
        self.assertEqual(response["profiles"]["revision"], 0)
        self.assertFalse((self.root / "decision_profiles.json").exists())
        saved_status, response = self.post({
            "expected_revision": 0, "kind": "policy",
            "profile": {**POLICY_DEFAULT, "minFit": 77},
        })
        self.assertEqual(saved_status, 200)
        self.assertEqual(response["profiles"]["policy_version"], 2)
        self.assertEqual(self.get()[1]["profiles"]["policy"]["minFit"], 77)
        self.assertEqual(load_state(self.root / "decision_profiles.json")["revision"], 1)
        self.assertEqual(self.post({
            "expected_revision": 0, "kind": "policy", "profile": POLICY_DEFAULT,
        })[0], 409)
        self.assertEqual(self.post({
            "expected_revision": 1, "kind": "factors", "weights": FACTOR_DEFAULTS,
        })[0], 200)
        self.assertEqual(self.get()[1]["profiles"]["factor_version"], 2)
        self.assertEqual(json.loads((self.root / "cases.json").read_text())["cases"][0]["id"], "existing")
        self.assertFalse((self.root / "operations.json").exists())

    def test_invalid_and_forbidden_requests_do_not_write(self):
        self.assertEqual(self.post({
            "expected_revision": 0, "kind": "factors",
            "weights": {**FACTOR_DEFAULTS, "risk": 3},
        })[0], 400)
        self.assertEqual(self.post({
            "expected_revision": 0, "kind": "policy", "profile": POLICY_DEFAULT,
        }, headers={"Content-Type": "application/json"})[0], 403)
        self.assertFalse((self.root / "decision_profiles.json").exists())

    def test_corrupted_json_fails_closed(self):
        (self.root / "decision_profiles.json").write_text("{", encoding="utf8")
        self.assertEqual(self.get()[0], 503)
        self.assertEqual(self.post({
            "expected_revision": 0, "kind": "policy", "profile": POLICY_DEFAULT
        })[0], 503)
        self.assertEqual((self.root / "decision_profiles.json").read_text(), "{")


if __name__ == "__main__":
    unittest.main()
