"""공식 RFP 텍스트의 비공개 청크 저장 계약.

책임: 파서가 반환한 최대 44,000자의 텍스트를 원문 식별 해시와 함께 사본에 저장.
입력: 공고 저장 폴더, 원본 바이너리 SHA-256, 파서 출력(text/characters/truncated).
출력: 공개 대시보드에 넣어도 본문이 노출되지 않는 제한된 메타데이터.
경계: 원문은 루프백 UI/API의 일반 응답에 포함하지 않으며 외부 전송 없음.
부작용/실패: 로컬 content-addressed JSON 원자 저장; 기존 파일 손상 시 안전 실패.
불변조건: 청크 연결 시 저장된 정규화 텍스트와 SHA가 일치, offset은 실제 PDF 페이지가 아님.
관련: docs/design/RFP_FULLTEXT_CHUNKS_2026-10-12.md / test_rfp_fulltext.py.
"""
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

CHUNK_CHARS = 4000
MAX_TEXT_CHARS = 44000
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def store(root, source_sha256, doc):
    """Parser-returned text is kept privately; dashboard receives metadata only."""
    if not isinstance(source_sha256, str) or not _HEX64.fullmatch(source_sha256):
        raise ValueError("공식 파일 SHA-256 형식 오류")
    if not isinstance(doc, dict) or not isinstance(doc.get("text"), str) or not doc["text"].strip():
        raise ValueError("추출 본문 형식 오류")
    text = doc["text"]
    if len(text) > MAX_TEXT_CHARS:
        raise ValueError("문서 추출 텍스트 보관 한도 초과")
    reported = doc.get("characters", len(text))
    if type(reported) is not int or reported < len(text):
        raise ValueError("파서 원문 길이 메타데이터 오류")
    was_truncated = doc.get("truncated", False)
    if type(was_truncated) is not bool:
        raise ValueError("파서 절단 상태 오류")
    text_digest = _hash(text.encode("utf-8"))
    reference = _hash((source_sha256 + ":" + text_digest).encode("ascii"))
    chunks = []
    for idx, start in enumerate(range(0, len(text), CHUNK_CHARS)):
        part = text[start:start + CHUNK_CHARS]
        chunks.append({"index": idx, "start": start, "end": start + len(part),
                       "sha256": _hash(part.encode("utf-8")), "text": part})
    record = {"schema_version": 1, "source_sha256": source_sha256,
              "text_sha256": text_digest, "reported_chars": reported,
              "stored_chars": len(text),
              "truncated_by_parser": was_truncated or reported > len(text),
              "position_basis": "EXTRACTED_TEXT_OFFSETS_NOT_ORIGINAL_PAGES",
              "chunks": chunks}
    directory = Path(root) / "rfp_fulltext"
    directory.mkdir(mode=0o700, parents=False, exist_ok=True)
    path = directory / (reference + ".json")
    def require_compatible():
        old = load(root, reference)
        if (old["text_sha256"] != text_digest
                or old["reported_chars"] != reported
                or old["truncated_by_parser"] != record["truncated_by_parser"]):
            raise ValueError("동일 RFP 텍스트의 파서 길이·절단 메타데이터 불일치; 기존 캐시 보존")

    if path.exists():
        require_compatible()
    else:
        filename = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                             prefix=".rfp-", suffix=".tmp", dir=directory,
                                             delete=False) as output:
                filename = output.name
                json.dump(record, output, ensure_ascii=False, separators=(",", ":"))
                output.flush()
                os.fsync(output.fileno())
            # 같은 디렉터리의 완성된 임시 파일을 원자적 hard-link로 등록한다.
            # os.replace는 다른 프로세스가 생성한 동명 캐시를 덮으므로 금지.
            try:
                os.link(filename, path)
            except FileExistsError:
                require_compatible()
        finally:
            if filename and os.path.exists(filename):
                os.unlink(filename)
    return {"fulltext_ref": reference, "fulltext_chars": len(text),
            "fulltext_reported_chars": reported, "fulltext_chunks": len(chunks),
            "fulltext_truncated": record["truncated_by_parser"],
            "fulltext_position_basis": record["position_basis"]}


def load(root, reference):
    """Internal-only read with strict identifier, chunk boundaries and hashes."""
    if not isinstance(reference, str) or not _HEX64.fullmatch(reference):
        raise ValueError("RFP 청크 참조값 오류")
    directory = Path(root) / "rfp_fulltext"
    record = json.loads((directory / (reference + ".json")).read_text(encoding="utf-8"))
    chunks = record.get("chunks", [])
    if not isinstance(chunks, list) or len(chunks) > 11:
        raise ValueError("RFP 청크 수 오류")
    parts = []
    next_start = 0
    for i, chunk in enumerate(chunks):
        if (not isinstance(chunk, dict) or chunk.get("index") != i
                or chunk.get("start") != next_start or not isinstance(chunk.get("text"), str)):
            raise ValueError("RFP 청크 위치 오류")
        part = chunk["text"]
        next_start += len(part)
        if (chunk.get("end") != next_start or len(part) > CHUNK_CHARS
                or chunk.get("sha256") != _hash(part.encode("utf-8"))):
            raise ValueError("RFP 청크 해시/길이 오류")
        parts.append(part)
    text = "".join(parts)
    if (next_start != record.get("stored_chars") or next_start > MAX_TEXT_CHARS
            or record.get("text_sha256") != _hash(text.encode("utf-8"))
            or record.get("source_sha256") is None
            or _hash((record["source_sha256"] + ":" + record["text_sha256"]).encode("ascii")) != reference):
        raise ValueError("RFP 텍스트 무결성 오류")
    return record
