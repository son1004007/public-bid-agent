"""P0-02: synthetic-only immutable raw-vs-canonical notice/source mapping tests.

No real G2B API, private bytes, credentials, NAS migration or model calls.
"""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import uuid
import zipfile

from django.db import DatabaseError, connection, transaction
from django.test import TestCase
from django.utils import timezone

from ai_gateway_core.official_g2b_capture import CAPTURE_DIR
from bid_server.accounts.models import User
from bid_server.ai_gateway.models import OfficialSourceLink, PublicRfpAttestation
from bid_server.ai_gateway.official_source_link import (
    SourceLinkError, load_notice_only_source_files,
    reconcile_official_source_capture, verify_official_source_link,
)
from bid_server.procurement.models import (
    Document, DocumentFreshness, DocumentVersion, Notice, NoticeVersion,
)

NUMBER = "R26BK00999999"  # Fictional/never fetched.
REVISION = "000"
TITLE = "Synthetic-only official-looking RFP"
URL = (
    "https://www.g2b.go.kr/pn/pnp/pnpe/UntyAtchFile/downloadFile.do?"
    "bidPbancNo=R26BK00999999&bidPbancOrd=000"
    "&fileSeq=3&prcmBsneSeCd=05&fileType="
)
PWD = "synthetic-credential-not-used-live"


def _sha(payload):
    return hashlib.sha256(payload).hexdigest()


def _notice_bytes(extra=None):
    row = {
        "bidNtceNo": NUMBER, "bidNtceOrd": "000", "bidNtceNm": TITLE,
    }
    if extra:
        row.update(extra)
    return json.dumps({"response": {
        "header": {"resultCode": "00"},
        "body": {"items": {"item": [row]}},
    }}, sort_keys=True, separators=(",", ":")).encode()


def _document_bytes():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, mode="w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("Contents/section0.xml", "<section>SYNTHETIC ONLY</section>")
    return stream.getvalue()


def _manifest(raw_notice, raw_doc):
    n_sha, d_sha = _sha(raw_notice), _sha(raw_doc)
    capture_id = _sha(f"{n_sha}:{d_sha}:{NUMBER}:{REVISION}".encode())
    return {
        "status": "UNATTESTED_RAW_CAPTURE",
        "notice_number": NUMBER,
        "source_revision": REVISION,
        "notice_sha256": n_sha,
        "notice_size_bytes": len(raw_notice),
        "document_sha256": d_sha,
        "document_size_bytes": len(raw_doc),
        "document_type": "HWPX",
        "official_api_operation": "getBidPblancListInfoServc02",
        "capture_id": capture_id,
        "notice_storage_key": f"{CAPTURE_DIR}/{capture_id}.notice.raw.json",
        "document_storage_key": f"public-rfp/{d_sha}.hwpx",
        "document_storage_scope": "EXISTING_PRIVATE_MEDIA",
        "document_bytes_copied": False,
        "document_reference_validation": "HASH_AND_KEY_ONLY",
        "attestation_state": "UNREVIEWED",
    }


def _manifest_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


class OfficialSourceLinkTests(TestCase):
    def setUp(self):
        self.operator = User.objects.create_user(
            username="agw-p0-02-staff", password=PWD,
            must_change_password=False, is_staff=True,
        )
        self.reader = User.objects.create_user(
            username="agw-p0-02-reader", password=PWD, must_change_password=False,
        )
        self.raw_notice = _notice_bytes()
        self.raw_doc = _document_bytes()
        self.metadata_sha = _sha(b"legacy normalized metadata, NOT HTTP response")
        self.notice = Notice.objects.create(
            source="G2B_OFFICIAL_API", notice_number=NUMBER,
        )
        self.version = NoticeVersion.objects.create(
            notice=self.notice, version_seq=1, source_revision="0",
            observed_at=timezone.now(), title=TITLE,
            buyer="Synthetic Government", source_payload_digest=self.metadata_sha,
            source_url=(
                "https://www.g2b.go.kr/link/PNPE027_01/single/"
                "?bidPbancNo=R26BK00999999&bidPbancOrd=000"
            ),
        )
        self.notice.current_version = self.version
        self.notice.save(update_fields=["current_version"])
        self.document = Document.objects.create(
            notice=self.notice, logical_key="RFP",
        )
        self.doc = DocumentVersion.objects.create(
            document=self.document, notice_version=self.version,
            version_seq=1, sha256=_sha(self.raw_doc),
            size_bytes=len(self.raw_doc),
            owner_user=self.operator, shared_read_approved=False,
            storage_key=f"public-rfp/{_sha(self.raw_doc)}.hwpx",
            source_url=URL, freshness=DocumentFreshness.CURRENT,
        )
        self.manifest = _manifest(self.raw_notice, self.raw_doc)

    def link(self, apply=False, **kwargs):
        params = {
            "actor": self.operator,
            "notice_version_id": self.version.pk,
            "document_version_id": self.doc.pk,
            "raw_notice_payload_bytes": self.raw_notice,
            "raw_document_bytes": self.raw_doc,
            "manifest_bytes": _manifest_bytes(self.manifest),
            "apply": apply,
        }
        params.update(kwargs)
        return reconcile_official_source_capture(**params)

    def test_dry_run_and_insert_does_not_rewrite_legacy_digest_or_approve(self):
        self.assertIsNone(self.link())
        self.assertFalse(OfficialSourceLink.objects.exists())
        linked = self.link(apply=True)
        self.assertEqual(linked.notice_version_id, self.version.pk)
        self.assertEqual(linked.document_version_id, self.doc.pk)
        self.assertEqual(linked.official_revision, "000")
        self.assertEqual(linked.raw_notice_sha256, _sha(self.raw_notice))
        self.assertEqual(linked.metadata_canonical_sha256, self.metadata_sha)
        self.assertNotEqual(linked.raw_notice_sha256, self.metadata_sha)
        self.assertEqual(linked.document_sha256, self.doc.sha256)
        self.assertEqual(linked.raw_notice_storage_key, self.manifest["notice_storage_key"])
        self.assertEqual(linked.manifest_storage_key,
                         f"{CAPTURE_DIR}/{linked.capture_id}.existing.manifest.json")
        self.assertEqual(linked.existing_document_storage_key, self.doc.storage_key)
        self.version.refresh_from_db()
        self.doc.refresh_from_db()
        self.assertEqual(self.version.source_payload_digest, self.metadata_sha)
        self.assertFalse(self.doc.shared_read_approved)
        self.assertEqual(NoticeVersion.objects.filter(notice=self.notice).count(), 1)
        self.assertEqual(DocumentVersion.objects.filter(document=self.document).count(), 1)
        self.assertEqual(PublicRfpAttestation.objects.count(), 0)

    def test_idempotent_replay_and_current_source_verification(self):
        first = self.link(apply=True)
        self.assertEqual(first.pk, self.link(apply=True).pk)
        self.assertEqual(first.pk, self.link(apply=False).pk)
        self.assertEqual(first.pk, verify_official_source_link(
            actor=self.operator, document_version_id=self.doc.pk,
            raw_notice_payload_bytes=self.raw_notice,
            raw_document_bytes=self.raw_doc,
            manifest_bytes=_manifest_bytes(self.manifest),
        ).pk)
        self.assertEqual(OfficialSourceLink.objects.count(), 1)

    def test_same_revision_changed_raw_response_requires_conflict_review(self):
        self.link(apply=True)
        changed_notice = _notice_bytes({"extraField": "changed but same revision"})
        changed_manifest = _manifest(changed_notice, self.raw_doc)
        with self.assertRaisesRegex(SourceLinkError, "SOURCE_CAPTURE_CONFLICT"):
            self.link(
                apply=True, raw_notice_payload_bytes=changed_notice,
                manifest_bytes=_manifest_bytes(changed_manifest),
            )
        self.assertEqual(OfficialSourceLink.objects.count(), 1)
        self.assertEqual(NoticeVersion.objects.count(), 1)

    def test_current_version_correction_cancel_and_source_drift_fail_closed(self):
        for field, value in [
            ("cancellation", True), ("correction", True),
            ("source_revision", "1"),
            ("title", "Same revision, different title"),
            ("source_payload_digest", "0" * 64),
        ]:
            with self.subTest(field=field):
                original = getattr(self.version, field)
                setattr(self.version, field, value)
                self.version.save(update_fields=[field])
                if field == "source_payload_digest":
                    # A different canonical digest is valid before first link,
                    # but must remain separate from raw SHA, not replace it.
                    self.assertIsNone(self.link())
                else:
                    with self.assertRaises(SourceLinkError):
                        self.link(apply=True)
                setattr(self.version, field, original)
                self.version.save(update_fields=[field])
        self.notice.current_version = None
        self.notice.save(update_fields=["current_version"])
        with self.assertRaisesRegex(SourceLinkError, "SOURCE_VERSION_STALE"):
            self.link(apply=True)
        self.assertEqual(OfficialSourceLink.objects.count(), 0)

    def test_existing_mapping_rejects_canonical_digest_mutation(self):
        self.link(apply=True)
        self.version.source_payload_digest = "f" * 64
        self.version.save(update_fields=["source_payload_digest"])
        with self.assertRaisesRegex(SourceLinkError, "SOURCE_CAPTURE_CONFLICT"):
            self.link(apply=True)

    def test_existing_mapping_denied_when_doc_acl_or_file_identity_changes(self):
        self.link(apply=True)
        self.doc.freshness = DocumentFreshness.STALE
        self.doc.save(update_fields=["freshness"])
        with self.assertRaisesRegex(SourceLinkError, "SOURCE_VERSION_STALE"):
            self.link(apply=True)
        self.doc.freshness = DocumentFreshness.CURRENT
        self.doc.storage_key = "public-rfp/changed.hwpx"
        self.doc.save(update_fields=["freshness", "storage_key"])
        with self.assertRaisesRegex(SourceLinkError, "SOURCE_VERSION_STALE"):
            self.link(apply=True)

    def test_manifest_tampering_and_document_byte_mismatch_denied_before_write(self):
        for key, value in [
            ("notice_sha256", "a" * 64),
            ("document_storage_key", "public-rfp/other.hwpx"),
            ("document_bytes_copied", True),
            ("attestation_state", "APPROVED"),
            ("notice_size_bytes", len(self.raw_notice) + 1),
            ("capture_id", "b" * 64),
        ]:
            with self.subTest(field=key):
                altered = copy.deepcopy(self.manifest)
                altered[key] = value
                with self.assertRaises(SourceLinkError):
                    self.link(apply=True, manifest_bytes=_manifest_bytes(altered))
        with self.assertRaises(SourceLinkError):
            self.link(apply=True, raw_document_bytes=self.raw_doc + b"X")
        self.assertFalse(OfficialSourceLink.objects.exists())

    def test_url_forgery_owner_missing_and_staff_auth_denied(self):
        with self.assertRaisesRegex(SourceLinkError, "LINK_OPERATOR_NOT_AUTHORIZED"):
            self.link(apply=True, actor=self.reader)
        self.doc.source_url = URL.replace("www.g2b.go.kr", "www.g2b.go.kr.evil.invalid")
        self.doc.save(update_fields=["source_url"])
        with self.assertRaisesRegex(SourceLinkError, "SOURCE_VERSION_STALE"):
            self.link(apply=True)
        self.doc.source_url = URL
        self.doc.owner_user = None
        self.doc.save(update_fields=["source_url", "owner_user"])
        with self.assertRaisesRegex(SourceLinkError, "SOURCE_VERSION_STALE"):
            self.link(apply=True)
        self.assertEqual(OfficialSourceLink.objects.count(), 0)

    def test_stored_source_link_ordinary_orm_immutable(self):
        link = self.link(apply=True)
        with self.assertRaisesRegex(ValueError, "IMMUTABLE_OFFICIAL_SOURCE_LINK"):
            OfficialSourceLink.objects.filter(pk=link.pk).update(
                raw_notice_sha256="0" * 64,
            )
        with self.assertRaisesRegex(ValueError, "IMMUTABLE_OFFICIAL_SOURCE_LINK"):
            OfficialSourceLink.objects.filter(pk=link.pk).delete()
        with self.assertRaisesRegex(ValueError, "IMMUTABLE_OFFICIAL_SOURCE_LINK"):
            OfficialSourceLink.objects.bulk_update([link], ["raw_notice_sha256"])
        with self.assertRaisesRegex(ValueError, "IMMUTABLE_OFFICIAL_SOURCE_LINK"):
            link.save()
        with self.assertRaisesRegex(ValueError, "IMMUTABLE_OFFICIAL_SOURCE_LINK"):
            link.delete()
        self.assertEqual(OfficialSourceLink.objects.count(), 1)

    def test_raw_sql_postgres_immutable_trigger(self):
        if connection.vendor != "postgresql":
            self.skipTest("Real PostgreSQL trigger is tested by CI postgres-authentication job")
        link = self.link(apply=True)
        with self.assertRaisesRegex(DatabaseError, "IMMUTABLE_OFFICIAL_SOURCE_LINK"):
            # Let atomic see the exception and rollback to its savepoint.
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE ai_gateway_officialsourcelink "
                        "SET raw_notice_sha256 = %s WHERE id = %s",
                        ["0" * 64, link.pk],
                    )
        link.refresh_from_db()
        self.assertEqual(link.raw_notice_sha256, _sha(self.raw_notice))

    def test_reverification_fails_when_source_link_missing(self):
        with self.assertRaisesRegex(SourceLinkError, "SOURCE_LINK_MISSING"):
            verify_official_source_link(
                actor=self.operator, document_version_id=self.doc.pk,
                raw_notice_payload_bytes=self.raw_notice,
                raw_document_bytes=self.raw_doc,
                manifest_bytes=_manifest_bytes(self.manifest),
            )


    @unittest.skipIf(os.name == "nt", "POSIX 0700/0600 storage only; NTFS ACL unverified")
    def test_private_archive_loader_existing_document_no_copy_and_tamper(self):
        capture_id = self.manifest["capture_id"]
        with tempfile.TemporaryDirectory() as base:
            root = Path(base)
            media = root / "private-media"
            media.mkdir(mode=0o700)
            doc_dir = media / "public-rfp"
            doc_dir.mkdir(mode=0o700)
            capture_dir = root / "official-g2b-capture"
            capture_dir.mkdir(mode=0o700)
            raw_path = capture_dir / (capture_id + ".notice.raw.json")
            manifest_path = capture_dir / (capture_id + ".existing.manifest.json")
            document_path = doc_dir / (self.doc.sha256 + ".hwpx")
            for p, value in [
                (raw_path, self.raw_notice),
                (manifest_path, _manifest_bytes(self.manifest)),
                (document_path, self.raw_doc),
            ]:
                p.write_bytes(value)
                p.chmod(0o600)
            raw, doc, manifest = load_notice_only_source_files(
                capture_root=root, private_media_root=media,
                capture_id=capture_id, document_sha256=self.doc.sha256,
            )
            self.assertEqual(raw, self.raw_notice)
            self.assertEqual(doc, self.raw_doc)
            self.assertEqual(manifest, _manifest_bytes(self.manifest))
            self.assertEqual(
                len(list(capture_dir.iterdir())), 2,
                "Existing HWPX must not be copied into capture archive",
            )
            with self.assertRaisesRegex(SourceLinkError, "PRIVATE_SOURCE_PATH_DENIED"):
                load_notice_only_source_files(
                    capture_root="relative", private_media_root=media,
                    capture_id=capture_id, document_sha256=self.doc.sha256,
                )
            document_path.chmod(0o644)
            with self.assertRaisesRegex(SourceLinkError, "PRIVATE_SOURCE_PATH_DENIED"):
                load_notice_only_source_files(
                    capture_root=root, private_media_root=media,
                    capture_id=capture_id, document_sha256=self.doc.sha256,
                )
            document_path.chmod(0o600)
            manifest_path.write_bytes(
                _manifest_bytes({**self.manifest, "notice_sha256": "0" * 64}),
            )
            manifest_path.chmod(0o600)
            with self.assertRaisesRegex(SourceLinkError, "CAPTURE_INTEGRITY_MISMATCH"):
                load_notice_only_source_files(
                    capture_root=root, private_media_root=media,
                    capture_id=capture_id, document_sha256=self.doc.sha256,
                )

    def test_private_archive_loader_denies_non_hex_ids_before_filesystem(self):
        with self.assertRaisesRegex(SourceLinkError, "CAPTURE_IDENTITY_MISMATCH"):
            load_notice_only_source_files(
                capture_root="relative", private_media_root="relative",
                capture_id="../" + "a" * 64,
                document_sha256=self.doc.sha256,
            )
