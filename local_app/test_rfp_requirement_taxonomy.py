"""정답 라벨이 알려진 합성 문장으로 입찰참가자격/평가기준/과업범위 분리 검증.

실제 공공 RFP 평가 정확도라고 해석하지 않는다. 정답 라벨은 테스트 작성자가 정의.
외부 LLM, 회사 자료, 로컬 비공개 RFP를 사용하지 않는다.
"""
import unittest
from rfp_requirements import _category_matches

# (합성 문장, 기대되는 세 유형). 다른 기존 6개 유형은 이 검사의 범위 밖.
CASES = (
    ("입찰참가자격: 나라장터 등록 업체", ("participation",)),
    ("참가자격은 소프트웨어사업자로 제한", ("participation",)),
    ("공동수급체 구성에 의한 참여 가능", ("participation",)),
    ("공동수급 허용 범위는 3개 업체 이내", ("participation",)),
    ("공동수급협정서 제출해야 함", ("participation",)),
    ("공동도급 참여 제한", ("participation",)),
    ("단독 입찰만 허용", ("participation",)),
    ("직접생산확인서 보유 업체", ("participation",)),
    ("중소기업확인서 제출 필수", ("participation",)),
    ("입찰 등록을 마감 전 완료", ("participation",)),
    ("기술평가 배점 80점", ("evaluation",)),
    ("제안서 평가 방법은 정량평가와 정성평가", ("evaluation",)),
    ("공동수급체 구성원별 점수에 지분율을 곱한 후 최종 평가", ("evaluation",)),
    ("공동수급체의 평가점수를 합산하여 높은 순서대로 선정", ("evaluation",)),
    ("평가 결과 동점인 경우 소수점 아래 숫자를 비교", ("evaluation",)),
    ("입찰 참여 기업의 동점 처리 규정", ("evaluation",)),
    ("평가기준표에 따라 심사위원 평가", ("evaluation",)),
    ("평가 점수가 85점 이상인 업체를 협상대상자로 선정", ("evaluation",)),
    ("가격평가 산식 및 평점 계산", ("evaluation",)),
    ("정량평가 항목별 가점과 감점", ("evaluation",)),
    ("과업범위: 데이터 수집 플랫폼 구축", ("scope",)),
    ("주요 과업은 공공 API 연계 구축", ("scope",)),
    ("기능 요구사항에 따른 시스템 개발", ("scope",)),
    ("수행 내용: DB 마이그레이션 및 통계 개발", ("scope",)),
    ("업무 범위: 현황 분석 및 운영시스템 설계", ("scope",)),
    ("사업 내용: 데이터 품질관리 체계 마련", ("scope",)),
    ("과업 범위를 평가할 때의 배점 기준", ("evaluation",)),
    ("수행 내용의 평가 방법 및 배점", ("evaluation",)),
    ("공동수급체 구성원별 평가 배점 기준", ("evaluation",)),
    ("공동수급체의 구성 조건은 참여 제한 사유", ("participation",)),
    ("참가자격과 평가기준을 모두 확인", ("participation", "evaluation")),
    ("과업내용은 API 개발, 평가기준은 배점표 확인", ("scope", "evaluation")),
    ("기술평가 70점 및 가격평가 30점", ("evaluation",)),
    ("사업예산 5억, 사업기간 8개월", ()),
    ("제안요청서의 원본 파일명을 기록", ()),
    ("감리 수행 업체의 계약서 작성 안내", ()),
    ("학생별 이해도, 퀴즈 점수, 추세를 조회하는 기능 구현", ()),
    ("평가결과 승복 확인서 1부를 제출", ()),
    ("본 사업 내용의 이해도와 제안사의 추진 전략을 평가", ("evaluation",)),
    ("입찰에 참가하는 자는 과업내용서 등을 반드시 열람하고 숙지", ()),
    ("이 용역 입찰계약에서 하도급을 실시할 경우 과업내용서의 승인절차 준수", ()),
    ("국가 전자정부법의 감리법인 업무범위를 준수", ()),
    ("과업내용 및 시스템관련문의: 전화번호 02-123-4567", ()),
    ("과업내용의 변경 및 계약금액 조정", ()),
    ("나. 기타 기능 요구사항", ()),
    ("가. 과업내용: 데이터 처리 API 개발 및 배포", ("scope",)),
    ("과업내용은 서비스 운영에 필요한 사용자 인증 기능 구현", ("scope",)),
    ("공동수급체의 평가점수를 합산하여 동점 처리", ("evaluation",)),
    ("기술평가와 가격평가 비율은 80대20", ("evaluation",)),
    ("공동수급체 참여업체별 평가점수를 합산하여 선정", ("evaluation",)),
    ("기능 요구사항: API 연계 개발, 세부 사항은 협의하여 처리", ("scope",)),
    ("과업 범위: 데이터 연계 구축 및 추가 요구사항 반영", ("scope",)),
    ("공동수급 협정에 따른 구성원별 점수 합산", ("evaluation",)),
    ("공동수급 협정에 따른 구성원별 점수 합산이 가능한 경우", ("evaluation",)),
    ("공동수급체 구성이 허용되는 경우", ("participation",)),
    ("과업내용 변경 및 데이터 연계 시스템 개발", ("scope",)),
    ("과업내용 변경 및 사업비 정산", ()),
    ("공동수급협정서 제출 필수", ("participation",)),
)


def labels(text):
    return set(_category_matches(text)).intersection({"participation", "evaluation", "scope"})


class RfpTaxonomyBenchmarkTests(unittest.TestCase):
    def test_labeled_synthetic_three_way_classification(self):
        actual_tp = actual_fp = actual_fn = 0
        for text, expected_tuple in CASES:
            expected = set(expected_tuple)
            observed = labels(text)
            with self.subTest(text=text):
                self.assertEqual(observed, expected)
            actual_tp += len(observed & expected)
            actual_fp += len(observed - expected)
            actual_fn += len(expected - observed)
        self.assertEqual((actual_fp, actual_fn), (0, 0))
        self.assertGreater(actual_tp, 30)

    def test_joint_venture_scoring_is_not_eligibility(self):
        for snippet in ("공동수급 협정에 따른 구성원별 점수 합산",
                        "공동수급체 구성원별 점수를 합산", "공동수급체의 평가 결과 동점",
                        "공동수급체 구성원별 해당 점수로 평가"):
            with self.subTest(snippet=snippet):
                self.assertNotIn("participation", labels(snippet))
                self.assertIn("evaluation", labels(snippet))


if __name__ == "__main__":
    unittest.main()
