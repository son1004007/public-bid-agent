"""기존 공식 RFP 추출 근거를 원본 검증 후 로컬 청크로 소급 보강하는 배치.

책임: 이전 EXTRACTED 문서의 SHA-256, 첨부 식별값, 추출 글자수/발췌 일치 확인.
입력/출력: 비공개 dashboard.json + 검증된 공식 첨부; metadata 보강 및 처리 원장.
신뢰 경계: 공식 HTTPS 다운로드 제한, 외부 AI 전송/공개 데이터 응답 없음.
상태 변경: 원본 기록의 문서 증거에 fulltext_ref 등 추가, 독립 원장 저장.
실패/중단: 원본 수정·요건/사람 결정 덮어쓰기 금지, 변경·불일치 별도 상태.
불변조건: 기존 excerpt/원문 SHA/판단 이력 불변. 재실행은 성공 건을 건너뜀.
관련: docs/design/RFP_BACKFILL_VERIFIED_2026-10-12.md, test_rfp_backfill.py.
"""
import hashlib
import json
import re
import time
from pathlib import Path

from dashboard_backend import read as read_dashboard
from json_transaction import transaction
from procurement_documents import official_url, fetch_attachment, DocumentFetchError
from rfp_fulltext import store as store_fulltext, load as load_fulltext

HEX64 = re.compile(r"^[0-9a-f]{64}$")
FINAL = {"DONE", "SOURCE_CHANGED", "PARSER_CHANGED", "UNMATCHED", "FETCH_FAILED"}
METADATA_KEYS = frozenset({
    "fulltext_ref", "fulltext_chars", "fulltext_reported_chars",
    "fulltext_chunks", "fulltext_truncated", "fulltext_position_basis"
})


def signature(items):
    source = [(n["id"], e["identity"], e["sha256"])
              for n, e in items]
    return hashlib.sha256(json.dumps(source, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def eligible(board, target_ids):
    """Preserve source ordering; only 127 previously extracted documents in the pinned set."""
    allowed = set(target_ids)
    result = []
    for notice in board["notices"]:
        if notice["id"] not in allowed:
            continue
        for evidence in notice.get("document_evidence", []):
            if not isinstance(evidence, dict) or evidence.get("status") != "EXTRACTED":
                continue
            if not isinstance(evidence.get("identity"), str) or not HEX64.fullmatch(evidence["identity"]):
                continue
            if not isinstance(evidence.get("sha256"), str) or not HEX64.fullmatch(evidence["sha256"]):
                continue
            if not isinstance(evidence.get("excerpt"), str) or not evidence["excerpt"]:
                continue
            if type(evidence.get("chars")) is not int or evidence["chars"] <= 0:
                continue
            result.append((notice, evidence))
    return result


def match_attachment(notice, evidence):
    """Exact old document identity, never filename-only / best-effort matching."""
    matches = []
    for item in notice.get("attachments", []):
        if not isinstance(item, dict):
            continue
        name, url = item.get("name"), item.get("url")
        if not isinstance(name, str) or not official_url(url):
            continue
        digest = hashlib.sha256((url + "\n" + name).encode()).hexdigest()
        if digest == evidence["identity"]:
            matches.append(item)
    return matches[0] if len(matches) == 1 else None


def verify_and_store(root, notice, evidence, extractor, fetcher=fetch_attachment,
                     writer=store_fulltext):
    """Only the identical binary and identical formerly extracted prefix may be backfilled."""
    item = match_attachment(notice, evidence)
    if item is None:
        return "UNMATCHED", None
    try:
        raw = fetcher(item["url"])
    except (DocumentFetchError, OSError, TimeoutError, ValueError):
        return "FETCH_FAILED", None
    binary_hash = hashlib.sha256(raw).hexdigest()
    if binary_hash != evidence["sha256"]:
        return "SOURCE_CHANGED", None
    try:
        parsed = extractor(item["name"], raw)
        text = parsed.get("text") if isinstance(parsed, dict) else None
        if (not isinstance(text, str) or not text.strip()
                or len(text) != evidence["chars"]
                or text[:len(evidence["excerpt"])] != evidence["excerpt"]):
            return "PARSER_CHANGED", None
        meta = writer(root, binary_hash, parsed)
        # The writer is a trust boundary: metadata may never override old evidence.
        if not isinstance(meta, dict) or set(meta) != METADATA_KEYS:
            raise ValueError("청크 메타데이터 허용 필드 위반")
        if (not isinstance(meta["fulltext_ref"], str)
                or not HEX64.fullmatch(meta["fulltext_ref"])
                or type(meta["fulltext_chars"]) is not int
                or meta["fulltext_chars"] != evidence["chars"]
                or type(meta["fulltext_reported_chars"]) is not int
                or meta["fulltext_reported_chars"] < meta["fulltext_chars"]
                or type(meta["fulltext_chunks"]) is not int
                or not 1 <= meta["fulltext_chunks"] <= 11
                or type(meta["fulltext_truncated"]) is not bool
                or meta["fulltext_position_basis"] != "EXTRACTED_TEXT_OFFSETS_NOT_ORIGINAL_PAGES"):
            raise ValueError("청크 메타데이터 형식 오류")
        record = load_fulltext(root, meta["fulltext_ref"])
        reconstructed = "".join(chunk["text"] for chunk in record["chunks"])
        if (record["source_sha256"] != binary_hash
                or len(reconstructed) != evidence["chars"]
                or reconstructed[:len(evidence["excerpt"])] != evidence["excerpt"]
                or len(record["chunks"]) != meta["fulltext_chunks"]
                or record["reported_chars"] != meta["fulltext_reported_chars"]
                or record["truncated_by_parser"] != meta["fulltext_truncated"]
                or record["position_basis"] != meta["fulltext_position_basis"]):
            raise ValueError("청크 저장 내용·기존 근거 불일치")
    except (DocumentFetchError, ValueError, OSError, TimeoutError, TypeError):
        return "PARSER_CHANGED", None
    return "DONE", meta


def orphan_inventory(root):
    """Read-only inventory of content-addressed files lacking dashboard references."""
    directory = Path(root) / "rfp_fulltext"
    if not directory.exists():
        return {"sidecars": 0, "referenced": 0, "unreferenced": 0}
    board = read_dashboard(Path(root) / "dashboard.json")
    refs = {e.get("fulltext_ref") for n in board["notices"]
            for e in n.get("document_evidence", [])
            if isinstance(e, dict) and isinstance(e.get("fulltext_ref"), str)}
    paths = list(directory.glob("*.json"))
    if len(paths) > 2500:
        raise ValueError("사이드카 수 상한 초과")
    return {"sidecars": len(paths),
            "referenced": sum(p.stem in refs for p in paths),
            "unreferenced": sum(p.stem not in refs for p in paths)}


class Backfill:
    """One bounded synchronous slice. Caller provides an isolated writable root."""

    def __init__(self, root, target_ids, persist, extractor, fetcher=fetch_attachment,
                 writer=store_fulltext, delay=3):
        self.root, self.target_ids = Path(root), tuple(target_ids)
        self.persist, self.extractor = persist, extractor
        self.fetcher, self.writer, self.delay = fetcher, writer, delay
        if len(self.target_ids) != len(set(self.target_ids)) or len(self.target_ids) > 143:
            raise ValueError("이관 대상 수/중복 오류")

    def _state(self, source_signature):
        path = self.root / "rfp_backfill.json"
        if path.exists():
            state = json.loads(path.read_text(encoding="utf-8"))
            if (state.get("schema_version") != 1 or state.get("scope_hash") != source_signature
                    or not isinstance(state.get("items"), dict)):
                raise ValueError("이관 원장/대상 변경: 중지")
            return state
        return {"schema_version": 1, "revision": 0, "scope_hash": source_signature,
                "items": {}}

    def run(self, limit=10):
        # Same-stage writers must never run the same backfill concurrently.
        with transaction(self.root, timeout=0, name=".rfp-batch-worker.lock"):
            return self._run(limit)

    def _run(self, limit=10):
        if type(limit) is not int or limit not in (1, 3, 10, 25):
            raise ValueError("회차는 1/3/10/25건")
        board = read_dashboard(self.root / "dashboard.json")
        items = eligible(board, self.target_ids)
        if not items:
            raise ValueError("이관 대상 없음")
        scope = signature(items)
        with transaction(self.root):
            state = self._state(scope)
        complete = 0
        for notice, evidence in items:
            key = hashlib.sha256((notice["id"]+"\n"+evidence["identity"]).encode()).hexdigest()
            if state["items"].get(key, {}).get("status") in FINAL:
                continue
            if evidence.get("fulltext_ref"):
                # Crash after dashboard update but before ledger: resume without download.
                # A forged/stale reference cannot be trusted solely because it exists.
                cached = load_fulltext(self.root, evidence["fulltext_ref"])
                content = "".join(chunk["text"] for chunk in cached["chunks"])
                if (cached["source_sha256"] != evidence["sha256"]
                        or cached["stored_chars"] != evidence["chars"]
                        or content[:len(evidence["excerpt"])] != evidence["excerpt"]):
                    raise ValueError("기존 청크 근거 불일치: 중지")
                with transaction(self.root):
                    state = self._state(scope)
                    state["items"][key] = {"status": "DONE", "cached": True}
                    state["revision"] += 1
                    self.persist(state, self.root / "rfp_backfill.json")
                continue
            if complete >= limit:
                break
            outcome, meta = verify_and_store(
                self.root, notice, evidence, self.extractor, self.fetcher, self.writer)
            if outcome == "DONE":
                with transaction(self.root):
                    latest = read_dashboard(self.root / "dashboard.json")
                    current = next((n for n in latest["notices"] if n["id"] == notice["id"]), None)
                    current_evidence = next(
                        (e for e in current.get("document_evidence", [])
                         if isinstance(e, dict) and e.get("identity") == evidence["identity"]),
                        None) if current else None
                    if (current_evidence is None or current_evidence.get("sha256") != evidence["sha256"]
                            or current_evidence.get("excerpt") != evidence["excerpt"]
                            or current_evidence.get("chars") != evidence["chars"]
                            or (current_evidence.get("fulltext_ref")
                                and current_evidence["fulltext_ref"] != meta["fulltext_ref"])):
                        raise ValueError("재수집 중 근거 충돌: 중지")
                    current_evidence.update(meta)
                    latest["revision"] += 1
                    self.persist(latest, self.root / "dashboard.json")
            with transaction(self.root):
                state = self._state(scope)
                state["items"][key] = {"status": outcome}
                state["revision"] += 1
                self.persist(state, self.root / "rfp_backfill.json")
            complete += 1
            if complete < limit and self.delay:
                time.sleep(self.delay)
        state = self._state(scope)
        counts = {status: sum(v.get("status") == status for v in state["items"].values())
                  for status in ("DONE", "SOURCE_CHANGED", "PARSER_CHANGED",
                                 "UNMATCHED", "FETCH_FAILED")}
        counts["pending"] = len(items)-sum(counts.values())
        counts["total_documents"] = len(items)
        counts["attempted_this_slice"] = complete
        return counts
