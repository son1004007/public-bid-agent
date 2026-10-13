"""공식 공고번호·차수·공고종류에 따른 정정/취소 수명주기.

실제 사람의 참여 결정과 RFP 추출·원문은 보존한다. 공고명 키워드나 누락
응답만으로 취소를 확정하지 않는다. 정정·취소/구차수는 추천에서 차단한다.
"""
from collections import defaultdict

MAX_EVENTS = 20
# 원문 재검증이 필요한 공식 필드. observed_at은 자동 갱신되므로 제외.
EVIDENCE_FIELDS = frozenset((
    "title", "budget", "end", "source_url", "notice_kind",
    "notice_published_at", "qualification_deadline",
    "procurement_classification", "procurement_code",
    "industry_restriction", "participation_restriction", "contract_method",
    "attachments",
))


def is_cancel_kind(kind):
    """조달청 공고종류명 중 '취소' 명시 신호만 취소로 판정."""
    return isinstance(kind, str) and "취소" in kind


def order_number(item):
    try:
        value = str(item.get("bid_order", ""))
        return int(value) if value.isdecimal() else None
    except (ValueError, TypeError):
        return None


def record(item, state, timestamp, *, replaced_by=None, reason=None):
    prior = item.get("notice_lifecycle")
    old_link = item.get("superseded_by")
    if (prior == state and old_link == replaced_by
            and isinstance(item.get("lifecycle_events"), list) and item["lifecycle_events"]):
        return False
    item["notice_lifecycle"] = state
    item["superseded_by"] = replaced_by
    item["lifecycle_observed_at"] = timestamp
    events = item.get("lifecycle_events")
    if not isinstance(events, list):
        events = []
    event = {"status": state, "observed_at": timestamp,
             "source": "G2B_OFFICIAL_API", "bid_order": str(item.get("bid_order",""))}
    if replaced_by:
        event["superseded_by"] = replaced_by
    if reason:
        event["reason"] = reason
    item["lifecycle_events"] = [*events[-(MAX_EVENTS - 1):], event]
    return True


def mark_stale(item, timestamp, reason):
    """본문과 추출 SHA·이력은 그대로 두고 해당 근거의 최신성만 보류."""
    if item.get("rfp_review_status") == "STALE":
        return False
    if item.get("document_status") != "EXTRACTED" and not item.get("rfp_text"):
        return False
    item["rfp_review_status"] = "STALE"
    item["rfp_stale_reason"] = reason
    item["rfp_stale_at"] = timestamp
    return True


def reconcile(notices, timestamp):
    """전체 보관분의 동일 공고번호 차수를 연결. 동차수 형식이 중복되면 보수적으로 차단."""
    groups = defaultdict(list)
    changes = 0
    for item in notices:
        if (not isinstance(item, dict) or item.get("source") != "G2B_OFFICIAL_API"
                or not item.get("bid_no") or order_number(item) is None
                or item.get("id") != "G2B-"+str(item["bid_no"])+"-"+str(item["bid_order"])):
            continue
        groups[item["bid_no"]].append(item)
    for items in groups.values():
        latest = max(order_number(item) for item in items)
        newer = [item for item in items if order_number(item) == latest]
        # 같은 차수의 서로 다른 ID가 존재한다면 자동으로 우열을 결정하지 않는다.
        ambiguous = len(newer) > 1
        replacement = newer[0]["id"] if not ambiguous else None
        for item in items:
            order = order_number(item)
            if order < latest:
                state = "SUPERSEDED"
                changes += int(record(item, state, timestamp, replaced_by=replacement,
                                      reason="공식 공고번호의 후속 차수 확인"))
                changes += int(mark_stale(item, timestamp, "공식 후속 차수 공고 존재"))
            elif ambiguous:
                changes += int(record(item, "REVIEW", timestamp,
                                      reason="동일 공고번호·동차수 표기가 복수이므로 수동 확인"))
            else:
                state = "CANCELLED" if is_cancel_kind(item.get("notice_kind")) else "CURRENT"
                changes += int(record(item, state, timestamp,
                                      reason="공식 공고종류 취소 확인" if state == "CANCELLED" else None))
                if state == "CANCELLED":
                    changes += int(mark_stale(item, timestamp, "공식 취소공고"))
    return changes


def mark_if_metadata_changed(old, fresh, timestamp):
    """저장된 추출 문서가 있을 때 공식 핵심 메타데이터가 바뀌면 재검증 대기."""
    def official_pairs(items):
        if not isinstance(items, list):
            return set()
        return {(f.get("name"), f.get("url")) for f in items if isinstance(f, dict)
                and isinstance(f.get("url"), str) and f.get("url")}
    changed = sorted(field for field in EVIDENCE_FIELDS if field != "attachments"
                     and field in fresh and fresh[field] not in (None, "")
                     and old.get(field) != fresh[field])
    # 추출 증거가 포함된 과거 첨부는 병합 보존된다. 과거 공식 링크가
    # 새로운 검색 응답에 생략됐다는 이유만으로 임의의 삭제/정정을 추정하지 않는다.
    new_files = official_pairs(fresh.get("attachments")) - official_pairs(old.get("attachments"))
    if new_files:
        changed.append("attachments")
    if changed:
        return mark_stale(old, timestamp, "공식 메타데이터 변경: " + ", ".join(changed))
    return False
