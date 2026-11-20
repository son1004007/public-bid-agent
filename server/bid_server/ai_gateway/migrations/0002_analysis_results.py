"""AGW-05/09 immutable-snapshot run and append-only result history metadata.

No credential/token columns, model auto-execution, or private source exports.
"""
import uuid
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ai_gateway", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("procurement", "0008_shared_review"),
    ]

    operations = [
        migrations.CreateModel(
            name="AnalysisRun",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False,
                                        primary_key=True, serialize=False)),
                ("corpus_snapshot_id", models.UUIDField()),
                ("request_key", models.UUIDField()),
                ("input_digest", models.CharField(max_length=64)),
                ("prompt_version", models.CharField(max_length=64)),
                ("snapshot_sha256", models.CharField(max_length=64)),
                ("snapshot_payload", models.JSONField()),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("owner", models.ForeignKey(
                    to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT,
                    related_name="ai_analysis_runs",
                )),
                ("notice_version", models.ForeignKey(
                    to="procurement.noticeversion",
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="ai_analysis_runs",
                )),
            ],
            options={"constraints": [
                models.UniqueConstraint(
                    fields=("owner", "notice_version", "request_key"),
                    name="agw_one_run_per_request_key",
                ),
            ]},
        ),
        migrations.CreateModel(
            name="AnalysisRevision",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False,
                                        primary_key=True, serialize=False)),
                ("provider", models.CharField(max_length=10, choices=[
                    ("CODEX", "Codex"), ("CLAUDE", "Claude Code"),
                ])),
                ("revision_seq", models.PositiveIntegerField()),
                ("result_sha256", models.CharField(max_length=64)),
                ("validated_payload", models.JSONField()),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("run", models.ForeignKey(
                    to="ai_gateway.analysisrun",
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="revisions",
                )),
            ],
            options={"constraints": [
                models.UniqueConstraint(
                    fields=("run", "provider", "result_sha256"),
                    name="agw_unique_result_digest",
                ),
                models.UniqueConstraint(
                    fields=("run", "provider", "revision_seq"),
                    name="agw_unique_result_revision",
                ),
                models.CheckConstraint(
                    condition=models.Q(revision_seq__gte=1),
                    name="agw_revision_seq_positive",
                ),
            ]},
        ),
    ]
