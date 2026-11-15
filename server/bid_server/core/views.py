"""health 설계 계약.

목적: 프로세스의 HTTP 응답 가능 여부만 공개한다. DB/Redis/모델 readiness가 아니다.
입력/출력: 인자 없는 GET -> 고정 status/scope. 원문/버전/설정/주소 노출 없음.
권한/부작용: 명시적 익명 read-only, 인증기/DB/파일/외부 호출 없음.
실패/재시도: 잘못된 query400, method405. health가 정상이어도 업무 API 사용 가능을 뜻하지 않음.
관련: server/openapi.json, docs/server-migration/28, tests/test_api.py.
"""
from pathlib import Path
from django.conf import settings
from django.http import HttpResponse
from rest_framework.exceptions import ParseError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    http_method_names = ["get", "head"]

    def get(self, request):
        if request.query_params:
            raise ParseError()
        return Response({"status": "ok", "scope": "process"})


class WorkspaceView(APIView):
    """사용자가 브라우저로 실제 서버와 연결된 워크스페이스를 테스트할 수 있는 HTML 뷰."""
    authentication_classes = []
    permission_classes = [AllowAny]
    http_method_names = ["get"]

    def get(self, request):
        repo_root = Path(__file__).resolve().parents[3]
        path = repo_root / "frontend" / "public" / "server-workspace-live.html"
        if not path.exists():
            path = repo_root / "frontend" / "public" / "server-workspace-preview.html"
        return HttpResponse(
            path.read_text(encoding="utf-8"),
            content_type="text/html; charset=utf-8",
        )
