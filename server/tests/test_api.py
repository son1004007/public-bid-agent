"""합성 HTTP 계약 검사. DB 접근을 금지하고 실제 응답과 OpenAPI schema를 비교한다."""
from io import StringIO
import json
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

from django.test import Client, SimpleTestCase, override_settings
from jsonschema import Draft202012Validator, FormatChecker
from rest_framework.test import APIClient

SPEC = json.loads((Path(__file__).resolve().parents[1] / "openapi.json").read_text(encoding="utf-8"))


@override_settings(ROOT_URLCONF="tests.urls", MIDDLEWARE=[
    "bid_server.core.middleware.ApiBoundaryMiddleware", "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
])
class ApiContractTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient(raise_request_exception=False)

    def validate(self, response, schema):
        body = response.json()
        root = {"$ref": "#/components/schemas/" + schema, "components": SPEC["components"]}
        Draft202012Validator(root, format_checker=FormatChecker()).validate(body)
        self.assertEqual(str(UUID(body["request_id"])), body["request_id"])
        self.assertEqual(response["X-Request-ID"], body["request_id"])
        self.assertEqual(response["Cache-Control"], "no-store")
        return body

    def error(self, response, status, code):
        self.assertEqual(response.status_code, status)
        body = self.validate(response, "ErrorResponse")
        self.assertEqual(body["error"]["code"], code)
        self.assertNotIn("SENSITIVE_FIXTURE", response.content.decode())
        self.assertNotIn("traceback", response.content.decode().lower())
        self.assertFalse(body["error"]["retryable"])
        return body

    def test_process_health_no_database_or_auth(self):
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        body = self.validate(response, "HealthResponse")
        self.assertEqual(body["data"], {"status": "ok", "scope": "process"})
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")

    def test_head_has_request_id_and_no_body(self):
        response = self.client.head("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"")
        UUID(response["X-Request-ID"])

    def test_client_request_id_is_not_trusted(self):
        one = self.client.get("/api/v1/health", HTTP_X_REQUEST_ID="SENSITIVE_FIXTURE_DO_NOT_ECHO")
        two = self.client.get("/api/v1/health", HTTP_X_REQUEST_ID=one["X-Request-ID"])
        self.validate(one, "HealthResponse")
        self.assertNotEqual(one["X-Request-ID"], two["X-Request-ID"])
        self.assertNotIn("SENSITIVE_FIXTURE", one.content.decode())

    def test_unknown_url_and_trailing_slash_do_not_redirect(self):
        for url in ["/api/v1/missing", "/api/v1/health/", "/admin"]:
            with self.subTest(url=url):
                self.error(self.client.get(url), 404, "NOT_FOUND")

    def test_method_not_allowed(self):
        response = self.client.post("/api/v1/health", {}, format="json")
        self.error(response, 405, "METHOD_NOT_ALLOWED")
        self.assertIn("GET", response["Allow"])

    def test_health_rejects_query_without_reflecting_it(self):
        self.error(self.client.get("/api/v1/health?token=SENSITIVE_FIXTURE_DO_NOT_ECHO"), 400, "INVALID_REQUEST")

    def test_default_permissions_are_closed(self):
        response = self.client.get("/_tests/private")
        self.error(response, 401, "AUTHENTICATION_REQUIRED")
        self.assertEqual(response["WWW-Authenticate"], "Session")

    def test_single_response_schema(self):
        response = self.client.post("/_tests/input", {"count": 1}, format="json")
        self.assertEqual(self.validate(response, "SingleResponse")["data"], {"count": 1})

    def test_list_total_unknown_and_decimal_string(self):
        response = self.client.get("/_tests/list")
        body = self.validate(response, "PageResponse")
        self.assertEqual(body["page"], {"next_cursor": None, "total": None})
        self.assertEqual(body["data"], [{"amount": "123.40"}])

    def test_malformed_json_is_400(self):
        self.error(self.client.post("/_tests/input", '{"count":', content_type="application/json"), 400, "INVALID_REQUEST")

    def test_semantic_validation_is_422(self):
        self.error(self.client.post("/_tests/input", {"count": -1}, format="json"), 422, "VALIDATION_ERROR")

    def test_unknown_media_is_415(self):
        self.error(self.client.post("/_tests/input", "raw", content_type="text/plain"), 415, "UNSUPPORTED_MEDIA_TYPE")

    def test_response_negotiation_is_406_safe_json(self):
        self.error(self.client.get("/api/v1/health", HTTP_ACCEPT="text/html"), 406, "NOT_ACCEPTABLE")

    def test_disallowed_host_is_json(self):
        self.error(self.client.get("/api/v1/health", HTTP_HOST="SENSITIVE_FIXTURE.invalid"), 400, "INVALID_REQUEST")

    def test_invalid_content_length(self):
        self.error(self.client.get("/api/v1/health", CONTENT_LENGTH="invalid"), 400, "INVALID_REQUEST")

    def test_body_limit(self):
        self.error(self.client.post("/_tests/input", "x" * (1024 * 1024 + 1), content_type="application/json"), 413, "PAYLOAD_TOO_LARGE")

    def test_missing_body_length_is_not_read_unbounded(self):
        from django.test import RequestFactory
        from bid_server.core.middleware import ApiBoundaryMiddleware
        request = RequestFactory().post("/_tests/input", "{}", content_type="application/json")
        request.META.pop("CONTENT_LENGTH")
        response = ApiBoundaryMiddleware(lambda req: self.fail("must stop before view"))(request)
        self.assertEqual(response.status_code, 411)

    def test_csrf_failure_is_safe_json(self):
        client = Client(enforce_csrf_checks=True, raise_request_exception=False)
        self.error(client.post("/_tests/csrf", "{}", content_type="application/json"), 403, "PERMISSION_DENIED")

    def test_framework_error_mapping_no_private_details(self):
        cases = {"validation": (422, "VALIDATION_ERROR"), "forbidden": (403, "PERMISSION_DENIED"),
                 "unauthenticated": (401, "AUTHENTICATION_REQUIRED"), "notfound": (404, "NOT_FOUND"),
                 "conflict": (409, "REVISION_CONFLICT"), "throttle": (429, "RATE_LIMITED"),
                 "unavailable": (503, "SERVICE_UNAVAILABLE"), "internal": (500, "INTERNAL_ERROR")}
        for kind, (status, code) in cases.items():
            with self.subTest(kind=kind):
                response = self.client.get("/_tests/fail/" + kind)
                self.error(response, status, code)
                if status == 429:
                    self.assertEqual(response["Retry-After"], "3")

    def test_django_error_handlers(self):
        for kind, status, code in [("internal", 500, "INTERNAL_ERROR"), ("forbidden", 403, "PERMISSION_DENIED"),
                                   ("large", 413, "PAYLOAD_TOO_LARGE")]:
            with self.subTest(kind=kind):
                self.error(self.client.get("/_tests/django/" + kind), status, code)

    def test_error_log_is_only_safe_metadata(self):
        stream = StringIO()
        import logging
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter("%(error_code)s %(request_id)s"))
        logger = logging.getLogger("bid_server.safe")
        with patch.object(logger, "handlers", [handler]):
            self.client.get("/_tests/fail/internal")
        self.assertIn("INTERNAL_ERROR", stream.getvalue())
        self.assertNotIn("SENSITIVE_FIXTURE", stream.getvalue())

    def test_openapi_scope_and_error_statuses(self):
        self.assertEqual(SPEC["openapi"], "3.1.0")
        self.assertEqual(len(SPEC["paths"]), 6)
        self.assertIn("400", SPEC["paths"]["/health"]["get"]["responses"])
        self.assertFalse(SPEC["paths"]["/health"]["get"]["security"])
        for schema in SPEC["components"]["schemas"].values():
            Draft202012Validator.check_schema(schema)
