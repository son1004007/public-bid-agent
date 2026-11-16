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
    if config_path and config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    env_cfg = os.environ.get("SM03_TEST_DB_CONFIG_FILE")
    if env_cfg and Path(env_cfg).exists():
        with open(env_cfg, "r", encoding="utf-8") as f:
            return json.load(f)
    default_cfg = Path(os.environ.get("LOCALAPPDATA", "")) / "PublicBidAgent" / "sm03-postgres" / "connection.private.json"
    if default_cfg.exists():
        with open(default_cfg, "r", encoding="utf-8") as f:
            return json.load(f)
    raise RuntimeError("PostgreSQL connection configuration file not found.")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def get_table_counts(conn) -> dict:
    """Count source tables in the same exported PostgreSQL snapshot as pg_dump."""
    tables = [
        "accounts_user",
        "procurement_notice",
        "procurement_noticeversion",
        "procurement_document",
        "procurement_documentversion",
        "procurement_proposal",
        "procurement_proposalrevision",
        "procurement_proposalsection",
        "jobs_job",
        "jobs_jobattempt",
    ]
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
    if output_dir.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError("Backup output must be outside the Git working tree")
    cfg = load_db_config(config_path)
    pg_bin = get_pg_bin_path()
    pg_dump = str(pg_bin / "pg_dump.exe") if pg_bin.name else "pg_dump"

    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_id = f"backup_{timestamp_str}"
    bundle_dir = output_dir / backup_id
    bundle_dir.mkdir(parents=True, exist_ok=True)

    print(f"[*] Starting backup generation for bundle: {backup_id}")
    print(f"[*] Target DB: {cfg['HOST']}:{cfg['PORT']}/{cfg['NAME']}")

    # Export one REPEATABLE READ snapshot and keep the exporting transaction
    # open until pg_dump exits. This ensures row counts and dump share one MVCC view.
    import psycopg
    dump_file = bundle_dir / "db_dump.sql"
    env = os.environ.copy()
    env["PGPASSWORD"] = cfg["PASSWORD"]
    conn = psycopg.connect(
        host=cfg["HOST"], port=cfg["PORT"], dbname=cfg["NAME"],
        user=cfg["USER"], password=cfg["PASSWORD"],
    )
    try:
        with conn.cursor() as cur:
            cur.execute("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            cur.execute("SELECT pg_export_snapshot()")
            snapshot_id = cur.fetchone()[0]
        print("[*] Counting source rows in exported snapshot...")
        table_counts = get_table_counts(conn)
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
        res = subprocess.run(dump_cmd, env=env, capture_output=True, text=True)
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
        for root, _, files in os.walk(storage_dir):
            for file in files:
                src_path = Path(root) / file
                rel_path = src_path.relative_to(storage_dir)
                dest_path = bundle_storage_dir / rel_path
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                dest_path.write_bytes(src_path.read_bytes())

                h = sha256_file(dest_path)
                storage_files_meta.append({
                    "relative_path": str(rel_path).replace("\\", "/"),
                    "sha256": h,
                    "size_bytes": dest_path.stat().st_size,
                })

    # 4. Manifest generation
    manifest_data = {
        "manifest_version": "1.0",
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
    parser.add_argument("--output-dir", default=str(Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "PublicBidAgent" / "backups"), help="Output outside Git tree")
    parser.add_argument("--config", default=None, help="Path to connection.private.json")
    parser.add_argument("--storage-dir", default=None, help="Path to storage/artifacts directory")
    args = parser.parse_args()

    out = Path(args.output_dir)
    cfg_p = Path(args.config) if args.config else None
    stg_p = Path(args.storage_dir) if args.storage_dir else None

    create_backup(output_dir=out, config_path=cfg_p, storage_dir=stg_p)
