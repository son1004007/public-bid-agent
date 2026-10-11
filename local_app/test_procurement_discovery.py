"""검토대기 메타데이터 후보 재발굴의 출처/미확인/원본불변 계약."""
import copy
import unittest
from procurement_discovery import evaluate, shortlist

class DiscoveryTests(unittest.TestCase):
    def test_review_and_source_evidence(self):
        n={"id":"G2B-test","department_status":"REVIEW",
           "title":"정보시스템 통합 고도화 사업",
           "procurement_classification":"정보시스템 개발 서비스",
           "information_business":"Y","window_status":"OPEN",
           "attachments":[{"name":"제안요청서.pdf"}]}
        original=copy.deepcopy(n)
        result=evaluate(n)
        self.assertGreaterEqual(result["score"],5)
        self.assertEqual(result["eligibility"],"UNVERIFIED")
        self.assertEqual(result["status"],"DETAIL_REVIEW_REQUIRED")
        self.assertIn("공공조달분류"," ".join(x["source"] for x in result["evidence"]))
        self.assertEqual(original,n)

    def test_preserves_low_priority_and_candidates(self):
        n={"id":"one","department_status":"REVIEW","title":"청소 용역",
           "information_business":"N"}
        candidate={**n,"id":"two","department_status":"CANDIDATE"}
        self.assertEqual(shortlist([n,candidate]),{"total_review":1,"priority_count":0,
             "results":[],"basis":"공식 메타데이터만 사용한 상세검토 우선순위, SW 개발/법적 참가자격 미확인"})

    def test_order_open_first_and_limit(self):
        n={"id":"a","department_status":"REVIEW","title":"신규 정보시스템 개발",
            "information_business":"Y","window_status":"CLOSED"}
        r={**n,"id":"b","window_status":"OPEN"}
        result=shortlist([n,r],limit=1)
        self.assertEqual(result["priority_count"],2)
        self.assertEqual(result["results"][0]["id"],"b")
        with self.assertRaises(ValueError):shortlist([n],0)

if __name__=="__main__":unittest.main()
