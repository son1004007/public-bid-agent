"""로컬 개발 및 사용자 웹서비스 테스트 전용 설정.
목적: 개발자가 로컬 loopback 환경에서 실제 DB와 연결된 웹 화면을 브라우저로 직접 테스트할 수 있도록 지원한다.
경계: 127.0.0.1 / localhost loopback만 허용하며 외부 노출 금지.
"""
import json
import os
from pathlib import Path
from .common import *  # noqa: F403

# Private per-device signing key; never commit an application SECRET_KEY.
_secret_file = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "PublicBidAgent" / "local" / "django_secret_key.txt"
SECRET_KEY = os.environ.get("BID_LOCAL_SECRET_KEY", "") or (_secret_file.read_text(encoding="utf-8").strip() if _secret_file.exists() else "")
if len(SECRET_KEY) < 40:
    raise RuntimeError("Local Django secret is missing; create a secret outside the repository")
DEBUG = False
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]
CSRF_TRUSTED_ORIGINS = ["http://127.0.0.1:8000", "http://localhost:8000"]
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# 로컬 PostgreSQL 17 클러스터 연결 설정 자동 로드
conn_file = (
    Path(os.environ.get("LOCALAPPDATA", ""))
    / "PublicBidAgent"
    / "sm03-postgres"
    / "connection.private.json"
)

if conn_file.exists():
    db_cfg = json.loads(conn_file.read_text(encoding="utf-8"))
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            **db_cfg,
            "OPTIONS": {"connect_timeout": 5, "sslmode": "disable"},
        }
    }
