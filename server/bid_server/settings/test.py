"""테스트 전용 설정 계약.

목적: 외부 환경/비밀/DB를 읽지 않는 합성 단위 테스트를 제공한다.
경계: CLI/ASGI/WSGI 기본값이 아니며 운영에 사용하지 않는다.
부작용: 랜덤 테스트 키 메모리 생성만. 메모리 SQLite도 SimpleTestCase에서는 접속 금지.
관련: server/README.md, tests/.
"""
import secrets
from .common import *  # noqa: F403

SECRET_KEY = secrets.token_urlsafe(64)
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1", "[::1]"]
CSRF_TRUSTED_ORIGINS = ["http://testserver"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
