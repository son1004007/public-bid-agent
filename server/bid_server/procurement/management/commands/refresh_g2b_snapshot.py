"""운영자 전용 공개 스냅샷 입력. stdin만 허용, 오류 원문·키 미출력."""
import json
import sys
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from bid_server.procurement.live_ingest import ingest_snapshot


class Command(BaseCommand):
    help = "Import a bounded public G2B snapshot from stdin; dry-run by default."
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--expected-db-name", required=True)
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        try:
            if connection.vendor != "postgresql":
                raise ValueError("POSTGRES_REQUIRED")
            with connection.cursor() as c:
                c.execute("SELECT current_database()")
                if c.fetchone()[0] != options["expected_db_name"]:
                    raise ValueError("DB_MISMATCH")
            raw = sys.stdin.buffer.read(16 * 1024 * 1024 + 1)
            if len(raw) > 16 * 1024 * 1024:
                raise ValueError("SIZE")
            def unique(items):
                out = {}
                for k, v in items:
                    if k in out:
                        raise ValueError("DUPLICATE_KEY")
                    out[k] = v
                return out
            data = json.loads(raw, object_pairs_hook=unique)
            result = ingest_snapshot(data, apply=options["apply"])
        except Exception:
            raise CommandError("G2B_SNAPSHOT_REJECTED") from None
        self.stdout.write(json.dumps(result, ensure_ascii=True))
