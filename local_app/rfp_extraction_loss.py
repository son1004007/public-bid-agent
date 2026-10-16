"""RFP 추출 문자 절단 증거의 비식별·읽기 전용 진단.

목적/책임: 저장된 파서 길이 메타데이터로 보관되지 않은 문자 수를 정량화한다.
입력/출력: 공고별 문서 증거 메타데이터 -> 정수 집계만 출력.
신뢰 경계: 원문·URL·SHA·파일명·개별 공고 ID는 반환/로그하지 않는다.
상태 변경/부작용: 없음. 파일 열기, 네트워크, 외부 AI 호출 금지.
실패: 잘못된 길이/버전/형식은 추정하지 않고 검증 불가로 기록한다.
핵심 불변조건: 이 차이는 '저장 메타데이터가 신고한 미보관 문자 수'이지
원본 PDF/HWP 누락률, 필수 요건 누락 수, 중복 제외 유일 문자 수가 아니다.
관련: rfp_coverage.py, rfp_fulltext.py, test_rfp_extraction_loss.py, D-17.
"""

MAX_SCAN = 120
MAX_STORED_CHARS = 44_000
MAX_REPORTED_CHARS = 20_000_000
_KEYS = (
    "extracted_records", "truncation_records", "quantified_truncation_records",
    "unquantified_truncation_records", "reported_unstored_characters",
    "warning_records", "inconsistent_metadata_records",
    "evidence_scan_limit_exceeded", "malformed_evidence"
)


def empty():
    return {key: 0 for key in _KEYS}


def _valid_reference(value):
    return (isinstance(value, str) and len(value) == 64
            and all(c in "0123456789abcdef" for c in value))


def _valid_lengths(item):
    stored, reported = item.get("fulltext_chars"), item.get("fulltext_reported_chars")
    return (type(stored) is int and 0 < stored <= MAX_STORED_CHARS
            and type(reported) is int and stored <= reported <= MAX_REPORTED_CHARS
            and _valid_reference(item.get("fulltext_ref")))


def inspect(notice):
    """원본 대신 증거 기록 최대 120개만 읽고 출처 식별값 없이 집계한다."""
    result = empty()
    evidence = notice.get("document_evidence", [])
    if not isinstance(evidence, list):
        result["malformed_evidence"] = 1
        return result
    if len(evidence) > MAX_SCAN:
        result["evidence_scan_limit_exceeded"] = 1
    for item in evidence[:MAX_SCAN]:
        if not isinstance(item, dict):
            result["malformed_evidence"] = 1
            continue
        if item.get("status") != "EXTRACTED":
            continue
        result["extracted_records"] += 1
        if isinstance(item.get("warnings"), list) and bool(item["warnings"]):
            result["warning_records"] += 1
        truncated = item.get("fulltext_truncated")
        if truncated is True:
            result["truncation_records"] += 1
            if _valid_lengths(item):
                lost = item["fulltext_reported_chars"] - item["fulltext_chars"]
                if lost > 0:
                    result["quantified_truncation_records"] += 1
                    result["reported_unstored_characters"] += lost
                    continue
            result["unquantified_truncation_records"] += 1
        elif truncated is not None and type(truncated) is not bool:
            result["inconsistent_metadata_records"] += 1
        elif truncated is False and _valid_lengths(item):
            if item["fulltext_reported_chars"] > item["fulltext_chars"]:
                result["inconsistent_metadata_records"] += 1
    return result


def accumulate(aggregate, report):
    """동일 문서의 중복 저장 가능성을 유지한 관측 기록 합계."""
    for key in _KEYS:
        aggregate[key] += report[key]
