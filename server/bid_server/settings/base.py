"""실행 설정 계약.

목적: 검증된 환경 설정을 Django 설정으로 변환한다. 비밀 읽기 외 저장/접속 없음.
경계: production은 HTTPS, development는 명시적 loopback host만 허용한다.
실패: 필수값 누락은 startup 실패이며 SQLite나 기본 암호로 fallback하지 않는다.
관련: config.py, docs/server-migration/22,28, tests/test_config.py.
"""
import os
from bid_server.config import load_config
from .common import *  # noqa: F403

CONFIG = load_config(os.environ)
SECRET_KEY = CONFIG.secret_key
ALLOWED_HOSTS = list(CONFIG.hosts)
CSRF_TRUSTED_ORIGINS = list(CONFIG.origins)
PRIVATE_MEDIA_ROOT = CONFIG.media_root
PUBLIC_BID_POLICY_SOURCE_FILE = CONFIG.policy_source
REDIS_URL = CONFIG.redis_url  # SM02에서는 broker 연결을 시작하지 않는다.
DATABASES = {"default": {
    "ENGINE": "django.db.backends.postgresql", "HOST": CONFIG.database_host,
    "PORT": CONFIG.database_port, "NAME": CONFIG.database_name,
    "USER": CONFIG.database_user, "PASSWORD": CONFIG.database_password,
    "CONN_MAX_AGE": 0, "OPTIONS": {"connect_timeout": 5, "sslmode": CONFIG.database_sslmode},
}}
SECURE_SSL_REDIRECT = CONFIG.environment == "production"
SECURE_HSTS_SECONDS = 31536000 if CONFIG.environment == "production" else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SESSION_COOKIE_SECURE = CONFIG.environment == "production"
CSRF_COOKIE_SECURE = CONFIG.environment == "production"
