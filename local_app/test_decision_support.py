"""입찰 실무용 보수적 참고판단 회귀검사."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
from decision_support import advise
import server


class DecisionSupportTests(unittest.TestCase):
    def prepare(self,fail=None):
        case=server.create_case("가상 공개 입찰")
        result=server.normalize({
            "gates":{k:{"status":"fail" if k==fail else "unknown",
                        "evidence":"입찰 공고 3절과 가상 회사 조건의 명시적 불일치" if k==fail else ""}
                     for k,_ in server.GATES},
            "factors":{"technical":{"score":4,"evidence":"가상 기술팀 경험"}},
            "recommendation":"bid" if fail else "hold","reason":""
        })
        case["ai_draft"]=result
        return case

    def test_unanalyzed_does_not_claim_eligibility(self):
        advice=advise(server.create_case("합성"))
        self.assertEqual(advice["status"],"NOT_ANALYZED")
        self.assertTrue(advice["not_legal_eligibility"])

    def test_hard_gate_failure_is_visible_even_if_model_said_bid(self):
        case=self.prepare(fail="eligibility")
        res=advise(case)
        self.assertEqual(res["status"],"REVIEW_NO_BID_PROVISIONAL")
        self.assertIn("eligibility",res["failed_gate_keys"])
        self.assertEqual(res["ai_raw_recommendation"],"bid")
        self.assertEqual(case["decision"],"undecided")
        self.assertTrue(any(x["type"]=="model_reason_missing" for x in res["flags"]))

    def test_resources_failure_is_separate_from_eligibility(self):
        case=self.prepare(fail="resources")
        self.assertEqual(advise(case)["status"],"REVIEW_NO_BID_PROVISIONAL")

    def test_missing_documents_stay_hold(self):
        case=self.prepare()
        self.assertEqual(advise(case)["status"],"HOLD_UNVERIFIED")
        self.assertEqual(advise(case)["unverified_gate_count"],len(server.GATES))

    def test_user_verifies_failure_then_can_still_make_own_decision(self):
        case=self.prepare()
        case["gates"]["eligibility"]={"status":"fail","evidence":"확인된 가상 실적증명","verified":True}
        out=advise(case)
        self.assertEqual(out["status"],"REVIEW_NO_BID_VERIFIED")
        self.assertEqual(case["decision"],"undecided")

    def test_ai_human_conflict_is_hold_not_assumed_compliant(self):
        case=self.prepare(fail="eligibility")
        case["gates"]["eligibility"]={"status":"pass","evidence":"사용자가 확인한 가상 증빙","verified":True}
        out=advise(case)
        self.assertEqual(out["status"],"HOLD_CONFLICT")
        self.assertIn("eligibility",[x["gate"] for x in out["flags"] if x["type"]=="ai_user_disagreement"])

    def test_all_human_verified_is_ready_not_final_bid(self):
        case=self.prepare()
        for k,_ in server.GATES:
            case["gates"][k]={"status":"pass","evidence":"가상 서류 검증","verified":True}
        result=advise(case)
        self.assertEqual(result["status"],"READY_FOR_HUMAN")
        self.assertEqual(result["ai_raw_recommendation"],"hold")
        self.assertEqual(case["decision"],"undecided")


if __name__=="__main__": unittest.main()
