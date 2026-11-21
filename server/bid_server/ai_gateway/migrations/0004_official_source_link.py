"""P0-02 separately bind immutable official raw HTTP bytes to existing source versions.

Never overwrite NoticeVersion.source_payload_digest (canonical importer metadata).
No historical data migration, approval, model dispatch, or private material import.
PostgreSQL blocks normal UPDATE/DELETE even via raw SQL; SQLite is test-only.
"""
import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def install_postgres_immutable_trigger(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("""
        CREATE FUNCTION agw_official_source_link_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'IMMUTABLE_OFFICIAL_SOURCE_LINK';
        END
        $$;
    """)
    schema_editor.execute("""
        CREATE TRIGGER agw_official_source_link_no_mutation
        BEFORE UPDATE OR DELETE ON ai_gateway_officialsourcelink
        FOR EACH ROW EXECUTE FUNCTION agw_official_source_link_immutable();
    """)


def remove_postgres_immutable_trigger(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("""
        DROP TRIGGER IF EXISTS agw_official_source_link_no_mutation
        ON ai_gateway_officialsourcelink;
    """)
    schema_editor.execute("""
        DROP FUNCTION IF EXISTS agw_official_source_link_immutable();
    """)


class Migration(migrations.Migration):
    dependencies = [
        ("ai_gateway", "0003_public_rfp_attestation"),
        ("procurement", "0008_shared_review"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="OfficialSourceLink",
            fields=[
                ("id", models.UUIDField(
                    primary_key=True, serialize=False, editable=False, default=uuid.uuid4,
                )),
                ("capture_id", models.CharField(max_length=64, unique=True)),
                ("official_revision", models.CharField(max_length=5)),
                ("metadata_canonical_sha256", models.CharField(max_length=64)),
                ("raw_notice_sha256", models.CharField(max_length=64)),
                ("raw_notice_size_bytes", models.PositiveIntegerField()),
                ("raw_notice_storage_key", models.CharField(max_length=160)),
                ("manifest_storage_key", models.CharField(max_length=180)),
                ("document_sha256", models.CharField(max_length=64)),
                ("document_size_bytes", models.PositiveIntegerField()),
                ("existing_document_storage_key", models.CharField(max_length=180)),
                ("linked_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("notice_version", models.ForeignKey(
                    to="procurement.noticeversion", related_name="official_source_links",
                    on_delete=django.db.models.deletion.PROTECT,
                )),
                ("document_version", models.OneToOneField(
                    to="procurement.documentversion", related_name="official_source_link",
                    on_delete=django.db.models.deletion.PROTECT,
                )),
                ("linked_by", models.ForeignKey(
                    to=settings.AUTH_USER_MODEL, related_name="official_source_links",
                    on_delete=django.db.models.deletion.PROTECT,
                )),
            ],
        ),
        migrations.RunPython(
            install_postgres_immutable_trigger,
            remove_postgres_immutable_trigger,
        ),
    ]
