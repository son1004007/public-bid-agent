"""Windows on-device rehearsal of a trusted PostgreSQL custom archive.

Operator prerequisite: protected ACLs and an already initialized, stopped,
dedicated SCRAM cluster. Never use an existing service cluster. No production
credentials are read. Only sanitized stage/result indicators leave the machine.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import time

TABLES = (
    "accounts_user", "procurement_notice", "procurement_noticeversion",
    "procurement_document", "procurement_documentversion", "procurement_proposal",
    "procurement_proposalrevision", "procurement_proposalsection", "jobs_job",
    "jobs_jobattempt", "procurement_exportartifact",
)
ADMIN = "bid_rehearsal_admin"


def require(condition, code):
    if not condition:
        raise RuntimeError(code)


def checked_path(path):
    for p in (path, *path.parents):
        meta = p.lstat()
        require(not p.is_symlink() and not (getattr(meta, "st_file_attributes", 0) & 1024),
                "REPARSE_PATH")
    return path.resolve(strict=True)


def rehearse(root, work, archive, manifest, binaries, port):
    root, work, archive, manifest, binaries = map(checked_path, (root, work, archive, manifest, binaries))
    require(work.parent == root and work.name.startswith("rehearsal-")
            and archive.parent == manifest.parent == root and archive.is_file()
            and manifest.is_file(), "INVALID_LAYOUT")
    data = checked_path(work / "data")
    require((data / "PG_VERSION").read_text().strip() == "17" and
            not (data / "postmaster.pid").exists(), "CLUSTER_NOT_STOPPED")
    require(49152 <= port <= 65535, "INVALID_REHEARSAL_PORT")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", port))
    with manifest.open(encoding="utf-8-sig") as f:
        meta = json.load(f)
    with archive.open("rb") as f:
        require(meta["scope"] == "DB_ONLY" and meta["bytes"] == archive.stat().st_size
                and hashlib.file_digest(f, "sha256").hexdigest().lower() == meta["sha256"].lower(),
                "ARCHIVE_IDENTITY")
    admin = checked_path(work / "admin.private").read_text().strip()
    require(re.fullmatch(r"[0-9a-fA-F]{64}", admin), "INVALID_REHEARSAL_CREDENTIAL")
    token = secrets.token_hex(8)
    role, db = "restore_" + token, "rehearsal_" + token
    owner = secrets.token_hex(32)
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("PG")}
    env.update(PGCONNECT_TIMEOUT="3", PGSSLMODE="disable", PGCLIENTENCODING="UTF8")

    def pg(tool, args, password=None, inp=None, timeout=12):
        child_env = env.copy()
        if password is not None:
            child_env["PGPASSWORD"] = password
        exe = checked_path(binaries / (tool + ".exe"))
        return subprocess.run([str(exe), *args], env=child_env, input=inp,
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout, cwd=work)

    def sql(user, name, password, query):
        result = pg("psql", ["-X", "-w", "-qAt", "-h", "127.0.0.1", "-p", str(port),
                             "-U", user, "-d", name, "-v", "ON_ERROR_STOP=1"], password, query)
        require(result.returncode == 0, "SQL_FAILED")
        return result.stdout.strip()

    phase, success, stopped, server = "start", False, False, None
    logpath = work / ("managed-" + token + ".private.log")
    with logpath.open("xb") as log:
        try:
            # pg_ctl on Windows drops administrative privileges for postgres.
            # Send launcher output to a real file, not an inherited capture pipe.
            server = subprocess.Popen([str(checked_path(binaries / "pg_ctl.exe")), "start",
                                       "-D", str(data), "-l", str(work / ("postgres-" + token + ".private.log")),
                                       "-o", f"-p {port} -h 127.0.0.1 -c max_connections=8 -c shared_buffers=32MB",
                                       "-w", "-t", "10"], env=env, cwd=work, stdin=subprocess.DEVNULL,
                                      stdout=log, stderr=subprocess.STDOUT)
            server.wait(timeout=15)
            require(server.returncode == 0 and (data / "postmaster.pid").is_file(), "PG_CTL_START_FAILED")
            phase = "identity"
            actual = sql(ADMIN, "postgres", admin, "SELECT current_setting('data_directory');")
            require(Path(actual).resolve() == data, "WRONG_CLUSTER")
            require(sql(ADMIN, "postgres", admin, "SELECT current_setting('listen_addresses');") == "127.0.0.1",
                    "LISTENER_BOUNDARY")
            phase = "provision"
            sql(ADMIN, "postgres", admin,
                f"CREATE ROLE {role} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD '{owner}';\n"
                f"CREATE DATABASE {db} OWNER {role} TEMPLATE template0;")
            require(sql(role, db, owner, "SELECT NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole "
                        "FROM pg_roles WHERE rolname=current_user;") == "t", "ROLE_BOUNDARY")
            phase = "restore"
            result = pg("pg_restore", ["-w", "-h", "127.0.0.1", "-p", str(port), "-U", role,
                         "-d", db, "--no-owner", "--no-privileges", "--no-tablespaces",
                         "--single-transaction", "--exit-on-error", str(archive)], owner, timeout=40)
            if result.returncode:
                with (work / ("restore-" + token + ".private.log")).open("x", encoding="utf-8") as f:
                    f.write(result.stderr)
                raise RuntimeError("RESTORE_FAILED")
            print("ACTUAL_ARCHIVE_RESTORED", flush=True)
            phase = "checks"
            query = " UNION ALL ".join(
                f"SELECT '{t}', count(*), md5(coalesce(string_agg(md5(to_jsonb(x)::text),'' "
                f"ORDER BY md5(to_jsonb(x)::text)),'')) FROM public.{t} x" for t in TABLES)
            rows = sql(role, db, owner, "BEGIN READ ONLY; SET LOCAL timezone='UTC'; "
                       "SET LOCAL statement_timeout='8s'; " + query + "; ROLLBACK;").splitlines()
            require(len(rows) == len(TABLES) and {r.split("|")[0] for r in rows} == set(TABLES)
                    and all(re.fullmatch(r"[a-z_]+\|\d+\|[a-f0-9]{32}", r) for r in rows),
                    "INVALID_ROW_RECORD")
            require(sql(role, db, owner, "SELECT count(*) FROM pg_constraint WHERE contype='f' AND NOT convalidated;")
                    == "0", "UNVALIDATED_FK")
            require(sql(role, db, owner, "BEGIN; CREATE TABLE public.bid_rehearsal_probe(id integer PRIMARY KEY); "
                        "INSERT INTO public.bid_rehearsal_probe VALUES(1); SELECT count(*)=1 FROM public.bid_rehearsal_probe; "
                        "ROLLBACK; SELECT to_regclass('public.bid_rehearsal_probe') IS NULL;").splitlines()
                    == ["t", "t"], "ROLLBACK_FAILED")
            with (work / ("parity-" + token + ".private.txt")).open("x", encoding="ascii") as f:
                f.write("\n".join(rows) + "\n")
            success = True
        except Exception:
            print("RECOVERY_FAILED_STAGE=" + phase, flush=True)
        finally:
            if server is not None:
                try:
                    if server.poll() is None:
                        server.wait(timeout=10)
                    if (data / "postmaster.pid").exists():
                        result = pg("pg_ctl", ["stop", "-D", str(data), "-m", "fast", "-w", "-t", "10"], timeout=15)
                        require(result.returncode == 0, "STOP_FAILED")
                    stopped = server.poll() is not None and not (data / "postmaster.pid").exists()
                except Exception:
                    print("SHUTDOWN_NOT_CONFIRMED", flush=True)
    # The archive-time source row digests were not captured; no source parity claim.
    print(json.dumps({"restoreVerified": success, "clusterStopped": stopped,
                      "sourceSnapshotParity": "NOT_VERIFIED"}), flush=True)
    return success and stopped


def main():
    parser = argparse.ArgumentParser()
    for name in ("root", "work", "archive", "manifest", "binaries"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--port", required=True, type=int)
    args = parser.parse_args()
    try:
        return 0 if rehearse(**vars(args)) else 1
    except Exception:
        print("RECOVERY_PREFLIGHT_FAILED", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
