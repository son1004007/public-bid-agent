"""독립 라벨이 붙은 RFP 추출 텍스트 '한 줄'만 대상으로 계산하는 3유형 분류 평가.

목적: 참가자격·평가기준·과업 후보에 대한 TP/FP/FN과 Precision/Recall/F1 계산.
입력: 입력자가 사전에 라벨링한 줄의 메모리 객체 및 선언한 표본 출처.
출력: 숫자형 집계만 반환. 원문/파일명/직원정보/개별 라벨은 응답에 포함하지 않음.
보안: 파일 읽기·쓰기/네트워크/LLM 호출 없음. 라벨 출처의 실제 독립성은 검증하지 못함.
한계: 표본에 포함된 *추출 텍스트 한 줄*의 3개 유형에 한정.
원본 PDF/HWP 파서 누락, 전체 문서 요구사항 누락률, 법적 자격·적격성은 측정하지 않음.
관련: test_rfp_taxonomy_benchmark.py, RFP_TAXONOMY_BENCHMARK_PROTOCOL_2026-10-16.md.
"""
from rfp_requirements import _category_matches

LABELS = ("participation", "evaluation", "scope")
ORIGINS = frozenset(("SYNTHETIC", "DECLARED_INDEPENDENT_HUMAN"))
MAX_LINES = 1000
MAX_LINE_CHARS = 1200


def _ratio(top, bottom):
    return round(top / bottom, 6) if bottom else None


def _score(tp, fp, fn):
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    # F1은 자신의 분모만 확인한다. FP-only/FN-only는 0.0이며 정의 불능이 아니다.
    f1 = _ratio(2 * tp, 2 * tp + fp + fn)
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision,
            "recall": recall, "f1": f1}


def evaluate(lines, *, origin):
    """원문이나 라벨을 반환하지 않으며, 입력의 대표성/독립성을 자동 보증하지 않는다."""
    if not isinstance(origin, str) or origin not in ORIGINS:
        raise ValueError("표본 라벨 출처 선언 필요")
    if not isinstance(lines, (list, tuple)) or not 1 <= len(lines) <= MAX_LINES:
        raise ValueError("라벨링 줄 수는 1~1000 범위여야 합니다")
    counts = {name: {"tp": 0, "fp": 0, "fn": 0} for name in LABELS}
    for case in lines:
        if not isinstance(case, dict) or set(case) != {"text", "labels"}:
            raise ValueError("라벨 항목은 text와 labels만 허용합니다")
        text, expected = case["text"], case["labels"]
        if (not isinstance(text, str) or not text.strip() or len(text) > MAX_LINE_CHARS
                or "\r" in text or "\n" in text):
            raise ValueError("평가는 길이 제한이 있는 단일 추출 줄만 허용합니다")
        if (not isinstance(expected, (list, tuple))
                or any(not isinstance(v, str) or v not in LABELS for v in expected)
                or len(set(expected)) != len(expected)):
            raise ValueError("정답 라벨 집합 형식 오류")
        truth = set(expected)
        predicted = set(_category_matches(text)).intersection(LABELS)
        for name in LABELS:
            if name in predicted and name in truth:
                counts[name]["tp"] += 1
            elif name in predicted:
                counts[name]["fp"] += 1
            elif name in truth:
                counts[name]["fn"] += 1
    totals = {key: sum(x[key] for x in counts.values()) for key in ("tp", "fp", "fn")}
    return {
        "evaluation_scope": "ANNOTATED_EXTRACTED_TEXT_LINES_ONLY",
        "label_origin_declared": origin,
        "label_origin_independently_verified": False,
        "line_count": len(lines),
        "categories": {name: _score(**values) for name, values in counts.items()},
        "micro": _score(**totals),
        "unmeasured": [
            "WHOLE_RFP_REQUIREMENTS_RECALL",
            "UNEXTRACTED_ORIGINAL_PDF_HWP_CONTENT",
            "LEGAL_ELIGIBILITY",
        ],
        "interpretation": "숫자는 제공된 라벨 줄에만 적용되며 전체 RFP 또는 독립 표본 대표성을 뜻하지 않음",
    }
