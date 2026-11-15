"""합성 권한 endpoint. 실제 업무 결정/계정 수정 기능이 아니다."""
from django.urls import path
from rest_framework.response import Response
from rest_framework.views import APIView
from bid_server.core.permissions import DirectorOnly
from bid_server.urls import urlpatterns as production

class Business(APIView):
    def get(self, request):
        return Response({"fixture": True})
    def post(self, request):
        return Response({"fixture": True})

class Director(Business):
    permission_classes = [DirectorOnly]

urlpatterns = production + [path("fixture/business", Business.as_view(), name="fixture-business"),
    path("fixture/decision", Director.as_view(), name="fixture-decision"),
    path("fixture/accounts", Director.as_view(), name="fixture-accounts"),
    path("fixture/secrets", Director.as_view(), name="fixture-secrets")]
