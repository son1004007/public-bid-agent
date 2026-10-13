"""로컬 공식 RFP 검증 사본을 운영 JSON으로 안전히 승격하는 오프라인 도구.

전제: 운영 서버 정지, 비공개 stage 전수 검증, 별도 원본 백업.
입력: 운영 데이터 경로, 검증 stage 경로, 백업 경로, dry-run/apply.
검증: 70건 exact 공식 evidence 출처/해시/발췌·sidecar, 사용자 결정 보존.
부작용: apply만 기존 dashboard/rfp_batch와 sidecar를 바꾸며 SHA-256 검증 후 기록.
복원: 백업한 두 JSON으로 롤백할 수 있다. 백업과 sidecar는 삭제하지 않는다.
경계: 공개 웹/API·모델 전송·데이터 외부 이동 없음; 개인 PC localhost 전용.
"""
import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from contextlib import ExitStack
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "local_app"))
from dashboard_backend import read as read_dashboard
from rfp_fulltext import load as load_fulltext
from procurement_documents import official_url
from json_transaction import transaction
from release_lease import (exclusive_release_access, reject_reparse, safe_read, save_intent, read_intent, pin_directories)

REF_RE = re.compile(r"^[0-9a-f]{64}$")
JOURNAL = ".rfp-release-transaction.json"
PROMOTE_FIELDS = ("attachments", "document_status", "rfp_text",
                  "document_source_name", "document_evidence", "document_error",
                  "needs_document", "category_evidence", "department_categories")


def digest(p):
    return hashlib.sha256(safe_read(p)).hexdigest()


def write_atomic(path, obj):
    path = Path(path)
    name = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=path.parent,
                                         prefix=".release-", suffix=".tmp", delete=False) as out:
            name = out.name
            json.dump(obj, out, ensure_ascii=False, indent=2)
            out.flush()
            os.fsync(out.fileno())
        durable_replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def durable_replace(source, target):
    """Sync an atomic filesystem replacement; SQLite intent guards mixed generations."""
    if os.name == "nt":
        import ctypes
        fn = ctypes.WinDLL("kernel32", use_last_error=True).MoveFileExW
        fn.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32)
        fn.restype = ctypes.c_int
        if not fn(str(source), str(target), 0x1 | 0x8):
            raise ctypes.WinError(ctypes.get_last_error())
    else:
        os.replace(source, target)
        fd = os.open(str(Path(target).parent), os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)


def plan(live_root, stage_root):
    live_root, stage_root = reject_reparse(live_root), reject_reparse(stage_root)
    live = read_dashboard(live_root / "dashboard.json")
    stage = read_dashboard(stage_root / "dashboard.json")
    old_ledger = json.loads((live_root / "rfp_batch.json").read_text(encoding="utf-8"))
    target_ledger = json.loads((stage_root / "rfp_batch_original.json").read_text(encoding="utf-8"))
    backfill = json.loads((stage_root / "rfp_backfill.json").read_text(encoding="utf-8"))
    targets = target_ledger["target_ids"]
    if (len(targets) != 70 or len(set(targets)) != 70 or target_ledger["status"] != "COMPLETE"
            or len(backfill.get("items", {})) != 127
            or any(e.get("status") != "DONE" for e in backfill["items"].values())):
        raise ValueError("70개 공고·127개 문서 검증 원장 미완료")
    if len(live["notices"]) != len(stage["notices"]) or len(live["notices"]) != 2223:
        raise ValueError("공고 수 불일치")
    live_map = {n["id"]: n for n in live["notices"]}
    stage_map = {n["id"]: n for n in stage["notices"]}
    if set(live_map) != set(stage_map):
        raise ValueError("공고 ID 변경")
    if (old_ledger["status"] == "RUNNING"
            or any(x.get("status") == "IN_PROGRESS" for x in old_ledger["items"].values())):
        raise ValueError("운영 RFP 배치 작업 중")
    if not set(targets).issubset(set(old_ledger["target_ids"])):
        raise ValueError("운영 배치 공고 스코프 변경")
    candidate = copy.deepcopy(live)
    candidate_map = {n["id"]: n for n in candidate["notices"]}
    refs = {}
    evidence_count = 0
    related_classification = 0
    for ident in targets:
        current, incoming = live_map[ident], stage_map[ident]
        if (current.get("document_status") not in (None, "PENDING", "NOT_AVAILABLE")
                or current.get("rfp_text") or current.get("document_evidence")):
            raise ValueError("운영 문서가 이미 수정된 대상: 안전 병합 거부")
        if incoming.get("document_status") != "EXTRACTED" or not incoming.get("rfp_text"):
            raise ValueError("이관 완료 본문이 없는 공고")
        if not isinstance(incoming.get("document_evidence"), list):
            raise ValueError("문서 근거 형식 오류")
        accepted = [e for e in incoming["document_evidence"] if e.get("status") == "EXTRACTED"]
        if not accepted:
            raise ValueError("추출 근거 누락")
        for evidence in accepted:
            ref = evidence.get("fulltext_ref")
            if not isinstance(ref, str) or not REF_RE.fullmatch(ref):
                raise ValueError("청크 SHA-256 참조값 형식 오류")
            source = stage_root / "rfp_fulltext" / (ref + ".json")
            if stage_root.is_symlink() or source.parent.is_symlink() or source.is_symlink():
                raise ValueError("청크 심볼릭 링크 거부")
            snapshot_sha = digest(source)
            record = load_fulltext(stage_root, ref)
            if digest(source) != snapshot_sha:
                raise ValueError("검증 중 원문 청크 파일 교체 감지")
            content = "".join(part["text"] for part in record["chunks"])
            if (record["source_sha256"] != evidence.get("sha256")
                    or record["stored_chars"] != evidence.get("chars")
                    or not content.startswith(evidence.get("excerpt", ""))
                    or record["truncated_by_parser"] != evidence.get("fulltext_truncated")):
                raise ValueError("청크와 공식 파일 근거 불일치")
            if not any(isinstance(a, dict) and official_url(a.get("url"))
                and isinstance(a.get("name"), str)
                and hashlib.sha256((a["url"] + "\n" + a["name"]).encode()).hexdigest() == evidence.get("identity")
                for a in incoming.get("attachments", [])):
                raise ValueError("공식 첨부 identity 일치 실패")
            evidence_count += 1
            refs[ref] = snapshot_sha
        if len(accepted) > 2:
            raise ValueError("공고당 허용 문서 개수 초과")
        if current.get("department_categories") != incoming.get("department_categories"):
            related_classification += 1
        for field in PROMOTE_FIELDS:
            if field in incoming:
                candidate_map[ident][field] = copy.deepcopy(incoming[field])
    if evidence_count != 127 or len(refs) != 124:
        raise ValueError("이관 문서·사이드카 참조 수 불일치")
    candidate["revision"] = live["revision"] + 1
    new_ledger = copy.deepcopy(old_ledger)
    for ident in targets:
        current = new_ledger["items"][ident]
        if current.get("status") not in ("PENDING", "DONE"):
            raise ValueError("운영 작업 대상의 비정상 상태")
        current["status"] = "DONE"
    new_ledger["revision"] += 1
    new_ledger["updated_at"] = datetime.now(timezone.utc).isoformat()
    remaining = sum(new_ledger["items"].get(k, {}).get("status") == "PENDING"
                    for k in new_ledger["target_ids"])
    new_ledger["status"] = "PAUSED" if remaining else "COMPLETE"
    if candidate["history"] != live["history"]:
        raise ValueError("사람의 판단 이력 변경")
    for n in live["notices"]:
        c = candidate_map[n["id"]]
        if any(c.get(k) != n.get(k) for k in ("final", "finalReason", "rec", "reasons",
                                           "fit", "margin", "hard", "ops", "exp", "score")):
            raise ValueError("담당자의 판단 변경")
        if n["id"] not in targets and c != n:
            raise ValueError("이관 대상 외 공고 변경")
    return candidate, new_ledger, refs, {
        "notices": len(live["notices"]), "target_notices": len(targets),
        "documents": evidence_count, "sidecar_files": len(refs),
        "department_classifications_updated": related_classification,
        "previous_batch_done": sum(v.get("status") == "DONE" for v in old_ledger["items"].values()),
        "batch_done_after": sum(v.get("status") == "DONE" for v in new_ledger["items"].values()),
        "batch_pending_after": remaining}


def prepare_backup(live_root, backup_root, original_hash):
    """Resume only a verified, release-owned, never-published partial backup."""
    marker = backup_root / ".backup-intent.json"
    if backup_root.exists():
        reject_reparse(backup_root)
        allowed = {".backup-intent.json", "dashboard.json", "rfp_batch.json", "restore_metadata.json"}
        if any(x.name not in allowed for x in backup_root.iterdir()):
            raise ValueError("백업 경로에 알 수 없는 파일 존재")
        if marker.exists():
            intent = json.loads(safe_read(marker))
            if intent.get("original_files") != original_hash:
                raise ValueError("운영 내용이 변경되어 백업 재개 거부")
            if (backup_root / "restore_metadata.json").exists():
                raise FileExistsError("이미 준비된 백업 경로 재사용 금지")
        elif any(backup_root.iterdir()):
            raise FileExistsError("소유권 미확인 백업 경로 재사용 금지")
    else:
        backup_root.mkdir(mode=0o700, parents=True)
    write_atomic(marker, {"original_files": original_hash, "status":"PREPARING"})


def guard_no_incomplete_journal(root):
    """Fail closed if a previous two-file rollout was interrupted."""
    intent = read_intent(root)
    if intent and intent.get("status") == "PREPARED":
        raise ValueError("미완료 SQLite 배포 저널: 복구 필요")
    path = Path(root) / JOURNAL
    if path.exists():
        state = json.loads(path.read_text(encoding="utf-8"))
        if state.get("status") != "COMPLETED":
            raise ValueError("미완료 RFP 운영 배포 존재: 명시적 복구 필요")


def apply(live_root, stage_root, backup_root):
    live_root, stage_root, backup_root = map(reject_reparse, (live_root, stage_root, backup_root))
    with ExitStack() as pins, pin_directories(live_root, stage_root, backup_root.parent, stage_root/'rfp_fulltext'), exclusive_release_access(live_root, timeout=0), transaction(live_root):
        guard_no_incomplete_journal(live_root)
        candidate, ledger, refs, summary = plan(live_root, stage_root)
        originals = ("dashboard.json", "rfp_batch.json")
        original_hash = {name: digest(live_root/name) for name in originals}
        prepare_backup(live_root, backup_root, original_hash)
        pins.enter_context(pin_directories(backup_root))
        for name in originals:
            shutil.copy2(live_root / name, backup_root / name)
        if not all(digest(backup_root/name)==original_hash[name] for name in originals):
            raise ValueError("배포 백업 해시 확인 실패")
        expected_new = {
            "dashboard.json": hashlib.sha256(json.dumps(
                candidate, ensure_ascii=False, indent=2).encode("utf-8")).hexdigest(),
            "rfp_batch.json": hashlib.sha256(json.dumps(
                ledger, ensure_ascii=False, indent=2).encode("utf-8")).hexdigest()
        }
        restore_metadata = {"original_files": original_hash,
                            "release_dashboard_revision": candidate["revision"],
                            "release_ledger_revision": ledger["revision"],
                            "release_file_sha256": expected_new}
        write_atomic(backup_root / "restore_metadata.json", restore_metadata)
        added = 0
        directory = live_root / "rfp_fulltext"
        directory.mkdir(mode=0o700, exist_ok=True)
        pins.enter_context(pin_directories(directory))
        # Copy fully-verified content-addressed files before publishing any references.
        for ref in sorted(refs):
            src = stage_root / "rfp_fulltext" / (ref + ".json")
            target = directory / (ref + ".json")
            if src.is_symlink() or target.is_symlink() or src.parent.is_symlink() or target.parent.is_symlink():
                raise ValueError("청크 심볼릭 링크 거부")
            if target.exists():
                if refs[ref] != digest(target):
                    raise ValueError("운영 청크 캐시 충돌")
            else:
                temp = None
                try:
                    with tempfile.NamedTemporaryFile(dir=directory, prefix=".promote-",
                                                     suffix=".tmp", delete=False) as out:
                        temp = out.name
                        with open(src, "rb") as inp:
                            shutil.copyfileobj(inp, out)
                        out.flush()
                        os.fsync(out.fileno())
                    if digest(temp) != refs[ref] or digest(src) != refs[ref]:
                        raise ValueError("검증한 청크가 복사 중 변경됨")
                    durable_replace(temp, target)
                    added += 1
                finally:
                    if temp and os.path.exists(temp): os.unlink(temp)
            if digest(target) != refs[ref]:
                raise ValueError("운영 청크 복사 최종 검증 실패")
        journal = {"status": "PREPARED", "backup_path": str(backup_root),
                   "original_files": original_hash,
                   "expected_new_files": dict(expected_new)}
        save_intent(live_root, "PREPARED", journal)
        write_atomic(live_root / JOURNAL, journal)
        try:
            write_atomic(live_root / "dashboard.json", candidate)
            write_atomic(live_root / "rfp_batch.json", ledger)
            if not all(digest(live_root/name) == sha for name,sha in expected_new.items()):
                raise ValueError("배포 직후 두 JSON SHA-256 불일치")
        except BaseException:
            # Offline promotion can fail across the two JSON commits.
            # Restore both from the verified local snapshot. Keep sidecars intact.
            for name in originals:
                _copy_atomic(backup_root / name, live_root / name)
            journal["status"] = "COMPLETED"
            journal["resolution"] = "ROLLBACK_AFTER_EXCEPTION"
            write_atomic(live_root / JOURNAL, journal)
            save_intent(live_root, "COMPLETED", journal)
            raise
        journal["status"] = "COMPLETED"
        journal["resolution"] = "RELEASE_APPLIED"
        write_atomic(live_root / JOURNAL, journal)
        save_intent(live_root, "COMPLETED", journal)
        summary.update({"result": "APPLIED", "backup_present": True,
                        "new_sidecar_files": added,
                        "original_sha_preserved_in_backup": all(digest(backup_root/n)==original_hash[n] for n in originals)})
        return summary


def _copy_atomic(source, destination):
    destination = Path(destination)
    filename = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".restore-",
                                         suffix=".tmp", delete=False) as output:
            filename = output.name
            with open(source, "rb") as original:
                shutil.copyfileobj(original, output)
            output.flush()
            os.fsync(output.fileno())
        durable_replace(filename, destination)
    finally:
        if filename and os.path.exists(filename):
            os.unlink(filename)


def recover(live_root, backup_root):
    """Resolve an interrupted multi-file rollout before accepting any web requests."""
    live_root, backup_root = reject_reparse(live_root), reject_reparse(backup_root)
    with pin_directories(live_root, backup_root), exclusive_release_access(live_root, timeout=0), transaction(live_root):
        path = live_root / JOURNAL
        state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
        intent = read_intent(live_root)
        if intent and intent["status"] == "PREPARED":
            state = intent
        if state is None or state.get("status") in ("COMPLETED","VERIFIED"):
            return {"result": "NO_PENDING_RELEASE"}
        if (state.get("status") != "PREPARED"
                or state.get("backup_path") != str(backup_root)):
            raise ValueError("배포 저널 경로/상태 오류: 수동 조사")
        original = state.get("original_files", {})
        expected_new = state.get("expected_new_files", {})
        if set(original) != {"dashboard.json", "rfp_batch.json"} or set(expected_new) != set(original):
            raise ValueError("배포 저널 형식 오류")
        if any(not REF_RE.fullmatch(v) for v in list(original.values())+list(expected_new.values())):
            raise ValueError("배포 저널 해시 형식 오류")
        if any(digest(backup_root/name) != sha for name, sha in original.items()):
            raise ValueError("배포 복구용 백업 무결성 오류")
        # Both new files persisted: merely finalize the interruption marker.
        if all(digest(live_root/name) == sha for name, sha in expected_new.items()):
            result = "RECOVERED_COMMIT"
        else:
            # At least one new file is incomplete: restore BOTH old generations.
            for name in ("dashboard.json", "rfp_batch.json"):
                _copy_atomic(backup_root/name, live_root/name)
            if not all(digest(live_root/name) == sha for name,sha in original.items()):
                raise ValueError("저널 복구 재검증 실패")
            result = "RECOVERED_ROLLBACK"
        state["status"] = "COMPLETED"
        state["resolution"] = result
        write_atomic(path,state)
        save_intent(live_root, "COMPLETED", state)
        return {"result":result,"backup_verified":True}


def rollback(live_root, backup_root):
    live_root, backup_root = reject_reparse(live_root), reject_reparse(backup_root)
    meta = json.loads((backup_root / "restore_metadata.json").read_text(encoding="utf-8"))
    with pin_directories(live_root, backup_root), exclusive_release_access(live_root, timeout=0), transaction(live_root):
        guard_no_incomplete_journal(live_root)
        board = read_dashboard(live_root / "dashboard.json")
        ledger = json.loads((live_root / "rfp_batch.json").read_text(encoding="utf-8"))
        if (board["revision"] != meta["release_dashboard_revision"]
                or ledger["revision"] != meta["release_ledger_revision"]):
            raise ValueError("배포 후 다른 수정 발생: 자동 복원 거부")
        expected = meta.get("release_file_sha256")
        if (not isinstance(expected,dict)
                or set(expected) != {"dashboard.json", "rfp_batch.json"}
                or not all(isinstance(sha,str) and REF_RE.fullmatch(sha)
                           for sha in expected.values())
                or not all(digest(live_root/name) == sha for name,sha in expected.items())):
            raise ValueError("배포 후 JSON 실제 내용 변경: 자동 롤백 거부")
        for name, sha in meta["original_files"].items():
            if digest(backup_root/name) != sha:
                raise ValueError("백업 무결성 오류")
        # Manual rollback also crosses two atomic files: journal it before the first write.
        journal = {"status": "PREPARED", "operation": "ROLLBACK",
                   "backup_path": str(backup_root),
                   "original_files": dict(meta["original_files"]),
                   "expected_new_files": dict(meta["original_files"])}
        save_intent(live_root, "PREPARED", journal)
        write_atomic(live_root / JOURNAL, journal)
        for name in ("dashboard.json", "rfp_batch.json"):
            _copy_atomic(backup_root / name, live_root / name)
        if not all(digest(live_root/name)==sha
                   for name,sha in meta["original_files"].items()):
            raise ValueError("롤백 파일 무결성 오류: 저널 기반 복구 필요")
        journal["status"] = "COMPLETED"
        journal["resolution"] = "MANUAL_ROLLBACK"
        write_atomic(live_root / JOURNAL, journal)
        save_intent(live_root, "COMPLETED", journal)
        return {"result": "ROLLED_BACK", "backup_verified": True}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--live",required=True)
    parser.add_argument("--stage",required=True)
    parser.add_argument("--backup",default="")
    parser.add_argument("--apply",action="store_true")
    parser.add_argument("--rollback",action="store_true")
    parser.add_argument("--recover",action="store_true")
    args=parser.parse_args()
    if sum((args.apply,args.rollback,args.recover))>1:
        parser.error("apply/rollback/recover 중 하나만")
    if args.recover:
        if not args.backup:parser.error("--backup required")
        result=recover(args.live,args.backup)
    elif args.rollback:
        if not args.backup:parser.error("--backup required")
        result=rollback(args.live,args.backup)
    elif args.apply:
        if not args.backup: parser.error("--backup required with --apply")
        result=apply(args.live,args.stage,args.backup)
    else:
        *_,result=plan(args.live,args.stage)
        result["result"]="DRY_RUN"
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
