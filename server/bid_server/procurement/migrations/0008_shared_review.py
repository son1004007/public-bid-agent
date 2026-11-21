import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("procurement", "0007_aggregate_cost"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.AddField(model_name="costmembership", name="can_decide", field=models.BooleanField(default=False)),
        migrations.CreateModel(
            name="SharedBidReviewEvent",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, serialize=False, editable=False)),
                ("department", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="procurement.costdepartment")),
                ("notice_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="procurement.noticeversion")),
                ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ("revision", models.PositiveIntegerField()),
                ("kind", models.CharField(max_length=20)),
                ("payload", models.JSONField(default=dict)),
                ("basis", models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to="procurement.departmentcostbasis")),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={"constraints": [
                models.UniqueConstraint(fields=("department", "notice_version", "revision"), name="shared_review_revision_unique"),
                models.CheckConstraint(condition=models.Q(revision__gte=1, kind__in=["OPINION", "ESTIMATE", "DECISION"]),
                    name="shared_review_event_valid"),
            ]},
        ),
    ]
