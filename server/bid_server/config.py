"""설정 로더 설계 계약.

목적/책임: 승인된 환경 설정과 비밀 파일을 검증해 불변 런타임 설정을 만든다.
입력/출력: 문자열 환경 mapping -> RuntimeConfig. 실제 비밀값/경로를 오류에 넣지 않는다.
신뢰 경계/권한: 운영자가 제공한 파일만 읽고 평문 비밀 환경변수는 거부한다.
상태 변경/부작용: 제한된 정규 파일 읽기만 수행. DB 접속/폴더 생성/정책 원문 로딩 없음.
실패/재시도: 잘못된 설정은 ImproperlyConfigured로 중단하며 fallback/재시도하지 않는다.
불변조건: DEBUG는 별도 settings에서도 False, 저장소 안의 비밀/media 경로 금지.
관련: docs/server-migration/22,28; tests/test_config.py.
"""
from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
from typing import Mapping
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def invalid(name: str) -> ImproperlyConfigured:
    return ImproperlyConfigured(f"Invalid or missing configuration: {name}")


def required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value or len(value) > 4096 or any(c in value for c in "\r\n\x00"):
        raise invalid(name)
    return value


def private_path(env: Mapping[str, str], name: str) -> Path:
    raw = required(env, name)
    path = Path(raw)
    try:
        if not path.is_absolute() or path.is_symlink():
            raise invalid(name)
        resolved = path.resolve()
        if resolved.is_relative_to(REPOSITORY_ROOT):
            raise invalid(name)
        return resolved
    except (OSError, ValueError):
        raise invalid(name) from None


def secret_file(env: Mapping[str, str], name: str, *, minimum: int = 1) -> str:
    # 평문 비밀은 빈값이어도 허용하지 않는다. 경로와 비밀은 repr/exception에 넣지 않는다.
    if name in env:
        raise invalid(name)
    path = private_path(env, name + "_FILE")
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        with os.fdopen(os.open(path, flags), "rb") as stream:
            metadata = os.fstat(stream.fileno())
            if not stat.S_ISREG(metadata.st_mode):
                raise invalid(name + "_FILE")
            if os.name != "nt" and metadata.st_mode & 0o077:
                raise invalid(name + "_FILE")
            raw = stream.read(4097)
        if len(raw) > 4096:
            raise invalid(name + "_FILE")
        value = raw.decode("utf-8").rstrip("\r\n")
        if len(value) < minimum or not value.strip() or any(c in value for c in "\r\n\x00"):
            raise invalid(name + "_FILE")
        return value
    except (OSError, ValueError, UnicodeError):
        raise invalid(name + "_FILE") from None


def load_local_database(path: Path) -> dict:
    """Read only explicit local PostgreSQL fields; never spread arbitrary options."""
    try:
        private = private_path({"LOCAL_DATABASE_FILE": str(path)}, "LOCAL_DATABASE_FILE")
        flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
        with os.fdopen(os.open(private, flags), "rb") as stream:
            metadata = os.fstat(stream.fileno())
            if not stat.S_ISREG(metadata.st_mode) or (os.name != "nt" and metadata.st_mode & 0o077):
                raise ValueError
            raw = stream.read(4097)
        if len(raw) > 4096:
            raise ValueError
        cfg = json.loads(raw.decode("utf-8"))
        if not isinstance(cfg, dict) or set(cfg) != {"HOST", "PORT", "NAME", "USER", "PASSWORD"}:
            raise ValueError
        if cfg["HOST"] not in ("127.0.0.1", "::1"):
            raise ValueError
        if type(cfg["PORT"]) not in (int, str) or not re.fullmatch(r"[0-9]{1,5}", str(cfg["PORT"])):
            raise ValueError
        if not 1 <= int(cfg["PORT"]) <= 65535:
            raise ValueError
        for key in ("NAME", "USER"):
            if not isinstance(cfg[key], str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,63}", cfg[key]):
                raise ValueError
        if cfg["NAME"].lower() in ("postgres", "template0", "template1"):
            raise ValueError
        if not isinstance(cfg["PASSWORD"], str) or not cfg["PASSWORD"] or any(c in cfg["PASSWORD"] for c in "\r\n\x00"):
            raise ValueError
        return {**cfg, "PORT": int(cfg["PORT"])}
    except (ImproperlyConfigured, OSError, ValueError, TypeError, UnicodeError):
        raise invalid("LOCAL_DATABASE_FILE") from None


def load_local_media_root(env: Mapping[str, str], app_root: Path) -> Path:
    """The Windows loopback launcher must select a dedicated, precreated root.

    Filesystem ACL validation belongs to the launcher/operator. Do not resolve
    away a junction, symlink or other reparse point in the configured path.
    """
    key = "BID_LOCAL_PRIVATE_MEDIA_ROOT"
    try:
        profile = Path(required(env, "USERPROFILE"))
        raw = Path(required(env, key))
        if not profile.is_absolute() or raw != profile / "PublicBidAgent-private-media":
            raise invalid(key)
        for component in (raw, *raw.parents):
            meta = component.lstat()
            if (stat.S_ISLNK(meta.st_mode) or not stat.S_ISDIR(meta.st_mode)
                    or getattr(meta, "st_file_attributes", 0)
                    & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024)):
                raise invalid(key)
        media = private_path(env, key)
        app = app_root.resolve()
        if (media.is_relative_to(app) or app.is_relative_to(media)
                or REPOSITORY_ROOT.is_relative_to(media)):
            raise invalid(key)
        if os.name != "nt" and media.stat().st_mode & 0o077:
            raise invalid(key)
        return media
    except (OSError, ValueError, RuntimeError):
        raise invalid(key) from None


def valid_host(value: str) -> bool:
    if value.startswith("[") and value.endswith("]"):
        try:
            return ipaddress.ip_address(value[1:-1]).version == 6
        except ValueError:
            return False
    if len(value) > 253 or not re.fullmatch(r"[A-Za-z0-9.-]+", value):
        return False
    return all(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
               for label in value.split("."))


def csv_values(env: Mapping[str, str], name: str) -> tuple[str, ...]:
    values = tuple(x.strip() for x in required(env, name).split(","))
    if not values or any(not x for x in values):
        raise invalid(name)
    return tuple(dict.fromkeys(values))


@dataclass(frozen=True, repr=False)
class RuntimeConfig:
    environment: str
    hosts: tuple[str, ...]
    origins: tuple[str, ...]
    secret_key: str
    database_host: str
    database_port: int
    database_name: str
    database_user: str
    database_password: str
    media_root: Path
    database_sslmode: str
    redis_url: str | None
    policy_source: Path | None


def load_config(env: Mapping[str, str]) -> RuntimeConfig:
    environment = env.get("APP_ENV", "production")
    if environment not in {"production", "development"}:
        raise invalid("APP_ENV")
    if "APP_DEBUG" in env and env["APP_DEBUG"].lower() not in {"false", "0"}:
        raise invalid("APP_DEBUG")
    hosts = csv_values(env, "APP_ALLOWED_HOSTS")
    if not all(valid_host(h) for h in hosts):
        raise invalid("APP_ALLOWED_HOSTS")
    if environment == "development" and not set(hosts) <= {"localhost", "127.0.0.1", "[::1]"}:
        raise invalid("APP_ALLOWED_HOSTS")
    origins = csv_values(env, "APP_CSRF_TRUSTED_ORIGINS")
    for origin in origins:
        try:
            url = urlsplit(origin)
            port = url.port
            if (url.scheme not in ({"https"} if environment == "production" else {"http", "https"})
                    or not url.hostname or not valid_host(url.netloc.split(":")[0] if not url.netloc.startswith("[") else "[" + url.hostname + "]")
                    or url.username or url.password or url.path or url.query or url.fragment
                    or (port is not None and not 1 <= port <= 65535)):
                raise invalid("APP_CSRF_TRUSTED_ORIGINS")
            if environment == "development" and url.hostname not in {"localhost", "127.0.0.1", "::1"}:
                raise invalid("APP_CSRF_TRUSTED_ORIGINS")
        except ValueError:
            raise invalid("APP_CSRF_TRUSTED_ORIGINS") from None
    key = secret_file(env, "DJANGO_SECRET_KEY", minimum=50)
    if len(set(key)) < 5:
        raise invalid("DJANGO_SECRET_KEY_FILE")
    db_host = required(env, "DATABASE_HOST")
    if not valid_host(db_host):
        raise invalid("DATABASE_HOST")
    raw_port = env.get("DATABASE_PORT", "5432")
    if not re.fullmatch(r"[0-9]{1,5}", raw_port) or not 1 <= int(raw_port) <= 65535:
        raise invalid("DATABASE_PORT")
    db_name = required(env, "DATABASE_NAME")
    db_user = required(env, "DATABASE_USER")
    if any(not re.fullmatch(r"[A-Za-z0-9_.-]{1,63}", v) for v in (db_name, db_user)):
        raise invalid("DATABASE_NAME/DATABASE_USER")
    password = secret_file(env, "DATABASE_PASSWORD")
    media = private_path(env, "PRIVATE_MEDIA_ROOT")
    if (media.exists() and not media.is_dir()) or REPOSITORY_ROOT.is_relative_to(media):
        raise invalid("PRIVATE_MEDIA_ROOT")
    # Storage is not a secret directory. Prevent overlapping paths even if
    # a future file-serving adapter is incorrectly configured.
    for secret_name in ("DJANGO_SECRET_KEY_FILE", "DATABASE_PASSWORD_FILE", "REDIS_URL_FILE",
                        "PUBLIC_BID_POLICY_SOURCE_FILE"):
        if secret_name in env:
            private = private_path(env, secret_name)
            if private.is_relative_to(media) or media.is_relative_to(private):
                raise invalid("PRIVATE_MEDIA_ROOT")
    sslmode = env.get("DATABASE_SSLMODE", "verify-full" if environment == "production" else "disable")
    if sslmode not in ({"verify-full"} if environment == "production" else {"disable", "require", "verify-full"}):
        raise invalid("DATABASE_SSLMODE")
    redis = secret_file(env, "REDIS_URL") if "REDIS_URL_FILE" in env or "REDIS_URL" in env else None
    if redis:
        try:
            parsed = urlsplit(redis)
            if parsed.scheme not in {"redis", "rediss"} or not parsed.hostname or parsed.fragment:
                raise invalid("REDIS_URL_FILE")
            _ = parsed.port
        except ValueError:
            raise invalid("REDIS_URL_FILE") from None
    policy = private_path(env, "PUBLIC_BID_POLICY_SOURCE_FILE") if "PUBLIC_BID_POLICY_SOURCE_FILE" in env else None
    # 정책 접근이나 준수 완료는 이 경로 설정만으로 판정하지 않는다.
    return RuntimeConfig(environment, hosts, origins, key, db_host, int(raw_port), db_name,
                         db_user, password, media, sslmode, redis, policy)
