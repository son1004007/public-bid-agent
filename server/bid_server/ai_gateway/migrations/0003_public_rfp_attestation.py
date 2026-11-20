"""AGW-05 deny-by-default reviewed provenance for official public RFP input.

No existing attachment is automatically marked PUBLIC or exportable.
"""
import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("ai_gateway", "0002_analysis_results"),
        ("procurement", "0008_shared_review"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PublicRfpAttestation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False,
                                        primary_key=True, serialize=False)),
                ("notice_source_sha256", models.CharField(max_length=64)),
                ("document_sha256", models.CharField(max_length=64)),
                ("source_url", models.TextField()),
                ("packet_approved", models.BooleanField(default=False)),
                ("provider_export_approved", models.BooleanField(default=False)),
                ("revoked", models.BooleanField(default=False)),
                ("reviewed_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("document_version", models.OneToOneField(
                    to="procurement.documentversion", related_name="public_rfp_attestation",
                    on_delete=django.db.models.deletion.PROTECT,
                )),
                ("approved_by", models.ForeignKey(
                    to=settings.AUTH_USER_MODEL, related_name="public_rfp_attestations",
                    on_delete=django.db.models.deletion.PROTECT,
                )),
            ],
        ),
    ]
