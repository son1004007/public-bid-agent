"""사용자 저장 계약.
목적: 업무 역할과 세션 폐기 epoch, 임시 암호 유효기간을 DB에 결속한다.
경계: 기술 superuser는 업무 권한 예외가 아니다. 민감 변경은 save 경로만 사용한다.
부작용: 기존 사용자 보안 필드 변경 시 행 잠금과 단조 epoch 갱신. bulk update 금지.
실패: transaction 실패는 전체 rollback. 인증정보/원문 로그 없음.
관련: 문서17,03,29 및 tests.test_auth.
"""
import uuid
from datetime import timedelta
from django.contrib.auth.models import AbstractUser
from django.db import models, transaction
from django.utils import timezone


def temporary_deadline():
    return timezone.now() + timedelta(hours=24)


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(max_length=8, choices=[("director", "director"), ("lead", "lead")], default="lead")
    display_name = models.CharField(max_length=150, blank=True)
    must_change_password = models.BooleanField(default=True)
    auth_epoch = models.PositiveBigIntegerField(default=1)
    temporary_expires_at = models.DateTimeField(null=True, default=temporary_deadline)
    password_changed_at = models.DateTimeField(null=True)
    locked_until = models.DateTimeField(null=True)
    SECURITY_FIELDS = {"password", "role", "is_active", "must_change_password", "temporary_expires_at", "locked_until"}

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(role__in=["director", "lead"]), name="user_role_valid"),
                       models.CheckConstraint(condition=models.Q(auth_epoch__gte=1), name="user_epoch_positive")]

    def save(self, *args, **kwargs):
        if self._state.adding:
            return super().save(*args, **kwargs)
        using = kwargs.get("using") or self._state.db or "default"
        fields = kwargs.get("update_fields")
        with transaction.atomic(using=using):
            old = type(self).objects.using(using).select_for_update().get(pk=self.pk)
            selected = self.SECURITY_FIELDS if fields is None else self.SECURITY_FIELDS.intersection(fields)
            changed = any(getattr(old, key) != getattr(self, key) for key in selected)
            if self.auth_epoch < old.auth_epoch:
                raise ValueError("stale security revision")
            self.auth_epoch = max(self.auth_epoch, old.auth_epoch + int(changed))
            if fields is not None:
                kwargs["update_fields"] = set(fields) | {"auth_epoch"}
            return super().save(*args, **kwargs)


class LoginBucket(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    failures = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(default=timezone.now)
    locked_until = models.DateTimeField(null=True)


class AuthEvent(models.Model):
    actor = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    kind = models.CharField(max_length=32)
    request_id = models.UUIDField()
    created_at = models.DateTimeField(auto_now_add=True)
