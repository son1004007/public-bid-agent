"""Django 외곽 API 경계 계약.

목적: 프레임워크 밖의 Host/본문/CSRF/URL 오류에도 서버request_id와 안전 JSON을 유지한다.
입력/출력: HTTP request -> bounded body/고정 오류/보안 header response.
경계: client request-id, Host,Content-Length를 신뢰하지 않는다. 본문을 로그에 넣지 않는다.
부작용: 요청별 제한 메모리 읽기만. 파일/업무 데이터 저장과 DB 접속 없음.
실패: 잘못된 길이400/없는길이411/초과413. Django의 ASGI 사전 body 수신은 ingress 제한이 별도 필요.
관련: docs/server-migration/18,28, tests/test_api.py.
"""
from uuid import uuid4
from django.conf import settings
from django.core.exceptions import DisallowedHost, RequestDataTooBig
from io import BytesIO
from .errors import json_error


class ApiBoundaryMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = str(uuid4())
        try:
            request.get_host()
        except DisallowedHost:
            return self.finish(request, json_error(request, 400))
        raw_length = request.META.get("CONTENT_LENGTH", "")
        if raw_length and (not raw_length.isascii() or not raw_length.isdigit() or len(raw_length) > 12):
            return self.finish(request, json_error(request, 400))
        limit = settings.DATA_UPLOAD_MAX_MEMORY_SIZE
        if raw_length and int(raw_length) > limit:
            return self.finish(request, json_error(request, 413))
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            if not raw_length:
                return self.finish(request, json_error(request, 411))
            try:
                body = request.read(limit + 1)
                if len(body) > limit:
                    return self.finish(request, json_error(request, 413))
                # 하위 parser와 CSRF는 같은 제한 검증된 bytes를 읽는다.
                request._body = body
                request._stream = BytesIO(body)
            except RequestDataTooBig:
                return self.finish(request, json_error(request, 413))
        response = self.get_response(request)
        if response.status_code >= 400 and not response.get("Content-Type", "").startswith("application/json"):
            original = response
            response = json_error(request, original.status_code)
            for header in ("Allow", "Retry-After", "WWW-Authenticate"):
                if header in original:
                    response[header] = original[header]
        return self.finish(request, response)

    @staticmethod
    def finish(request, response):
        response["X-Request-ID"] = request.request_id
        response["Cache-Control"] = "no-store"
        response["X-Content-Type-Options"] = "nosniff"
        response["X-Frame-Options"] = "DENY"
        return response
