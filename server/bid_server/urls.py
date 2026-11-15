"""격리 URL 계약: health와 SM03 인증 및 SM05 작업 API만 연결하며 기존 서비스/데이터/admin은 연결하지 않는다."""
from django.urls import path, include
from .core.views import HealthView, WorkspaceView

from .accounts.views import CsrfView, LoginView, SessionView, ChangePasswordView, LogoutView
urlpatterns = [
    path("", WorkspaceView.as_view(), name="workspace-index"),
    path("workspace", WorkspaceView.as_view(), name="workspace"),
    path("api/v1/health", HealthView.as_view(), name="health"),
    path("api/v1/", include("bid_server.jobs.urls")),
    path("api/v1/", include("bid_server.procurement.urls")),
]
for route, view in [("csrf", CsrfView), ("login", LoginView), ("session", SessionView),
                    ("change-password", ChangePasswordView), ("logout", LogoutView)]:
    urlpatterns.append(path("api/v1/auth/" + route, view.as_view(), name="auth-" + route))
handler400 = "bid_server.core.errors.bad_request"
handler403 = "bid_server.core.errors.permission_denied"
handler404 = "bid_server.core.errors.not_found"
handler500 = "bid_server.core.errors.server_error"
