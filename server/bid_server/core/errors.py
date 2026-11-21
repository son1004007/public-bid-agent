"""API 오류 경계 설계 계약.

목적/책임: DRF와 Django 오류를 공통 안전 JSON으로 변환한다.
입력/출력: 예외/서버 상태 -> 고정 code/message/fields/retryable 및 request_id.
경계: 예외 문자열/입력값/traceback/SQL/비밀은 응답과 로그에 전달하지 않는다.
부작용: server UUID와 code만 안전 logger로 기록. 저장/재시도 없음.
불변조건: JSON400, 필드의미422, 미디어415. 알 수 없는 오류는500으로 닫는다.
관련: docs/server-migration/18,28; tests/test_api.py.
"""
import logging
from uuid import uuid4

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied, RequestDataTooBig
from django.http import Http404, JsonResponse
from rest_framework import exceptions
from rest_framework.response import Response

ERRORS = {
    400: ("INVALID_REQUEST", "요청 형식을 확인해 주세요."),
    401: ("AUTHENTICATION_REQUIRED", "로그인이 필요합니다."),
    403: ("PERMISSION_DENIED", "요청을 수행할 권한이 없습니다."),
    404: ("NOT_FOUND", "요청한 항목을 찾을 수 없습니다."),
    405: ("METHOD_NOT_ALLOWED", "허용되지 않는 요청 방식입니다."),
    406: ("NOT_ACCEPTABLE", "지원하는 응답 형식을 요청해 주세요."),
    409: ("REVISION_CONFLICT", "변경된 자료를 다시 확인해 주세요."),
    411: ("LENGTH_REQUIRED", "요청 본문 길이가 필요합니다."),
    413: ("PAYLOAD_TOO_LARGE", "요청 크기 한도를 초과했습니다."),
    415: ("UNSUPPORTED_MEDIA_TYPE", "지원하지 않는 입력 형식입니다."),
    422: ("VALIDATION_ERROR", "입력 항목을 확인해 주세요."),
    429: ("RATE_LIMITED", "요청 한도를 확인해 주세요."),
    500: ("INTERNAL_ERROR", "요청을 처리할 수 없습니다."),
    503: ("SERVICE_UNAVAILABLE", "서비스를 사용할 수 없습니다."),
}


def request_id(request) -> str:
    if not getattr(request, "request_id", None):
        request.request_id = str(uuid4())
    return request.request_id


def error_data(status: int) -> dict:
    code, message = ERRORS.get(status, ERRORS[500])
    # 필드 오류의 원문을 노출하지 않는다. 신뢰한 serializer별 매핑은 추후 명시한다.
    fields = {"_schema": ["INVALID_VALUE"]} if status == 422 else {}
    return {"error": {"code": code, "message": message, "fields": fields, "retryable": False}}


def safe_log(request, status: int) -> None:
    if status >= 500:
        logging.getLogger("bid_server.safe").error(
            "request_failed", extra={"error_code": ERRORS.get(status, ERRORS[500])[0],
                                     "request_id": request_id(request)})


def json_error(request, status: int, *, password_change=False):
    payload = error_data(status)
    if password_change:
        payload["error"].update(code="PASSWORD_CHANGE_REQUIRED", message="먼저 비밀번호를 변경해 주세요.")
    payload["request_id"] = request_id(request)
    safe_log(request, status)
    response = JsonResponse(payload, status=status, json_dumps_params={"ensure_ascii": False})
    response["X-Request-ID"] = payload["request_id"]
    response["Cache-Control"] = "no-store"
    return response


def exception_handler(exc, context):
    request = context["request"]
    if isinstance(exc, exceptions.NotAuthenticated):
        status = 401
    elif isinstance(exc, exceptions.ValidationError):
        status = 422
    elif isinstance(exc, RequestDataTooBig):
        status = 413
    elif isinstance(exc, Http404):
        status = 404
    elif isinstance(exc, DjangoPermissionDenied):
        status = 403
    elif isinstance(exc, exceptions.APIException):
        status = exc.status_code if exc.status_code in ERRORS else 500
    else:
        status = 500
    safe_log(request, status)
    response = Response(error_data(status), status=status)
    response.contract_error = True
    if status == 401:
        response["WWW-Authenticate"] = "Session"
    if isinstance(exc, exceptions.Throttled) and exc.wait is not None:
        import math
        response["Retry-After"] = str(math.ceil(exc.wait))
    return response


def bad_request(request, exception=None):
    return json_error(request, 413 if isinstance(exception, RequestDataTooBig) else 400)


def permission_denied(request, exception=None):
    return json_error(request, 403)


def not_found(request, exception=None):
    return json_error(request, 404)


def server_error(request):
    return json_error(request, 500)


def csrf_failure(request, reason=""):
    return json_error(request, 403)
