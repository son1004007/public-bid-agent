"""BID-05 공식 문서 후속 작업 큐 설계 계약.

목적/책임: 문서 확보·추출·차수/해시 위험을 작업/보류 큐로 읽기 전용 분류한다.
입력/출력: 고정 로컬 JSON/제한 캐시 -> 고정 코드·건수 및 로컬 상세용 검증 ID.
신뢰 경계: BID-04 캡처/release 검증, 공식 URL/identity/차수·캐시 해시 대조.
상태 변경/부작용: 원본·성공 결과·사람 이력 불변, 파일 생성/잠금/외부 I/O 없음.
실패/제한: 변경 관측/오류는 고정 AuditBlocked, 캐시 512KiB·128개·총32MiB.
자동 재시도·다운로드·배치 실행·AI·입찰 없음. 캐시 상한은 검증 보류로 표시한다.
불변: 공식 최신성/원본 binary 재검증·적격·수익은 UNVERIFIED; 역량 자동 배제 금지.
상세 연결: 캡처한 dashboard_revision을 반환해 기존 메모리와 최신 큐의 혼용을 막는다.
관련: BID05_DOCUMENT_FOLLOWUP_2026-10-19.md, test_bid_document_queue.py.
"""
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import os
from pathlib import Path, PurePath
import re
import sqlite3
import stat

from bid_now_audit import parse_time, _deadline
from bid_now_audit_cli import AuditBlocked, _capture, _release, _json
from bid_now_shortlist import VALID_ID, MAX_NOTICE_COUNT
from notice_lifecycle import is_cancel_kind
from procurement_documents import official_url, SUPPORTED
from procurement_filter import KST
from release_lease import reject_reparse
from rfp_coverage import _status
from rfp_fulltext import validate_record

HEX = re.compile(r"[0-9a-f]{64}\Z")
MAX_CACHE_BYTES = 512 * 1024
MAX_CACHE_FILES = 128
MAX_TOTAL_BYTES = 32 * 1024 * 1024
EFFORT = {"LOW_METADATA_CHECK": 0, "MEDIUM_DOWNLOAD_APPROVAL": 1,
          "HIGH_ORIGINAL_COMPARISON": 2, "UNKNOWN": 3}
HARD_HOLDS = frozenset(("INVALID_IDENTITY", "DUPLICATE_IDENTITY", "CANCELLED",
    "SUPERSEDED", "LIFECYCLE_UNVERIFIED", "DEADLINE_PASSED", "STALE_SOURCE",
    "SOURCE_VERSION_MISMATCH", "SOURCE_HASH_MISMATCH", "SOURCE_HASH_CONFLICT",
    "REGISTRATION_AFTER_CLOSE", "REGISTRATION_PASSED"))
BINDING_BLOCKS = frozenset(("SOURCE_VERSION_UNVERIFIED", "SOURCE_VERSION_MISMATCH",
    "SOURCE_PROVENANCE_UNVERIFIED", "SOURCE_HASH_MISMATCH", "SOURCE_HASH_CONFLICT",
    "CACHE_UNAVAILABLE", "CACHE_INVALID", "CACHE_SCAN_LIMIT", "NO_EXTRACTED_TEXT"))


def _hex(value):
    return isinstance(value, str) and HEX.fullmatch(value) is not None


def _cache_capture(root, reference):
    directory = reject_reparse(root / "rfp_fulltext")
    path = reject_reparse(directory / (reference + ".json"))
    try:
        before = path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_CACHE_BYTES:
        raise AuditBlocked("BLOCKED_INPUT")
    def signature(meta):
        change = meta.st_birthtime_ns if os.name == "nt" else meta.st_ctime_ns
        return (meta.st_dev, meta.st_ino, meta.st_size, meta.st_mtime_ns, change)
    with path.open("rb") as handle:
        opened = os.fstat(handle.fileno())
        body = handle.read(MAX_CACHE_BYTES + 1)
        closed = os.fstat(handle.fileno())
    reject_reparse(path)
    after = path.lstat()
    if (len(body) != before.st_size or len(body) > MAX_CACHE_BYTES
            or not signature(before) == signature(opened) == signature(closed) == signature(after)):
        raise AuditBlocked("BLOCKED_SNAPSHOT")
    return signature(after), body


class _Caches:
    def __init__(self, root):
        self.root, self.entries, self.bytes = root, {}, 0

    def read(self, reference):
        if not _hex(reference):
            return "CACHE_UNAVAILABLE", None
        if reference not in self.entries:
            if len(self.entries) >= MAX_CACHE_FILES or self.bytes + MAX_CACHE_BYTES > MAX_TOTAL_BYTES:
                return "CACHE_SCAN_LIMIT", None
            entry = _cache_capture(self.root, reference)
            self.entries[reference] = entry
            self.bytes += len(entry[1]) if entry else 0
        entry = self.entries[reference]
        if entry is None:
            return "CACHE_UNAVAILABLE", None
        try:
            record = validate_record(reference, _json(entry[1]))
            if (type(record.get("schema_version")) is not int or record["schema_version"] != 1
                    or type(record.get("truncated_by_parser")) is not bool
                    or type(record.get("reported_chars")) is not int
                    or type(record.get("stored_chars")) is not int
                    or not 0 < record["stored_chars"] <= 44000
                    or not record["stored_chars"] <= record["reported_chars"] <= 20000000):
                raise ValueError("CACHE")
            return "STORED_HASHES_MATCH", record
        except (ValueError, KeyError, TypeError, UnicodeError, RecursionError):
            return "CACHE_INVALID", None

    def verify(self):
        if any(_cache_capture(self.root, ref) != entry for ref, entry in self.entries.items()):
            raise AuditBlocked("BLOCKED_SNAPSHOT")


def _documents(notice, cache_loader):
    reasons, files = set(), {}
    attachments, proofs = notice.get("attachments", []), notice.get("document_evidence", [])
    if not isinstance(attachments, list) or not isinstance(proofs, list):
        return {"METADATA_REVIEW", "NO_EXTRACTED_TEXT"}, 0, 0, "UNVERIFIED"
    if len(attachments) > 120 or len(proofs) > 120:
        reasons.add("METADATA_SCAN_LIMIT")
    for item in attachments[:120]:
        if not isinstance(item, dict):
            reasons.add("METADATA_REVIEW")
            continue
        name, url = item.get("name"), item.get("url")
        if not isinstance(name, str) or not 1 <= len(name) <= 200 or not official_url(url):
            reasons.add("METADATA_REVIEW")
            continue
        if PurePath(name).suffix.lower() not in SUPPORTED:
            reasons.add("UNSUPPORTED_FORMAT")
            continue
        identity = hashlib.sha256((url + "\n" + name).encode()).hexdigest()
        files[identity] = item
    if not files:
        reasons.add("OFFICIAL_ATTACHMENT_MISSING")
    extracted = [p for p in proofs[:120] if isinstance(p, dict) and p.get("status") == "EXTRACTED"]
    if any(not isinstance(p, dict) for p in proofs[:120]):
        reasons.add("METADATA_REVIEW")
    for proof in proofs[:120]:
        if isinstance(proof, dict) and proof.get("status") == "FAILED":
            reasons.add({"DOWNLOAD": "DOWNLOAD_FAILED", "EXTRACTION": "EXTRACTION_FAILED"}.get(
                proof.get("failure_stage"), "FAILED_STAGE_UNKNOWN"))
    if notice.get("document_status") == "FAILED" and not any(
            c in reasons for c in ("DOWNLOAD_FAILED", "EXTRACTION_FAILED", "FAILED_STAGE_UNKNOWN")):
        reasons.add("FAILED_STAGE_UNKNOWN")
    if not extracted:
        reasons.add("NO_EXTRACTED_TEXT")
        if files and notice.get("document_status") != "FAILED":
            reasons.add("DOWNLOAD_PENDING")
    versions = defaultdict(set)
    for proof in extracted:
        if _hex(proof.get("identity")) and _hex(proof.get("sha256")):
            versions[proof["identity"]].add(proof["sha256"])
    if any(len(values) > 1 for values in versions.values()):
        reasons.add("SOURCE_HASH_CONFLICT")
    matched = set()
    for proof in extracted:
        identity = proof.get("identity")
        official = files.get(identity) if isinstance(identity, str) else None
        if official is None or proof.get("name") != official["name"] or not _hex(proof.get("sha256")):
            reasons.add("SOURCE_PROVENANCE_UNVERIFIED")
            continue
        keys = (("notice_id", "id"), ("notice_bid_no", "bid_no"), ("notice_bid_order", "bid_order"))
        if any(not isinstance(proof.get(k), str) or not proof[k] for k, _ in keys):
            reasons.add("SOURCE_VERSION_UNVERIFIED")
            continue
        if any(proof[k] != notice.get(n) for k, n in keys):
            reasons.add("SOURCE_VERSION_MISMATCH")
            continue
        state, cache = cache_loader(proof.get("fulltext_ref"))
        if cache is None:
            reasons.add(state)
            continue
        if cache.get("source_sha256") != proof["sha256"]:
            reasons.add("SOURCE_HASH_MISMATCH")
            continue
        if (proof.get("fulltext_chars") != cache["stored_chars"]
                or proof.get("fulltext_reported_chars") != cache["reported_chars"]
                or proof.get("fulltext_truncated") is not cache["truncated_by_parser"]):
            reasons.add("METADATA_REVIEW")
        if (cache["truncated_by_parser"] or cache["reported_chars"] > cache["stored_chars"]
                or proof.get("fulltext_truncated") is True):
            reasons.add("TEXT_OR_TABLE_TRUNCATED")
        warnings = proof.get("warnings")
        if warnings is not None and (not isinstance(warnings, list) or warnings):
            reasons.add("EXTRACTION_WARNING")
        matched.add(identity)
    extracted_ids = {p["identity"] for p in extracted
                     if isinstance(p.get("identity"), str) and p["identity"] in files}
    if extracted_ids and len(extracted_ids) < len(files):
        reasons.add("PARTIAL_EXTRACTION")
    # Parser truncation/warnings remain visible even when provenance/cache is unavailable.
    if any(p.get("fulltext_truncated") is True for p in extracted):
        reasons.add("TEXT_OR_TABLE_TRUNCATED")
    if any(isinstance(p.get("warnings"), list) and p["warnings"] for p in extracted):
        reasons.add("EXTRACTION_WARNING")
    binding = "STORED_HASHES_MATCH" if files and len(matched) == len(files) and not reasons & (
        BINDING_BLOCKS | {"METADATA_REVIEW", "METADATA_SCAN_LIMIT"}) else "UNVERIFIED"
    return reasons, len(files), len(matched), binding


def build(notices, *, cache_loader=None, at=None, limit=30):
    """후속 확인 작업만 정렬한다. 입력과 기존 사용자 결정/추출 결과를 수정하지 않는다."""
    if (not isinstance(notices, list) or len(notices) > MAX_NOTICE_COUNT
            or type(limit) is not int or not 1 <= limit <= 100
            or at is not None and (not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None)):
        raise ValueError("BLOCKED_INPUT")
    stamp = (at or datetime.now(KST)).astimezone(KST)
    cache_loader = cache_loader or (lambda ref: ("CACHE_UNAVAILABLE", None))
    valid, ids, orders = [], Counter(), defaultdict(list)
    for item in notices:
        n = item if isinstance(item, dict) else {}
        ident = VALID_ID.fullmatch(n["id"]) if isinstance(n.get("id"), str) else None
        ok = bool(ident and n.get("source") == "G2B_OFFICIAL_API"
                  and n.get("bid_no") == ident.group(1) and n.get("bid_order") == ident.group(2))
        valid.append((n, ok))
        if ok:
            ids[n["id"]] += 1
            orders[n["bid_no"]].append(int(n["bid_order"]))
    active, held, counts = [], [], Counter()
    for index, (n, ok) in enumerate(valid):
        reasons, official_count, matched_count, binding = _documents(n, cache_loader)
        if not ok:
            reasons.add("INVALID_IDENTITY")
        else:
            if ids[n["id"]] != 1:
                reasons.add("DUPLICATE_IDENTITY")
            group, order = orders[n["bid_no"]], int(n["bid_order"])
            if order < max(group) or n.get("notice_lifecycle") == "SUPERSEDED":
                reasons.add("SUPERSEDED")
            elif group.count(order) > 1 or n.get("notice_lifecycle") not in ("CURRENT", "CANCELLED"):
                reasons.add("LIFECYCLE_UNVERIFIED")
        if n.get("notice_lifecycle") == "CANCELLED" or is_cancel_kind(n.get("notice_kind")):
            reasons.add("CANCELLED")
        if n.get("rfp_review_status") == "STALE":
            reasons.add("STALE_SOURCE")
        if isinstance(n.get("notice_kind"), str) and "정정" in n["notice_kind"]:
            reasons.add("CORRECTION_RECHECK")
        if not official_url(n.get("source_url")):
            reasons.add("OFFICIAL_NOTICE_URL_UNVERIFIED")
        due, registration = parse_time(n.get("end")), parse_time(n.get("qualification_deadline"))
        deadline = _deadline(due, stamp)
        if deadline == "CLOSED":
            reasons.add("DEADLINE_PASSED")
        elif deadline == "UNKNOWN":
            reasons.add("DEADLINE_UNKNOWN")
        if registration is None:
            reasons.add("REGISTRATION_UNKNOWN")
        elif due and registration > due:
            reasons.add("REGISTRATION_AFTER_CLOSE")
        elif registration <= stamp:
            reasons.add("REGISTRATION_PASSED")
        reasons.add("OFFICIAL_ORIGINAL_RECHECK")
        is_held = bool(reasons & HARD_HOLDS)
        quality = bool(reasons & {"PARTIAL_EXTRACTION", "TEXT_OR_TABLE_TRUNCATED", "EXTRACTION_WARNING",
                                 "METADATA_REVIEW", "METADATA_SCAN_LIMIT", "UNSUPPORTED_FORMAT"})
        reevaluation = ("BLOCKED_SOURCE" if is_held or binding != "STORED_HASHES_MATCH"
                        else "BLOCKED_EXTRACTION_QUALITY" if quality else "STORED_TEXT_ONLY")
        if is_held:
            next_steps = ["VERIFY_HELD_STATUS_NO_RETRY", "CONFIRM_CURRENT_OFFICIAL_VERSION"]
        elif "OFFICIAL_ATTACHMENT_MISSING" in reasons:
            next_steps = ["LOCATE_OFFICIAL_ATTACHMENT", "OBTAIN_ORIGINAL_AFTER_APPROVAL"]
        elif "DOWNLOAD_FAILED" in reasons:
            next_steps = ["CHECK_DOWNLOAD_FAILURE_NO_AUTO_RETRY", "OBTAIN_ORIGINAL_AFTER_APPROVAL"]
        elif "EXTRACTION_FAILED" in reasons:
            next_steps = ["CHECK_PARSER_ON_CONFIRMED_ORIGINAL"]
        elif "DOWNLOAD_PENDING" in reasons:
            next_steps = ["OBTAIN_ORIGINAL_AFTER_APPROVAL", "EXTRACT_ONCE_AFTER_SOURCE_CHECK"]
        else:
            next_steps = ["CONFIRM_CURRENT_OFFICIAL_VERSION", "COMPARE_PAGES_TABLES_FOOTNOTES_OCR"]
        effort = ("LOW_METADATA_CHECK" if is_held or "OFFICIAL_ATTACHMENT_MISSING" in reasons
                  else "MEDIUM_DOWNLOAD_APPROVAL" if "DOWNLOAD_PENDING" in reasons or "DOWNLOAD_FAILED" in reasons
                  else "HIGH_ORIGINAL_COMPARISON")
        integrity = bool(reasons & {"SOURCE_HASH_MISMATCH", "SOURCE_HASH_CONFLICT", "SOURCE_VERSION_MISMATCH", "STALE_SOURCE"})
        tier = 1 if deadline in ("WITHIN_24H", "UNKNOWN") else 2 if deadline == "WITHIN_72H" or integrity else 3
        row = {"id": n.get("id") if ok and ids[n["id"]] == 1 else None,
               "queue_state": "HELD" if is_held else "ACTION_REQUIRED",
               "priority": "HOLD" if is_held else "P" + str(tier),
               "deadline_bucket": deadline, "effort_band": effort,
               "priority_reasons": ["OFFICIAL_DEADLINE_ORDER", "INTEGRITY_RISK_REVIEW" if integrity
                                    else "DOCUMENT_GAP_REVIEW", "EFFORT_TIE_BREAK_ONLY"],
               "document_state": _status(n), "reason_codes": sorted(reasons),
               "official_attachment_count": official_count, "bound_extracted_count": matched_count,
               "source_binding": binding, "reevaluation_status": reevaluation,
               "can_reevaluate_stored_text": reevaluation == "STORED_TEXT_ONLY",
               "next_steps": next_steps, "official_freshness": "UNVERIFIED",
               "original_binary_sha_rechecked": False, "analysis_complete": False,
               "legal_eligibility": "UNVERIFIED", "estimated_profit": "UNVERIFIED",
               "staffing_and_mm": "UNVERIFIED", "evidence_status": "BLOCKED_EVIDENCE"}
        counts.update(reasons)
        key = (tier, (due - stamp).total_seconds() if due else float("inf"), EFFORT[effort], -len(reasons), row["id"] or "", index)
        (held if is_held else active).append((key, row))
    active.sort(key=lambda pair: pair[0]); held.sort(key=lambda pair: pair[0])
    return {"schema_version": 1, "mode": "READ_ONLY_DOCUMENT_FOLLOWUP", "status": "BLOCKED_EVIDENCE",
            "evaluated_at": stamp.isoformat(), "total_notices": len(notices),
            "needs_attention_count": len(notices), "action_required_count": len(active), "held_count": len(held),
            "reason_counts": dict(sorted(counts.items())), "results": [r for _, r in active[:limit]],
            "held_results": [r for _, r in held[:limit]], "omitted_count": max(0, len(active) - limit),
            "held_omitted_count": max(0, len(held) - limit), "automatic_download": False,
            "automatic_retry": False, "automatic_bid_submittal": False, "analysis_complete": False,
            "legal_eligibility": "UNVERIFIED", "estimated_profit": "UNVERIFIED",
            "staffing_and_mm": "UNVERIFIED", "cannot_auto_discard_on_capability_gap": True,
            "private_text_included": False, "source_files_written": False}


def read_queue(root, *, at=None, limit=30):
    """잠금 생성 없이 고정 입력과 사용한 캐시의 전후 관측 안정성을 확인한다."""
    try:
        root = Path(root).absolute()
        before = _capture(root)
        try:
            release_state = _release(before)
        except AuditBlocked:
            raise
        except (ValueError, TypeError, sqlite3.Error, UnicodeError, RecursionError):
            raise AuditBlocked("BLOCKED_SNAPSHOT") from None
        entry = before["dashboard.json"]
        board = _json(entry[1]) if entry else None
        if (not isinstance(board, dict) or type(board.get("schema_version")) is not int
                or board["schema_version"] != 1 or type(board.get("revision")) is not int or board["revision"] < 0):
            raise AuditBlocked("BLOCKED_INPUT")
        caches = _Caches(root)
        report = build(board.get("notices"), cache_loader=caches.read, at=at, limit=limit)
        caches.verify()
        if _capture(root) != before:
            raise AuditBlocked("BLOCKED_SNAPSHOT")
        return {**report, "dashboard_revision": board["revision"],
                "snapshot_check": "STABLE_OBSERVED_READS", "release_metadata_state": release_state}
    except AuditBlocked:
        raise
    except (OSError, ValueError, TypeError, KeyError, OverflowError, RecursionError):
        raise AuditBlocked("BLOCKED_INPUT") from None
