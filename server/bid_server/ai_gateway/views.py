"""Authenticated, user-scoped, read-only AI profile status API."""
from rest_framework.response import Response
from rest_framework.views import APIView
from bid_server.core.permissions import ClosedUntilAuthentication
from .service import provider_status_for_user


class ProviderStatusView(APIView):
    permission_classes = [ClosedUntilAuthentication]

    def get(self, request):
        response = Response(provider_status_for_user(request.user))
        response["Cache-Control"] = "no-store"
        return response
