"""세션 및 강제 암호 변경 경계 계약.
입력: Django DB 세션. 출력: 허용된 URL 또는 안전한401/403.
경계: 익명으로 바뀐 잔존 인증 세션도 폐기. URL prefix/클라이언트 역할 신뢰 금지.
부작용: 세션 만료/epoch 불일치 시 flush, 유효 요청의 idle 시각 갱신.
실패/재시도: 자동 인증 재시도 없음. 모든 unsafe 요청은 APIView 예외와 무관하게 CSRF 검사.
관련: 문서03,18,29 및 tests.test_auth.
"""
import time
from django.conf import settings
from django.contrib.auth import SESSION_KEY
from django.middleware.csrf import CsrfViewMiddleware
from django.urls import resolve, Resolver404
from django.utils import timezone
from bid_server.core.errors import json_error

class StrictCsrfMiddleware(CsrfViewMiddleware):
    def process_view(self, request, callback, callback_args, callback_kwargs):
        return super().process_view(request, lambda request: None, callback_args, callback_kwargs)

class AuthGateMiddleware:
    LIMITED = {"auth-csrf", "auth-session", "auth-change-password", "auth-logout"}
    PUBLIC = {"health", "auth-csrf", "auth-login", "auth-logout", "workspace-index", "workspace"}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            name = resolve(request.path_info).url_name
        except Resolver404:
            name = None
        # Public, data-free HTML shell is needed to recover a limited or expired session.
        shell = request.method == "GET" and name in {"workspace-index", "workspace"}
        had_auth = SESSION_KEY in request.session
        user = request.user
        if user.is_authenticated:
            now = time.time()
            login = request.session.get("login_at")
            last = request.session.get("last_seen")
            epoch = request.session.get("auth_epoch")
            invalid = (not user.is_active or (user.locked_until and user.locked_until > timezone.now())
                       or type(epoch) is not int or epoch != user.auth_epoch
                       or type(login) not in (int, float) or type(last) not in (int, float)
                       or not (0 <= login <= now and 0 <= last <= now))
            if not invalid:
                invalid = (last < login or now < login or now < last or now-login >= settings.AUTH_ABSOLUTE_SECONDS
                           or now-last >= settings.AUTH_IDLE_SECONDS
                           or (user.must_change_password and (now-login >= settings.AUTH_LIMITED_SECONDS
                               or not user.temporary_expires_at or user.temporary_expires_at <= timezone.now())))
            if invalid:
                request.session.flush()
                from django.contrib.auth.models import AnonymousUser
                request.user = AnonymousUser()
                if shell:
                    return self.get_response(request)
                return json_error(request, 401)
            request.session["last_seen"] = now
            if user.must_change_password and name not in self.LIMITED and not shell:
                return json_error(request, 403, password_change=True)
        else:
            if had_auth:
                request.session.flush()
                if shell:
                    return self.get_response(request)
                return json_error(request, 401)
            if name is not None and name not in self.PUBLIC:
                return json_error(request, 401)
        return self.get_response(request)
