"""Explicit read-only routing; no provider token/login/reset endpoint."""
from django.urls import path
from .views import ProviderStatusView

urlpatterns = [
    path("ai/providers", ProviderStatusView.as_view(), name="ai-provider-status"),
]
