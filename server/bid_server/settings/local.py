"""Local loopback staging only; no fallback DB, secret or remote host."""
import os
from pathlib import Path
from bid_server.config import invalid, load_local_database, private_path, secret_file, REPOSITORY_ROOT
from .common import *  # noqa: F403

# Keep credentials outside Git. Do not inherit a plaintext signing key.
local_app = os.environ.get("LOCALAPPDATA")
if not local_app or not Path(local_app).is_absolute():
    raise invalid("LOCALAPPDATA")
root = Path(local_app) / "PublicBidAgent"
if "BID_LOCAL_SECRET_KEY" in os.environ:
    raise invalid("BID_LOCAL_SECRET_KEY")
SECRET_KEY = secret_file(
    {"LOCAL_SECRET_KEY_FILE": str(root / "local" / "django_secret_key.txt")},
    "LOCAL_SECRET_KEY", minimum=50,
)
if len(set(SECRET_KEY)) < 5:
    raise invalid("LOCAL_SECRET_KEY_FILE")

DEBUG = False
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "[::1]"]
CSRF_TRUSTED_ORIGINS = ["http://127.0.0.1:8000", "http://localhost:8000"]
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
db_cfg = load_local_database(root / "sm03-postgres" / "connection.private.json")
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        **db_cfg,
        "OPTIONS": {"connect_timeout": 5, "sslmode": "disable"},
    }
}

# No directory creation at import; export fails closed if storage is absent.
PRIVATE_MEDIA_ROOT = private_path(
    {"PRIVATE_MEDIA_ROOT": str(root / "local-media")}, "PRIVATE_MEDIA_ROOT",
)
if REPOSITORY_ROOT.is_relative_to(PRIVATE_MEDIA_ROOT):
    raise invalid("PRIVATE_MEDIA_ROOT")
