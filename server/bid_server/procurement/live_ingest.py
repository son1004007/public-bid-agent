"""공개 API 스냅샷 적재: 최신 차수/취소 상태 보호, 원자적 갱신.
입력: 공개 메타데이터 전용 제한 스키마, 24시간 관측 시각. 출력: 집계 상태만.
권한: 서버 운영자 명령 전용, 외부 I/O 없음. PostgreSQL advisory lock + row lock.
실패: 전체 롤백. 오래된 차수·동차수 충돌은 보존/집계, 명시 취소만 우선.
"""
import re
from datetime import datetime, timedelta
from django.db import connection, transaction
from django.utils import timezone
from .models import Notice
from .importer import LegacyNoticeImporter, compute_canonical_digest
from .serializers import public_notice_url

FIELDS = {"id", "bid_no", "bid_order", "source", "title", "org", "budget", "end", "notice_kind", "source_url"}


def validate_snapshot(data, now=None):
    now = now or timezone.now()
    if not isinstance(data, dict) or set(data) != {"rows", "scanned", "unique_revisions", "window_end"}:
        raise ValueError("SNAPSHOT")
    rows, scanned, revisions = data["rows"], data["scanned"], data["unique_revisions"]
    if (not isinstance(rows, list) or type(scanned) is not int or type(revisions) is not int
            or not 0 <= len(rows) <= revisions <= scanned <= 100000 or len(rows) > 10000
            or (scanned > 0 and not rows)):
        raise ValueError("COUNT")
    at = datetime.fromisoformat(data["window_end"])
    if at.tzinfo is None or not now - timedelta(hours=48) <= at <= now + timedelta(minutes=5):
        raise ValueError("WINDOW")
    numbers = set()
    for r in rows:
        if not isinstance(r, dict) or set(r) != FIELDS:
            raise ValueError("FIELDS")
        no, revision = r["bid_no"], r["bid_order"]
        if (not isinstance(no, str) or not re.fullmatch(r"[A-Za-z0-9-]{4,32}", no)
            or no.startswith("SYNTHETIC-") or no in numbers or not isinstance(revision, str)
            or not re.fullmatch(r"(?:0|[1-9][0-9]{0,4})", revision)
            or r["id"] != f"G2B-{no}-{revision}" or r["source"] != "G2B_OFFICIAL_API"):
            raise ValueError("IDENTITY")
        numbers.add(no)
        for k, limit in (("title", 500), ("org", 300), ("end", 40), ("notice_kind", 60), ("source_url", 1000)):
            if not isinstance(r[k], str) or len(r[k]) > limit or any(ord(c) < 32 for c in r[k]):
                raise ValueError("TEXT")
        if not r["title"].strip() or not r["org"].strip():
            raise ValueError("TEXT")
        if r["budget"] is not None and (type(r["budget"]) is not int or not 0 <= r["budget"] <= 999999999999999):
            raise ValueError("BUDGET")
        if r["end"]:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2}:\d{2})?", r["end"]):
                raise ValueError("DEADLINE")
            datetime.fromisoformat(r["end"])
        if r["source_url"] and (not r["source_url"].startswith("https://www.g2b.go.kr/link/PNPE027_01/single/?")
                               or not public_notice_url(r["source_url"], no, revision)):
            raise ValueError("LINK")
    return rows


def ingest_snapshot(data, *, apply=False):
    rows = validate_snapshot(data)
    counts = {"scanned": data["scanned"], "logical": len(rows), "unchanged": 0,
              "stale": 0, "same_revision_review": 0, "created_notices": 0, "created_versions": 0,
              "idempotent_skipped": 0, "window_end": data["window_end"]}
    with transaction.atomic():
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_try_advisory_xact_lock(731508213, 20261119)")
                if not cursor.fetchone()[0]:
                    raise ValueError("COLLECTION_BUSY")
        eligible = []
        for row in rows:
            n = Notice.objects.select_for_update().filter(source=row["source"], notice_number=row["bid_no"]).first()
            if n is None:
                eligible.append(row)
                continue
            v = n.current_version
            if v is None or v.notice_id != n.pk or not (v.source_revision or "").isdecimal():
                counts["same_revision_review"] += 1
                continue
            incoming, current = int(row["bid_order"]), int(v.source_revision)
            if incoming < current or (v.cancellation and incoming == current and "취소" not in row["notice_kind"]):
                counts["stale"] += 1
                continue
            if v.source_payload_digest == compute_canonical_digest(row):
                counts["unchanged"] += 1
                continue
            same_metadata = (v.title == row["title"] and v.buyer == row["org"] and v.budget_amount == row["budget"]
                             and v.deadline_raw == row["end"] and v.cancellation == ("취소" in row["notice_kind"])
                             and v.correction == ("정정" in row["notice_kind"] or "변경" in row["notice_kind"]))
            if incoming == current:
                if same_metadata and v.source_url == row["source_url"]:
                    counts["unchanged"] += 1
                    continue
                # Allow an official cancellation or missing-link enrichment only.
                if not (("취소" in row["notice_kind"] and not v.cancellation)
                        or (same_metadata and not v.source_url and row["source_url"])):
                    counts["same_revision_review"] += 1
                    continue
            eligible.append(row)
        result = LegacyNoticeImporter(source_system="G2B_NAS_API", dataset="PUBLIC_SERVICE_NOTICES").import_notices(
            eligible, snapshot_ref=data["window_end"])
        for k in ("created_notices", "created_versions", "idempotent_skipped"):
            counts[k] = result[k]
        if result["errors"] or sum(counts[k] for k in ("unchanged", "stale", "same_revision_review", "created_versions", "idempotent_skipped")) != len(rows):
            raise ValueError("IMPORT_COUNT")
        counts["status"] = "SUCCESS_REVIEW_REQUIRED" if counts["same_revision_review"] else "SUCCESS"
        if not apply:
            counts["status"] = "DRY_RUN"
            transaction.set_rollback(True)
    return counts
