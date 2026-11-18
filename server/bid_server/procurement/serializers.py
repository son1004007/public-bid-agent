"""조달 공고 API 직렬화 계약.
목적: Notice, NoticeVersion, Document, DocumentVersion을 일관된 JSON 스키마로 변환한다.
경계: 민감 시스템 내부 키나 원시 비밀번호는 노출하지 않는다.
관련: docs/server-migration/18-screen-api-contract.md §31-35.
"""
from urllib.parse import urlsplit, urlunsplit
from rest_framework import serializers
from .models import (
    Notice,
    NoticeVersion,
    Document,
    DocumentVersion,
    Proposal,
    ProposalRevision,
    ProposalSection,
    ExportArtifact,
    DocumentStructure,
    DocumentBlock,
    TableBlock,
    TableCell,
    FootnoteBlock,
)


def public_source_url(value):
    """Expose only public procurement links without credentials or query secrets.

    The original URL remains in the private data source; links with query
    parameters are withheld rather than changing their meaning.
    """
    if not isinstance(value, str) or not value or any(ord(c) < 33 or c == "\\" for c in value):
        return ""
    try:
        parts = urlsplit(value)
        host = parts.hostname or ""
        if (parts.scheme != "https" or not (host == "g2b.go.kr" or host.endswith(".g2b.go.kr"))
                or parts.username is not None or parts.password is not None
                or parts.port not in (None, 443) or parts.query or parts.fragment):
            return ""
        return urlunsplit(("https", parts.netloc, parts.path, "", ""))
    except ValueError:
        return ""


class DocumentVersionSerializer(serializers.ModelSerializer):
    source_url = serializers.SerializerMethodField()

    def get_source_url(self, obj):
        return public_source_url(obj.source_url)

    class Meta:
        model = DocumentVersion
        fields = [
            "id",
            "version_seq",
            "sha256",
            "size_bytes",
            "media_type",
            "source_url",
            "freshness",
            "acquired_at",
        ]


class DocumentSerializer(serializers.ModelSerializer):
    versions = DocumentVersionSerializer(many=True, read_only=True)

    class Meta:
        model = Document
        fields = [
            "id",
            "logical_key",
            "source_attachment_id",
            "versions",
        ]


class NoticeSummarySerializer(serializers.ModelSerializer):
    title = serializers.CharField(source="current_version.title", read_only=True)
    buyer = serializers.CharField(source="current_version.buyer", read_only=True)
    version_id = serializers.UUIDField(source="current_version.id", read_only=True)
    version_seq = serializers.IntegerField(source="current_version.version_seq", read_only=True)
    deadline_at = serializers.DateTimeField(source="current_version.deadline_at", read_only=True)
    deadline_status = serializers.CharField(source="current_version.deadline_status", read_only=True)
    cancellation = serializers.BooleanField(source="current_version.cancellation", read_only=True)
    correction = serializers.BooleanField(source="current_version.correction", read_only=True)
    budget_amount = serializers.IntegerField(source="current_version.budget_amount", read_only=True)
    categories = serializers.ListField(source="current_version.department_categories", read_only=True)
    source_url = serializers.SerializerMethodField()

    def get_source_url(self, obj):
        return public_source_url(obj.current_version.source_url) if obj.current_version else ""
    document_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Notice
        fields = [
            "id",
            "source",
            "notice_number",
            "title",
            "buyer",
            "version_id",
            "version_seq",
            "deadline_at",
            "deadline_status",
            "cancellation",
            "correction",
            "budget_amount",
            "categories",
            "source_url",
            "document_count",
            "created_at",
            "updated_at",
        ]


class NoticeDetailSerializer(serializers.ModelSerializer):
    title = serializers.CharField(source="current_version.title", read_only=True)
    buyer = serializers.CharField(source="current_version.buyer", read_only=True)
    version_id = serializers.UUIDField(source="current_version.id", read_only=True)
    version_seq = serializers.IntegerField(source="current_version.version_seq", read_only=True)
    deadline_raw = serializers.CharField(source="current_version.deadline_raw", read_only=True)
    deadline_at = serializers.DateTimeField(source="current_version.deadline_at", read_only=True)
    deadline_status = serializers.CharField(source="current_version.deadline_status", read_only=True)
    cancellation = serializers.BooleanField(source="current_version.cancellation", read_only=True)
    correction = serializers.BooleanField(source="current_version.correction", read_only=True)
    budget_amount = serializers.IntegerField(source="current_version.budget_amount", read_only=True)
    categories = serializers.ListField(source="current_version.department_categories", read_only=True)
    extra_data = serializers.SerializerMethodField()

    def get_extra_data(self, obj):
        # Legacy analysis/decision payloads are not an approved shared projection.
        return {}
    source_url = serializers.SerializerMethodField()

    def get_source_url(self, obj):
        return public_source_url(obj.current_version.source_url) if obj.current_version else ""
    documents = DocumentSerializer(many=True, read_only=True)
    total_versions = serializers.IntegerField(read_only=True)

    class Meta:
        model = Notice
        fields = [
            "id",
            "source",
            "notice_number",
            "title",
            "buyer",
            "version_id",
            "version_seq",
            "deadline_raw",
            "deadline_at",
            "deadline_status",
            "cancellation",
            "correction",
            "budget_amount",
            "categories",
            "extra_data",
            "source_url",
            "documents",
            "total_versions",
            "created_at",
            "updated_at",
        ]


class NoticeVersionHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = NoticeVersion
        fields = [
            "id",
            "version_seq",
            "source_revision",
            "observed_at",
            "title",
            "buyer",
            "cancellation",
            "correction",
            "deadline_at",
            "deadline_status",
            "budget_amount",
            "department_categories",
            "source_payload_digest",
            "created_at",
        ]


class ProposalSectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProposalSection
        fields = [
            "id",
            "section_key",
            "ordinal",
            "title",
            "body",
            "created_at",
        ]


class ExportArtifactSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExportArtifact
        fields = [
            "id",
            "format",
            "file_name",
            "sha256",
            "size_bytes",
            "created_at",
        ]


class ProposalRevisionSerializer(serializers.ModelSerializer):
    sections = ProposalSectionSerializer(many=True, read_only=True)
    export_artifacts = serializers.SerializerMethodField()

    def get_export_artifacts(self, obj):
        # Legacy path-only rows are not verified saved artifacts.
        rows = obj.export_artifacts.filter(storage_path__startswith="bid-export-")
        return ExportArtifactSerializer(rows, many=True).data
    author_username = serializers.CharField(source="author.username", read_only=True)

    class Meta:
        model = ProposalRevision
        fields = [
            "id",
            "seq",
            "status",
            "provenance",
            "author_username",
            "title",
            "summary",
            "metadata",
            "sections",
            "export_artifacts",
            "created_at",
        ]


class ProposalSerializer(serializers.ModelSerializer):
    notice_id = serializers.UUIDField(source="notice.id", read_only=True)
    notice_number = serializers.CharField(source="notice.notice_number", read_only=True)
    current_revision = ProposalRevisionSerializer(read_only=True)
    total_revisions = serializers.SerializerMethodField()

    class Meta:
        model = Proposal
        fields = [
            "id",
            "notice_id",
            "notice_number",
            "current_revision",
            "total_revisions",
            "created_at",
            "updated_at",
        ]

    def get_total_revisions(self, obj):
        return obj.revisions.count()


class DocumentStructureSerializer(serializers.ModelSerializer):
    blocks_count = serializers.SerializerMethodField()
    tables_count = serializers.SerializerMethodField()
    footnotes_count = serializers.SerializerMethodField()

    class Meta:
        model = DocumentStructure
        fields = [
            "id",
            "schema_version",
            "coverage",
            "blocks_count",
            "tables_count",
            "footnotes_count",
            "created_at",
        ]

    def get_blocks_count(self, obj):
        return obj.blocks.count()

    def get_tables_count(self, obj):
        return obj.blocks.filter(kind="table").count()

    def get_footnotes_count(self, obj):
        return obj.blocks.filter(kind="footnote").count()
