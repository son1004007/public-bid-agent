"""운영자 전용 실패 HWPX 원본 재추출: 명시 owner, 최신 공고, 원본 해시 검증.
외부 통신/공유 권한 변경 없음. 문서별 트랜잭션, 실패 이력과 이전 결과 보존.
공개 RFP 텍스트 전용 fallback, 구조/각주 연결을 성공으로 주장하지 않는다.
"""
import json
import hashlib
import os
import re
import stat
from collections import Counter
from pathlib import Path
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone
from bid_server.procurement.models import Notice, DocumentVersion, DocumentFreshness, ExtractionState, DeadlineStatus
from bid_server.procurement.extractor_service import ExtractionService
from bid_server.procurement.parser import ParserError, MAX_INPUT_BYTES
from bid_server.procurement.serializers import public_attachment_url


def retry_one(pk, owner):
    # Lock notice first (same ordering as refresh/import) and verify exact version/ACL.
    seed = DocumentVersion.objects.select_related("document").get(pk=pk)
    with transaction.atomic():
        n = Notice.objects.select_for_update().get(pk=seed.document.notice_id)
        d = DocumentVersion.objects.select_for_update().select_related("document","notice_version").get(pk=pk)
        v = n.current_version
        if (d.owner_user_id != owner.pk or d.shared_read_approved or d.freshness != DocumentFreshness.REVIEW_REQUIRED
            or n.source != "G2B_OFFICIAL_API" or n.notice_number.startswith("SYNTHETIC-")
            or not v or d.notice_version_id != v.pk or d.document.notice_id != n.pk
            or v.cancellation or v.correction or v.deadline_status != DeadlineStatus.PARSED
            or not v.deadline_at or v.deadline_at <= timezone.now()
            or not public_attachment_url(d.source_url,n.notice_number,v.source_revision)
            or d.document.versions.order_by("-version_seq").first().pk != d.pk):
            return "SKIPPED"
        previous = d.extraction_runs.order_by("-created_at","-pk").first()
        if not previous or previous.state != ExtractionState.FAILED or previous.warnings != ["PARSER_LIMIT_OR_UNSUPPORTED_CONTENT"]:
            return "SKIPPED"
        if not re.fullmatch(r"[0-9a-f]{64}",d.sha256) or d.storage_key != "public-rfp/"+d.sha256+".hwpx":
            raise ValueError("KEY")
        root = Path(settings.PRIVATE_MEDIA_ROOT)
        folder = root/"public-rfp"
        if not root.is_absolute() or root.is_symlink() or folder.is_symlink() or not folder.is_dir():
            raise ValueError("STORAGE")
        fd = os.open(folder/(d.sha256+".hwpx"),os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
        with os.fdopen(fd,"rb") as f:
            if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
                raise ValueError("FILE")
            raw=f.read(MAX_INPUT_BYTES+1)
        if len(raw)>MAX_INPUT_BYTES or len(raw)!=d.size_bytes or hashlib.sha256(raw).hexdigest()!=d.sha256:
            raise ValueError("HASH")
        try:
            with transaction.atomic():
                run=ExtractionService.extract_and_persist(d,raw,"document.hwpx",public_hwpx_text_only=True)
                if not run.chunks.exists():
                    raise ParserError("No chunks")
        except ParserError:
            return "STILL_LIMITED"
        d.freshness=DocumentFreshness.CURRENT
        d.save(update_fields=["freshness"])
        return "PARSED_TEXT_ONLY"


class Command(BaseCommand):
    help="Retry at most five failed current public HWPX documents, with text-only coverage."
    requires_system_checks=[]
    def add_arguments(self,parser):
        parser.add_argument("--expected-db-name",required=True)
        parser.add_argument("--owner",required=True)
        parser.add_argument("--apply",action="store_true",required=True)
    def handle(self,*args,**opts):
        try:
            if connection.vendor!="postgresql": raise ValueError("DB")
            with connection.cursor() as c:
                c.execute("SELECT current_database()")
                if c.fetchone()[0]!=opts["expected_db_name"]:raise ValueError("DB")
            owner=get_user_model().objects.get(username=opts["owner"],is_active=True)
            ids=list(DocumentVersion.objects.filter(owner_user=owner,shared_read_approved=False,
                freshness=DocumentFreshness.REVIEW_REQUIRED,storage_key__startswith="public-rfp/").order_by("pk").values_list("pk",flat=True)[:5])
            counts=Counter()
            for pk in ids:
                counts[retry_one(pk,owner)]+=1
            self.stdout.write(json.dumps(dict(counts),ensure_ascii=True))
        except Exception:
            raise CommandError("PUBLIC_RFP_RETRY_REJECTED") from None
