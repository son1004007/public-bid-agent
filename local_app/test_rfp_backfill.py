"""RFP 소급 청크 이관의 안전 실패/성공 회귀 테스트.

합성 공고 2개와 가짜 공식 첨부를 사용한다. 외부 네트워크/기밀 입력 금지.
"""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from rfp_backfill import Backfill, eligible, verify_and_store
from rfp_fulltext import load

URL = "https://www.g2b.go.kr/pn/download/document"


def persist(value, path):
    target = path.with_suffix(".tmp")
    target.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    target.replace(path)


def doc_case(ident, raw=b"SYNTHETIC PDF", text="실제 아닌 합성 문서입니다" * 2000):
    name = "제안요청서.pdf"
    link = URL + ident
    eid = hashlib.sha256((link+"\n"+name).encode()).hexdigest()
    return {"id": ident, "final": "no_bid", "finalReason": "사람 결정",
            "attachments": [{"name": name, "url": link}],
            "document_status": "EXTRACTED", "rfp_text": text[:6000],
            "document_evidence": [{"identity": eid, "name": name, "status": "EXTRACTED",
                                  "sha256": hashlib.sha256(raw).hexdigest(),
                                  "chars": len(text), "excerpt": text[:6000]}]}


class BackfillTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.content = "".join(f"문서{i:04d};" for i in range(5000))
        self.raw = b"FAKE-PDF-BYTES"
        self.notice = doc_case("one", self.raw, self.content)
        self.original = {"schema_version": 1, "revision": 0,
                         "notices": [self.notice], "history": [{"key": "human"}],
                         "collection": {"status": "SUCCESS"}}
        persist(self.original, self.root / "dashboard.json")
        self.requests = 0

    def reader(self, name, raw):
        return {"text": self.content, "characters": len(self.content), "truncated": False}

    def fetch(self, url):
        self.requests += 1
        return self.raw

    def worker(self, fetcher=None, extractor=None, delay=0):
        return Backfill(self.root, ["one"], persist, extractor or self.reader,
                        fetcher=fetcher or self.fetch, delay=delay)

    def test_match_and_backfill_preserves_decision_history_and_excerpt(self):
        worker = self.worker()
        result = worker.run(1)
        self.assertEqual(result["DONE"], 1)
        self.assertEqual(result["pending"], 0)
        self.assertEqual(result["total_documents"], 1)
        updated = json.loads((self.root/"dashboard.json").read_text(encoding="utf-8"))
        self.assertEqual(updated["history"], self.original["history"])
        self.assertEqual(updated["notices"][0]["finalReason"], "사람 결정")
        meta = updated["notices"][0]["document_evidence"][0]
        self.assertEqual(meta["excerpt"], self.content[:6000])
        self.assertEqual(meta["sha256"], hashlib.sha256(self.raw).hexdigest())
        self.assertEqual(meta["fulltext_chars"], len(self.content))
        self.assertEqual("".join(c["text"] for c in load(self.root, meta["fulltext_ref"])["chunks"]), self.content)
        self.assertNotIn(self.content[6000:], json.dumps(updated, ensure_ascii=False))
        # Second run is truly idempotent, no external fetch.
        before = (self.root/"dashboard.json").read_bytes()
        result = worker.run(1)
        self.assertEqual(result["attempted_this_slice"], 0)
        self.assertEqual(self.requests, 1)
        self.assertEqual(before, (self.root/"dashboard.json").read_bytes())

    def test_changed_binary_is_quarantined_and_original_untouched(self):
        result = self.worker(fetcher=lambda url: b"CHANGED").run(1)
        self.assertEqual(result["SOURCE_CHANGED"], 1)
        self.assertEqual(result["DONE"], 0)
        actual = json.loads((self.root/"dashboard.json").read_text(encoding="utf-8"))
        self.assertEqual(actual, self.original)

    def test_identical_binary_different_extracted_text_is_quarantined(self):
        result = self.worker(extractor=lambda name, raw: {"text": "different"}).run(1)
        self.assertEqual(result["PARSER_CHANGED"], 1)
        self.assertEqual(json.loads((self.root/"dashboard.json").read_text(encoding="utf-8")), self.original)

    def test_unmatched_identity_is_quarantined(self):
        self.notice["attachments"][0]["url"] = URL + "other"
        persist(self.original, self.root/"dashboard.json")
        result = self.worker().run(1)
        self.assertEqual(result["UNMATCHED"], 1)
        self.assertEqual(self.requests, 0)

    def test_resume_two_document_slices_and_reject_wrong_scope(self):
        two = doc_case("two", self.raw, self.content)
        board = json.loads((self.root/"dashboard.json").read_text(encoding="utf-8"))
        board["notices"].append(two)
        persist(board, self.root/"dashboard.json")
        worker = Backfill(self.root, ["one","two"], persist, self.reader,
                          fetcher=self.fetch, delay=0)
        one = worker.run(1)
        self.assertEqual(one["pending"], 1)
        two = worker.run(1)
        self.assertEqual(two["pending"], 0)
        self.assertEqual(two["DONE"], 2)
        with self.assertRaises(ValueError):
            self.worker().run(1)

    def test_reject_unsafe_scope_or_batch_size(self):
        with self.assertRaises(ValueError):
            Backfill(self.root, ["one","one"], persist, self.reader)
        with self.assertRaises(ValueError):
            self.worker().run(100)


    def test_untrusted_writer_cannot_override_previous_evidence(self):
        from rfp_backfill import verify_and_store
        fake = lambda root, sha, parsed: {"excerpt": "changed", "sha256": "0" * 64}
        outcome, result = verify_and_store(
            self.root, self.notice, self.notice["document_evidence"][0],
            self.reader, self.fetch, fake)
        self.assertEqual(outcome, "PARSER_CHANGED")
        self.assertIsNone(result)
        self.assertEqual(json.loads((self.root/"dashboard.json").read_text(encoding="utf-8")),
                         self.original)

    def test_crash_after_dashboard_commit_restores_ledger_without_redownload(self):
        attempts = {"failed": False}
        def unstable(value, path):
            if path.name == "rfp_backfill.json" and not attempts["failed"]:
                attempts["failed"] = True
                raise OSError("synthetic ledger failure")
            persist(value, path)
        worker = Backfill(self.root, ["one"], unstable, self.reader,
                          fetcher=self.fetch, delay=0)
        with self.assertRaises(OSError):
            worker.run(1)
        self.assertEqual(self.requests, 1)
        state = self.worker().run(1)
        self.assertEqual(state["DONE"], 1)
        self.assertEqual(state["attempted_this_slice"], 0)
        self.assertEqual(self.requests, 1)

    def test_cached_reference_tamper_fails_closed(self):
        attempts = {"failed": False}
        def unstable(value, path):
            if path.name == "rfp_backfill.json" and not attempts["failed"]:
                attempts["failed"] = True
                raise OSError("synthetic ledger failure")
            persist(value, path)
        with self.assertRaises(OSError):
            Backfill(self.root, ["one"], unstable, self.reader,
                     fetcher=self.fetch, delay=0).run(1)
        board = json.loads((self.root/"dashboard.json").read_text(encoding="utf-8"))
        ref = board["notices"][0]["document_evidence"][0]["fulltext_ref"]
        p = self.root/"rfp_fulltext"/(ref+".json")
        obj = json.loads(p.read_text(encoding="utf-8"))
        obj["chunks"][0]["text"] = "tampered"
        p.write_text(json.dumps(obj),encoding="utf-8")
        with self.assertRaises(ValueError):
            self.worker().run(1)

    def test_unreferenced_cache_is_only_reported(self):
        from rfp_backfill import orphan_inventory
        self.worker().run(1)
        summary = orphan_inventory(self.root)
        self.assertEqual(summary, {"sidecars": 1, "referenced": 1, "unreferenced": 0})
        extra = self.root/"rfp_fulltext"/("f"*64+".json")
        extra.write_text("{}", encoding="utf-8")
        summary = orphan_inventory(self.root)
        self.assertEqual(summary["unreferenced"], 1)
        self.assertTrue(extra.exists())


if __name__ == "__main__":
    unittest.main()
