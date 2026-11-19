"""A16: 운영 스테이징 이관 및 DB + 파일 통합 백업 서비스.

목적: PostgreSQL DB 덤프와 비공개 산출물/스토리지 파일을 단일 세대 manifest.json으로 묶어
      원자적 백업 번들을 생성한다.
관련: docs/server-migration/06-migration-and-acceptance.md, 20-acceptance-and-open-decisions.md (A16).
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
import stat
import shutil
from datetime import datetime, timezone
from pathlib import Path


def get_pg_bin_path() -> Path:
    local_app = os.environ.get("LOCALAPPDATA", "")
    pg_bin = Path(local_app) / "PublicBidAgent" / "sm03-postgres" / "pgsql" / "bin"
    if pg_bin.exists():
        return pg_bin
    # Fallback to PATH
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


# Version 1 remains inspectable for legacy rehearsals but is not an MVP release baseline.
LEGACY_TABLES = (
    "accounts_user", "procurement_notice", "procurement_noticeversion",
    "procurement_document", "procurement_documentversion", "procurement_proposal",
    "procurement_proposalrevision", "procurement_proposalsection", "jobs_job", "jobs_jobattempt",
)
MVP_FINGERPRINT_TABLES = (
    "procurement_costdepartment", "procurement_costmembership",
    "procurement_departmentcostbasis", "procurement_sharedbidreviewevent",
)
MVP_TABLES = LEGACY_TABLES + MVP_FINGERPRINT_TABLES + (
    "procurement_extractionrun", "procurement_documentstructure", "procurement_documentblock",
    "procurement_tableblock", "procurement_tablecell", "procurement_footnoteblock",
    "procurement_chunk", "procurement_legacyidentity", "procurement_requirementmapping",
    "procurement_evidencereference", "procurement_exportartifact",
    "jobs_outbox", "jobs_automationpolicy", "jobs_automationpolicyversion",
    "accounts_authevent", "accounts_loginbucket", "django_session",
)


def get_mvp_fingerprints(conn):
    """Hash ordered JSONB rows, not user data in logs. Same PostgreSQL cluster/format."""
    from psycopg import sql
    result = {}
    with conn.cursor() as cur:
        cur.execute("SET LOCAL TIME ZONE 'UTC'")
        for table in MVP_FINGERPRINT_TABLES:
            digest = hashlib.sha256()
            cur.execute(sql.SQL("SELECT to_jsonb(t)::text FROM {} AS t ORDER BY id").format(sql.Identifier(table)))
            while rows := cur.fetchmany(1000):
                for (row,) in rows:
                    digest.update(row.encode("utf-8"))
                    digest.update(b"\n")
            result[table] = digest.hexdigest()
    return result


def get_table_counts(conn) -> dict:
    """Count selected domain/session tables in the same exported snapshot as pg_dump."""
    tables = MVP_TABLES
    counts = {}
    with conn.cursor() as cur:
        for tbl in tables:
            try:
                cur.execute(f"SELECT count(*) FROM {tbl}")
                counts[tbl] = cur.fetchone()[0]
            except Exception:
                raise RuntimeError(f"Cannot read source table {tbl}") from None
    return counts


def create_backup(
    output_dir: Path,
    config_path: Path | None = None,
    storage_dir: Path | None = None,
) -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    # Explicit storage selection must not diverge from the local service contract.
    selected = os.environ.get("BID_LOCAL_PRIVATE_MEDIA_ROOT")
    if selected is not None:
        if not selected or storage_dir is None or storage_dir != Path(selected):
            raise ValueError("Backup must explicitly include the selected private media root")
    output_dir = output_dir.resolve()
    if output_dir.is_relative_to(repo_root) or repo_root.is_relative_to(output_dir):
        raise ValueError("Backup output must be outside the Git working tree")
    if storage_dir is not None:
        if storage_dir.is_symlink():
            raise ValueError("Storage root must not be a symbolic link")
        storage_dir = storage_dir.resolve(strict=True)
        if (not storage_dir.is_dir() or storage_dir.is_relative_to(repo_root)
                or repo_root.is_relative_to(storage_dir) or output_dir.is_relative_to(storage_dir)
                or storage_dir.is_relative_to(output_dir)):
            raise ValueError("Invalid or overlapping backup storage root")
        # Preflight before opening PostgreSQL: never traverse file or directory links.
        for directory, dirs, files in os.walk(storage_dir, followlinks=False):
            for name in dirs + files:
                entry = Path(directory) / name
                if (entry.is_symlink() or getattr(entry.lstat(), "st_file_attributes", 0) & 1024
                        or not entry.resolve().is_relative_to(storage_dir)):
                    raise ValueError("Storage contains an unsafe link")
                if not (entry.is_dir() or entry.is_file()):
                    raise ValueError("Storage contains a nonregular entry")
    cfg = load_db_config(config_path)
    pg_bin = get_pg_bin_path()
    pg_dump = str(pg_bin / "pg_dump.exe") if pg_bin.name else "pg_dump"

    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_id = f"backup_{timestamp_str}_{uuid.uuid4().hex}"
    bundle_dir = output_dir / backup_id
    bundle_dir.mkdir(mode=0o700, parents=True, exist_ok=False)

    print(f"[*] Starting backup generation for bundle: {backup_id}")


    # Export one REPEATABLE READ snapshot and keep the exporting transaction
    # open until pg_dump exits. This ensures row counts and dump share one MVCC view.
    import psycopg
    dump_file = bundle_dir / "db_dump.sql"
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("PG")}
    env["PGCONNECT_TIMEOUT"] = "5"
    env["PGPASSWORD"] = cfg["PASSWORD"]
    conn = psycopg.connect(
        host=cfg["HOST"], port=cfg["PORT"], dbname=cfg["NAME"],
        user=cfg["USER"], password=cfg["PASSWORD"], connect_timeout=5, sslmode="disable",
    )
    try:
        with conn.cursor() as cur:
            cur.execute("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            cur.execute("SELECT pg_export_snapshot()")
            snapshot_id = cur.fetchone()[0]
        print("[*] Counting source rows in exported snapshot...")
        table_counts = get_table_counts(conn)
        mvp_fingerprints = get_mvp_fingerprints(conn)
        dump_cmd = [
            pg_dump,
            "-h", str(cfg["HOST"]),
            "-p", str(cfg["PORT"]),
            "-U", str(cfg["USER"]),
            "-d", str(cfg["NAME"]),
            "--snapshot", snapshot_id,
            "--clean", "--if-exists", "--no-owner", "--no-acl",
            "-f", str(dump_file),
        ]
        t0 = time.perf_counter()
        res = subprocess.run(dump_cmd, env=env, capture_output=True, text=True, timeout=300)
        if res.returncode != 0:
            raise RuntimeError(f"pg_dump failed (code {res.returncode})")
        dump_duration = time.perf_counter() - t0
    finally:
        conn.rollback()
        conn.close()

    dump_sha256 = sha256_file(dump_file)
    dump_size = dump_file.stat().st_size
    print(f"[+] DB dump created in {dump_duration:.2f}s: {dump_size} bytes, SHA-256={dump_sha256[:16]}...")

    # 3. Storage / Artifacts backup
    storage_files_meta = []
    bundle_storage_dir = bundle_dir / "storage"
    bundle_storage_dir.mkdir(exist_ok=True)

    if storage_dir and storage_dir.exists():
        for root, dirs, files in os.walk(storage_dir, followlinks=False):
            if any((Path(root) / name).is_symlink() for name in dirs):
                raise ValueError("Storage contains an unsafe link")
            for file in files:
                src_path = Path(root) / file
                rel_path = src_path.relative_to(storage_dir)
                dest_path = bundle_storage_dir / rel_path
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                if src_path.is_symlink() or not src_path.resolve(strict=True).is_relative_to(storage_dir):
                    raise ValueError("Storage contains an unsafe link")
                before = src_path.stat()
                if not stat.S_ISREG(before.st_mode):
                    raise ValueError("Storage contains a nonregular file")
                with src_path.open("rb") as source, dest_path.open("xb") as dest:
                    shutil.copyfileobj(source, dest, length=65536)
                after = src_path.stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise ValueError("Storage changed during backup; retry when quiesced")

                h = sha256_file(dest_path)
                storage_files_meta.append({
                    "relative_path": str(rel_path).replace("\\", "/"),
                    "sha256": h,
                    "size_bytes": dest_path.stat().st_size,
                })

    # 4. Manifest generation
    manifest_data = {
        "manifest_version": "2.0",
        "backup_id": backup_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "database": {
            "name": cfg["NAME"],
            "host": cfg["HOST"],
            "port": cfg["PORT"],
            "dump_file": "db_dump.sql",
            "dump_sha256": dump_sha256,
            "dump_size_bytes": dump_size,
            "dump_duration_seconds": round(dump_duration, 3),
            "table_counts": table_counts,
            "mvp_fingerprints": mvp_fingerprints,
        },
        "coverage": "DB_AND_STORAGE" if storage_dir and storage_dir.exists() else "DB_ONLY",
        "storage": {
            "files_count": len(storage_files_meta),
            "files": storage_files_meta,
        },
    }

    manifest_bytes = json.dumps(manifest_data, indent=2, ensure_ascii=False).encode("utf-8")
    manifest_file = bundle_dir / "manifest.json"
    manifest_file.write_bytes(manifest_bytes)
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()

    # Write manifest checksum file
    (bundle_dir / "manifest.sha256").write_text(f"{manifest_hash}  manifest.json\n", encoding="utf-8")

    print(f"[+] Backup bundle completed successfully: {bundle_dir}")
    print(f"[+] Manifest SHA-256: {manifest_hash}")
    return bundle_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A16 Automated System Backup Tool")
    parser.add_argument("--output-dir", required=True, help="Preapproved private output outside Git tree")
    parser.add_argument("--config", required=True, help="Explicit private connection configuration")
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--storage-dir", help="Explicit private artifact storage directory")
    scope.add_argument("--db-only", action="store_true", help="Explicit DB-only partial backup; not a release backup")
    args = parser.parse_args()

    out = Path(args.output_dir)
    cfg_p = Path(args.config) if args.config else None
    stg_p = Path(args.storage_dir) if args.storage_dir else None

    create_backup(output_dir=out, config_path=cfg_p, storage_dir=stg_p)
