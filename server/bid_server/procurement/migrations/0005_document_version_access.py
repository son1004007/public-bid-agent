"""Require explicit document version classification; no legacy auto-sharing."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("procurement", "0004_proposal_owner_user"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.AddField(
            model_name="documentversion", name="owner_user",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="owned_document_versions", to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="documentversion", name="shared_read_approved",
            field=models.BooleanField(default=False),
        ),
    ]
