"""RFP 청크 저장의 실패·재시도·출처 무결성 회귀 검증.

입력: 합성 RFP 텍스트, 임시 파일, 공식 형태의 가상 URL.
출력: 본문 청크 재조립·절단 여부/위조 탐지·배치 연결 테스트.
실제 회사 데이터/외부 API/AI 없음.
"""
import hashlib
import json
import tempfile
import threading
import unittest
from pathlib import Path

from rfp_fulltext import CHUNK_CHARS, MAX_TEXT_CHARS, load, store
from rfp_batch import Manager
from test_rfp_batch import notice, persist


class RfpFulltextTests(unittest.TestCase):
    def test_full_44000_chars_reconstructed_without_dashboard_embedding(self):
        text = "".join(str(i % 10) for i in range(MAX_TEXT_CHARS))
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = hashlib.sha256(b"synthetic PDF").hexdigest()
            meta = store(root, source, {"text": text, "characters": 52000,
                                        "truncated": True})
            record = load(root, meta["fulltext_ref"])
            self.assertEqual("".join(x["text"] for x in record["chunks"]), text)
            self.assertEqual(meta["fulltext_chunks"], 11)
            self.assertTrue(meta["fulltext_truncated"])
            self.assertEqual(meta["fulltext_chars"], 44000)
            self.assertEqual(meta["fulltext_reported_chars"], 52000)
            self.assertTrue(all(len(x["text"]) <= CHUNK_CHARS for x in record["chunks"]))
            self.assertEqual(meta["fulltext_position_basis"],
                             "EXTRACTED_TEXT_OFFSETS_NOT_ORIGINAL_PAGES")
            self.assertNotIn("text", meta)

    def test_duplicate_is_idempotent_and_corrupted_cache_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            digest = hashlib.sha256(b"source").hexdigest()
            doc = {"text": "가상 요구내용" * 1500}
            first = store(root, digest, doc)
            self.assertEqual(first, store(root, digest, doc))
            path = root / "rfp_fulltext" / (first["fulltext_ref"] + ".json")
            record = json.loads(path.read_text(encoding="utf-8"))
            record["chunks"][0]["text"] = "위조"
            path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(ValueError):
                load(root, first["fulltext_ref"])
            with self.assertRaises(ValueError):
                store(root, digest, doc)

    def test_two_process_conflicting_creation_never_overwrites_first(self):
        import os
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as td:
            source = hashlib.sha256(b"concurrent synthetic original").hexdigest()
            code = (
                "import sys;from rfp_fulltext import store;"
                "root,source,reported=sys.argv[1:4];"
                "doc={'text':'synthetic body','characters':int(reported),'truncated':True};"
                "store(root,source,doc)"
            )
            env = os.environ.copy()
            env["PYTHONPATH"] = str(Path(__file__).parent) + os.pathsep + env.get("PYTHONPATH","")
            procs=[subprocess.Popen([sys.executable,"-c",code,td,source,str(x)],
                       env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                   for x in (120,121)]
            outcome=[p.communicate(timeout=12) for p in procs]
            self.assertEqual(sorted(p.returncode for p in procs),[0,1])
            self.assertEqual(len(list((Path(td)/"rfp_fulltext").glob("*.json"))),1)
            winner = [p for p in procs if p.returncode==0]
            self.assertEqual(len(winner),1)
            # 충돌 뒤에도 단 하나의 완전하고 무결한 파일을 보관한다.
            import json
            stored=json.loads(next((Path(td)/"rfp_fulltext").glob("*.json")).read_text(encoding="utf-8"))
            loaded=load(Path(td), hashlib.sha256((source+":"+stored["text_sha256"]).encode()).hexdigest())
            self.assertIn(loaded["reported_chars"],(120,121))
            self.assertEqual(loaded["stored_chars"],len("synthetic body"))

    def test_existing_cache_conflicting_parser_metadata_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = hashlib.sha256(b"synthetic fixed source").hexdigest()
            initial = {"text": "동일한 원문 텍스트", "characters": 123, "truncated": True}
            meta = store(root, source, initial)
            path = root / "rfp_fulltext" / (meta["fulltext_ref"] + ".json")
            original = path.read_bytes()
            for altered in (
                {"text": initial["text"], "characters": 124, "truncated": True},
                {"text": initial["text"], "characters": 122, "truncated": False},
                {"text": initial["text"], "characters": len(initial["text"]), "truncated": False},
            ):
                with self.subTest(altered=altered), self.assertRaisesRegex(ValueError, "불일치"):
                    store(root, source, altered)
                self.assertEqual(path.read_bytes(), original)
            self.assertEqual(store(root, source, initial), meta)

    def test_invalid_and_oversized_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sha = hashlib.sha256(b"x").hexdigest()
            bad = [
                {"text": "hello", "characters": 2},
                {"text": "hello", "truncated": "yes"},
                {"text": "x" * (MAX_TEXT_CHARS + 1)},
                {"text": "   "},
            ]
            for doc in bad:
                with self.subTest(doc_type=type(doc.get("text")).__name__):
                    with self.assertRaises(ValueError):
                        store(root, sha, doc)
            with self.assertRaises(ValueError):
                load(root, "../data.json")

    def test_manager_persists_only_reference_and_keeps_human_decision(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            original = notice("case1")
            original["finalReason"] = "합성 사례의 사람 결정"
            persist({"schema_version": 1, "revision": 0, "notices": [original],
                     "history": [{"id": "case1", "event": "no_bid"}],
                     "collection": {"status": "SUCCESS"}}, root / "dashboard.json")
            persist({"schema_version": 1, "revision": 0, "categories": ["SW"],
                     "include_review": False}, root / "department_profile.json")
            fulltext = "".join(f"{i:05d}:요건" for i in range(2500))
            manager = Manager(root, threading.RLock(), persist,
                              lambda name, raw: {"text": fulltext},
                              fetcher=lambda url: b"synthetic raw pdf", delay=0)
            manager.start(1)
            manager.worker.join(10)
            self.assertFalse(manager.worker.is_alive())
            self.assertEqual(manager.status()["statistics"]["done"], 1)
            board = json.loads((root / "dashboard.json").read_text(encoding="utf-8"))
            updated = board["notices"][0]
            self.assertEqual(updated["final"], original["final"])
            self.assertEqual(updated["finalReason"], original["finalReason"])
            self.assertEqual(board["history"], [{"id": "case1", "event": "no_bid"}])
            evidence = updated["document_evidence"][0]
            self.assertEqual(len(evidence["excerpt"]), 6000)
            self.assertNotIn("chunks", evidence)
            self.assertNotIn(fulltext[6000:], json.dumps(board, ensure_ascii=False))
            self.assertEqual("".join(chunk["text"] for chunk in
                                     load(root, evidence["fulltext_ref"])["chunks"]),
                             fulltext)
            self.assertEqual(evidence["fulltext_chunks"],
                             (len(fulltext) + CHUNK_CHARS - 1) // CHUNK_CHARS)


if __name__ == "__main__":
    unittest.main()
