"""A16: 운영 스테이징 복구 리허설 및 무결성 검증 도구.

목적: 백업 번들(DB 덤프 + 스토리지)로부터 격리된 임시 데이터베이스에 복원을 수행하고,
      테이블 건수 일치, 외래키 무결성, 산출물 SHA-256 해시, 복구 후 새 쓰기(A16)를 검증한 후
      임시 DB를 안전하게 정리한다.
관련: docs/server-migration/06-migration-and-acceptance.md, 20-acceptance-and-open-decisions.md (A16).
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import tempfile
import shutil
import stat
from datetime import datetime, timezone
from pathlib import Path
import psycopg
from psycopg import sql

REHEARSAL_DB_PATTERN = re.compile(r"^sm03_(?:test_)?[a-z0-9_]*rehearsal(?:_[a-z0-9]+)?$")

def validate_rehearsal_target(name: str, config: dict) -> None:
    if not REHEARSAL_DB_PATTERN.fullmatch(name):
        raise ValueError("Restore target is outside reserved sm03_*rehearsal namespace")
    if name.lower() in {"postgres","template0","template1",str(config.get("NAME","")).lower()}:
        raise ValueError("Restore target must never equal the source or system DB")
    if str(config.get("HOST","")).strip().lower() not in {"127.0.0.1","localhost","::1"}:
        raise ValueError("Restore rehearsals are restricted to a local PostgreSQL cluster")



def get_pg_bin_path() -> Path:
    local_app = os.environ.get("LOCALAPPDATA", "")
    pg_bin = Path(local_app) / "PublicBidAgent" / "sm03-postgres" / "pgsql" / "bin"
    if pg_bin.exists():
        return pg_bin
    return Path("")


def load_db_config(config_path: Path | None = None) -> dict:
    """Require explicit private local database configuration, never a fallback."""
    if config_path is None:
        raise ValueError("Explicit private database configuration required")
    # Reuse the application configuration contract without importing settings.
    server = str(Path(__file__).resolve().parents[1] / "server")
    if server not in sys.path:
        sys.path.insert(0, server)
    from bid_server.config import load_local_database
    return load_local_database(config_path)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def run_rehearsal(
    bundle_dir: Path,
    rehearsal_db_name: str = "sm03_restore_rehearsal",
    config_path: Path | None = None,
    keep_db: bool = False,
    *, trusted_dump_sha256: str | None = None,
) -> dict:
    # Fail closed before touching any PostgreSQL database.
    t_start = time.perf_counter()
    manifest_file = bundle_dir / "manifest.json"
    if not manifest_file.exists():
        raise FileNotFoundError(f"Manifest not found in {bundle_dir}")

    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    backup_id = manifest.get("backup_id", "unknown")
    db_meta = manifest["database"]
    storage_meta = manifest.get("storage", {})

    # Fail closed before creating any database: an empty/partial manifest would
    # otherwise make all([]) report success and silently skip missing tables.
    required_tables = {
        "accounts_user", "procurement_notice", "procurement_noticeversion",
        "procurement_document", "procurement_documentversion",
        "procurement_proposal", "procurement_proposalrevision",
        "procurement_proposalsection", "jobs_job", "jobs_jobattempt",
    }
    table_counts = db_meta.get("table_counts")
    if (not isinstance(table_counts, dict)
            or set(table_counts) != required_tables
            or any(type(count) is not int or count < 0 for count in table_counts.values())):
        raise ValueError("Backup manifest table_counts must cover all required tables with nonnegative integer counts")

    print(f"[*] Starting Restore Rehearsal for Backup: {backup_id}")
    print(f"[*] Rehearsal Target Database: {rehearsal_db_name}")

    # 1. Verify Manifest and Dump Integrity
    # A manifest is untrusted input: never follow absolute paths or ../ outside this bundle.
    bundle_root = bundle_dir.resolve(strict=True)
    def bundle_member(root: Path, relative: str) -> Path:
        if not isinstance(relative, str) or not relative or "\\x00" in relative:
            raise ValueError("Invalid bundle member path")
        candidate = (root / relative).resolve()
        if not candidate.is_relative_to(root):
            raise ValueError("Bundle member escapes backup directory")
        return candidate

    dump_file = bundle_member(bundle_root, db_meta["dump_file"])
    if not dump_file.exists():
        raise FileNotFoundError(f"Dump file {dump_file} not found.")

    actual_dump_sha256 = sha256_file(dump_file)
    if actual_dump_sha256 != db_meta["dump_sha256"]:
        raise ValueError(
            f"Dump SHA-256 mismatch! Expected {db_meta['dump_sha256']}, got {actual_dump_sha256}"
        )
    print(f"[+] Dump SHA-256 verified: {actual_dump_sha256[:16]}...")

    # Verify Storage Artifacts
    storage_verification_errors = []
    # Resolve storage relative to the verified bundle root, not as an independent trust root.
    # A symlinked storage directory must never redirect verification outside the bundle.
    bundle_storage_dir = bundle_member(bundle_root, "storage")
    for item in storage_meta.get("files", []):
        file_path = bundle_member(bundle_storage_dir, item["relative_path"])
        if not file_path.is_relative_to(bundle_storage_dir):
            raise ValueError("Storage member escapes storage directory")
        if not file_path.exists():
            storage_verification_errors.append(f"Missing file: {item['relative_path']}")
            continue
        h = sha256_file(file_path)
        if h != item["sha256"]:
            storage_verification_errors.append(f"Hash mismatch on {item['relative_path']}")

    if storage_verification_errors:
        raise ValueError(f"Storage verification errors: {storage_verification_errors}")
    print(f"[+] Storage artifacts verified ({len(storage_meta.get('files', []))} files).")

    # A checksum from the bundle itself is not a trust decision. Only run
    # a dump whose provenance was independently approved by the operator.
    if (not isinstance(trusted_dump_sha256, str)
            or not re.fullmatch(r"[0-9a-f]{64}", trusted_dump_sha256)
            or trusted_dump_sha256 != actual_dump_sha256):
        raise ValueError("Trusted dump SHA-256 required from an independent record")

    # A coordinated bundle must enumerate every regular member and prove
    # that a fresh, separate recovery directory can actually receive the bytes.
    storage_recovery = "NOT_INCLUDED"
    if manifest.get("coverage") == "DB_AND_STORAGE":
        entries = storage_meta.get("files")
        if (not isinstance(entries, list) or storage_meta.get("files_count") != len(entries)
                or not bundle_storage_dir.is_dir() or (bundle_root / "storage").is_symlink()):
            raise ValueError("Storage inventory incomplete")
        expected = {}
        for row in entries:
            name = row["relative_path"]
            member = Path(name)
            if (member.is_absolute() or "\\" in name or ".." in member.parts
                    or member.as_posix() != name or name.casefold() in expected
                    or type(row.get("size_bytes")) is not int or row["size_bytes"] < 0
                    or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"])):
                raise ValueError("Invalid storage inventory")
            expected[name.casefold()] = row
        observed = set()
        for directory, dirs, files in os.walk(bundle_storage_dir, followlinks=False):
            for name in dirs + files:
                path = Path(directory) / name
                meta = path.lstat()
                if (stat.S_ISLNK(meta.st_mode) or getattr(meta, "st_file_attributes", 0) & 1024
                        or not (stat.S_ISREG(meta.st_mode) or stat.S_ISDIR(meta.st_mode))):
                    raise ValueError("Unsafe storage entry")
                if stat.S_ISREG(meta.st_mode):
                    rel = path.relative_to(bundle_storage_dir).as_posix()
                    row = expected.get(rel.casefold())
                    if (row is None or row["relative_path"] != rel or rel.casefold() in observed
                            or meta.st_size != row["size_bytes"]):
                        raise ValueError("Storage inventory mismatch")
                    observed.add(rel.casefold())
        if observed != set(expected):
            raise ValueError("Storage inventory mismatch")
        # This is a copy rehearsal, not restoration to a service's live media root.
        # The bundle parent must be provisioned and protected by the operator.
        with tempfile.TemporaryDirectory(prefix="storage-rehearsal-", dir=bundle_root) as temp:
            destination = Path(temp)
            for row in entries:
                source = bundle_storage_dir / row["relative_path"]
                target = destination / row["relative_path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.open("rb") as src, target.open("xb") as dst:
                    shutil.copyfileobj(src, dst, length=65536)
                if target.stat().st_size != row["size_bytes"] or sha256_file(target) != row["sha256"]:
                    raise ValueError("Restored storage integrity mismatch")
        storage_recovery = "PASS"

    # 2. Re-create Clean Target Rehearsal DB
    cfg = load_db_config(config_path)
    validate_rehearsal_target(rehearsal_db_name, cfg)
    pg_bin = get_pg_bin_path()
    psql = str(pg_bin / "psql.exe") if pg_bin.name else "psql"

    maint_conn = psycopg.connect(
        host=cfg["HOST"],
        port=cfg["PORT"],
        dbname="postgres",
        user=cfg["USER"],
        password=cfg["PASSWORD"], connect_timeout=5, sslmode="disable",
        autocommit=True,
    )
    try:
        with maint_conn.cursor() as cur:
            # Never drop a pre-existing database, even within the rehearsal namespace.
            # A collision is an explicit stop; only a freshly created target is ours.
            print(f"[*] Creating new rehearsal database {rehearsal_db_name}...")
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(rehearsal_db_name)))
    finally:
        maint_conn.close()

    # Only a newly created rehearsal DB is eligible for cleanup. A restore failure
    # must not bypass cleanup or leave a partial database available for reuse.
    try:
        # 3. Restore Dump via psql
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith("PG")}
        env["PGCONNECT_TIMEOUT"] = "5"
        env["PGPASSWORD"] = cfg["PASSWORD"]
    
        restore_cmd = [
            psql,
            "-X",
            "-h", str(cfg["HOST"]),
            "-p", str(cfg["PORT"]),
            "-U", str(cfg["USER"]),
            "-d", rehearsal_db_name,
            "-f", str(dump_file),
            "-v", "ON_ERROR_STOP=1",
        ]
    
        print(f"[*] Restoring database dump into {rehearsal_db_name}...")
        t_restore_start = time.perf_counter()
        res = subprocess.run(restore_cmd, env=env, capture_output=True, text=True, timeout=300)
        rto_seconds = round(time.perf_counter() - t_restore_start, 3)
    
        if res.returncode != 0:
            raise RuntimeError(f"psql restore failed (code {res.returncode})")
        print(f"[+] Database restore completed in {rto_seconds}s (RTO).")
    
        # 4. Parity & Integrity Verification
        restored_conn = psycopg.connect(
            host=cfg["HOST"],
            port=cfg["PORT"],
            dbname=rehearsal_db_name,
            user=cfg["USER"],
            password=cfg["PASSWORD"], connect_timeout=5, sslmode="disable",
        )
    
        table_parities = {}
        fk_errors = []
        new_write_ok = False
    
        try:
            with restored_conn.cursor() as cur:
                # A. Row count parity
                for tbl, expected_count in db_meta["table_counts"].items():
                    try:
                        # Table identifiers come from a backup manifest and must never be SQL interpolated.
                        if not isinstance(tbl, str) or not re.fullmatch(r"[a-z_][a-z0-9_]*", tbl):
                            raise ValueError("Invalid table name in backup manifest")
                        cur.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(tbl)))
                        actual_count = cur.fetchone()[0]
                        matched = (actual_count == expected_count)
                        table_parities[tbl] = {
                            "manifest_count": expected_count,
                            "restored_count": actual_count,
                            "matched": matched,
                        }
                        if not matched:
                            print(f"[!] Parity mismatch on {tbl}: expected {expected_count}, got {actual_count}")
                    except Exception as e:
                        table_parities[tbl] = {
                            "manifest_count": expected_count,
                            "restored_count": -1,
                            "matched": False,
                            "error": str(e),
                        }
    
                # B. Foreign Key Integrity Checks
                fk_queries = [
                    (
                        "procurement_noticeversion_orphans",
                        "SELECT count(*) FROM procurement_noticeversion nv WHERE NOT EXISTS (SELECT 1 FROM procurement_notice n WHERE n.id = nv.notice_id)",
                    ),
                    (
                        "procurement_documentversion_orphans",
                        "SELECT count(*) FROM procurement_documentversion dv WHERE NOT EXISTS (SELECT 1 FROM procurement_document d WHERE d.id = dv.document_id)",
                    ),
                    (
                        "procurement_proposalsection_orphans",
                        "SELECT count(*) FROM procurement_proposalsection ps WHERE NOT EXISTS (SELECT 1 FROM procurement_proposalrevision pr WHERE pr.id = ps.proposal_revision_id)",
                    ),
                    (
                        "jobs_jobattempt_orphans",
                        "SELECT count(*) FROM jobs_jobattempt ja WHERE NOT EXISTS (SELECT 1 FROM jobs_job j WHERE j.id = ja.job_id)",
                    ),
                ]
                for check_name, q in fk_queries:
                    cur.execute(q)
                    orphan_cnt = cur.fetchone()[0]
                    if orphan_cnt > 0:
                        fk_errors.append(f"{check_name}: {orphan_cnt} orphaned rows detected")
    
                # C. Post-Restore New Write Test (A16: "전환 후 새 쓰기와 rollback")
                import uuid
                test_notice_id = str(uuid.uuid4())
                test_version_id = str(uuid.uuid4())
                test_notice_num = f"REHEARSAL-{int(time.time())}"
    
                # Insert new test notice & version
                cur.execute(
                    "INSERT INTO procurement_notice (id, source, notice_number, created_at, updated_at) VALUES (%s, %s, %s, NOW(), NOW())",
                    (test_notice_id, "REHEARSAL_TEST", test_notice_num),
                )
                cur.execute(
                    """INSERT INTO procurement_noticeversion
                       (id, notice_id, version_seq, source_revision, observed_at, title, buyer,
                        source_url, deadline_raw, deadline_status, cancellation, correction,
                        source_payload_digest, created_at, budget_amount, department_categories, extra_data)
                       VALUES (%s, %s, 1, '1', NOW(), '리허설 검증 공고', '조달청',
                               'https://test.kr', '2026-12-31', 'VALID', false, false,
                               'digest', NOW(), 100000000, '[\"AI\"]'::jsonb, '{}'::jsonb)""",
                    (test_version_id, test_notice_id),
                )
                # Update current_version FK
                cur.execute(
                    "UPDATE procurement_notice SET current_version_id = %s WHERE id = %s",
                    (test_version_id, test_notice_id),
                )
                # Verify the new write in the same transaction, then roll back all synthetic rows.
                # Never commit rehearsal fixtures: exceptions must not leave test notices behind.
                cur.execute("SELECT notice_number, current_version_id FROM procurement_notice WHERE id = %s", (test_notice_id,))
                row = cur.fetchone()
                if row and row[0] == test_notice_num and str(row[1]) == test_version_id:
                    new_write_ok = True
                    print("[+] Post-restore new write test: SUCCESS (transactional readback).")
                else:
                    raise RuntimeError("Post-restore synthetic write readback failed")
                restored_conn.rollback()
        finally:
            restored_conn.close()
    finally:
        if not keep_db:
            clean_conn = psycopg.connect(
                host=cfg["HOST"],
                port=cfg["PORT"],
                dbname="postgres",
                user=cfg["USER"],
                password=cfg["PASSWORD"], connect_timeout=5, sslmode="disable",
                autocommit=True,
            )
            try:
                with clean_conn.cursor() as cur:
                    print(f"[*] Cleaning up temporary database {rehearsal_db_name}...")
                    cur.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(rehearsal_db_name)))
            finally:
                clean_conn.close()

    total_duration = round(time.perf_counter() - t_start, 3)

    # Parity success criteria: all tables matched
    parity_all_matched = all(p["matched"] for p in table_parities.values())
    rehearsal_success = parity_all_matched and (len(fk_errors) == 0) and new_write_ok

    report = {
        "rehearsal_id": f"rehearsal_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        "backup_id": backup_id,
        "status": "SUCCESS" if rehearsal_success else "FAILED",
        "rto_seconds": rto_seconds,
        "total_duration_seconds": total_duration,
        "rpo_status": "DB_COUNT_PARITY_ONLY" if parity_all_matched else "DB_COUNT_MISMATCH",
        "storage_scope": manifest.get("coverage", "LEGACY_UNVERIFIED"),
        "storage_recovery_verification": storage_recovery,
        "table_parities": table_parities,
        "fk_integrity_errors": fk_errors,
        "storage_integrity_errors": storage_verification_errors,
        "new_write_verification": "PASS" if new_write_ok else "FAIL",
        "tested_at": datetime.now(timezone.utc).isoformat(),
    }

    report_path = bundle_dir / "rehearsal_report.json"
    with report_path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False)

    print(f"\n==========================================")
    print(f" Restore Rehearsal Summary: {report['status']}")
    print(f" RTO (Recovery Time): {rto_seconds} seconds")
    print(f" RPO (Data Loss):     {report['rpo_status']}")
    print(f" Table Parity:        {'ALL PASSED' if parity_all_matched else 'FAILED'}")
    print(f" FK Integrity:        {'0 ORPHANS' if not fk_errors else 'ERRORS'}")
    print(f" New Write & Rollback: {report['new_write_verification']}")
    print(f" Report saved:        {report_path}")
    print(f"==========================================\n")

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A16 Automated Restore Rehearsal Tool")
    parser.add_argument("bundle_dir", help="Path to backup bundle directory")
    parser.add_argument("--rehearsal-db", default="sm03_restore_rehearsal", help="Rehearsal database name")
    parser.add_argument("--config", required=True, help="Explicit isolated private connection configuration")
    parser.add_argument("--trusted-dump-sha256", required=True, help="SHA-256 from independently approved private backup record")
    parser.add_argument("--keep-db", action="store_true", help="Keep rehearsal DB without dropping")
    args = parser.parse_args()

    b_dir = Path(args.bundle_dir)
    cfg_p = Path(args.config) if args.config else None

    report = run_rehearsal(
        bundle_dir=b_dir,
        rehearsal_db_name=args.rehearsal_db,
        config_path=cfg_p,
        keep_db=args.keep_db,
        trusted_dump_sha256=args.trusted_dump_sha256,
    )
    # A parity/FK/write failure returns a FAILED report without raising. Propagate
    # it as a nonzero process exit so CI and automation cannot mark it successful.
    if report["status"] != "SUCCESS":
        sys.exit(1)
