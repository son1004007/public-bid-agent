"""공식 정정·취소: 합성 API 필드로 차수 연결과 원문 근거 보호 검증."""
import copy
import json
import unittest

from dashboard_backend import blank, normalize, update_collection
from notice_lifecycle import reconcile
from recommendations import shortlist

T = "2026-10-13T13:00:00+09:00"


def notice(no, order="000", *, kind="일반공고", title="정보시스템 개발", end="2099-12-31 18:00:00"):
    return normalize({
        "bidNtceNo": no, "bidNtceOrd": order, "bidNtceNm": title,
        "ntceKindNm": kind, "bidClseDt": end,
        "pubPrcrmntClsfcNm": "소프트웨어개발",
        "ntceSpecFileNm1": "제안요청서.pdf",
        "ntceSpecDocUrl1": "https://www.g2b.go.kr/doc.pdf",
    })


class OfficialLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.no = "R26BK12345011"
        self.profile = {"categories": ["SW"], "revision": 0}

    def merge(self, state, items, timestamp=T):
        return update_collection(state, items, len(items), timestamp)

    def test_original_then_newer_correction_supersedes_without_deletion(self):
        initial = notice(self.no, "000")
        initial["final"] = "human_bid"
        initial["finalReason"] = "담당자 실제 결정"
        initial["rfp_text"] = "과거 추출 RFP 내용"
        initial["document_status"] = "EXTRACTED"
        initial["document_evidence"] = [{"status": "EXTRACTED", "sha256": "f" * 64}]
        state = blank()
        state["history"] = [{"id": "history-snapshot"}]
        state = self.merge(state, [initial])
        state = self.merge(state, [notice(self.no, "001", kind="변경공고")], "later")
        rows = {n["bid_order"]: n for n in state["notices"]}
        self.assertEqual(rows["000"]["notice_lifecycle"], "SUPERSEDED")
        self.assertEqual(rows["000"]["superseded_by"], rows["001"]["id"])
        self.assertEqual(rows["000"]["rfp_review_status"], "STALE")
        self.assertEqual(rows["000"]["rfp_text"], "과거 추출 RFP 내용")
        self.assertEqual(rows["000"]["document_evidence"], initial["document_evidence"])
        self.assertEqual(rows["000"]["final"], "human_bid")
        self.assertEqual(rows["000"]["finalReason"], "담당자 실제 결정")
        self.assertEqual(state["history"], [{"id": "history-snapshot"}])
        self.assertEqual(rows["001"]["notice_lifecycle"], "CURRENT")
        ranks = shortlist(state["notices"], self.profile)
        self.assertEqual([n["id"] for n in ranks["results"]], [rows["001"]["id"]])

    def test_cancel_new_revision_blocks_old_and_cancel_in_recommendations(self):
        original = notice(self.no, "000")
        canceled = notice(self.no, "001", kind="취소공고")
        state = self.merge(self.merge(blank(), [original]), [canceled])
        rows = {n["bid_order"]: n for n in state["notices"]}
        self.assertEqual(rows["000"]["notice_lifecycle"], "SUPERSEDED")
        self.assertEqual(rows["001"]["notice_lifecycle"], "CANCELLED")
        self.assertEqual(rows["001"]["window_status"], "CANCELLED")
        self.assertEqual(shortlist(state["notices"], self.profile)["results"], [])
        self.assertEqual(len(state["notices"]), 2)

    def test_same_revision_official_cancel_and_keep_human(self):
        n = notice(self.no, "000")
        n["final"] = "human_bid"
        initial = self.merge(blank(), [n])
        canceled = notice(self.no, "000", kind="취소공고")
        result = self.merge(initial, [canceled], "later")
        row = result["notices"][0]
        self.assertEqual(row["notice_lifecycle"], "CANCELLED")
        self.assertEqual(row["final"], "human_bid")
        self.assertEqual(shortlist(result["notices"], self.profile)["results"], [])
        self.assertTrue(any(x["status"] == "CANCELLED" for x in row["lifecycle_events"]))

    def test_title_word_cancel_does_not_create_official_cancel(self):
        # 제목 문구가 아니라 조달청 공고종류/차수만 신뢰한다.
        n = notice(self.no, kind="일반공고", title="취소된 자료를 활용한 정보시스템 개발")
        result = self.merge(blank(), [n])
        self.assertEqual(result["notices"][0]["notice_lifecycle"], "CURRENT")

    def test_notice_number_boundary_no_cross_bid_supersession(self):
        a = notice("R26BK12345021", "000")
        b = notice("R26BK12345022", "005", kind="취소공고")
        state = self.merge(blank(), [a, b])
        self.assertEqual(state["notices"][0]["notice_lifecycle"], "CURRENT")
        self.assertEqual(state["notices"][1]["notice_lifecycle"], "CANCELLED")

    def test_newer_normal_after_prior_cancel_reopens_only_new_revision(self):
        a = notice(self.no, "000", kind="취소공고")
        b = notice(self.no, "001", kind="변경공고")
        result = self.merge(blank(), [a, b])
        self.assertEqual(result["notices"][0]["notice_lifecycle"], "SUPERSEDED")
        self.assertEqual(result["notices"][1]["notice_lifecycle"], "CURRENT")

    def test_existing_document_metadata_change_stales_rfp_without_overwrite(self):
        n = notice(self.no, "000")
        n["document_status"] = "EXTRACTED"
        n["rfp_text"] = "원본 RFP"
        n["document_evidence"] = [{"identity": "proof"}]
        state = self.merge(blank(), [n])
        changed = notice(self.no, "000", end="2099-12-30 18:00:00")
        result = self.merge(state, [changed], "later")
        item = result["notices"][0]
        self.assertEqual(item["rfp_review_status"], "STALE")
        self.assertEqual(item["rfp_text"], "원본 RFP")
        self.assertEqual(item["document_status"], "EXTRACTED")
        self.assertEqual(item["document_evidence"], [{"identity": "proof"}])
        self.assertEqual(shortlist(result["notices"], self.profile)["results"], [])

    def test_same_official_attachments_with_prior_extraction_not_stale(self):
        n = notice(self.no, "000")
        n["document_status"] = "EXTRACTED"
        n["rfp_text"] = "원본 RFP"
        n["attachments"].append({"name": "검증된 보존 캐시", "url": "https://www.g2b.go.kr/other", "identity": "extra"})
        state = self.merge(blank(), [n])
        result = self.merge(state, [notice(self.no, "000")])
        self.assertNotEqual(result["notices"][0].get("rfp_review_status"), "STALE")

    def test_new_attachment_link_requires_recheck(self):
        n = notice(self.no, "000")
        n["document_status"] = "EXTRACTED"
        n["rfp_text"] = "원본 RFP"
        state = self.merge(blank(), [n])
        fresh = notice(self.no, "000")
        fresh["attachments"].append({"name": "공식정정.pdf", "url": "https://www.g2b.go.kr/correct.pdf"})
        result = self.merge(state, [fresh])
        self.assertEqual(result["notices"][0]["rfp_review_status"], "STALE")
        self.assertEqual(result["notices"][0]["rfp_text"], "원본 RFP")

    def test_repeated_poll_idempotent_lifecycle_event_and_decision(self):
        initial = notice(self.no, "000")
        state = self.merge(blank(), [initial])
        count = len(state["notices"][0]["lifecycle_events"])
        newer = self.merge(state, [notice(self.no, "000")], "later")
        self.assertEqual(len(newer["notices"][0]["lifecycle_events"]), count)

    def test_older_returning_later_cannot_unblock_cancelled_revision(self):
        old = notice(self.no, "000")
        cancel = notice(self.no, "001", kind="취소공고")
        state = self.merge(blank(), [old, cancel])
        next_state = self.merge(state, [old], "later")
        self.assertEqual(next_state["notices"][0]["notice_lifecycle"], "SUPERSEDED")
        self.assertEqual(next_state["notices"][1]["notice_lifecycle"], "CANCELLED")

    def test_out_of_order_items_still_use_highest_official_revision(self):
        old = notice(self.no, "000")
        latest = notice(self.no, "002", kind="취소공고")
        state = self.merge(blank(), [latest, old])
        rows = {n["bid_order"]: n for n in state["notices"]}
        self.assertEqual(rows["000"]["notice_lifecycle"], "SUPERSEDED")
        self.assertEqual(rows["002"]["notice_lifecycle"], "CANCELLED")


    def test_sticky_same_revision_cancellation_after_generic_refresh(self):
        canceled = notice(self.no, "000", kind="취소공고")
        state = self.merge(blank(), [canceled])
        generic = notice(self.no, "000", kind="일반공고")
        state = self.merge(state, [generic])
        self.assertEqual(len(state["notices"]), 1)
        self.assertEqual(state["notices"][0]["notice_lifecycle"], "CANCELLED")
        self.assertEqual(shortlist(state["notices"], self.profile)["results"], [])

    def test_alias_order_cancellation_preserves_existing_user_and_rfp(self):
        old = notice(self.no, "00", kind="일반공고")
        old["final"] = "human_bid"
        old["rfp_text"] = "원문 보존"
        old["document_status"] = "EXTRACTED"
        state = self.merge(blank(), [old])
        cancel_variant = notice(self.no, "000", kind="취소공고")
        result = self.merge(state, [cancel_variant])
        self.assertEqual(len(result["notices"]), 1)
        item = result["notices"][0]
        self.assertEqual(item["id"], old["id"])
        self.assertEqual(item["bid_order"], "00")
        self.assertEqual(item["notice_lifecycle"], "CANCELLED")
        self.assertEqual(item["rfp_review_status"], "STALE")
        self.assertEqual(item["final"], "human_bid")
        self.assertEqual(item["rfp_text"], "원문 보존")
        self.assertEqual(shortlist(result["notices"], self.profile)["results"], [])
        result = self.merge(result, [notice(self.no, "0", kind="일반공고")])
        self.assertEqual(len(result["notices"]), 1)
        self.assertEqual(result["notices"][0]["notice_lifecycle"], "CANCELLED")

    def test_alias_order_same_batch_deduplicates_to_one(self):
        variant_a = notice(self.no, "00")
        variant_b = notice(self.no, "000", kind="취소공고")
        state = self.merge(blank(), [variant_a, variant_b])
        self.assertEqual(len(state["notices"]), 1)
        self.assertEqual(state["notices"][0]["notice_lifecycle"], "CANCELLED")

    def test_existing_duplicate_aliases_with_cancel_never_reopen(self):
        a = notice(self.no, "00", kind="일반공고")
        b = notice(self.no, "000", kind="취소공고")
        state = blank()
        state["notices"] = [a, b]
        result = self.merge(state, [])
        self.assertEqual(len(result["notices"]), 2)
        self.assertTrue(all(n["notice_lifecycle"] == "CANCELLED" for n in result["notices"]))
        self.assertEqual(shortlist(result["notices"], self.profile)["results"], [])


if __name__ == "__main__":
    unittest.main()
