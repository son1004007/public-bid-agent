"""BID-06 독립 원본 정답 검수 설계 계약.

목적/책임: 기존 후보와 독립적인 사람 정답을 로컬 이벤트로 보존하고 표본만 평가한다.
입력/출력: 현재 공식 공고/제한 캐시·사람의 구절/페이지/검수 -> 표본/이력/지표.
신뢰 경계: 원본 SHA 서버 대조·현재 차수/취소/STALE·서명 티켓·명시적 사람 확인.
상태 변경: append는 순수 함수, 서버가 공통 transaction/원자 저장. 기존 자료 불변.
실패/제한: 충돌409, 손상/링크/크기 오류 안전 실패. 자동 다운로드/AI/재시도 없음.
불변조건: 승인 정답0이면 NOT_EVALUATED, 대표성/회사 적격·수익/MM은 미검증.
관련: docs/design/BID06_GROUND_TRUTH_2026-10-19.md, test_rfp_ground_truth.py.
"""
import base64
import copy
import hashlib
import hmac
import json
import re
import time
import unicodedata
from pathlib import Path

from bid_document_queue import _Caches
from bid_now_audit_cli import _json
from notice_lifecycle import is_cancel_kind
from procurement_documents import official_url
from release_lease import reject_reparse
from rfp_audit_labels import _check_stamp
from rfp_requirements import structure, _identity, SCHEMA_VERSION

CATEGORIES = ("participation", "evaluation", "scope")
ROUTES = ("TEXT", "TABLE", "FOOTNOTE", "IMAGE", "OCR")
CHECKS = ("pages", "tables", "footnotes", "images", "ocr")
MAX_BYTES = 8 * 1024 * 1024
MAX_EVENTS = 200
HEX = re.compile(r"[a-f0-9]{64}\Z")
UUID = re.compile(r"[a-f0-9-]{36}\Z")
FILE_NAME = "rfp_ground_truth.json"


class ReviewConflict(ValueError):
    """현재 검수 snapshot/revision 또는 멱등키가 변경됨."""


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


def normalized(text):
    return " ".join(unicodedata.normalize("NFC", text).split())


def initial():
    return {"schema_version": 1, "revision": 0, "events": []}


def _text(value, maximum=1000, *, empty=False):
    if (not isinstance(value, str) or len(value) > maximum
            or (not empty and not value.strip())
            or any(ord(c) < 32 and c not in "\r\n\t" for c in value)):
        raise ValueError("검수 텍스트 형식 오류")
    return value


def _int(value, lower, upper):
    if type(value) is not int or not lower <= value <= upper:
        raise ValueError("검수 범위 오류")
    return value


def _uuid(value):
    if not isinstance(value, str) or not UUID.fullmatch(value):
        raise ValueError("검수 식별자 오류")
    return value


def _hash(value):
    if not isinstance(value, str) or not HEX.fullmatch(value):
        raise ValueError("검수 해시 오류")
    return value


def _scope(scope):
    if not isinstance(scope, dict) or set(scope) != {
            "start", "end", "page_start", "page_end", "location", "route"}:
        raise ValueError("표본 범위 필드 오류")
    _int(scope["start"], 0, 43999); _int(scope["end"], scope["start"] + 1, 44000)
    _int(scope["page_start"], 1, 10000)
    _int(scope["page_end"], scope["page_start"], 10000)
    _text(scope["location"], 200)
    if scope["route"] not in ROUTES:
        raise ValueError("표본 추출 경로 오류")


def _gold(rows, scope):
    if not isinstance(rows, list) or len(rows) > 30:
        raise ValueError("정답 표본 상한 오류")
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"category", "text", "page", "location"}:
            raise ValueError("정답 필드 오류")
        if row["category"] not in CATEGORIES:
            raise ValueError("정답 분류 오류")
        _text(row["text"]); _text(row["location"], 200)
        _int(row["page"], scope["page_start"], scope["page_end"])
        key = (row["category"], normalized(row["text"]), row["page"], normalized(row["location"]))
        if key in seen:
            raise ValueError("같은 위치의 중복 정답")
        seen.add(key)


def _confirmations(checks):
    if (not isinstance(checks, dict) or set(checks) != set(CHECKS)
            or any(v not in ("REVIEWED", "NOT_APPLICABLE", "UNKNOWN") for v in checks.values())):
        raise ValueError("원본 검수 범위 오류")


def validate(state):
    if (not isinstance(state, dict) or set(state) != {"schema_version", "revision", "events"}
            or type(state["schema_version"]) is not int or state["schema_version"] != 1
            or type(state["revision"]) is not int or not isinstance(state["events"], list)
            or state["revision"] != len(state["events"]) or len(state["events"]) > MAX_EVENTS):
        raise ValueError("정답 이력 형식 오류")
    seen = set()
    fields = {"request_id", "request_digest", "scope_id", "notice_id", "bid_no", "bid_order",
              "version_key", "identity", "source_sha256", "fulltext_ref", "scope", "gold",
              "predictions", "status", "checks", "official_current_confirmed",
              "independent_review_confirmed", "source_sha_checked", "recorded_at"}
    for event in state["events"]:
        if not isinstance(event, dict) or set(event) != fields:
            raise ValueError("정답 이력 필드 오류")
        _uuid(event["request_id"]); _uuid(event["scope_id"])
        if event["request_id"] in seen:
            raise ValueError("중복 검수 이벤트")
        seen.add(event["request_id"])
        for field in ("request_digest", "version_key", "identity", "source_sha256", "fulltext_ref"):
            _hash(event[field])
        if (not isinstance(event["notice_id"], str)
                or not re.fullmatch(r"G2B-[A-Za-z0-9-]{4,100}", event["notice_id"])
                or not isinstance(event["bid_no"], str)
                or not re.fullmatch(r"[A-Za-z0-9-]{4,32}", event["bid_no"])
                or not isinstance(event["bid_order"], str)
                or not re.fullmatch(r"[0-9]{1,5}", event["bid_order"])):
            raise ValueError("공고 버전 오류")
        _scope(event["scope"]); _gold(event["gold"], event["scope"])
        _confirmations(event["checks"]); _check_stamp(event["recorded_at"])
        if event["status"] not in ("APPROVED", "HOLD"):
            raise ValueError("정답 검수 상태 오류")
        for field in ("official_current_confirmed", "independent_review_confirmed", "source_sha_checked"):
            if type(event[field]) is not bool:
                raise ValueError("사람 확인 형식 오류")
        if event["status"] == "APPROVED" and (
                not all(event[k] for k in ("official_current_confirmed", "independent_review_confirmed", "source_sha_checked"))
                or event["checks"]["pages"] != "REVIEWED" or "UNKNOWN" in event["checks"].values()):
            raise ValueError("승인 증거 누락")
        preds = event["predictions"]
        if not isinstance(preds, list) or len(preds) > 15:
            raise ValueError("추출 표본 상한 오류")
        for row in preds:
            if (not isinstance(row, dict) or set(row) != {"category", "text", "start", "end"}
                    or row["category"] not in CATEGORIES):
                raise ValueError("추출 표본 형식 오류")
            _text(row["text"], 220)
            _int(row["start"], event["scope"]["start"], event["scope"]["end"] - 1)
            _int(row["end"], row["start"] + 1, event["scope"]["end"])
    return state


def load(root):
    path = reject_reparse(Path(root) / FILE_NAME)
    if not path.exists():
        return initial()
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError("정답 이력 크기 오류")
    with path.open("rb") as file:
        raw = file.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("정답 이력 크기 오류")
    return validate(_json(raw))


def context(notice, root):
    """현재 공식 첨부·저장된 문서/후보만 제한 캡처; 페이지/최신성 자동 추정 없음."""
    if (not isinstance(notice, dict) or not re.fullmatch(r"G2B-[A-Za-z0-9-]{4,100}", str(notice.get("id", "")))):
        raise ValueError("공고 식별 오류")
    blocked = (notice.get("notice_lifecycle") != "CURRENT" or notice.get("document_status") != "EXTRACTED"
               or notice.get("window_status") in ("CANCELLED", "SUPERSEDED")
               or is_cancel_kind(notice.get("notice_kind")) or notice.get("rfp_review_status") == "STALE")
    attachments, proofs = notice.get("attachments", []), notice.get("document_evidence", [])
    if not isinstance(attachments, list) or not isinstance(proofs, list):
        raise ValueError("문서 메타데이터 오류")
    cache = _Caches(Path(root))
    documents = []
    if len(proofs) <= 120 and len(attachments) <= 120:
        for proof in proofs:
            if not isinstance(proof, dict) or proof.get("status") != "EXTRACTED":
                continue
            identity = proof.get("identity")
            if not isinstance(identity, str) or not HEX.fullmatch(identity):
                continue
            known = [a for a in attachments if _identity(a) == identity]
            same = [p for p in proofs if isinstance(p, dict) and p.get("identity") == identity
                    and p.get("status") == "EXTRACTED"]
            if len(known) != 1 or len(same) != 1 or proof.get("name") != known[0].get("name"):
                continue
            state, record = cache.read(proof.get("fulltext_ref"))
            if record is None or record.get("source_sha256") != proof.get("sha256"):
                continue
            if len(documents) >= 2:
                break
            text = "".join(c["text"] for c in record["chunks"])
            version_matched = all(isinstance(notice.get(k), str) and notice[k]
                                  and proof.get(p) == notice[k] for p, k in (
                                      ("notice_id", "id"), ("notice_bid_no", "bid_no"), ("notice_bid_order", "bid_order")))
            documents.append({"identity": identity, "source_sha256": proof["sha256"],
                              "fulltext_ref": proof["fulltext_ref"], "name": known[0]["name"],
                              "official_url": known[0]["url"], "text": text,
                              "binding": "VERSION_MATCHED" if version_matched else "VERSION_UNVERIFIED",
                              "truncated": record["truncated_by_parser"],
                              "parser_warnings_present": bool(proof.get("warnings"))})
    # Only bounded, validated caches reach the existing extractor. No parser/batch rerun.
    safe_notice = {**notice, "document_evidence": [p for p in proofs if isinstance(p, dict)
                   and any(p.get("identity") == d["identity"] and p.get("fulltext_ref") == d["fulltext_ref"] for d in documents)]}
    report = structure(safe_notice, root) if documents else {"requirements": [], "omitted_candidate_count": 0}
    candidates = []
    for group in report["requirements"]:
        if group["category"] not in CATEGORIES:
            continue
        for item in group["items"]:
            ev = item["evidence"]
            doc = next((d for d in documents if d["fulltext_ref"] == ev["fulltext_ref"]
                        and d["source_sha256"] == ev["source_sha256"]), None)
            if doc:
                candidates.append({"identity": doc["identity"], "category": group["category"],
                                   "text": ev["excerpt"], "start": ev["offset_start"], "end": ev["offset_end"]})
    cache.verify()
    version = digest({"id": notice["id"], "bid_no": notice.get("bid_no"), "bid_order": notice.get("bid_order"),
                      "kind": notice.get("notice_kind"), "lifecycle": notice.get("notice_lifecycle"),
                      "review": notice.get("rfp_review_status"), "window": notice.get("window_status"),
                      "deadline": notice.get("end"), "registration_deadline": notice.get("qualification_deadline"),
                      "official_notice_url": notice.get("source_url"),
                      "documents": documents, "candidates": candidates, "extractor_schema": SCHEMA_VERSION})
    return {"id": notice["id"], "bid_no": notice.get("bid_no"), "bid_order": notice.get("bid_order"),
            "title": str(notice.get("title", "RFP 검수"))[:200], "version_key": version,
            "blocked": bool(blocked), "documents": documents, "candidates": candidates,
            "omitted_candidate_count": report.get("omitted_candidate_count", 0),
            "original_pages_tables_ocr": "HUMAN_REVIEW_REQUIRED", "official_freshness": "UNVERIFIED",
            "legal_eligibility": "UNVERIFIED", "profitability": "UNVERIFIED", "staffing_and_mm": "UNVERIFIED"}


def _document(ctx, identity):
    docs = [d for d in ctx["documents"] if d["identity"] == identity]
    if len(docs) != 1:
        raise ReviewConflict("현재 문서/원본 결속을 다시 확인하세요")
    return docs[0]


def source_ticket(ctx, identity, raw, secret, *, clock=None):
    """명시 선택한 로컬 원본을 메모리에서 SHA 대조; 원본 bytes/티켓은 저장하지 않음."""
    doc = _document(ctx, identity)
    if (ctx["blocked"] or doc["binding"] != "VERSION_MATCHED"
            or not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES
            or hashlib.sha256(raw).hexdigest() != doc["source_sha256"]):
        raise ReviewConflict("원본 SHA/최신 공고 버전을 확인할 수 없습니다")
    body = {"version_key": ctx["version_key"], "identity": identity,
            "expires": int(time.time() if clock is None else clock) + 900}
    encoded = base64.urlsafe_b64encode(json.dumps(body, sort_keys=True).encode()).decode()
    signature = hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return encoded + "." + signature


def _ticket(token, ctx, identity, secret, clock=None):
    if not isinstance(token, str) or len(token) > 2000:
        raise ReviewConflict("로컬 원본을 다시 선택해 확인하세요")
    try:
        encoded, signature = token.split(".")
        expected = hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("SIGNATURE")
        body = _json(base64.urlsafe_b64decode(encoded))
        if (body["version_key"] != ctx["version_key"] or body["identity"] != identity
                or type(body["expires"]) is not int
                or not (time.time() if clock is None else clock) < body["expires"]):
            raise ValueError("EXPIRED")
    except (ValueError, KeyError, TypeError, UnicodeError):
        raise ReviewConflict("원본 대조가 만료되었거나 공고가 변경되었습니다") from None


def _latest(state, ident):
    latest = {}
    for event in state["events"]:
        if event["notice_id"] == ident:
            latest[event["scope_id"]] = event
    return list(latest.values())


def _current(event, ctx):
    return not ctx["blocked"] and event["version_key"] == ctx["version_key"]


def append(state, ctx, request, stamp, secret, *, clock=None):
    validate(state); _check_stamp(stamp)
    fields = {"id", "expected_revision", "request_id", "scope_id", "version_key", "identity",
              "scope", "gold", "status", "checks", "official_current_confirmed",
              "independent_review_confirmed", "source_ticket"}
    if not isinstance(request, dict) or set(request) != fields:
        raise ValueError("검수 요청 필드 오류")
    _uuid(request["request_id"]); _uuid(request["scope_id"])
    request_hash = digest(request)
    existing = next((e for e in state["events"] if e["request_id"] == request["request_id"]), None)
    if existing:
        if existing["request_digest"] != request_hash:
            raise ReviewConflict("동일 제출 키의 내용이 다릅니다")
        return state
    if type(request["expected_revision"]) is not int or request["expected_revision"] != state["revision"]:
        raise ReviewConflict("다른 창에서 검수 이력이 변경되었습니다")
    if request["id"] != ctx["id"] or request["version_key"] != ctx["version_key"]:
        raise ReviewConflict("현재 공고/원본 버전이 변경되었습니다")
    doc = _document(ctx, request["identity"])
    _scope(request["scope"]); _gold(request["gold"], request["scope"])
    _confirmations(request["checks"])
    if request["scope"]["end"] > len(doc["text"]):
        raise ValueError("저장 텍스트 구간을 벗어났습니다")
    if any(e["scope_id"] == request["scope_id"] and e["notice_id"] != ctx["id"] for e in state["events"]):
        raise ReviewConflict("다른 공고의 표본 ID입니다")
    if request["status"] == "APPROVED":
        if ctx["blocked"] or doc["binding"] != "VERSION_MATCHED":
            raise ReviewConflict("원본/공고 재검수 전 승인할 수 없습니다")
        _ticket(request["source_ticket"], ctx, doc["identity"], secret, clock)
    predictions = [{k: c[k] for k in ("category", "text", "start", "end")}
                   for c in ctx["candidates"] if c["identity"] == doc["identity"]
                   and request["scope"]["start"] <= c["start"] and c["end"] <= request["scope"]["end"]]
    # Cut-off candidates must not silently disappear at the review boundary.
    if any(c["identity"] == doc["identity"] and c["start"] < request["scope"]["end"]
           and c["end"] > request["scope"]["start"] and c not in [
               {**p, "identity": doc["identity"]} for p in predictions] for c in ctx["candidates"]):
        raise ValueError("후보 구절 중간을 자른 범위는 검수할 수 없습니다")
    event = {"request_id": request["request_id"], "request_digest": request_hash,
             "scope_id": request["scope_id"], "notice_id": ctx["id"], "bid_no": ctx["bid_no"],
             "bid_order": ctx["bid_order"], "version_key": ctx["version_key"],
             "identity": doc["identity"], "source_sha256": doc["source_sha256"], "fulltext_ref": doc["fulltext_ref"],
             "scope": copy.deepcopy(request["scope"]), "gold": copy.deepcopy(request["gold"]),
             "predictions": predictions, "status": request["status"], "checks": copy.deepcopy(request["checks"]),
             "official_current_confirmed": request["official_current_confirmed"],
             "independent_review_confirmed": request["independent_review_confirmed"],
             "source_sha_checked": request["status"] == "APPROVED", "recorded_at": stamp}
    if event["status"] == "APPROVED":
        for other in _latest(state, ctx["id"]):
            if (other["scope_id"] != event["scope_id"] and other["status"] == "APPROVED"
                    and _current(other, ctx) and other["identity"] == event["identity"]
                    and (max(other["scope"]["start"], event["scope"]["start"]) < min(other["scope"]["end"], event["scope"]["end"])
                         or max(other["scope"]["page_start"], event["scope"]["page_start"]) <= min(other["scope"]["page_end"], event["scope"]["page_end"]))):
                raise ReviewConflict("기존 승인 표본과 문서/페이지 범위가 겹칩니다. 기존 표본을 수정하세요")
    out = copy.deepcopy(state); out["events"].append(event); out["revision"] += 1
    validate(out)
    # Match server.persist(indent=2), so a successful save remains readable at the cap.
    if len(json.dumps(out, ensure_ascii=False, indent=2).encode()) > MAX_BYTES:
        raise ReviewConflict("정답 이력 상한: 기존 자료를 보존합니다")
    return out


def _counts(gold, predictions):
    from collections import Counter
    g = Counter((r["category"], normalized(r["text"])) for r in gold)
    p = Counter((r["category"], normalized(r["text"])) for r in predictions)
    tp = sum((g & p).values()); fp = sum(p.values()) - tp; fn = sum(g.values()) - tp
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall,
            "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
            "miss_rate": fn / (tp + fn) if tp + fn else None}


def evaluate(events):
    """승인된 독립 정답이 없는 경우 수치를 생성하지 않는다. 구간 간 매칭 금지."""
    approved = [e for e in events if e["status"] == "APPROVED"]
    gold_count = sum(len(e["gold"]) for e in approved)
    null = dict.fromkeys(("tp", "fp", "fn", "precision", "recall", "f1", "miss_rate"))
    def aggregate(chosen, category=None):
        totals = {"tp": 0, "fp": 0, "fn": 0}
        for e in chosen:
            g = [r for r in e["gold"] if category is None or r["category"] == category]
            p = [r for r in e["predictions"] if category is None or r["category"] == category]
            counts = _counts(g, p)
            for key in totals: totals[key] += counts[key]
        tp, fp, fn = (totals[k] for k in ("tp", "fp", "fn"))
        return {**totals, "precision": tp / (tp + fp) if tp + fp else None,
                "recall": tp / (tp + fn) if tp + fn else None,
                "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
                "miss_rate": fn / (tp + fn) if tp + fn else None}
    return {"state": "EVALUATED_APPROVED_SAMPLE_ONLY" if gold_count else "NOT_EVALUATED",
            "approved_gold_count": gold_count, "approved_scope_count": len(approved),
            "metrics": aggregate(approved) if gold_count else null,
            "by_category": {c: aggregate(approved, c) if gold_count else null.copy() for c in CATEGORIES},
            "by_route": {r: aggregate([e for e in approved if e["scope"]["route"] == r])
                         if gold_count and any(e["scope"]["route"] == r for e in approved) else null.copy() for r in ROUTES},
            "scope": "HUMAN_SELECTED_ORIGINAL_PAGES_AND_DISPLAYED_CANDIDATES_ONLY",
            "representativeness": "NOT_ESTABLISHED", "whole_document_accuracy": "NOT_EVALUATED"}


def view(state, ctx):
    validate(state)
    latest = _latest(state, ctx["id"])
    current = [e for e in latest if _current(e, ctx)]
    rows = [{**e, "validity": "CURRENT_AS_OF_HUMAN_CHECK" if _current(e, ctx) else "REVIEW_REQUIRED"}
            for e in latest]
    # Private text is returned to same-owner localhost UI only, never operational logs.
    return {"revision": state["revision"], "context": ctx, "scopes": rows,
            "history": [{k: e[k] for k in ("scope_id", "status", "recorded_at", "source_sha256")}
                        for e in state["events"] if e["notice_id"] == ctx["id"]][-60:],
            "evaluation": evaluate(current), "stale_scope_count": len(latest) - len(current),
            "storage": "LOCAL_PRIVATE_REVIEW", "automatic_source_changes": False,
            "legal_eligibility": "UNVERIFIED", "profitability": "UNVERIFIED", "staffing_and_mm": "UNVERIFIED"}
