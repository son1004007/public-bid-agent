import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("procurement", "0006_template_provenance"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="CostDepartment",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("active", models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name="CostMembership",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("department", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="procurement.costdepartment")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ("active", models.BooleanField(default=False)),
                ("can_manage_cost", models.BooleanField(default=False)),
            ],
            options={"constraints": [models.UniqueConstraint(fields=("department", "user"), name="cost_member_unique")]},
        ),
        migrations.CreateModel(
            name="DepartmentCostBasis",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("department", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="procurement.costdepartment")),
                ("revision", models.PositiveIntegerField()),
                ("period_start", models.DateField()),
                ("period_end", models.DateField()),
                ("valid_until", models.DateField()),
                ("labor_total_krw", models.PositiveBigIntegerField()),
                ("allocation_mm", models.DecimalField(max_digits=12, decimal_places=2)),
                ("available_mm", models.DecimalField(max_digits=12, decimal_places=2)),
                ("headcount", models.PositiveIntegerField()),
                ("minimum_headcount", models.PositiveIntegerField()),
                ("rate_rounding_krw", models.PositiveIntegerField()),
                ("capacity_rounding_mm", models.PositiveIntegerField()),
                ("approved_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ("approved", models.BooleanField(default=False)),
                ("current", models.BooleanField(default=False)),
            ],
            options={"constraints": [
                models.UniqueConstraint(fields=("department", "revision"), name="cost_basis_revision_unique"),
                models.UniqueConstraint(fields=("department",), condition=models.Q(current=True), name="cost_basis_one_current"),
                models.CheckConstraint(condition=models.Q(revision__gte=1, allocation_mm__gt=0,
                    available_mm__gte=0, available_mm__lte=models.F("allocation_mm"),
                    labor_total_krw__gt=0, headcount__gte=1, minimum_headcount__gte=2,
                    rate_rounding_krw__gt=0, capacity_rounding_mm__gt=0,
                    period_end__gte=models.F("period_start")), name="cost_basis_valid_values"),
            ]},
        ),
    ]
