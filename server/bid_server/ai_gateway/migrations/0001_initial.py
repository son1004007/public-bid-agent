"""AGW-01 initial schema; no tokens, passwords or model invocations."""
import uuid
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("procurement", "0008_shared_review"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProviderProfile",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False,
                                        primary_key=True, serialize=False)),
                ("provider", models.CharField(max_length=10, choices=[
                    ("CODEX", "Codex"), ("CLAUDE", "Claude Code"),
                ])),
                ("enabled", models.BooleanField(default=False)),
                ("auth_state", models.CharField(max_length=16, default="UNKNOWN", choices=[
                    ("UNKNOWN", "Unknown"), ("AUTH_REQUIRED", "Sign in required"),
                    ("AUTHENTICATED", "Authenticated"),
                ])),
                ("policy_approved", models.BooleanField(default=False)),
                ("runtime_isolated", models.BooleanField(default=False)),
                ("data_export_approved", models.BooleanField(default=False)),
                ("quota_available", models.BooleanField(default=False)),
                ("verified_auth_epoch", models.PositiveBigIntegerField(default=0)),
                ("verified_at", models.DateTimeField(null=True, blank=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("user", models.ForeignKey(to=settings.AUTH_USER_MODEL,
                                           on_delete=django.db.models.deletion.CASCADE,
                                           related_name="ai_provider_profiles")),
            ],
            options={"constraints": [
                models.UniqueConstraint(fields=("user", "provider"),
                                        name="agw_user_provider_unique"),
            ]},
        ),
        migrations.CreateModel(
            name="SessionBinding",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False,
                                        primary_key=True, serialize=False)),
                ("purpose", models.CharField(max_length=16, default="ANALYSIS", choices=[
                    ("ANALYSIS", "Independent first pass"),
                    ("ISSUE_REVIEW", "Disagreement review"),
                ])),
                ("issue_key", models.CharField(max_length=64, blank=True, default="")),
                ("provider_session_id", models.UUIDField(null=True, blank=True)),
                ("state", models.CharField(max_length=20, default="NEW", choices=[
                    ("NEW", "New"), ("PAUSED", "Ready to resume"),
                    ("RECOVERABLE", "Recoverable"), ("RESET_REQUIRED", "Reset required"),
                    ("ARCHIVED", "Historical"),
                ])),
                ("is_current", models.BooleanField(default=True)),
                ("lease_owner", models.CharField(max_length=80, blank=True, default="")),
                ("lease_epoch", models.PositiveBigIntegerField(default=1)),
                ("lease_expires_at", models.DateTimeField(null=True, blank=True)),
                ("last_success_at", models.DateTimeField(null=True, blank=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("notice", models.ForeignKey(to="procurement.notice",
                                             on_delete=django.db.models.deletion.PROTECT,
                                             related_name="ai_session_bindings")),
                ("last_notice_version", models.ForeignKey(
                    to="procurement.noticeversion", on_delete=django.db.models.deletion.PROTECT,
                    null=True, blank=True, related_name="+",
                )),
                ("profile", models.ForeignKey(to="ai_gateway.providerprofile",
                                              on_delete=django.db.models.deletion.PROTECT,
                                              related_name="session_bindings")),
            ],
            options={"constraints": [
                models.UniqueConstraint(
                    fields=("profile", "notice", "purpose", "issue_key"),
                    condition=models.Q(is_current=True),
                    name="agw_one_current_session_per_context",
                ),
                models.CheckConstraint(
                    condition=(models.Q(purpose="ANALYSIS", issue_key="")
                               | (models.Q(purpose="ISSUE_REVIEW") & ~models.Q(issue_key=""))),
                    name="agw_issue_key_matches_purpose",
                ),
                models.CheckConstraint(
                    condition=models.Q(lease_epoch__gte=1),
                    name="agw_session_lease_epoch_positive",
                ),
            ]},
        ),
    ]
