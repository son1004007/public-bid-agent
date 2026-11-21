"""공식 공개 첨부 제한 적재. 파싱은 외부 연결 없는 전용 프로세스에서 실행.
입력: 운영자가 실제 API에서 내려받은 HWPX 바이트/공고 차수와 버전, 명시 소유자.
출력: 집계만. 원본은 비공개 SHA 파일, 추출·실패 상태는 DB에 저장.
경계: 최신 공고 차수 재검증, 문서 단위 잠금/트랜잭션, 공유 권한 부여 금지.
실패: 파서 한도 미완료 표시. DB 실패 시 SHA 원본이 남을 수 있음(정리 별도).
"""
import base64
import hashlib
import json
import os
import re
import stat
import sys
import uuid
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone
from bid_server.procurement.extractor_service import ExtractionService
from bid_server.procurement.models import (Notice, Document, DocumentVersion,
    DeadlineStatus, DocumentFreshness, ExtractionRun, ExtractionState)
from bid_server.procurement.parser import ParserError, parse_document_bytes
from bid_server.procurement.serializers import public_attachment_url

MAX_BYTES = 8 * 1024 * 1024
MEDIA = "application/hwp+zip"


def store(raw, digest):
    root = Path(settings.PRIVATE_MEDIA_ROOT)
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        raise ValueError("STORAGE")
    dest = root / "public-rfp"
    dest.mkdir(mode=0o700, exist_ok=True)
    if dest.is_symlink() or not dest.is_dir() or stat.S_IMODE(dest.stat().st_mode) != 0o700:
        raise ValueError("STORAGE")
    name = digest + ".hwpx"
    p = dest / name
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(p, flags, 0o600)
    except FileExistsError:
        fd = os.open(p, os.O_RDONLY | getattr(os,"O_NOFOLLOW",0))
        with os.fdopen(fd,"rb") as existing:
            if not stat.S_ISREG(os.fstat(existing.fileno()).st_mode) or existing.read(MAX_BYTES+1) != raw:
                raise ValueError("STORAGE_CONFLICT")
    else:
        with os.fdopen(fd, "wb") as f:
            f.write(raw); f.flush(); os.fsync(f.fileno())
    return "public-rfp/" + name


def register(row, owner_id):
    if set(row) != {"no","rev","vid","name","url","status","size","sha256","data"} or row["status"] != "DOWNLOADED":
        raise ValueError("SCHEMA")
    name, no, rev = row["name"],row["no"],row["rev"]
    if (not isinstance(name,str) or len(name)>180 or not name.lower().endswith(".hwpx")
         or any(ord(c)<32 or c in "/\\" for c in name) or no.startswith("SYNTHETIC-")):
        raise ValueError("NAME")
    link = public_attachment_url(row["url"],no,rev)
    if not link:
        raise ValueError("LINK")
    seq = parse_qs(urlsplit(link).query)["fileSeq"][0]
    code = parse_qs(urlsplit(link).query)["prcmBsneSeCd"][0]
    vid = uuid.UUID(row["vid"])
    raw = base64.b64decode(row["data"],validate=True)
    digest = hashlib.sha256(raw).hexdigest()
    if not raw.startswith(b"PK") or type(row["size"]) is not int or not 0<len(raw)<=MAX_BYTES or row["size"]!=len(raw) or digest!=row["sha256"]:
        raise ValueError("RAW")
    with transaction.atomic():
        n = Notice.objects.select_for_update().get(source="G2B_OFFICIAL_API",notice_number=no)
        v = n.current_version
        if (not v or v.id!=vid or v.source_revision!=rev or v.cancellation or v.correction
                or v.deadline_at is None or v.deadline_at<=timezone.now() or v.deadline_status!=DeadlineStatus.PARSED):
            return "STALE"
        doc, _ = Document.objects.get_or_create(notice=n,logical_key="G2B "+seq+" "+name,defaults={"source_attachment_id":code+":"+seq})
        doc = Document.objects.select_for_update().get(pk=doc.pk)
        latest = doc.versions.order_by("-version_seq").first()
        if latest:
            if latest.owner_user_id!=owner_id or latest.shared_read_approved or latest.notice_version_id!=v.id or latest.sha256!=digest or latest.source_url!=link:
                return "CONFLICT"
            return "UNCHANGED"
        key = store(raw,digest)
        dv = DocumentVersion.objects.create(document=doc,notice_version=v,version_seq=1,sha256=digest,size_bytes=len(raw),
              media_type=MEDIA,owner_user_id=owner_id,shared_read_approved=False,storage_key=key,source_url=link,freshness=DocumentFreshness.CURRENT)
        try:
            with transaction.atomic():
                run = ExtractionService.extract_and_persist(dv,raw,file_name=name)
                if not run.chunks.exists():
                    raise ParserError("No extractable chunks")
        except ParserError:
            dv.freshness=DocumentFreshness.REVIEW_REQUIRED
            dv.save(update_fields=["freshness"])
            ExtractionRun.objects.create(document_version=dv,extractor_version="1.0.0-def03",
                state=ExtractionState.FAILED,warnings=["PARSER_LIMIT_OR_UNSUPPORTED_CONTENT"],completed_at=timezone.now())
            return "PARSE_FAILED"
        return "PARSED"


class Command(BaseCommand):
    help="Register up to five predownloaded official public HWPX files (operator only)."
    requires_system_checks=[]
    def add_arguments(self, parser):
        parser.add_argument("--expected-db-name",required=True)
        parser.add_argument("--owner",required=True)
        parser.add_argument("--apply",action="store_true",required=True)
    def handle(self,*args,**opts):
        try:
            if connection.vendor!="postgresql": raise ValueError("DB")
            with connection.cursor() as c:
                c.execute("SELECT current_database()")
                if c.fetchone()[0]!=opts["expected_db_name"]: raise ValueError("DB")
            owner=get_user_model().objects.get(username=opts["owner"],is_active=True)
            data=sys.stdin.buffer.read(56*1024*1024+1)
            if len(data)>56*1024*1024: raise ValueError("SIZE")
            rows=json.loads(data)
            if not isinstance(rows,list) or not 1<=len(rows)<=5: raise ValueError("COUNT")
            from collections import Counter
            counts=Counter()
            for row in rows:
                if not isinstance(row,dict): raise ValueError("SCHEMA")
                if row.get("status")=="FAILED":
                    counts["DOWNLOAD_FAILED"]+=1;continue
                counts[register(row,owner.pk)]+=1
            self.stdout.write(json.dumps(dict(counts),ensure_ascii=True))
        except Exception:
            raise CommandError("PUBLIC_RFP_IMPORT_REJECTED") from None
