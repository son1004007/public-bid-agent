"""LangGraph 교차검토 가상 AI 응답 회귀검증. 외부 모델 전송 없이 호출경로를 검증."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import server
from cross_review import execute_cross_review


def fake_result(rec, score=3, status="pass"):
    return {"status": "success", "result": {"recommendation":rec,"reason":"합성 샘플",
           "gates":{k:{"status":status,"evidence":"가상 원문 3절","verified":False} for k,_ in server.GATES},
           "factors":{k:{"score":score,"evidence":"가상 원문 4절","verified":False} for k,_,_ in server.FACTORS}}}


class CrossReviewTests(unittest.TestCase):
    def test_independent_and_one_peer_round(self):
        calls=[]
        def fake(provider,prompt):
            calls.append((provider,prompt))
            if len(calls)<3:
                return fake_result("bid" if provider=="codex" else "hold",
                                   4 if provider=="codex" else 2)
            self.assertIn("상대",prompt)
            return fake_result("hold",3)
        original=server.create_case("가상 공개 입찰")
        original["decision"]="hold"
        result=execute_cross_review("가상 RFP",["codex","claude"],fake)
        self.assertEqual([p for p,_ in calls],["codex","claude","codex","claude"])
        self.assertEqual(result["comparison"]["status"],"reviewed")
        self.assertEqual(result["comparison"]["rounds"],1)
        self.assertGreater(len(result["comparison"]["disagreements"]),0)
        self.assertTrue(result["comparison"]["awaiting_human"])
        self.assertEqual(original["decision"],"hold")
        self.assertNotIn("verified",result["comparison"])

    def test_single_provider_does_not_create_fake_peer(self):
        calls=[]
        result=execute_cross_review("합성",["codex"],lambda p,txt:(calls.append(p),fake_result("hold"))[1])
        self.assertEqual(calls,["codex"])
        self.assertEqual(result["comparison"]["status"],"single_or_failed")
        self.assertEqual(result["critiques"],{})

    def test_failure_does_not_trigger_peer_critique(self):
        calls=[]
        def fake(p,prompt):
            calls.append(p)
            return {"status":"unavailable","error":"CLI 미설치"} if p=="claude" else fake_result("bid")
        result=execute_cross_review("합성",["codex","claude"],fake)
        self.assertEqual(calls,["codex","claude"])
        self.assertEqual(result["comparison"]["status"],"single_or_failed")
        self.assertEqual(result["comparison"]["recommendations"],{"codex":"bid"})

    def test_missing_data_agreement_not_verified(self):
        a=fake_result("hold",3,status="unknown")["result"]
        b=fake_result("hold",3,status="unknown")["result"]
        a["factors"]={}
        b["factors"]={}
        out=execute_cross_review("합성",["codex","claude"],lambda p,t:{"status":"success","result":a if p=="codex" else b})
        self.assertEqual(len(out["comparison"]["agreements"]),0)

    def test_reject_bad_provider(self):
        with self.assertRaises(ValueError):
            execute_cross_review("abc",["codex","other"],lambda p,t:fake_result("hold"))

if __name__=="__main__": unittest.main()