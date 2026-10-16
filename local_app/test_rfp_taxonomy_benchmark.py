"""3분류 라벨 평가는 합성 자료만 사용하며 RFP 원문 전체 정확도로 해석하지 않는다."""
import unittest

from rfp_taxonomy_benchmark import evaluate, _score
from test_rfp_requirement_taxonomy import CASES


class TaxonomyBenchmarkTests(unittest.TestCase):
    def test_labeled_synthetic_examples_are_limited_to_annotated_lines(self):
        rows = [{"text": text, "labels": list(labels)} for text, labels in CASES]
        report = evaluate(rows, origin="SYNTHETIC")
        self.assertEqual(report["line_count"], len(CASES))
        self.assertEqual(report["evaluation_scope"], "ANNOTATED_EXTRACTED_TEXT_LINES_ONLY")
        self.assertFalse(report["label_origin_independently_verified"])
        self.assertEqual(report["micro"]["precision"], 1)
        self.assertEqual(report["micro"]["recall"], 1)
        self.assertEqual(report["micro"]["f1"], 1)
        self.assertIn("WHOLE_RFP_REQUIREMENTS_RECALL", report["unmeasured"])
        self.assertNotIn("text", str(report))
        self.assertTrue(all(set(v) == {"tp","fp","fn","precision","recall","f1"}
                            for v in report["categories"].values()))

    def test_false_positives_and_false_negatives_are_not_silenced(self):
        rows = [
            {"text": "입찰참가자격은 등록 업체로 제한", "labels": ["participation"]},
            {"text": "기술평가 배점 80점", "labels": []},  # false-positive
            {"text": "담당 개발팀은 데이터를 정규화하고 이관한다", "labels": ["scope"]},  # false-negative
        ]
        report = evaluate(rows, origin="DECLARED_INDEPENDENT_HUMAN")
        self.assertEqual(report["micro"]["tp"], 1)
        self.assertEqual(report["micro"]["fp"], 1)
        self.assertEqual(report["micro"]["fn"], 1)
        self.assertEqual(report["micro"]["precision"], 0.5)
        self.assertEqual(report["micro"]["recall"], 0.5)
        self.assertEqual(report["micro"]["f1"], 0.5)
        self.assertFalse(report["label_origin_independently_verified"])

    def test_absent_ground_truth_is_undefined_not_perfect_recall(self):
        report = evaluate([{"text": "문서 원본 확인", "labels": []}], origin="SYNTHETIC")
        self.assertIsNone(report["micro"]["precision"])
        self.assertIsNone(report["micro"]["recall"])
        self.assertIsNone(report["micro"]["f1"])

    def test_f1_only_false_positive_and_false_negative_are_zero(self):
        self.assertEqual(_score(0, 1, 0), {
            "tp":0, "fp":1, "fn":0, "precision":0.0, "recall":None, "f1":0.0
        })
        self.assertEqual(_score(0, 0, 1), {
            "tp":0, "fp":0, "fn":1, "precision":None, "recall":0.0, "f1":0.0
        })
        self.assertIsNone(_score(0, 0, 0)["f1"])

    def test_bad_annotation_and_multiline_are_rejected(self):
        sample = {"text": "참가 자격", "labels": ["participation"]}
        for items, origin in [
            ([], "SYNTHETIC"),
            ([sample], "UNVERIFIED"),
            ([sample], []),
            ([{"text": "참가 자격\n점수", "labels": ["participation"]}], "SYNTHETIC"),
            ([{"text": "참가 자격", "labels": ["fake"]}], "SYNTHETIC"),
            ([{"text": "참가 자격", "labels": ["scope", "scope"]}], "SYNTHETIC"),
            ([{"text": "참가 자격", "labels": ["scope"], "secret": "ignored"}], "SYNTHETIC"),
            (["not a line"], "SYNTHETIC"),
            ([{"text": "x"*1201, "labels": []}], "SYNTHETIC"),
        ]:
            with self.subTest(items=repr(items)[:40], origin=origin):
                with self.assertRaises(ValueError):
                    evaluate(items, origin=origin)


if __name__ == "__main__":
    unittest.main()
