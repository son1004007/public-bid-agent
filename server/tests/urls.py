"""테스트 전용 URL fixture. 운영 URL에는 포함하지 않으며 합성 예외만 만든다."""
from decimal import Decimal
from django.core.exceptions import PermissionDenied, RequestDataTooBig
from django.http import JsonResponse
from django.urls import path
from django.views.decorators.csrf import csrf_protect
from rest_framework import exceptions, serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from bid_server.core.responses import PageResponse
from bid_server.urls import urlpatterns as production_urls

SENTINEL = "SENSITIVE_FIXTURE_DO_NOT_ECHO"


class EchoInput(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        class Input(serializers.Serializer):
            count = serializers.IntegerField(min_value=1)
        value = Input(data=request.data)
        value.is_valid(raise_exception=True)
        return Response(value.validated_data)


class Private(APIView):
    def get(self, request):
        return Response({"should_not": "be_accessible"})


class ListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return PageResponse([{"amount": Decimal("123.40")}])


class Fail(APIView):
    permission_classes = [AllowAny]

    def get(self, request, kind):
        mapping = {
            "internal": RuntimeError(SENTINEL),
            "validation": exceptions.ValidationError({"secret": SENTINEL}),
            "forbidden": exceptions.PermissionDenied(SENTINEL),
            "unauthenticated": exceptions.NotAuthenticated(SENTINEL),
            "notfound": exceptions.NotFound(SENTINEL),
            "conflict": exceptions.APIException(SENTINEL),
            "throttle": exceptions.Throttled(wait=3, detail=SENTINEL),
            "unavailable": exceptions.APIException(SENTINEL),
        }
        exc = mapping[kind]
        if kind == "conflict":
            exc.status_code = 409
        if kind == "unavailable":
            exc.status_code = 503
        raise exc


def django_failure(request, kind):
    if kind == "internal":
        raise RuntimeError(SENTINEL)
    if kind == "large":
        raise RequestDataTooBig(SENTINEL)
    raise PermissionDenied(SENTINEL)


@csrf_protect
def csrf_target(request):
    return JsonResponse({"unreachable_without_token": True})


urlpatterns = production_urls + [
    path("_tests/input", EchoInput.as_view()),
    path("_tests/private", Private.as_view()),
    path("_tests/list", ListView.as_view()),
    path("_tests/fail/<str:kind>", Fail.as_view()),
    path("_tests/django/<str:kind>", django_failure),
    path("_tests/csrf", csrf_target),
]
handler400 = "bid_server.core.errors.bad_request"
handler403 = "bid_server.core.errors.permission_denied"
handler404 = "bid_server.core.errors.not_found"
handler500 = "bid_server.core.errors.server_error"
