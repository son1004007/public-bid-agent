"""설정과 비밀 경계 검사. 임시 합성 파일만 사용하며 운영 설정과 비밀은 읽지 않는다."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest import TestCase
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from bid_server.config import REPOSITORY_ROOT, load_config, secret_file


class ConfigurationTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pba-sm02-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.key = "SENSITIVE_FIXTURE_" + "AbCdEfGh1234567890" * 4
        self.write("key", self.key.encode())
        self.write("db", b"SENSITIVE_FIXTURE_db_password")
        self.env = {"APP_ALLOWED_HOSTS": "example.invalid", "APP_CSRF_TRUSTED_ORIGINS": "https://example.invalid",
                    "DJANGO_SECRET_KEY_FILE": str(self.root / "key"), "DATABASE_PASSWORD_FILE": str(self.root / "db"),
                    "DATABASE_HOST": "db", "DATABASE_NAME": "synthetic", "DATABASE_USER": "synthetic",
                    "PRIVATE_MEDIA_ROOT": str(self.root / "private")}

    def write(self, name, value):
        path = self.root / name
        path.write_bytes(value)
        if os.name != "nt":
            path.chmod(0o600)
        return path

    def reject(self, values, name=None):
        with self.assertRaises(ImproperlyConfigured) as caught:
            load_config(values)
        message = str(caught.exception)
        self.assertNotIn(self.key, message)
        self.assertNotIn(str(self.root), message)
        self.assertNotIn("SENSITIVE_FIXTURE", message)
        if name:
            self.assertIn(name, message)

    def test_strict_production_config_and_no_directory_creation(self):
        cfg = load_config(self.env)
        self.assertEqual(cfg.environment, "production")
        self.assertEqual(cfg.database_port, 5432)
        self.assertEqual(cfg.database_sslmode, "verify-full")
        self.assertEqual(cfg.secret_key, self.key)
        self.assertFalse(cfg.media_root.exists())
        self.assertNotIn(self.key, repr(cfg))

    def test_all_required_values_are_fail_closed(self):
        for name in self.env:
            with self.subTest(name=name):
                env = {k: v for k, v in self.env.items() if k != name}
                self.reject(env)

    def test_plaintext_is_rejected_with_or_without_file(self):
        for stem in ["DJANGO_SECRET_KEY", "DATABASE_PASSWORD", "REDIS_URL"]:
            with self.subTest(stem=stem):
                env = {**self.env, stem: "SENSITIVE_FIXTURE"}
                self.reject(env, stem)
                env.pop(stem + "_FILE", None)
                self.reject(env, stem)

    def test_empty_plaintext_still_rejected(self):
        self.reject({**self.env, "DJANGO_SECRET_KEY": ""}, "DJANGO_SECRET_KEY")

    def test_no_implicit_debug_or_unknown_environment(self):
        for k, v in [("APP_DEBUG", "true"), ("APP_DEBUG", "yes"), ("APP_ENV", "staging"), ("APP_ENV", "test")]:
            with self.subTest(k=k, v=v):
                self.reject({**self.env, k: v}, k)

    def test_hosts_must_be_explicit_and_not_wildcards(self):
        for host in ["*", ".example.invalid", "https://example.invalid", "host:80", "", "valid.invalid,", "a..invalid", "a/b"]:
            with self.subTest(host=host):
                self.reject({**self.env, "APP_ALLOWED_HOSTS": host}, "APP_ALLOWED_HOSTS")

    def test_origins_must_be_https_and_no_credentials_path_or_query(self):
        for origin in ["http://example.invalid", "https://a:b@example.invalid", "https://example.invalid/path",
                       "https://example.invalid?token=private", "https://example.invalid/#f", "https://example.invalid:abc"]:
            with self.subTest(origin=origin):
                self.reject({**self.env, "APP_CSRF_TRUSTED_ORIGINS": origin}, "APP_CSRF_TRUSTED_ORIGINS")

    def test_development_requires_loopback(self):
        env = {**self.env, "APP_ENV": "development", "APP_ALLOWED_HOSTS": "localhost,127.0.0.1,[::1]",
               "APP_CSRF_TRUSTED_ORIGINS": "http://localhost:8870"}
        cfg = load_config(env)
        self.assertEqual(cfg.database_sslmode, "disable")
        self.reject({**env, "APP_ALLOWED_HOSTS": "example.invalid"})
        self.reject({**env, "APP_CSRF_TRUSTED_ORIGINS": "http://example.invalid"})

    def test_relative_or_repository_secret_and_media_paths_rejected(self):
        for key in ["DJANGO_SECRET_KEY_FILE", "DATABASE_PASSWORD_FILE", "PRIVATE_MEDIA_ROOT"]:
            for value in ["relative/path", str(REPOSITORY_ROOT / "fixture-secret")]:
                with self.subTest(key=key):
                    self.reject({**self.env, key: value})

    def test_missing_directory_and_nonutf8_secret_rejected(self):
        for value in [self.root / "missing", self.root]:
            self.reject({**self.env, "DJANGO_SECRET_KEY_FILE": str(value)})
        self.write("key", b"\xff\xfe")
        self.reject(self.env)

    def test_secret_size_limit(self):
        self.write("key", b"X" * 4097)
        self.reject(self.env)

    def test_secret_empty_multiline_null_short_and_low_entropy(self):
        for value in [b"", b"short", b"x" * 60, b"x\ny" * 30, b"x\x00y" * 30]:
            with self.subTest(size=len(value)):
                self.write("key", value)
                self.reject(self.env)

    def test_trailing_newline_supported_without_normalizing_password_spaces(self):
        self.write("key", self.key.encode() + b"\r\n")
        self.write("db", b" password with spaces \n")
        cfg = load_config(self.env)
        self.assertEqual(cfg.secret_key, self.key)
        self.assertEqual(cfg.database_password, " password with spaces ")

    def test_symlink_secret_rejected_when_available(self):
        link = self.root / "linked"
        try:
            link.symlink_to(self.root / "key")
        except (OSError, NotImplementedError):
            with patch("bid_server.config.Path.is_symlink", return_value=True):
                self.reject(self.env)
            return
        self.reject({**self.env, "DJANGO_SECRET_KEY_FILE": str(link)})

    def test_writable_posix_secret_policy(self):
        if os.name == "nt":
            # 동일한 mode 검사를 합성 metadata로 검증, Windows ACL 지원을 가장하지 않는다.
            import stat
            class Metadata:
                st_mode = stat.S_IFREG | 0o644
            with patch("bid_server.config.os.name", "posix"), patch("bid_server.config.os.fstat", return_value=Metadata()):
                with self.assertRaises(ImproperlyConfigured):
                    secret_file(self.env, "DJANGO_SECRET_KEY", minimum=50)
        else:
            (self.root / "key").chmod(0o644)
            self.reject(self.env)

    def test_database_port_and_names_and_sslmode(self):
        for k, value in [("DATABASE_PORT", "0"), ("DATABASE_PORT", "65536"), ("DATABASE_PORT", "abc"),
                         ("DATABASE_HOST", "http://db"), ("DATABASE_NAME", "../private"),
                         ("DATABASE_USER", "x y"), ("DATABASE_SSLMODE", "disable")]:
            with self.subTest(k=k, value=value):
                self.reject({**self.env, k: value})

    def test_redis_optional_secret_reference_and_scheme(self):
        path = self.write("redis", b"redis://:private@localhost:6379/0")
        cfg = load_config({**self.env, "REDIS_URL_FILE": str(path)})
        self.assertNotIn("private", repr(cfg))
        self.write("redis", b"https://example.invalid")
        self.reject({**self.env, "REDIS_URL_FILE": str(path)})

    def test_policy_path_does_not_load_policy(self):
        cfg = load_config({**self.env, "PUBLIC_BID_POLICY_SOURCE_FILE": str(self.root / "not-read.json")})
        self.assertEqual(cfg.policy_source.name, "not-read.json")

    def production_environment(self):
        # OS 실행 필수값만 허용하며 앱/파이썬 주입 설정을 상속하지 않는다.
        os_keys = ("SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP", "COMSPEC", "PATHEXT", "LANG", "LC_ALL")
        env = {name: os.environ[name] for name in os_keys if name in os.environ}
        return {**env, **self.env, "DJANGO_SETTINGS_MODULE": "bid_server.settings.base"}

    def run_production_check(self):
        proc = subprocess.run([sys.executable, "manage.py", "check", "--deploy"],
                              cwd=Path(__file__).resolve().parents[1], env=self.production_environment(),
                              capture_output=True, text=True, timeout=20)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn(self.key, proc.stderr + proc.stdout)
        return proc

    def test_production_settings_import_and_framework_check_without_database(self):
        self.run_production_check()

    def test_subprocess_does_not_inherit_external_application_or_secret_environment(self):
        # 존재하지만 읽으면 startup 실패할 합성 파일. 실제 외부 비밀을 열지 않는다.
        external = self.write("external-redis", b"\\xff\\xfe")
        poisoned = {"REDIS_URL_FILE": str(external), "APP_ENV": "staging", "APP_DEBUG": "true",
                    "DATABASE_SSLMODE": "disable", "PUBLIC_BID_POLICY_SOURCE_FILE": "relative-source.json",
                    "DJANGO_SECRET_KEY": "SENSITIVE_FIXTURE_plain", "PYTHONPATH": "untrusted-module-path"}
        with patch.dict(os.environ, poisoned):
            env = self.production_environment()
            for name in poisoned:
                self.assertNotIn(name, env)
            self.run_production_check()
