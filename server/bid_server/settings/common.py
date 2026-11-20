"""공통 설정 계약.

목적: 격리 API 골격의 안전한 기본값을 정의한다. SM03 인증 앱을 등록하고 실제 업무 앱은 연결하지 않는다.
경계: 비밀과 DB 접속값은 base에서만 주입한다. DEBUG/공개 admin 없음.
부작용: 없음. 실제 운영 DB migration과 계정 발급은 별도 작업이다.
실패: middleware와 DRF는 동일한 안전 오류 경계를 사용하며 원문 예외 로그를 버린다.
관련: docs/server-migration/18,22,28 및 tests/test_api.py.
"""
DEBUG = False
ROOT_URLCONF = "bid_server.urls"
WSGI_APPLICATION = "bid_server.wsgi.application"
ASGI_APPLICATION = "bid_server.asgi.application"
INSTALLED_APPS = ["django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions",
                  "rest_framework", "bid_server.accounts.apps.AccountsConfig",
                  "bid_server.procurement.apps.ProcurementConfig",
                  "bid_server.jobs.apps.JobsConfig",
                  "bid_server.ai_gateway.apps.AIGatewayConfig"]
AUTH_USER_MODEL = "accounts.User"
MIDDLEWARE = [
    "bid_server.core.middleware.ApiBoundaryMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "bid_server.accounts.middleware.AuthGateMiddleware",
    "bid_server.accounts.middleware.StrictCsrfMiddleware",
]
APPEND_SLASH = False
USE_TZ = True
TIME_ZONE = "UTC"
LANGUAGE_CODE = "ko-kr"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_FAILURE_VIEW = "bid_server.core.errors.csrf_failure"
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
# Proxy 신뢰는 배포 ingress 확인 전 설정하지 않는다. 임의 forwarded header를 신뢰하지 않는다.
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["bid_server.core.permissions.ClosedUntilAuthentication"],
    "UNAUTHENTICATED_USER": None,
    "UNAUTHENTICATED_TOKEN": None,
    "DEFAULT_RENDERER_CLASSES": ["bid_server.core.responses.EnvelopeJSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "EXCEPTION_HANDLER": "bid_server.core.errors.exception_handler",
    "COERCE_DECIMAL_TO_STRING": True,
}
# Django 기본 오류 logger가 traceback/SQL/Host/원문을 기록하지 않게 한다.
# 별도 app audit는 code/request_id만 전용 logger로 기록한다.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
    "formatters": {"safe": {"format": "%(levelname)s code=%(error_code)s request_id=%(request_id)s"}},
    "handlers": {"safe": {"class": "logging.StreamHandler", "formatter": "safe"},
                 "null": {"class": "logging.NullHandler"}},
    "root": {"handlers": ["null"], "level": "WARNING"},
    "loggers": {"django": {"handlers": ["null"], "propagate": False},
                "bid_server.safe": {"handlers": ["safe"], "level": "WARNING", "propagate": False}},
}

# 신뢰한 서버 보안 정책. 사용자 API에서 변경하지 않는다.
AUTH_IDLE_SECONDS = 1800
AUTH_ABSOLUTE_SECONDS = 28800
AUTH_LIMITED_SECONDS = 900
AUTH_FAILURE_WINDOW = 900
AUTH_PAIR_FAILURES = 5
AUTH_IP_FAILURES = 20
SESSION_ENGINE = "django.contrib.sessions.backends.db"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
     "OPTIONS": {"user_attributes": ["username", "display_name", "first_name", "last_name", "email"]}},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
