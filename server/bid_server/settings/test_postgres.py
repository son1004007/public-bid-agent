"""임시 PostgreSQL 합성 테스트 전용 설정.
입력: 저장소 밖 SM03_TEST_DB_CONFIG_FILE JSON. 기존 운영 base 설정과 무관하다.
경계: loopback host와 sm03_ DB 이름만 허용. 비밀 stdout/로그/원격 연결 금지.
부작용: Django test runner가 test_sm03_* DB만 생성/삭제. 실제 자료 이관 없음.
관련: 문서29 및 tests.test_auth_concurrency.
"""
import json
import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
from .test import *  # noqa: F403

path = Path(os.environ["SM03_TEST_DB_CONFIG_FILE"])
if not path.is_absolute() or Path(__file__).resolve().parents[3] in path.resolve().parents:
    raise ImproperlyConfigured("isolated test config required")
config = json.loads(path.read_text(encoding="utf-8"))
if config["HOST"] != "127.0.0.1" or not config["NAME"].startswith("sm03_"):
    raise ImproperlyConfigured("isolated loopback database required")
DATABASES = {"default": {"ENGINE": "django.db.backends.postgresql", **config,
    "OPTIONS": {"connect_timeout": 5, "sslmode": "disable", "options": "-c statement_timeout=15000 -c lock_timeout=10000"}}}
