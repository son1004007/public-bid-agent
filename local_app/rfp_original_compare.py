"""RFP 공식 원본 파일과 저장된 텍스트 증거의 오프라인 비교.

목적/책임: 사용자가 로컬에서 확보한 공식 첨부 bytes, 공고 내 공식 링크/증거,
  검증된 fulltext 캐시와 현재 지정된 파서의 재추출 텍스트·길이 일치만 판정한다.
  저장·현재 provenance 모두 엄격한 schema 검증 후 기록 설정의 동일성을 비교한다.
  구형 증거는 NOT_VERIFIED이며 OCR 실행 파일·언어팩 동일성은 검증하지 않는다.
입력/출력: 공식 attachment, EXTRACTED proof, 이미 load()로 검증한 캐시 record,
  원본 bytes, 안전하게 분리 실행되는 로컬 parser callback -> 고정 상태 코드/정수.
신뢰 경계: 링크 정합/원본 SHA/캐시 SHA·참조·텍스트 검사. 입력 원문/경고를
  로그/파일/외부 LLM/네트워크로 내보내지 않는다. 자체 I/O가 없는 순수 어댑터.
부작용/실패: 파일 읽기·저장/다운로드/자동 재시도 없음. 부정합 시 실패 상태로
  중단. 실제 호출자는 server.extract_in_subprocess와 검증된 cache load 사용.
핵심 불변조건: 텍스트 재현은 PDF/HWP 원본의 전체 표·각주·이미지/OCR,
  공식 최신성이나 필수요건 Recall을 증명하지 않는다. 독립 육안 검증 필요.
관련: D-17, rfp_fulltext.py, procurement_documents.py,
  test_rfp_original_compare.py, docs/design/RFP_ORIGINAL_AUDIT_PLAN_2026-10-16.md.
"""
import hashlib

from procurement_documents import official_url, SUPPORTED, MAX_BYTES
from pathlib import PurePath

MAX_STORED = 44_000
_MAX_CHUNKS = 11


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _hex64(v):
    return isinstance(v, str) and len(v) == 64 and all(c in "0123456789abcdef" for c in v)


def _valid_parser_provenance(value):
    keys = {"schema_version", "fingerprint_sha256", "method",
            "ocr_binary_and_langpack_version"}
    return (isinstance(value, dict) and set(value) == keys
            and type(value["schema_version"]) is int and value["schema_version"] == 1
            and _hex64(value["fingerprint_sha256"])
            and isinstance(value["method"], str) and 1 <= len(value["method"]) <= 100
            and value["ocr_binary_and_langpack_version"] == "NOT_CAPTURED")


def _result(status, **counts):
    # 고정된 상태와 정수만 반환한다. 원본/파일명/링크/해시 절대 반환 금지.
    return {"status": status, "source_sha_matched": status not in (
        "INVALID_EVIDENCE", "ORIGINAL_SHA_MISMATCH", "ORIGINAL_UNAVAILABLE"),
        "text_prefix_matched": status in ("REPRODUCED_TEXT", "REPRODUCED_TRUNCATED_PREFIX"),
        "length_truncation_metadata_reproducibility": (
            "MATCHED" if status in ("REPRODUCED_TEXT", "REPRODUCED_TRUNCATED_PREFIX")
            else "MISMATCH" if status == "PARSER_METADATA_CHANGED" else "NOT_VERIFIED"),
        "parser_method_version_ocr_reproducibility": "NOT_VERIFIED",
        "original_page_table_ocr_coverage": "NOT_VERIFIED", **counts}


def compare(attachment, proof, record, raw, parser):
    """캐시와 공식 원본의 추출 텍스트 재현성을 로컬 메모리에서만 대조한다."""
    if not isinstance(attachment, dict) or not isinstance(proof, dict):
        return _result("INVALID_EVIDENCE")
    name, url = attachment.get("name"), attachment.get("url")
    if (not isinstance(name, str) or len(name) > 200
            or PurePath(name).suffix.lower() not in SUPPORTED
            or not official_url(url)):
        return _result("INVALID_EVIDENCE")
    identity = _sha((url + "\n" + name).encode("utf-8"))
    expected_sha, reference = proof.get("sha256"), proof.get("fulltext_ref")
    if (proof.get("status") != "EXTRACTED" or proof.get("identity") != identity
            or proof.get("name") != name or not _hex64(expected_sha)
            or not _hex64(reference)):
        return _result("INVALID_EVIDENCE")
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        return _result("ORIGINAL_UNAVAILABLE")
    if _sha(raw) != expected_sha:
        return _result("ORIGINAL_SHA_MISMATCH")
    # record는 반드시 rfp_fulltext.load()로 검증한 사본을 전달해야 한다.
    # 이중 방어를 위해 공개 API 밖에서만 캐시 정보의 해시/참조를 재검증한다.
    if (not isinstance(record, dict) or record.get("source_sha256") != expected_sha
            or not _hex64(record.get("text_sha256"))):
        return _result("CACHE_MISMATCH")
    chunks = record.get("chunks")
    if not isinstance(chunks, list) or not 0 < len(chunks) <= _MAX_CHUNKS:
        return _result("CACHE_MISMATCH")
    if any(not isinstance(c, dict) or not isinstance(c.get("text"), str)
           or len(c["text"]) > 4000 for c in chunks):
        return _result("CACHE_MISMATCH")
    text = "".join(c["text"] for c in chunks)
    text_sha = _sha(text.encode("utf-8"))
    ref = _sha((expected_sha + ":" + text_sha).encode("ascii"))
    stored, reported = record.get("stored_chars"), record.get("reported_chars")
    truncated = record.get("truncated_by_parser")
    position = "EXTRACTED_TEXT_OFFSETS_NOT_ORIGINAL_PAGES"
    if (type(record.get("schema_version")) is not int or record["schema_version"] != 1
            or type(stored) is not int or not 0 < stored <= MAX_STORED
            or type(reported) is not int or not stored <= reported <= 20_000_000
            or type(truncated) is not bool
            or (reported > stored and not truncated)
            or record.get("position_basis") != position
            or len(text) != stored or text_sha != record["text_sha256"]
            or ref != reference):
        return _result("CACHE_MISMATCH")
    # 같은 reference여도 공고에 저장된 fulltext_* 메타데이터가 손상됐을 수 있다.
    # bool은 Python 정수와 같다고 비교될 수 있으므로 종류부터 구분한다.
    fields = (("fulltext_chars", stored), ("fulltext_reported_chars", reported),
              ("fulltext_chunks", len(chunks)), ("fulltext_truncated", truncated),
              ("fulltext_position_basis", position))
    if (type(proof.get("fulltext_chars")) is not int
            or type(proof.get("fulltext_reported_chars")) is not int
            or type(proof.get("fulltext_chunks")) is not int
            or type(proof.get("fulltext_truncated")) is not bool
            or any(proof.get(key) != value for key, value in fields)):
        return _result("CACHE_MISMATCH")
    if not callable(parser):
        return _result("PARSER_UNAVAILABLE")
    try:
        parsed = parser(name, raw)
    except (ValueError, OSError, TimeoutError, TypeError):
        return _result("PARSER_UNAVAILABLE")
    if not isinstance(parsed, dict) or not isinstance(parsed.get("text"), str):
        return _result("PARSER_UNAVAILABLE")
    fresh = parsed["text"]
    if len(fresh) > MAX_STORED or not fresh.strip():
        return _result("PARSER_UNAVAILABLE")
    reported = parsed.get("characters", len(fresh))
    truncated = parsed.get("truncated", False)
    if (type(reported) is not int or not len(fresh) <= reported <= 20_000_000
            or type(truncated) is not bool):
        return _result("PARSER_UNAVAILABLE")
    if fresh != text:
        return _result("REEXTRACTED_TEXT_DIFFERS")
    if reported != record.get("reported_chars") or (
            (truncated or reported > len(fresh))
            != record.get("truncated_by_parser")):
        return _result("PARSER_METADATA_CHANGED")
    # 새로 기록된 코드·라이브러리·설정 fingerprint에 한해 재추출 환경이
    # 같은지 비교. OCR 바이너리/언어 데이터 버전은 별도 기록이 없어 계속 미검증.
    saved=proof.get("parser_provenance")
    current=parsed.get("parser_provenance")
    config="NOT_VERIFIED"
    if _valid_parser_provenance(saved):
        config=("RECORDED_CONFIG_MATCHED_OCR_BINARY_UNVERIFIED"
                if _valid_parser_provenance(current) and current==saved
                else "RECORDED_CONFIG_CHANGED_OR_UNAVAILABLE")
    if truncated or reported > len(fresh):
        return _result("REPRODUCED_TRUNCATED_PREFIX", stored_chars=len(fresh),
                       reported_chars=reported,
                       parser_method_version_ocr_reproducibility=config)
    return _result("REPRODUCED_TEXT", stored_chars=len(fresh),
                   reported_chars=reported,
                   parser_method_version_ocr_reproducibility=config)
