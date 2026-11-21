"""권한 계약: 세션 인증과 암호 변경을 강제하고 업무 역할은 DB에서 읽는다.
경계: client role와 is_superuser는 업무 권한을 부여하지 않는다. 부작용 없음.
관련: 문서03,18,29 및 A01/A02 테스트.
"""
from rest_framework.exceptions import NotAuthenticated, PermissionDenied
from rest_framework.permissions import BasePermission

class ClosedUntilAuthentication(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise NotAuthenticated()
        return not request.user.must_change_password

class DirectorOnly(ClosedUntilAuthentication):
    def has_permission(self, request, view):
        if not super().has_permission(request, view) or request.user.role != "director":
            raise PermissionDenied()
        return True
