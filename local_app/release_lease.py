"""Localhost RFP release safety primitives.

Use a lifetime OS lease for the server and the offline promoter. The SQLite
intent is fsynced by SQLite before JSON files are replaced; an incomplete
intent blocks startup even if the text journal is lost in a crash.
"""
import hashlib
import json
import os
import sqlite3
import stat
from contextlib import contextmanager, closing
from pathlib import Path

from json_transaction import transaction

LEASE = ".rfp-server-lease.lock"
INTENT = ".rfp-release-intent.sqlite3"
NAMES = ("dashboard.json", "rfp_batch.json")


def reject_reparse(path):
    """Reject existing symlink/junction/reparse components, including parents."""
    path = Path(os.path.abspath(path))
    for item in (path, *path.parents):
        if not item.exists() and not item.is_symlink():
            continue
        meta = item.lstat()
        if (item.is_symlink() or os.path.isjunction(item)
                or getattr(meta, "st_file_attributes", 0)
                & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
            raise ValueError("RFP release path contains a link or reparse point")
    return path


def safe_read(path):
    """Verify identity and bytes against path replacement around open/read."""
    path = reject_reparse(path)
    before = path.lstat()
    with path.open("rb") as handle:
        opened = os.fstat(handle.fileno())
        if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
            raise ValueError("RFP file swapped before read")
        body = handle.read()
        after = path.lstat()
        if (after.st_dev, after.st_ino) != (opened.st_dev, opened.st_ino):
            raise ValueError("RFP file swapped while reading")
    return body


@contextmanager
def exclusive_release_access(root, timeout=0.0):
    """Server holds this lease for lifetime; an offline promoter must own it."""
    root = reject_reparse(root)
    with transaction(root, timeout=timeout, name=LEASE):
        yield


def _connect(root):
    root = reject_reparse(root)
    db = reject_reparse(root / INTENT)
    conn = sqlite3.connect(db, timeout=2)
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute("CREATE TABLE IF NOT EXISTS release_state (key INTEGER PRIMARY KEY CHECK(key=1), phase TEXT NOT NULL, payload TEXT NOT NULL)")
    return conn


def save_intent(root, phase, payload):
    if phase not in ("PREPARED", "COMPLETED", "VERIFIED"):
        raise ValueError("invalid release intent phase")
    with closing(_connect(root)) as db:
        with db:
            db.execute("INSERT INTO release_state(key,phase,payload) VALUES(1,?,?) ON CONFLICT(key) DO UPDATE SET phase=excluded.phase,payload=excluded.payload",
                       (phase, json.dumps(payload, sort_keys=True)))
    # SQLite FULL synchronous protects the transaction under documented VFS assumptions.


def read_intent(root):
    path = Path(root) / INTENT
    if not path.exists():
        return None
    db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=2)
    try:
        row = db.execute("SELECT phase,payload FROM release_state WHERE key=1").fetchone()
    finally:
        db.close()
    if not row:
        raise ValueError("empty release intent database")
    return {**json.loads(row[1]), "status": row[0]}


def _sha256(path):
    return hashlib.sha256(safe_read(path)).hexdigest()


def guard_ready(root):
    """Fail closed for a missing/corrupt generation or pending promotion."""
    root = Path(root)
    state = read_intent(root)
    if not state:
        return
    if state["status"] == "PREPARED":
        raise RuntimeError("incomplete SQLite release intent: recovery required")
    if state["status"] == "COMPLETED":
        expected = state.get("expected_new_files", {})
        if set(expected) != set(NAMES) or any(
                _sha256(root / name) != expected[name] for name in NAMES):
            raise RuntimeError("release generation hash mismatch: recovery required")
        save_intent(root, "VERIFIED", state)


def acquire_guard(root):
    """Guard the release intent on every request, including unsafe POSTs."""
    state = read_intent(root)
    if state and state["status"] == "PREPARED":
        raise RuntimeError("release recovery required")
