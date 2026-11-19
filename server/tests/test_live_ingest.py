"""갱신/취소/정정 및 스냅샷 유효성 회귀."""
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from bid_server.procurement.live_ingest import ingest_snapshot
from bid_server.procurement.models import Notice, NoticeVersion


class LiveIngestTests(TestCase):
    def row(self, rev="0", **updates):
        no = "R26BK00000001"
        r = {"id": f"G2B-{no}-{rev}", "bid_no": no, "bid_order": rev, "source": "G2B_OFFICIAL_API",
             "title": "Synthetic service", "org": "Synthetic", "budget": 120000000,
             "end": "2027-01-01 00:00:00", "notice_kind": "일반",
             "source_url": f"https://www.g2b.go.kr/link/PNPE027_01/single/?bidPbancNo={no}&bidPbancOrd={rev}"}
        r.update(updates)
        return r

    def snapshot(self, *rows):
        return {"scanned": len(rows), "unique_revisions": len(rows), "rows": list(rows),
                "window_end": timezone.now().isoformat()}

    def apply(self, *rows):
        return ingest_snapshot(self.snapshot(*rows), apply=True)

    def test_dry_run_then_replay(self):
        self.assertEqual(ingest_snapshot(self.snapshot(self.row()))["created_notices"], 1)
        self.assertEqual(Notice.objects.count(), 0)
        self.assertEqual(self.apply(self.row())["created_versions"], 1)
        self.assertEqual(self.apply(self.row())["unchanged"], 1)
        self.assertEqual(NoticeVersion.objects.count(), 1)

    def test_cancellation_and_older_revision(self):
        self.apply(self.row())
        self.assertEqual(self.apply(self.row(notice_kind="취소"))["created_versions"], 1)
        self.assertEqual(self.apply(self.row())["stale"], 1)
        self.assertTrue(Notice.objects.get().current_version.cancellation)
        self.assertEqual(self.apply(self.row("1", notice_kind="정정"))["created_versions"], 1)
        self.assertEqual(self.apply(self.row())["stale"], 1)
        self.assertTrue(Notice.objects.get().current_version.correction)
        self.assertEqual(NoticeVersion.objects.count(), 3)

    def test_same_revision_change_preserves_current(self):
        self.apply(self.row())
        r = self.apply(self.row(budget=1))
        self.assertEqual(r["same_revision_review"], 1)
        self.assertEqual(r["status"], "SUCCESS_REVIEW_REQUIRED")
        self.assertEqual(Notice.objects.get().current_version.budget_amount, 120000000)

    def test_invalid_snapshot_does_not_write(self):
        for row in (self.row(source_url="https://evil.invalid/"), self.row(final="BID"), self.row(budget=True)):
            with self.assertRaises(ValueError):
                self.apply(row)
        with self.assertRaises(ValueError):
            self.apply(self.row(), self.row())
        late = self.snapshot(self.row())
        late["window_end"] = (timezone.now() - timedelta(days=3)).isoformat()
        with self.assertRaises(ValueError):
            ingest_snapshot(late, apply=True)
        self.assertEqual(Notice.objects.count(), 0)
