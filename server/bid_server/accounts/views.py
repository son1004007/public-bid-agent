"""인증 API 계약.
목적: CSRF 발급, DB 세션 로그인/조회/암호변경/로그아웃만 수행한다.
경계: 입력 whitelist, Django hash/암호 validator, HMAC 로그인 제한, 서버 role만 사용.
부작용: 행 잠금 아래 인증 상태/epoch/감사를 원자 변경. 암호 변경 후 모든 세션 무효.
실패: 인증 실패는 고정401, 제한429, revision409, 필드422. 비밀 저장/로그/자동 재전송 금지.
관련: 문서03,17,18,20,29 및 tests.test_auth.
"""
import time
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.crypto import salted_hmac
from rest_framework import serializers
from rest_framework.exceptions import NotAuthenticated, Throttled, APIException
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import User, LoginBucket, AuthEvent

class Conflict(APIException):
    status_code = 409

class StrictInput(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - set(self.fields):
            raise serializers.ValidationError({"_schema": ["INVALID_VALUE"]})
        return super().to_internal_value(data)

class LoginInput(StrictInput):
    username = serializers.CharField(max_length=150, trim_whitespace=False)
    password = serializers.CharField(max_length=128, trim_whitespace=False, write_only=True)

class PasswordInput(StrictInput):
    current_password = serializers.CharField(max_length=128, trim_whitespace=False, write_only=True)
    new_password = serializers.CharField(min_length=12, max_length=128, trim_whitespace=False, write_only=True)
    expected_auth_epoch = serializers.IntegerField(min_value=1)


def parse(cls, request):
    value = cls(data=request.data)
    value.is_valid(raise_exception=True)
    return value.validated_data


def session_data(user):
    return {"user": {"id": str(user.pk), "display_name": user.display_name or user.username,
                     "capabilities": [] if user.must_change_password else
                         (["review", "decide", "manage_accounts", "manage_connections"] if user.role == "director" else ["review"])},
            "access": "PASSWORD_CHANGE_REQUIRED" if user.must_change_password else "FULL",
            "auth_epoch": user.auth_epoch}


def usable(user, now):
    return (user.is_active and not (user.locked_until and user.locked_until > now)
            and (not user.must_change_password or
                 (user.temporary_expires_at is not None and user.temporary_expires_at > now)))


class PublicAuthView(APIView):
    permission_classes = [AllowAny]

class CsrfView(PublicAuthView):
    def get(self, request):
        return Response({"csrf_token": get_token(request._request)})

class LoginView(PublicAuthView):
    def post(self, request):
        data = parse(LoginInput, request)
        # Proxy header는 배포 신뢰 경계 확정 전 사용하지 않는다.
        ip = request.META.get("REMOTE_ADDR", "unknown")
        keys = [(salted_hmac("login-ip", ip, algorithm="sha256").hexdigest(), settings.AUTH_IP_FAILURES),
                (salted_hmac("login-pair", ip + "\0" + data["username"], algorithm="sha256").hexdigest(), settings.AUTH_PAIR_FAILURES)]
        failed = False
        with transaction.atomic():
            buckets = []
            for key, limit in sorted(keys):
                LoginBucket.objects.get_or_create(key=key)
                bucket = LoginBucket.objects.select_for_update().get(key=key)
                buckets.append((bucket, limit))
            now = timezone.now()
            if any(bucket.locked_until and bucket.locked_until > now for bucket, _ in buckets):
                raise Throttled(wait=settings.AUTH_FAILURE_WINDOW)
            user = User.objects.select_for_update().filter(username=data["username"]).first()
            if user is None:
                make_password(data["password"])  # 미등록 사용자도 같은 hash 비용을 소비한다.
                valid_hash = False
            else:
                valid_hash = check_password(data["password"], user.password)
            if user is None or not valid_hash or not usable(user, now):
                failed = True
                for bucket, limit in buckets:
                    if (now - bucket.started_at).total_seconds() >= settings.AUTH_FAILURE_WINDOW:
                        bucket.started_at, bucket.failures = now, 0
                    bucket.failures += 1
                    if bucket.failures >= limit:
                        bucket.locked_until = now + timedelta(seconds=settings.AUTH_FAILURE_WINDOW)
                    bucket.save()
                AuthEvent.objects.create(actor=None, kind="login_failed", request_id=request.request_id)
            else:
                # User 행 잠금 유지 중 최종 상태 재대조와 세션 발급. 초기화/비활성화와 직렬화한다.
                request.session.flush()
                login(request._request, user, backend="django.contrib.auth.backends.ModelBackend")
                request.session["auth_epoch"] = user.auth_epoch
                request.session["login_at"] = request.session["last_seen"] = time.time()
                request.session.set_expiry(settings.AUTH_ABSOLUTE_SECONDS)
                AuthEvent.objects.create(actor=user, kind="login", request_id=request.request_id)
                for bucket, _ in buckets:
                    # IP bucket은 성공으로 지우지 않아 공격자가 타 계정 잠금을 우회하지 못한다.
                    if bucket.key == keys[1][0]:
                        bucket.failures, bucket.locked_until = 0, None
                        bucket.started_at = now
                        bucket.save()
        if failed:
            raise NotAuthenticated()
        return Response(session_data(user))

class SessionView(PublicAuthView):
    def get(self, request):
        user = request._request.user
        if not user.is_authenticated:
            raise NotAuthenticated()
        return Response(session_data(user))

class ChangePasswordView(PublicAuthView):
    def post(self, request):
        data = parse(PasswordInput, request)
        actor = request._request.user
        if not actor.is_authenticated:
            raise NotAuthenticated()
        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=actor.pk)
            if not usable(user, timezone.now()):
                raise NotAuthenticated()
            if user.auth_epoch != data["expected_auth_epoch"] or user.auth_epoch != request.session.get("auth_epoch"):
                raise Conflict()
            if not check_password(data["current_password"], user.password):
                raise serializers.ValidationError("invalid password")
            new = data["new_password"]
            if check_password(new, user.password):
                raise serializers.ValidationError("password reuse")
            try:
                validate_password(new, user)
            except ValidationError:
                raise serializers.ValidationError("invalid password")
            user.set_password(new)
            user.must_change_password = False
            user.temporary_expires_at = None
            user.password_changed_at = timezone.now()
            user.save(update_fields=["password", "must_change_password", "temporary_expires_at", "password_changed_at"])
            AuthEvent.objects.create(actor=user, kind="password_changed", request_id=request.request_id)
        logout(request._request)
        return Response(status=204)

class LogoutView(PublicAuthView):
    def post(self, request):
        if not isinstance(request.data, dict) or request.data:
            raise serializers.ValidationError("unexpected fields")
        logout(request._request)
        return Response(status=204)
