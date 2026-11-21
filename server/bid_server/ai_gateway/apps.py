"""Django app for per-user provider status and persistent CLI session bindings."""
from django.apps import AppConfig


class AIGatewayConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "bid_server.ai_gateway"
    verbose_name = "사용자별 AI 연결 및 세션 메타데이터"
