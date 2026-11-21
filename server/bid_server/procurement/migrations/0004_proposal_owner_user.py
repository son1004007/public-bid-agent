"""Preserve existing workspaces without guessing ownership."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("procurement", "0003_proposal_proposalrevision_proposal_current_revision_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.AddField(
            model_name="proposal",
            name="owner_user",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="owned_proposals", to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
