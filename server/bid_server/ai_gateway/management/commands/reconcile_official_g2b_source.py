"""P0-02 operator-only offline raw-source reconciliation, default read-only.

Runs only on a trusted/admin PostgreSQL console with approved private mounts.
It does NOT download G2B, change a NoticeVersion/DocumentVersion or approve
PUBLIC sharing/model export. Operator ID is audit metadata, NOT login proof:
the terminal/OS/DB service identity must already be individually authorized.
"""
import json
import uuid

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from bid_server.procurement.models import DocumentVersion
from bid_server.ai_gateway.official_source_link import (
    SourceLinkError, load_notice_only_source_files,
    reconcile_official_source_capture,
)


class Command(BaseCommand):
    help = "Read-only verify or explicitly link official G2B raw capture (trusted operator)."
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--expected-db-name", required=True)
        parser.add_argument("--operator-id", required=True, type=uuid.UUID)
        parser.add_argument("--document-version-id", required=True, type=uuid.UUID)
        parser.add_argument("--capture-id", required=True)
        parser.add_argument("--capture-root", required=True)
        parser.add_argument("--private-media-root", required=True)
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        try:
            if connection.vendor != "postgresql":
                raise SourceLinkError("POSTGRESQL_REQUIRED")
            expected_name = options["expected_db_name"]
            if (type(expected_name) is not str
                    or not 1 <= len(expected_name) <= 63
                    or not all(c.isalnum() or c in "_-" for c in expected_name)):
                raise SourceLinkError("DATABASE_TARGET_DENIED")
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_database()")
                if cursor.fetchone()[0] != expected_name:
                    raise SourceLinkError("DATABASE_TARGET_DENIED")
            actor = get_user_model().objects.get(pk=options["operator_id"])
            doc = DocumentVersion.objects.get(pk=options["document_version_id"])
            raw_notice, raw_document, manifest = load_notice_only_source_files(
                capture_root=options["capture_root"],
                private_media_root=options["private_media_root"],
                capture_id=options["capture_id"],
                document_sha256=doc.sha256,
            )
            result = reconcile_official_source_capture(
                actor=actor,
                notice_version_id=doc.notice_version_id,
                document_version_id=doc.pk,
                raw_notice_payload_bytes=raw_notice,
                raw_document_bytes=raw_document,
                manifest_bytes=manifest,
                apply=bool(options["apply"]),
            )
            self.stdout.write(json.dumps({
                "status": (
                    "SOURCE_LINK_APPLIED" if options["apply"]
                    else "SOURCE_LINK_REPLAY_VERIFIED" if result else "SOURCE_LINK_DRY_RUN_VALID"
                ),
                "raw_notice_sha256": __import__("hashlib").sha256(raw_notice).hexdigest(),
                "doc_bytes_copied": False,
                "public_approved": False,
                "model_export_approved": False,
            }, sort_keys=True))
        except (
            SourceLinkError, ValueError, OSError, TypeError,
            get_user_model().DoesNotExist, DocumentVersion.DoesNotExist,
        ):
            raise CommandError("OFFICIAL_SOURCE_LINK_REJECTED") from None
