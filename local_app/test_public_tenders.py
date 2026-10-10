"""수동 수집한 실제 입찰 공고와 가상 부서 정보의 근거 경계를 확인한다.

공고의 법적 효력을 판단하지 않고, 형식·출처·가상부서 명시 및 기대 안전판만 검증.
"""
import json
import unittest
from datetime import datetime
from pathlib import Path

DATA = Path(__file__).parent / "fixtures" / "public_tenders_2026_10_10.json"


class PublicNoticeCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(DATA.read_text(encoding="utf-8"))

    def test_three_distinct_public_bids_and_scenarios(self):
        d=self.data
        self.assertEqual(len(d["notices"]),3)
        self.assertEqual(len(d["scenarios"]),4)
        self.assertEqual(len({x["id"] for x in d["notices"]}),3)
        self.assertEqual(len({x["id"] for x in d["scenarios"]}),4)
        self.assertTrue(all(x["notice_id"] in {y["id"] for y in d["notices"]} for x in d["scenarios"]))

    def test_source_and_date_provenance_required(self):
        d=self.data
        self.assertIn("원본",d["notice_source_quality"])
        self.assertIn("가상",d["department_profile_quality"])
        for bid in d["notices"]:
            self.assertRegex(bid["id"],r"^R26BK[0-9]{8}-[0-9]{3}$")
            self.assertGreaterEqual(len(bid["public_facts"]),4)
            self.assertTrue(bid["title"] and bid["issuer"])
            self.assertTrue(bid["sources"])
            self.assertTrue(all(x["url"].startswith("https://") for x in bid["sources"]))
            dt=datetime.fromisoformat(bid["deadline_local"])
            self.assertIsNotNone(dt.tzinfo)
        for test in d["scenarios"]:
            self.assertGreaterEqual(len(test["simulated_profile"]),3)
            self.assertIn("expected",test)
            self.assertIn("crucial_expectation",test)

if __name__=="__main__": unittest.main()
