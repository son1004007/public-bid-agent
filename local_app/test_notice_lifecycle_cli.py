"""로컬 공고 차수 리빌드 preview/apply와 원본 보존 검증."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from dashboard_backend import blank, normalize
from notice_lifecycle_cli import reconcile_local


def make(no, ord, kind):
    return normalize({"bidNtceNo": no, "bidNtceOrd": ord,
                      "bidNtceNm": "정보시스템 개발", "ntceKindNm": kind,
                      "pubPrcrmntClsfcNm": "소프트웨어개발",
                      "bidClseDt": "2099-12-31 18:00:00"})


class LocalReconcileTests(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root = Path(td.name)
        state = blank()
        old = make("R26BK30000001", "000", "일반공고")
        old["rfp_text"] = "과거 자료 보존"
        old["document_status"] = "EXTRACTED"
        old["document_evidence"] = [{"status": "EXTRACTED", "sha256": "a"*64}]
        old["final"] = "human_bid"
        next_notice = make("R26BK30000001", "001", "취소공고")
        state["notices"] = [old, next_notice]
        state["history"] = [{"id":"human-entry"}]
        state["revision"] = 42
        (self.root / "dashboard.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    def read(self):
        return json.loads((self.root / "dashboard.json").read_text(encoding="utf-8"))

    def test_preview_does_not_modify_json(self):
        before = (self.root / "dashboard.json").read_bytes()
        result = reconcile_local(self.root)
        self.assertEqual(result["status"], "PREVIEW")
        self.assertEqual(result["states"]["SUPERSEDED"], 1)
        self.assertEqual(result["states"]["CANCELLED"], 1)
        self.assertEqual((self.root / "dashboard.json").read_bytes(), before)

    def test_apply_marks_lifecycle_and_preserves_evidence(self):
        original = self.read()
        result = reconcile_local(self.root, apply=True)
        self.assertTrue(result["written"])
        updated = self.read()
        self.assertEqual(updated["revision"], 43)
        self.assertEqual(updated["history"], original["history"])
        self.assertEqual(updated["notices"][0]["rfp_text"], "과거 자료 보존")
        self.assertEqual(updated["notices"][0]["document_evidence"],
                         original["notices"][0]["document_evidence"])
        self.assertEqual(updated["notices"][0]["final"], "human_bid")
        self.assertEqual(updated["notices"][0]["window_status"], "SUPERSEDED")
        self.assertEqual(updated["notices"][1]["window_status"], "CANCELLED")
        second = reconcile_local(self.root, apply=True)
        self.assertFalse(second["written"])
        self.assertEqual(self.read()["revision"], 43)


if __name__ == "__main__":
    unittest.main()
