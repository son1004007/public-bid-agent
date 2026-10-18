"""운영 RFP 검증 사본의 롤포워드/롤백 합성 테스트.

공식 사이트·회사 원본·모델 호출 없이 2223개 합성 공고, 127개 가짜 문서,
124개 청크 파일을 생성해서 이관/백업/복원 계약을 검증한다.
P08: 수기 제출·평가·선정/미선정 사건도 합성 fixture에 포함해 백업/복구 시 보존하고,
백업 후 새 수기 기록 또는 백업 손상 시 복원이 안전하게 거부되는지 검증한다.
모든 apply/rollback/recover 호출의 대상은 테스트가 생성한 임시 경로뿐이다.
"""
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from promote_verified_rfp_stage import apply, plan, rollback, digest, write_atomic
from rfp_fulltext import store as store_fulltext, load as load_fulltext
from bid_outcomes import record as record_outcome


class ReleaseStageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.live = self.root/"live"
        self.stage = self.root/"stage"
        self.backup = self.root/"backup"
        self.live.mkdir()
        self.stage.mkdir()
        notices = []
        self.targets = []
        for i in range(2223):
            ident = f"G2B-R26BK900{i:05d}-001"
            if i < 70:
                self.targets.append(ident)
            notices.append({"id": ident, "title": "합성 SW 과업", "final": "no_bid" if i == 7 else None,
                            "finalReason": "합성 인적 판단" if i == 7 else "",
                            "department_categories": ["SW"], "category_evidence": [],
                            "needs_document": True, "attachments": [],
                            "document_status": "PENDING", "rfp_text": "",
                            "document_evidence": []})
        base = {"schema_version":1,"revision":45,"notices":notices,
                "history":[{"id":"synthetic-human-history"}],
                "collection":{"status":"SUCCESS"}}
        # Include each manual phase, including a notice outside the promotion scope.
        self.manual_events = {}
        for index, stages in ((0, ("SUBMITTED",)), (1, ("SUBMITTED", "EVALUATED")),
                              (2, ("SUBMITTED", "EVALUATED", "AWARDED")),
                              (3, ("SUBMITTED", "EVALUATED", "NOT_AWARDED")),
                              (70, ("SUBMITTED", "WITHDRAWN"))):
            notice = notices[index]
            notice["final"] = "bid"
            notice["finalReason"] = "합성 참여 결정"
            notice["rec"] = "hold"
            events = [{"stage": stage, "observed_on": "2026-10-16",
                       "evidence_reference": "합성 담당자 자료 확인",
                       "evaluation_score": 82.5 if stage in ("EVALUATED", "AWARDED", "NOT_AWARDED") else None,
                       "recorded_at": "2026-10-16T00:00:00+00:00",
                       "source": "HUMAN_DECLARED_UNVERIFIED"} for stage in stages]
            notice["submission_events"] = events
            self.manual_events[notice["id"]] = copy.deepcopy(events)
        write_atomic(self.live/"dashboard.json",base)
        candidate = copy.deepcopy(base)
        count = 0
        aliases = []
        for i, notice in enumerate(candidate["notices"][:70]):
            n_files = 2 if i < 57 else 1
            evidence = []
            attachments = []
            for j in range(n_files):
                doc_no = count
                if doc_no >= 124:
                    src_sha, content = aliases[doc_no-124]
                else:
                    content = "합성공고" + str(doc_no).zfill(4) + ("가" * 6500)
                    src_sha = hashlib.sha256(f"FAKE-DOCUMENT-{doc_no}".encode()).hexdigest()
                    aliases.append((src_sha,content))
                name = f"합성제안요청서{doc_no}.pdf"
                url = f"https://www.g2b.go.kr/pn/download/{doc_no}"
                identity = hashlib.sha256((url+"\n"+name).encode()).hexdigest()
                meta = store_fulltext(self.stage,src_sha,{"text":content})
                evidence.append({"identity":identity,"sha256":src_sha,"name":name,
                    "status":"EXTRACTED","chars":len(content),"excerpt":content[:6000],**meta})
                attachments.append({"name":name,"url":url,"source":"공식 합성"})
                count += 1
            notice["document_evidence"]=evidence
            notice["document_status"]="EXTRACTED"
            notice["rfp_text"]="\n\n".join(e["excerpt"] for e in evidence)[:12000]
            notice["attachments"]=attachments
            if i < 20:
                notice["department_categories"]=["AI","SW"]
            notice["needs_document"]=False
        self.assertEqual(count,127)
        write_atomic(self.stage/"dashboard.json",candidate)
        present = self.targets + [n["id"] for n in notices[70:143]]
        records = {ident:{"status": "PENDING","attempts":0} for ident in present}
        for ident in present[70:109]:
            records[ident]["status"]="DONE"
        write_atomic(self.live/"rfp_batch.json",{
            "schema_version":1,"revision":82,"status":"PAUSED",
            "target_ids":present,"items":records,"updated_at":None})
        write_atomic(self.stage/"rfp_batch_original.json",{
            "schema_version":1,"revision":146,"status":"COMPLETE",
            "target_ids":self.targets,
            "items":{ident:{"status":"DONE"} for ident in self.targets}})
        write_atomic(self.stage/"rfp_backfill.json",{
            "schema_version":1,"revision":127,
            "items":{str(i):{"status":"DONE"} for i in range(127)}})

    def test_plan_is_readonly_and_scope_bounded(self):
        a=digest(self.live/"dashboard.json")
        board, ledger, refs, report = plan(self.live,self.stage)
        self.assertEqual(report["documents"],127)
        self.assertEqual(report["sidecar_files"],124)
        self.assertEqual(report["department_classifications_updated"],20)
        self.assertEqual(report["batch_done_after"],109)
        self.assertEqual(report["batch_pending_after"],34)
        self.assertEqual(board["history"],[{"id":"synthetic-human-history"}])
        self.assertEqual(digest(self.live/"dashboard.json"),a)
        self.assertEqual(ledger["status"],"PAUSED")
        self.assertEqual(len(refs),124)

    def assert_manual_events(self, root):
        board = json.loads((root / "dashboard.json").read_text(encoding="utf-8"))
        notices = {notice["id"]: notice for notice in board["notices"]}
        for ident, events in self.manual_events.items():
            self.assertEqual(notices[ident]["submission_events"], events)
            self.assertEqual(notices[ident]["final"], "bid")
            self.assertEqual(notices[ident]["finalReason"], "합성 참여 결정")
            self.assertEqual(notices[ident]["rec"], "hold")
        self.assertEqual(board["history"], [{"id": "synthetic-human-history"}])

    def test_manual_outcomes_backup_restore_ignores_stage_human_fields(self):
        candidate = json.loads((self.stage / "dashboard.json").read_text(encoding="utf-8"))
        candidate["notices"][0]["submission_events"] = []
        candidate["notices"][0]["final"] = "no_bid"
        write_atomic(self.stage / "dashboard.json", candidate)
        before = {name: (self.live / name).read_bytes() for name in ("dashboard.json", "rfp_batch.json")}
        apply(self.live, self.stage, self.backup)
        self.assert_manual_events(self.live)
        self.assert_manual_events(self.backup)
        for name, content in before.items():
            self.assertEqual((self.backup / name).read_bytes(), content)
        self.assertEqual(rollback(self.live, self.backup)["result"], "ROLLED_BACK")
        self.assert_manual_events(self.live)
        for name, content in before.items():
            self.assertEqual((self.live / name).read_bytes(), content)
            self.assertEqual((self.backup / name).read_bytes(), content)

    def test_new_manual_evaluation_blocks_rollback_and_preserves_backup(self):
        apply(self.live, self.stage, self.backup)
        backup_bytes = (self.backup / "dashboard.json").read_bytes()
        board = json.loads((self.live / "dashboard.json").read_text(encoding="utf-8"))
        updated = record_outcome(board, {"id": self.targets[0], "expected_revision": board["revision"],
            "stage": "EVALUATED", "observed_on": "2026-10-18",
            "evaluation_score": 87.5, "evidence_reference": "합성 신규 평가 자료"},
            "2026-10-18T00:00:00+00:00")
        write_atomic(self.live / "dashboard.json", updated)
        before = {name: (self.live / name).read_bytes() for name in ("dashboard.json", "rfp_batch.json")}
        with self.assertRaisesRegex(ValueError, "다른 수정"):
            rollback(self.live, self.backup)
        for name, content in before.items():
            self.assertEqual((self.live / name).read_bytes(), content)
        self.assertEqual((self.backup / "dashboard.json").read_bytes(), backup_bytes)
        self.assertEqual(updated["notices"][0]["submission_events"][-1]["stage"], "EVALUATED")

    def test_same_revision_outcome_edit_cannot_be_lost_to_rollback(self):
        apply(self.live, self.stage, self.backup)
        board = json.loads((self.live / "dashboard.json").read_text(encoding="utf-8"))
        board["notices"][2]["submission_events"][-1]["evidence_reference"] = "합성 수동 정정 자료"
        write_atomic(self.live / "dashboard.json", board)
        before = (self.live / "dashboard.json").read_bytes()
        backup = (self.backup / "dashboard.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "실제 내용 변경"):
            rollback(self.live, self.backup)
        self.assertEqual((self.live / "dashboard.json").read_bytes(), before)
        self.assertEqual((self.backup / "dashboard.json").read_bytes(), backup)

    def test_modified_outcome_backup_blocks_rollback_and_pending_recovery(self):
        import promote_verified_rfp_stage as mod
        from release_lease import save_intent, read_intent
        apply(self.live, self.stage, self.backup)
        backup = json.loads((self.backup / "dashboard.json").read_text(encoding="utf-8"))
        backup["notices"][3]["submission_events"][-1]["stage"] = "AWARDED"
        write_atomic(self.backup / "dashboard.json", backup)
        before = {name: (self.live / name).read_bytes() for name in ("dashboard.json", "rfp_batch.json")}
        damaged_backup = (self.backup / "dashboard.json").read_bytes()
        with self.assertRaises(ValueError):
            rollback(self.live, self.backup)
        intent = json.loads((self.live / mod.JOURNAL).read_text(encoding="utf-8"))
        intent["status"] = "PREPARED"
        save_intent(self.live, "PREPARED", intent)
        with self.assertRaisesRegex(ValueError, "백업 무결성"):
            mod.recover(self.live, self.backup)
        self.assertEqual(read_intent(self.live)["status"], "PREPARED")
        for name, content in before.items():
            self.assertEqual((self.live / name).read_bytes(), content)
        self.assertEqual((self.backup / "dashboard.json").read_bytes(), damaged_backup)

    def test_partial_backup_refuses_resume_after_new_manual_evaluation(self):
        import promote_verified_rfp_stage as mod
        from unittest.mock import patch
        actual_copy = mod.shutil.copy2

        def fail_second_backup(source, destination, *args, **kwargs):
            if Path(destination) == self.backup / "rfp_batch.json":
                raise OSError("synthetic interrupted backup")
            return actual_copy(source, destination, *args, **kwargs)

        before = (self.live / "dashboard.json").read_bytes()
        with patch.object(mod.shutil, "copy2", side_effect=fail_second_backup):
            with self.assertRaises(OSError):
                apply(self.live, self.stage, self.backup)
        self.assertEqual((self.live / "dashboard.json").read_bytes(), before)
        self.assertEqual((self.backup / "dashboard.json").read_bytes(), before)
        board = json.loads(before)
        updated = record_outcome(board, {"id": self.targets[0], "expected_revision": board["revision"],
            "stage": "EVALUATED", "observed_on": "2026-10-18", "evaluation_score": 87.5,
            "evidence_reference": "합성 백업 중단 후 평가"}, "2026-10-18T00:00:00+00:00")
        write_atomic(self.live / "dashboard.json", updated)
        edited = (self.live / "dashboard.json").read_bytes()
        with self.assertRaises(ValueError):
            apply(self.live, self.stage, self.backup)
        self.assertEqual((self.live / "dashboard.json").read_bytes(), edited)
        self.assertEqual((self.backup / "dashboard.json").read_bytes(), before)
        self.assertFalse((self.backup / "restore_metadata.json").exists())

    def test_apply_rollback_preserves_human_decisions(self):
        before={name:digest(self.live/name) for name in ("dashboard.json","rfp_batch.json")}
        info=apply(self.live,self.stage,self.backup)
        self.assertTrue(info["original_sha_preserved_in_backup"])
        self.assertEqual(info["new_sidecar_files"],124)
        changed=json.loads((self.live/"dashboard.json").read_text(encoding="utf-8"))
        self.assertEqual(changed["notices"][7]["final"],"no_bid")
        self.assertEqual(changed["notices"][7]["finalReason"],"합성 인적 판단")
        self.assertEqual(changed["history"],[{"id":"synthetic-human-history"}])
        data=changed["notices"][7]["document_evidence"][0]
        self.assertEqual(load_fulltext(self.live,data["fulltext_ref"])["stored_chars"],data["chars"])
        self.assertEqual(rollback(self.live,self.backup)["result"],"ROLLED_BACK")
        self.assertTrue(all(digest(self.live/name)==sha for name,sha in before.items()))
        self.assertTrue(self.backup.exists())

    def test_reject_manual_document_override(self):
        value=json.loads((self.live/"dashboard.json").read_text(encoding="utf-8"))
        value["notices"][0]["rfp_text"]="담당자 수동 입력"
        write_atomic(self.live/"dashboard.json",value)
        with self.assertRaises(ValueError):
            plan(self.live,self.stage)
        self.assertFalse(self.backup.exists())

    def test_reject_source_cache_corruption(self):
        board=json.loads((self.stage/"dashboard.json").read_text(encoding="utf-8"))
        ref=board["notices"][0]["document_evidence"][0]["fulltext_ref"]
        path=self.stage/"rfp_fulltext"/(ref+".json")
        record=json.loads(path.read_text(encoding="utf-8"))
        record["chunks"][0]["text"]="변조"
        path.write_text(json.dumps(record,ensure_ascii=False),encoding="utf-8")
        with self.assertRaises(ValueError):
            plan(self.live,self.stage)

    def test_running_ledger_blocks(self):
        ledger=json.loads((self.live/"rfp_batch.json").read_text(encoding="utf-8"))
        ledger["status"]="RUNNING"
        write_atomic(self.live/"rfp_batch.json",ledger)
        with self.assertRaises(ValueError):
            plan(self.live,self.stage)

    def test_rollback_rejects_newer_edits(self):
        apply(self.live,self.stage,self.backup)
        board=json.loads((self.live/"dashboard.json").read_text(encoding="utf-8"))
        board["revision"] += 1
        write_atomic(self.live/"dashboard.json",board)
        with self.assertRaises(ValueError):
            rollback(self.live,self.backup)

    def test_interrupted_release_restores_both_generations(self):
        from promote_verified_rfp_stage import recover, JOURNAL, guard_no_incomplete_journal
        previous={n:digest(self.live/n) for n in ("dashboard.json","rfp_batch.json")}
        apply(self.live,self.stage,self.backup)
        ledger_old=self.backup/"rfp_batch.json"
        import shutil
        shutil.copy2(ledger_old,self.live/"rfp_batch.json")
        journal=self.live/JOURNAL
        state=json.loads(journal.read_text(encoding="utf-8"))
        state["status"]="PREPARED"
        write_atomic(journal,state)
        with self.assertRaises(ValueError):
            guard_no_incomplete_journal(self.live)
        report=recover(self.live,self.backup)
        self.assertEqual(report["result"],"RECOVERED_ROLLBACK")
        self.assertTrue(all(digest(self.live/n)==sha for n,sha in previous.items()))
        self.assert_manual_events(self.live)
        self.assert_manual_events(self.backup)
        guard_no_incomplete_journal(self.live)

    def test_interrupted_commit_finalizes_when_both_new_files_valid(self):
        from promote_verified_rfp_stage import recover, JOURNAL
        apply(self.live,self.stage,self.backup)
        before={n:digest(self.live/n) for n in ("dashboard.json","rfp_batch.json")}
        journal=self.live/JOURNAL
        state=json.loads(journal.read_text(encoding="utf-8"))
        state["status"]="PREPARED"
        write_atomic(journal,state)
        report=recover(self.live,self.backup)
        self.assertEqual(report["result"],"RECOVERED_COMMIT")
        self.assertTrue(all(digest(self.live/n)==sha for n,sha in before.items()))
        self.assert_manual_events(self.live)
        self.assert_manual_events(self.backup)


    def test_same_revision_human_edit_cannot_be_rolled_back(self):
        from promote_verified_rfp_stage import JOURNAL
        apply(self.live,self.stage,self.backup)
        board=json.loads((self.live/"dashboard.json").read_text(encoding="utf-8"))
        current_revision=board["revision"]
        board["notices"][7]["finalReason"]="배포 이후 담당자의 새로운 판단"
        write_atomic(self.live/"dashboard.json",board)
        self.assertEqual(board["revision"],current_revision)
        with self.assertRaises(ValueError):
            rollback(self.live,self.backup)
        actual=json.loads((self.live/"dashboard.json").read_text(encoding="utf-8"))
        self.assertEqual(actual["notices"][7]["finalReason"],"배포 이후 담당자의 새로운 판단")
        journal=json.loads((self.live/JOURNAL).read_text(encoding="utf-8"))
        self.assertEqual(journal["status"],"COMPLETED")

    def test_manual_rollback_interruption_can_be_recovered(self):
        from unittest.mock import patch
        import promote_verified_rfp_stage as mod
        apply(self.live,self.stage,self.backup)
        actual=mod._copy_atomic
        calls={"count":0}
        def crash_during_second_copy(src,dest):
            calls["count"] += 1
            if calls["count"] == 2:
                raise OSError("synthetic power-off after first rollback JSON")
            return actual(src,dest)
        with patch.object(mod, "_copy_atomic", side_effect=crash_during_second_copy):
            with self.assertRaises(OSError):
                rollback(self.live,self.backup)
        with self.assertRaises(ValueError):
            mod.guard_no_incomplete_journal(self.live)
        self.assertEqual(mod.recover(self.live,self.backup)["result"],"RECOVERED_ROLLBACK")
        self.assertEqual(digest(self.live/"dashboard.json"),
                         digest(self.backup/"dashboard.json"))
        self.assertEqual(digest(self.live/"rfp_batch.json"),
                         digest(self.backup/"rfp_batch.json"))
        self.assert_manual_events(self.live)

    def test_stage_file_swap_while_validating_is_rejected(self):
        from unittest.mock import patch
        import promote_verified_rfp_stage as mod
        real=mod.load_fulltext
        def switched(root,reference):
            data=real(root,reference)
            p=Path(root)/"rfp_fulltext"/(reference+".json")
            p.write_bytes(p.read_bytes()+b" ")
            return data
        with patch.object(mod,"load_fulltext",side_effect=switched):
            with self.assertRaises(ValueError):
                plan(self.live,self.stage)


    def test_running_server_lease_blocks_upgrade(self):
        from release_lease import exclusive_release_access
        with exclusive_release_access(self.live, timeout=0):
            with self.assertRaises(TimeoutError):
                apply(self.live, self.stage, self.backup)
        self.assertFalse(self.backup.exists())

    def test_sqlite_intent_blocks_when_json_journal_missing(self):
        from release_lease import save_intent, guard_ready, read_intent
        from promote_verified_rfp_stage import recover, JOURNAL
        import shutil
        self.backup.mkdir()
        hashes = {name:digest(self.live/name) for name in ("dashboard.json","rfp_batch.json")}
        for name in hashes:
            shutil.copy2(self.live/name,self.backup/name)
        state = {"status":"PREPARED","backup_path":str(self.backup),
                 "original_files":hashes,
                 "expected_new_files":{n:"0"*64 for n in hashes}}
        save_intent(self.live,"PREPARED",state)
        self.assertFalse((self.live/JOURNAL).exists())
        with self.assertRaises(RuntimeError):
            guard_ready(self.live)
        self.assertEqual(read_intent(self.live)["status"],"PREPARED")
        self.assertEqual(recover(self.live,self.backup)["result"],"RECOVERED_ROLLBACK")
        for n,sha in hashes.items():
            self.assertEqual(digest(self.live/n),sha)

    def test_partial_release_backup_can_resume_if_live_unchanged(self):
        import promote_verified_rfp_stage as mod
        from unittest.mock import patch
        actual = mod.shutil.copy2
        calls=[0]
        def fail_first_copy(src,dst,*args,**kwargs):
            calls[0]+=1
            if calls[0]==1:
                raise OSError("synthetic backup preparation crash")
            return actual(src,dst,*args,**kwargs)
        before = {n:digest(self.live/n) for n in ("dashboard.json","rfp_batch.json")}
        with patch.object(mod.shutil,"copy2",side_effect=fail_first_copy):
            with self.assertRaises(OSError):
                apply(self.live,self.stage,self.backup)
        self.assertTrue((self.backup/".backup-intent.json").exists())
        self.assertEqual(before,{n:digest(self.live/n) for n in before})
        result=apply(self.live,self.stage,self.backup)
        self.assertEqual(result["result"],"APPLIED")

    def test_reparse_root_denied(self):
        from unittest.mock import patch
        from release_lease import reject_reparse
        import os
        actual=os.path.isjunction
        def fake_junction(p):
            if str(p)==str(self.stage):
                return True
            return actual(p)
        import os
        with patch("os.path.isjunction",side_effect=fake_junction):
            with self.assertRaises(ValueError):
                reject_reparse(self.stage)

    def test_intent_complete_verifies_then_allows_normal_updates(self):
        from release_lease import save_intent, guard_ready, read_intent
        hashes={n:digest(self.live/n) for n in ("dashboard.json","rfp_batch.json")}
        save_intent(self.live,"COMPLETED",{"expected_new_files":hashes})
        guard_ready(self.live)
        self.assertEqual(read_intent(self.live)["status"],"VERIFIED")


    def test_windows_directory_pin_prevents_swap(self):
        import os
        from release_lease import pin_directories
        if os.name != "nt":
            self.skipTest("Windows CreateFileW lease test")
        with pin_directories(self.stage):
            with self.assertRaises((PermissionError,OSError)):
                self.stage.rename(self.root/"swapped-stage")
        self.assertTrue(self.stage.exists())


if __name__=="__main__":
    unittest.main()
