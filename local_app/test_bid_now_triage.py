"""현재 부서 입찰 검토 큐 보수 분류 합성 회귀 (실제 RFP 미사용)."""
import json
import unittest
from datetime import datetime
from bid_now_triage import classify
from procurement_filter import KST

NOW=datetime(2026,10,18,9,0,tzinfo=KST)
PROFILE={"categories":["AI","SW","DATA","SECURITY"]}

def notice(**overrides):
    data={
        "id":"G2B-TEST-2026","notice_lifecycle":"CURRENT",
        "notice_kind":"일반공고","end":"2099-12-31T23:59:00+09:00",
        "department_status":"CANDIDATE","department_categories":["SW"],
        "document_status":"EXTRACTED","rfp_text":"SECRET_SYNTHETIC_REQUIREMENT",
        "document_evidence":[],"attachments":[],
    }
    data.update(overrides)
    return data

class BidNowTriageTests(unittest.TestCase):
    def test_scope_and_secret_not_exposed(self):
        result=classify(notice(),PROFILE,at=NOW)
        self.assertEqual(result["status"],"NEEDS_EXTRACTION_REVIEW")
        self.assertEqual(result["legal_eligibility"],"UNVERIFIED")
        self.assertEqual(result["estimated_profit"],"UNVERIFIED")
        self.assertEqual(result["bid_decision"],"HUMAN_ONLY")
        self.assertNotIn("SECRET_SYNTHETIC_REQUIREMENT",json.dumps(result))
        self.assertNotIn("G2B-TEST",json.dumps(result))

    def test_skill_gap_not_discarded_in_case_high_profit_can_be_pursued(self):
        result=classify(notice(department_status="OUT_OF_SCOPE",
                               department_categories=[],estimated_profit_krw=9999999999),
                        PROFILE,at=NOW)
        self.assertEqual(result["status"],"CAPABILITY_GAP_MARGIN_REVIEW")
        self.assertEqual(result["profit_after_augmentation_cost"],"UNVERIFIED")
        self.assertEqual(result["subcontract_or_consortium_permitted"],"UNVERIFIED")
        self.assertTrue(result["cannot_auto_discard_on_capability_gap"])

    def test_cancel_and_supersede_never_overridden_by_large_price(self):
        for lifecycle in ("CANCELLED","SUPERSEDED","REVIEW"):
            with self.subTest(lifecycle=lifecycle):
                result=classify(notice(notice_lifecycle=lifecycle,
                                       estimated_profit_krw=9999999999),PROFILE,at=NOW)
                self.assertEqual(result["status"],"HOLD_OFFICIAL_STATUS")

    def test_missing_unknown_or_malformed_lifecycle_never_advances(self):
        for value in (None,"","UNKNOWN",123,{"value":"CURRENT"}):
            with self.subTest(value=repr(value)):
                r=classify(notice(notice_lifecycle=value,department_status="OUT_OF_SCOPE",
                                  department_categories=[]),PROFILE,at=NOW)
                self.assertEqual(r["status"],"HOLD_OFFICIAL_STATUS")
        n=notice()
        n.pop("notice_lifecycle")
        self.assertEqual(classify(n,PROFILE,at=NOW)["status"],"HOLD_OFFICIAL_STATUS")

    def test_malformed_registration_deadline_cannot_be_treated_as_open(self):
        for bad in ("invalid",None,"",{"date":"2099-01-01"},17):
            with self.subTest(value=repr(bad)):
                r=classify(notice(qualification_deadline=bad,
                                  department_status="OUT_OF_SCOPE",
                                  department_categories=[]),PROFILE,at=NOW)
                self.assertEqual(r["status"],"REVIEW_REGISTRATION")
                self.assertIn("QUALIFICATION_DEADLINE_INVALID_OR_UNVERIFIED",r["reason_codes"])
                self.assertNotEqual(r["status"],"CAPABILITY_GAP_MARGIN_REVIEW")

    def test_stale_and_deadline_guards(self):
        self.assertEqual(classify(notice(rfp_review_status="STALE"),PROFILE,at=NOW)["status"],
                         "HOLD_STALE_DOCUMENT")
        self.assertEqual(classify(notice(end="2020-10-18T00:00:00+09:00"),PROFILE,at=NOW)["status"],
                         "HOLD_DEADLINE")
        self.assertEqual(classify(notice(end="invalid"),PROFILE,at=NOW)["status"],
                         "REVIEW_UNKNOWN_DEADLINE")
        self.assertEqual(classify(notice(qualification_deadline="2020-01-01T00:00:00+09:00"),
                                  PROFILE,at=NOW)["status"],"REVIEW_REGISTRATION")

    def test_extraction_incomplete_never_priority(self):
        r=classify(notice(document_status="PENDING",rfp_text=""),PROFILE,at=NOW)
        self.assertEqual(r["status"],"NEEDS_OFFICIAL_DOCUMENT")
        r=classify(notice(document_evidence=[{"status":"EXTRACTED","fulltext_truncated":True,
                                               "warnings":["SECRET_UNTRUSTED_MSG"]}]),PROFILE,at=NOW)
        self.assertEqual(r["status"],"NEEDS_EXTRACTION_REVIEW")
        self.assertNotIn("SECRET_UNTRUSTED_MSG",json.dumps(r))

    def test_verified_evidence_still_not_legal_bid_approval(self):
        row=notice(document_evidence=[{"status":"EXTRACTED"}])
        r=classify(row,PROFILE,at=NOW)
        self.assertEqual(r["status"],"NEEDS_EXTRACTION_REVIEW")
        self.assertEqual(r["legal_eligibility"],"UNVERIFIED")
        self.assertEqual(r["estimated_profit"],"UNVERIFIED")

    def test_fail_on_invalid_configuration_or_clock(self):
        for p in ({"categories":["EVIL"]},{"categories":"SW"},None):
            with self.assertRaises(ValueError):
                classify(notice(),p,at=NOW)
        with self.assertRaises(ValueError):
            classify(notice(),PROFILE,at=datetime(2026,10,18))

if __name__=="__main__":
    unittest.main()
