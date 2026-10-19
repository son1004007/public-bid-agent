"""BID-04 로컬 파일 조회 설계 계약.

목적/책임: 제한된 로컬 JSON을 읽어 집계만 stdout에 출력한다.
입력/출력: 데이터 디렉터리 → 고정 집계 또는 고정 오류 코드, 경로/원문 미출력.
신뢰 경계/권한: 링크/재분석 지점·크기/JSON 검증; 인증키·RFP 캐시 미접근.
상태 변경/부작용: 읽기만. 디렉터리/잠금/저널/캐시 생성·수정/다운로드 없음.
실패/타임아웃/재시도: 관측 변경 시 BLOCKED_SNAPSHOT, 입력 오류 BLOCKED_INPUT,
자동 재시도 없음. 0=집계 수행(증빙 보류 포함), 2=수행 실패. 원시 예외 미출력.
핵심 불변조건: 읽기 전후 identity/메타데이터/바이트 비교, SHA는 메모리에만 유지.
이는 관측 안정성 검사이며 다중 파일 transaction/공식 최신성 증명은 아니다.
관련 요구사항/테스트/설계: D-20/BID-04, test_bid_now_audit.py,
docs/design/BID04_LOCAL_AGGREGATE_2026-10-19.md.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import stat
import sys
from datetime import datetime

from bid_now_audit import evaluate
from release_lease import reject_reparse

MIB = 1024 * 1024
LIMITS = {"dashboard.json": 128 * MIB, "department_profile.json": MIB,
          "operations.json": MIB, "workforce.json": MIB, "rfp_batch.json": 32 * MIB,
          ".rfp-release-transaction.json": MIB, ".rfp-release-intent.sqlite3": 2 * MIB}
SIDECARS = (".rfp-release-intent.sqlite3-journal", ".rfp-release-intent.sqlite3-wal",
            ".rfp-release-intent.sqlite3-shm")
JOURNAL = ".rfp-release-transaction.json"
INTENT = ".rfp-release-intent.sqlite3"


class AuditBlocked(Exception):
    """외부로 출력 가능한 고정 코드만 보유한다."""


def _json(body):
    def pairs(items):
        obj = {}
        for key, value in items:
            if key in obj:
                raise ValueError("DUPLICATE_JSON_KEY")
            obj[key] = value
        return obj

    def invalid_constant(_):
        raise ValueError("NON_FINITE_JSON")

    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("NON_FINITE_JSON")
        return number

    return json.loads(body.decode("utf-8-sig"), object_pairs_hook=pairs,
                      parse_constant=invalid_constant, parse_float=finite_float)


def _capture(root):
    """고정 파일만 제한 읽기. 파일명/메타데이터/바이트는 반환 보고에 포함하지 않는다."""
    reject_reparse(root)
    if not root.is_dir():
        raise AuditBlocked("BLOCKED_INPUT")
    snapshot = {}
    for name in (*LIMITS, *SIDECARS):
        path = reject_reparse(root / name)
        try:
            before = path.lstat()
        except FileNotFoundError:
            snapshot[name] = None
            continue
        if name in SIDECARS:
            raise AuditBlocked("BLOCKED_SNAPSHOT")
        if not stat.S_ISREG(before.st_mode) or before.st_size > LIMITS[name]:
            raise AuditBlocked("BLOCKED_INPUT")
        with path.open("rb") as handle:
            opened = os.fstat(handle.fileno())
            body = handle.read(LIMITS[name] + 1)
            after_open = os.fstat(handle.fileno())
        reject_reparse(path)
        after = path.lstat()

        def signature(meta):
            # CPython 3.12 Windows lstat/fstat ctime semantics can differ;
            # birthtime is the explicit creation-time field. Never use atime.
            change = meta.st_birthtime_ns if os.name == "nt" else meta.st_ctime_ns
            return (meta.st_dev, meta.st_ino, meta.st_size, meta.st_mtime_ns, change)

        if (len(body) > LIMITS[name] or len(body) != before.st_size
                or not signature(before) == signature(opened) == signature(after_open) == signature(after)):
            raise AuditBlocked("BLOCKED_SNAPSHOT")
        snapshot[name] = (signature(after), body)
    return snapshot


def _release(snapshot):
    """기존 복구 게이트의 읽기 전용 부분만 검사. SQLite는 메모리에서만 연다."""
    def body(name):
        record = snapshot[name]
        return record[1] if record is not None else None

    journal = _json(body(JOURNAL)) if body(JOURNAL) is not None else None
    if body(JOURNAL) is not None and (not isinstance(journal, dict) or journal.get("status") != "COMPLETED"):
        raise AuditBlocked("BLOCKED_SNAPSHOT")
    intent = None
    if body(INTENT) is not None:
        if not hasattr(sqlite3.Connection, "deserialize"):
            raise AuditBlocked("BLOCKED_INPUT")
        db = sqlite3.connect(":memory:")
        try:
            db.deserialize(body(INTENT))
            db.execute("PRAGMA query_only=ON")
            db.execute("PRAGMA trusted_schema=OFF")
            db.set_progress_handler(lambda: 1, 10000)
            schema = db.execute("SELECT type FROM sqlite_master WHERE name='release_state'").fetchall()
            if schema != [("table",)]:
                raise AuditBlocked("BLOCKED_SNAPSHOT")
            rows = db.execute("SELECT key,phase,payload FROM release_state LIMIT 2").fetchall()
            if (len(rows) != 1 or rows[0][0] != 1 or rows[0][1] not in ("COMPLETED", "VERIFIED")
                    or not isinstance(rows[0][2], str)):
                raise AuditBlocked("BLOCKED_SNAPSHOT")
            intent = _json(rows[0][2].encode("utf-8"))
            if not isinstance(intent, dict):
                raise AuditBlocked("BLOCKED_SNAPSHOT")
            intent = {**intent, "status": rows[0][1]}
        finally:
            db.close()
    # COMPLETED is an unverified generation. VERIFIED is intentionally not
    # compared to the old release hashes after ordinary collection updates.
    candidates = [intent] if intent and intent["status"] == "COMPLETED" else []
    for state in candidates:
        expected = state.get("expected_new_files")
        if not isinstance(expected, dict) or set(expected) != {"dashboard.json", "rfp_batch.json"}:
            raise AuditBlocked("BLOCKED_SNAPSHOT")
        for name, digest in expected.items():
            if (not isinstance(digest, str) or len(digest) != 64 or body(name) is None
                    or hashlib.sha256(body(name)).hexdigest() != digest):
                raise AuditBlocked("BLOCKED_SNAPSHOT")
    if journal and intent and intent["status"] == "COMPLETED":
        if journal.get("expected_new_files") != intent.get("expected_new_files"):
            raise AuditBlocked("BLOCKED_SNAPSHOT")
    if intent:
        return ("SQLITE_COMPLETED_HASHES_MATCH" if intent["status"] == "COMPLETED"
                else "SQLITE_VERIFIED_RECORD")
    # Legacy normal collection changes dashboard without refreshing the old
    # completed journal hashes. That journal cannot prove current generation integrity.
    return "LEGACY_COMPLETED_UNVERIFIED" if journal else "NO_RELEASE_METADATA"


def audit_local(root: Path, *, at: datetime | None = None) -> dict:
    """운영 파일에 쓰기 없이 전후 안정성을 확인한 집계만 반환한다."""
    try:
        root = Path(root).expanduser().absolute()
        before = _capture(root)
        try:
            release_state = _release(before)
        except AuditBlocked:
            raise
        except (ValueError, sqlite3.Error, UnicodeError, TypeError, RecursionError):
            raise AuditBlocked("BLOCKED_SNAPSHOT") from None
        board_entry = before["dashboard.json"]
        if board_entry is None:
            raise AuditBlocked("BLOCKED_INPUT")
        board = _json(board_entry[1])
        if (not isinstance(board, dict) or type(board.get("schema_version")) is not int
                or board["schema_version"] != 1 or type(board.get("revision")) is not int
                or board["revision"] < 0):
            raise AuditBlocked("BLOCKED_INPUT")

        def optional(name):
            entry = before[name]
            if entry is None:
                return None
            try:
                return _json(entry[1])
            except (ValueError, UnicodeError, TypeError, RecursionError):
                return None

        report = evaluate(board.get("notices"), optional("department_profile.json"),
                          optional("operations.json"), optional("workforce.json"), at=at)
        if _capture(root) != before:
            raise AuditBlocked("BLOCKED_SNAPSHOT")
        return {**report, "snapshot_check": "STABLE_OBSERVED_READS",
                "release_metadata_state": release_state,
                "source_files_written": False}
    except AuditBlocked:
        raise
    except (OSError, ValueError, TypeError, OverflowError, RecursionError, sqlite3.Error):
        raise AuditBlocked("BLOCKED_INPUT") from None


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        # argparse normally echoes unrecognized args, which may contain data.
        raise AuditBlocked("BLOCKED_INPUT")


def main(argv: list[str] | None = None) -> int:
    try:
        parser = _Parser(description="BID-04 read-only aggregate; no source data output")
        parser.add_argument("--data-dir", type=Path, default=Path(os.environ.get(
            "PUBLIC_BID_LOCAL_DATA", str(Path.home() / ".public-bid-agent-local"))))
        args = parser.parse_args(argv)
        report = audit_local(args.data_dir)
    except AuditBlocked as exc:
        print(json.dumps({"status": str(exc), "aggregate_available": False,
                          "source_files_written": False}))
        return 2
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
