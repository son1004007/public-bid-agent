"""공식 출처·차수·STALE 보호의 합성 회귀 계약.

목적/책임: D-06/D-09 및 P05의 식별자 충돌, 재수집 순서, 취소 유지,
  같은 배치/페이지/조회기간 중복 제거, 구차수 차단과 원문·사람 판단 보존을 검증한다.
입력/출력: 직접 생성한 가상 API 행·TXT bytes -> unittest 단언.
신뢰 경계: 실제 API/LLM/사용자 JSON/회사 자료를 읽거나 전송하지 않는다.
상태 변경: 메모리 사본과 TemporaryDirectory의 합성 캐시만 사용한다.
실패/재시도: 불일치·보류 상태에서는 캐시/파서 진입 차단을 확인한다.
핵심 불변조건: 합성 재현 성공도 공식 최신성 검증이나 STALE 해제가 아니다.
관련: DECISIONS.md D-06/09/10, test_notice_lifecycle.py,
  docs/design/REMAINING_EXECUTION_ROADMAP_2026-10-16.md P05.
"""
import copy
import hashlib
import itertools
import tempfile
import unittest
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch

from dashboard_backend import ProviderError, blank, collect, normalize, update_collection
from notice_lifecycle import reconcile
from recommendations import shortlist
from rfp_fulltext import load, store
from rfp_original_compare import compare
from rfp_original_workflow import verify
from rfp_requirements import structure
from scheduled_collection import fetch_window
from test_dashboard_backend import FakeTransport, response


STAMP = "2026-10-18T10:00:00+09:00"
PROFILE = {"categories": ["SW"], "revision": 0}


def api_row(order="000", **fields):
    return {"bidNtceNo": "SYNTHETIC-P05", "bidNtceOrd": order,
            "bidNtceNm": "합성 정보시스템 개발", "ntceKindNm": "일반공고",
            "bidClseDt": "2099-12-31 18:00:00",
            "pubPrcrmntClsfcNm": "소프트웨어개발", **fields}


def merge(state, rows, timestamp=STAMP):
    return update_collection(state, rows, len(rows), timestamp)


def preserved_fields(row):
    return {key: copy.deepcopy(row.get(key)) for key in (
        "id", "bid_no", "bid_order", "rfp_text", "document_status",
        "document_evidence", "final", "finalReason", "policyRef")}


class OfficialSourceSafetyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.raw = "입찰참가자격: 합성 실적 증명서를 제출하여야 한다.".encode()
        self.text = self.raw.decode()
        self.attachment = {"name": "synthetic-p05.txt",
                           "url": "https://www.g2b.go.kr/synthetic-p05.txt"}
        self.notice = normalize(api_row())
        meta = store(self.root, hashlib.sha256(self.raw).hexdigest(),
                     {"text": self.text, "characters": len(self.text), "truncated": False})
        self.proof = {
            "status": "EXTRACTED", "name": self.attachment["name"],
            "identity": hashlib.sha256((self.attachment["url"] + "\n"
                                        + self.attachment["name"]).encode()).hexdigest(),
            "sha256": hashlib.sha256(self.raw).hexdigest(),
            "notice_id": self.notice["id"], "notice_bid_no": self.notice["bid_no"],
            "notice_bid_order": self.notice["bid_order"], **meta,
        }
        self.notice.update({"attachments": [self.attachment], "rfp_text": self.text,
                            "document_status": "EXTRACTED", "document_evidence": [self.proof],
                            "final": "human_bid", "finalReason": "합성 사람 판단 보존",
                            "policyRef": {"revision": 7}})
        self.parser = Mock(return_value={"text": self.text, "characters": len(self.text),
                                        "truncated": False})

    def assert_preserved(self, original, actual):
        self.assertEqual(preserved_fields(actual), preserved_fields(original))

    def cache_bytes(self):
        return {p.name: p.read_bytes() for p in (self.root / "rfp_fulltext").glob("*.json")}

    def test_normalize_rejects_invalid_or_overlong_identity_without_truncation(self):
        invalid = {
            "bidNtceNo": (None, True, 1234, [], {}, "", "ABC", "A" * 33,
                          "A" * 32 + "!", "AB C", "가상공고"),
            "bidNtceOrd": (None, True, 1, [], {}, "", "-1", "+1", "1.0",
                           "000001", "00000!", "１２", "١"),
        }
        for field, values in invalid.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ProviderError):
                        normalize(api_row(**{field: value}))

    def test_normalize_preserves_identity_at_supported_length_boundaries(self):
        for number, order in itertools.product(("AB-1", "A" * 32), ("0", "99999")):
            with self.subTest(number=number, order=order):
                result = normalize(api_row(order, bidNtceNo=number))
                self.assertEqual((result["bid_no"], result["bid_order"]), (number, order))
                self.assertEqual(result["id"], f"G2B-{number}-{order}")

    def test_reconcile_does_not_link_untrusted_or_inconsistent_identities(self):
        for fields in ({"source": "SYNTHETIC_OTHER_SOURCE"}, {"id": "unrelated-id"},
                       {"bid_no": "OTHER-NOTICE"}, {"bid_order": "invalid"}):
            with self.subTest(fields=fields):
                current = copy.deepcopy(self.notice)
                candidate = normalize(api_row("001", ntceKindNm="취소공고"))
                candidate.update(fields)
                before = copy.deepcopy(candidate)
                reconcile([current, candidate], STAMP)
                self.assertEqual(current["notice_lifecycle"], "CURRENT")
                self.assertNotEqual(current.get("rfp_review_status"), "STALE")
                self.assertEqual(candidate, before)
                self.assert_preserved(self.notice, current)

    def test_numeric_revision_order_independent_of_batch_order_and_preserves_history(self):
        for orders in itertools.permutations(("2", "009", "010")):
            with self.subTest(orders=orders):
                initial = blank()
                initial["history"] = [{"id": "synthetic-human-history", "final": "human_bid"}]
                state = merge(initial, [self.notice])
                before = copy.deepcopy(state)
                incoming = [normalize(api_row(order)) for order in orders]
                incoming_before = copy.deepcopy(incoming)
                result = merge(state, incoming)
                rows = {n["bid_order"]: n for n in result["notices"]}
                self.assertEqual(rows["010"]["notice_lifecycle"], "CURRENT")
                for order in ("000", "2", "009"):
                    self.assertEqual(rows[order]["notice_lifecycle"], "SUPERSEDED")
                    self.assertEqual(rows[order]["superseded_by"], rows["010"]["id"])
                self.assertEqual(rows["000"]["rfp_review_status"], "STALE")
                self.assert_preserved(self.notice, rows["000"])
                self.assertEqual(result["history"], before["history"])
                self.assertEqual(state, before)
                self.assertEqual(incoming, incoming_before)
                self.assertEqual([n["id"] for n in shortlist(result["notices"], PROFILE)["results"]],
                                 [rows["010"]["id"]])

    def test_same_revision_cancel_wins_all_alias_arrival_orders(self):
        updates = [normalize(api_row("0")), normalize(api_row("00", ntceKindNm="취소공고")),
                   normalize(api_row("000"))]
        for ordered in itertools.permutations(updates):
            with self.subTest(orders=[n["bid_order"] for n in ordered]):
                state = merge(blank(), [self.notice])
                for update in ordered:
                    state = merge(state, [update])
                self.assertEqual(len(state["notices"]), 1)
                row = state["notices"][0]
                self.assertEqual(row["notice_lifecycle"], "CANCELLED")
                self.assertEqual(row["rfp_review_status"], "STALE")
                self.assert_preserved(self.notice, row)
                self.assertEqual(shortlist(state["notices"], PROFILE)["results"], [])

    def assert_cancelled_collection(self, initial, incoming, result):
        self.assertEqual(len(result["notices"]), 1)
        row = result["notices"][0]
        self.assertEqual(row["notice_lifecycle"], "CANCELLED")
        self.assertEqual(row["window_status"], "CANCELLED")
        self.assertEqual(shortlist(result["notices"], PROFILE)["results"], [])
        self.assertEqual(result["history"], initial["history"])
        if initial["notices"]:
            self.assert_preserved(initial["notices"][0], row)
            self.assertEqual(row["rfp_review_status"], "STALE")
        repeated = merge(result, incoming, "2026-10-19T10:00:00+09:00")
        self.assertEqual(repeated["notices"][0]["notice_lifecycle"], "CANCELLED")
        self.assertEqual(repeated["notices"][0]["lifecycle_events"], row["lifecycle_events"])

    def test_same_batch_cancellation_survives_identical_and_alias_permutations(self):
        batches = []
        for cancel_order, normal_order in itertools.product(("0", "00", "000"), repeat=2):
            batches.extend(itertools.permutations([
                normalize(api_row(cancel_order, ntceKindNm="취소공고")),
                normalize(api_row(normal_order)),
            ]))
        batches.extend(itertools.permutations([
            normalize(api_row("0")), normalize(api_row("00", ntceKindNm="취소공고")),
            normalize(api_row("000")),
        ]))
        for populated, batch in itertools.product((False, True), batches):
            with self.subTest(populated=populated,
                              batch=[(n["bid_order"], n["notice_kind"]) for n in batch]):
                initial = merge(blank(), [self.notice]) if populated else blank()
                initial["history"] = [{"id": "synthetic-human-history", "final": "human_bid"}]
                before = copy.deepcopy(initial)
                incoming = list(batch)
                incoming_before = copy.deepcopy(incoming)
                result = merge(initial, incoming)
                self.assertEqual(initial, before)
                self.assertEqual(incoming, incoming_before)
                self.assert_cancelled_collection(before, incoming, result)

    def test_collect_preserves_cancel_when_deduplicating_rows_and_pages(self):
        for kinds in itertools.permutations(("취소공고", "일반공고")):
            for paginated in (False, True):
                with self.subTest(kinds=kinds, paginated=paginated):
                    rows = [api_row(ntceKindNm=kind) for kind in kinds]
                    documents = ([response([row], total=2) for row in rows] if paginated
                                 else [response(rows)])
                    before = copy.deepcopy(documents)
                    with patch("dashboard_backend.MAX_ROWS", 1 if paginated else 100):
                        incoming, scanned = collect("synthetic-test-key-12345",
                                                    transport=FakeTransport(documents))
                    self.assertEqual(scanned, 2)
                    self.assertEqual(len(incoming), 1)
                    self.assertEqual(documents, before)
                    initial = merge(blank(), [self.notice])
                    self.assert_cancelled_collection(initial, incoming, merge(initial, incoming))

    def test_fetch_window_preserves_cancellation_at_every_day_position(self):
        for cancel_day in range(7):
            with self.subTest(cancel_day=cancel_day):
                daily = [[normalize(api_row(ntceKindNm="취소공고" if day == cancel_day
                                            else "일반공고"))] for day in range(7)]
                before = copy.deepcopy(daily)
                collector = Mock(side_effect=[(rows, 1) for rows in daily])
                incoming, scanned, _ = fetch_window(
                    "synthetic-test-key-12345", days=7, at=datetime.fromisoformat(STAMP),
                    collector=collector)
                self.assertEqual(scanned, 7)
                self.assertEqual(len(incoming), 1)
                self.assertEqual(daily, before)
                initial = merge(blank(), [self.notice])
                self.assert_cancelled_collection(initial, incoming, merge(initial, incoming))

    def test_empty_and_older_snapshots_cannot_remove_or_reopen_cancelled_revision(self):
        state = merge(blank(), [self.notice, normalize(api_row("001", ntceKindNm="취소공고"))])
        before = copy.deepcopy(state)
        for updates in ([], [normalize(api_row())], [normalize(api_row("001"))]):
            state = merge(state, updates)
            self.assertEqual([n["notice_lifecycle"] for n in state["notices"]],
                             ["SUPERSEDED", "CANCELLED"])
            self.assertEqual(state["notices"][0]["superseded_by"], state["notices"][1]["id"])
            self.assert_preserved(self.notice, state["notices"][0])
            self.assertEqual(shortlist(state["notices"], PROFILE)["results"], [])
        self.assertEqual([n["lifecycle_events"] for n in state["notices"]],
                         [n["lifecycle_events"] for n in before["notices"]])

    def test_existing_alias_ambiguity_is_review_without_deleting_human_records(self):
        alias = copy.deepcopy(self.notice)
        alias.update({"id": "G2B-SYNTHETIC-P05-00", "bid_order": "00",
                      "final": "human_no_bid", "finalReason": "다른 합성 과거 판단"})
        state = blank()
        state["notices"] = [self.notice, alias]
        result = merge(state, [])
        self.assertEqual(len(result["notices"]), 2)
        for original, actual in zip(state["notices"], result["notices"]):
            self.assertEqual(actual["notice_lifecycle"], "REVIEW")
            self.assert_preserved(original, actual)
        self.assertEqual(shortlist(result["notices"], PROFILE)["results"], [])

    def test_material_metadata_changes_stale_preserved_evidence(self):
        changes = {"title": "정정 합성 정보시스템 개발", "budget": "123456",
                   "end": "2099-12-30 18:00:00", "source_url": "https://www.g2b.go.kr/changed",
                   "notice_kind": "변경공고", "notice_published_at": "2026-10-18 10:00:00",
                   "qualification_deadline": "2099-12-29 18:00:00",
                   "procurement_classification": "데이터처리", "procurement_code": "SYNTHETIC",
                   "industry_restriction": "Y", "participation_restriction": "Y",
                   "contract_method": "합성 협상", "attachments": [
                       {**self.attachment, "name": "corrected-synthetic.txt"}]}
        for field, value in changes.items():
            with self.subTest(field=field):
                state = merge(blank(), [self.notice])
                fresh = normalize(api_row())
                fresh[field] = value
                row = merge(state, [fresh])["notices"][0]
                self.assertEqual(row["rfp_review_status"], "STALE")
                self.assertIn(field, row["rfp_stale_reason"])
                self.assert_preserved(self.notice, row)
                self.assertEqual(shortlist([row], PROFILE)["results"], [])

    def test_observation_only_or_omitted_attachment_does_not_invent_correction(self):
        state = merge(blank(), [self.notice])
        fresh = normalize(api_row())
        fresh["observed_at"] = "2099-01-01T00:00:00+09:00"
        row = merge(state, [fresh])["notices"][0]
        self.assertNotEqual(row.get("rfp_review_status"), "STALE")
        self.assertEqual(row["attachments"], self.notice["attachments"])
        self.assert_preserved(self.notice, row)

    def test_stale_is_sticky_when_old_metadata_returns_and_inputs_remain_unchanged(self):
        state = merge(blank(), [self.notice])
        corrected = normalize(api_row(bidClseDt="2099-12-30 18:00:00"))
        state = merge(state, [corrected])
        first_stale = {k: state["notices"][0][k] for k in (
            "rfp_review_status", "rfp_stale_at", "rfp_stale_reason")}
        for rows in ([normalize(api_row())], [corrected], []):
            before = copy.deepcopy(state)
            state = merge(state, rows, "2026-10-19T10:00:00+09:00")
            row = state["notices"][0]
            self.assertEqual({k: row[k] for k in first_stale}, first_stale)
            self.assert_preserved(self.notice, row)
            self.assertEqual(before["notices"][0]["rfp_review_status"], "STALE")
            self.assertEqual(shortlist([row], PROFILE)["results"], [])

    def test_blocked_states_stop_before_cache_or_parser_even_with_matching_original(self):
        variants = [{"notice_lifecycle": state} for state in ("CANCELLED", "SUPERSEDED", "REVIEW")]
        variants += [{"notice_kind": "취소공고"}, {"rfp_review_status": "STALE"}]
        cache_before = self.cache_bytes()
        for fields in variants:
            with self.subTest(fields=fields):
                row = {**copy.deepcopy(self.notice), **fields}
                before = copy.deepcopy(row)
                with patch("rfp_original_workflow.load") as loader:
                    result = verify(row, self.root, self.proof["identity"], self.raw, self.parser)
                    self.assertEqual(result["status"], "NOTICE_REVIEW_BLOCKED")
                    loader.assert_not_called()
                with patch("rfp_requirements.load_fulltext") as loader:
                    structured = structure(row, self.root)
                    self.assertEqual(structured["state"],
                                     "STALE_RFP" if "rfp_review_status" in fields else "EXCLUDED_NOTICE")
                    self.assertEqual(structured["legal_eligibility"], "UNVERIFIED")
                    loader.assert_not_called()
                self.assertEqual(row, before)
        self.parser.assert_not_called()
        self.assertEqual(self.cache_bytes(), cache_before)

    def test_wrong_or_legacy_proof_version_stops_before_cache_read(self):
        for key in ("notice_id", "notice_bid_no", "notice_bid_order"):
            for value in (None, "OTHER-VERSION"):
                with self.subTest(key=key, value=value):
                    row = copy.deepcopy(self.notice)
                    if value is None:
                        del row["document_evidence"][0][key]
                    else:
                        row["document_evidence"][0][key] = value
                    before = copy.deepcopy(row)
                    with patch("rfp_original_workflow.load") as loader:
                        result = verify(row, self.root, self.proof["identity"], self.raw, self.parser)
                        self.assertEqual(result["status"], "PROVENANCE_VERSION_UNVERIFIED")
                        loader.assert_not_called()
                    self.assertEqual(row, before)
        self.parser.assert_not_called()

    def test_forged_official_attachment_url_rejected_even_with_matching_identity_hash(self):
        cache = load(self.root, self.proof["fulltext_ref"])
        for url in ("https://www.g2b.go.kr.evil.invalid/rfp.txt", "http://www.g2b.go.kr/rfp.txt",
                    "https://www.g2b.go.kr@evil.invalid/rfp.txt", "https://127.0.0.1/rfp.txt"):
            with self.subTest(url=url):
                attachment = {**self.attachment, "url": url}
                proof = {**self.proof, "identity": hashlib.sha256(
                    (url + "\n" + attachment["name"]).encode()).hexdigest()}
                result = compare(attachment, proof, cache, self.raw, self.parser)
                self.assertEqual(result["status"], "INVALID_EVIDENCE")
        self.parser.assert_not_called()

    def test_matching_original_comparison_is_read_only_and_does_not_verify_completeness(self):
        before, caches = copy.deepcopy(self.notice), self.cache_bytes()
        result = verify(self.notice, self.root, self.proof["identity"], self.raw, self.parser)
        self.assertEqual(result["status"], "REPRODUCED_TEXT")
        self.assertEqual(result["original_page_table_ocr_coverage"], "NOT_VERIFIED")
        self.assertEqual(result["parser_method_version_ocr_reproducibility"], "NOT_VERIFIED")
        self.parser.assert_called_once_with(self.attachment["name"], self.raw)
        self.assertEqual(self.notice, before)
        self.assertEqual(self.cache_bytes(), caches)
        for secret in (self.text, self.attachment["url"], self.proof["sha256"]):
            self.assertNotIn(secret, str(result))


if __name__ == "__main__":
    unittest.main()
