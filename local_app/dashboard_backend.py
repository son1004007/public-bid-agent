"""입찰 대시보드 로컬 데이터/공식 API 읽기 전용 수집 계약.

목적/책임: 공식 나라장터 용역 입찰공고를 검증해 로컬 별도 JSON에 저장하고,
             서버가 판정한 미확인 상태/담당자 의사결정/프로필 버전 이력을 보존한다.
입력/출력: 공개 공식 목록(JSON) -> 보수적 공고 모델; 사용자 결정 -> 변경 이벤트.
신뢰 경계: 외부 필드와 사용자 입력 모두 비신뢰. 고정 HTTPS 호스트/경로, 시간·크기·페이지 제한.
상태/부작용: dashboard.json만 원자 갱신. cases.json/operations.json/AI·인증정보 무변경.
실패: 인증/통신/응답 오류는 실패; 저장된 공고를 0건 또는 취소로 오인하지 않음.
불변: 공식 자격/실적/수익/AI 판단을 추측하지 않음.
첨부 병합: 기존 RFP 증거와 서로 다른 공식 별첨 레코드를 우선 보존하고 공고당 40개 상한 적용. 사람이 내린 결정과 추천 분리.
관련 자료: docs/research/2026-10-11-dashboard-backend.md, 테스트 test_dashboard_backend.py.
"""
import copy
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from decision_profiles import clean_policy, clean_weights
from notice_lifecycle import reconcile, mark_if_metadata_changed
from procurement_filter import apply as apply_department_filter

API_URL = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoServcPPSSrch"
KEY_ENV = "DATA_GO_KR_SERVICE_KEY"
KEYWORDS = ("인공지능", "AI", "LLM", "생성형", "소프트웨어", "SW", "데이터", "플랫폼", "정보시스템",
            "시스템 구축", "빅데이터", "머신러닝", "클라우드", "API", "분석", "RAG")
MAX_ROWS = 100
MAX_PAGES = 20
MAX_RESPONSE = 4 * 1024 * 1024
KST = timezone(timedelta(hours=9))


class ProviderError(Exception):
    """공식 데이터 미확인: 기존 결과를 보존해야 하는 조회 실패."""


class DashboardConflict(Exception):
    """서버 수정 버전 불일치."""


def blank() -> dict:
    return {"schema_version": 1, "revision": 0, "notices": [], "history": [],
            "collection": {"status": "NEVER", "last_attempt": None, "last_success": None,
                           "last_error": None, "last_count": None, "last_scanned": None}}


def read(path: Path) -> dict:
    if not path.exists():
        return blank()
    with path.open(encoding="utf-8") as inp:
        obj = json.load(inp)
    if not isinstance(obj, dict) or obj.get("schema_version") != 1:
        raise ValueError("지원되지 않는 dashboard.json")
    if type(obj.get("revision")) is not int or obj["revision"] < 0:
        raise ValueError("대시보드 버전 오류")
    if not isinstance(obj.get("notices"), list) or not isinstance(obj.get("history"), list):
        raise ValueError("대시보드 항목 형식 오류")
    if not isinstance(obj.get("collection"), dict):
        raise ValueError("수집 상태 형식 오류")
    if len(obj["notices"]) > 10000 or len(obj["history"]) > 20000:
        raise ValueError("대시보드 보존 상한 초과")
    ids = []
    for item in obj["notices"]:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise ValueError("공고 데이터 형식 오류")
        ids.append(item["id"])
    if len(set(ids)) != len(ids):
        raise ValueError("중복 공고 ID")
    return obj


def _str(v, limit=200) -> str:
    return v.strip()[:limit] if isinstance(v, str) else ""


def _category(title: str) -> str:
    s = title.upper()
    if any(x in s for x in ("AI", "인공지능", "LLM", "생성형", "RAG", "머신러닝")):
        return "AI"
    if any(x in s for x in ("데이터", "빅데이터", "분석", "통계")):
        return "DATA"
    return "SW"


def _official_url(candidate) -> str | None:
    if not isinstance(candidate, str):
        return None
    try:
        value = urllib.parse.urlsplit(candidate.strip())
        if (value.scheme == "https" and value.hostname in ("www.g2b.go.kr", "g2b.go.kr")
                and not value.username and not value.password and not value.fragment):
            return candidate.strip()[:1000]
    except ValueError:
        pass
    return None


def normalize(item: dict) -> dict | None:
    if not isinstance(item, dict):
        raise ProviderError("공식 목록 항목 형식 오류")
    no = _str(item.get("bidNtceNo"), 32)
    order = _str(item.get("bidNtceOrd"), 5)
    title = _str(item.get("bidNtceNm"), 250)
    if not no or not re.fullmatch(r"[0-9A-Za-z-]{4,32}", no) or not re.fullmatch(r"[0-9]{1,5}", order):
        raise ProviderError("필수 공고번호·차수 누락")
    if not title:
        raise ProviderError("입찰공고 제목 누락")
    # 제목 키워드로 공고를 탈락시키지 않는다. 공공조달분류/원문 증빙은 이후 단계에서 분류.
    closing = _str(item.get("bidClseDt"), 40)
    org = _str(item.get("ntceInsttNm") or item.get("dminsttNm"), 120) or "기관 미확인"
    budget = _str(item.get("asignBdgtAmt"), 40)
    raw_url = item.get("bidNtceDtlUrl") or item.get("bidNtceUrl")
    attachments = []
    for n in range(1, 11):
        name = _str(item.get(f"ntceSpecFileNm{n}"), 200)
        url = _official_url(item.get(f"ntceSpecDocUrl{n}"))
        if name or url:
            attachments.append({"name": name or "첨부파일 " + str(n), "url": url, "source": "공고규격서"})
    # 공공데이터포털에 표시되는 것은 첨부 '링크'이며 문서 본문 자체가 아님.
    normalized = {
        "id": "G2B-" + no + "-" + order,
        "bid_no": no, "bid_order": order, "title": title, "org": org,
        "cat": _category(title), "budget": budget or "미확인",
        "end": closing or "미확인", "source": "G2B_OFFICIAL_API",
        "source_url": _official_url(raw_url),
        "observed_at": datetime.now(KST).isoformat(),
        "notice_kind": _str(item.get("ntceKindNm"), 60),
        "notice_published_at": _str(item.get("bidNtceDt"), 40),
        "qualification_deadline": _str(item.get("bidQlfctRgstDt"), 40),
        "procurement_classification": _str(item.get("pubPrcrmntClsfcNm"), 220),
        "procurement_code": _str(item.get("pubPrcrmntClsfcNo"), 40),
        "information_business": _str(item.get("infoBizYn"), 3),
        "industry_restriction": _str(item.get("indstrytyLmtYn"), 3),
        "participation_restriction": _str(item.get("bidPrtcptLmtYn"), 3),
        "contract_method": _str(item.get("cntrctCnclsMthdNm"), 110),
        "requirements_status": "UNKNOWN",
        "notice_lifecycle": "CANCELLED" if "취소" in _str(item.get("ntceKindNm"), 60) else "CURRENT",
        "superseded_by": None,
        "attachments": attachments,
        "rfp_text": "",
        "document_status": "PENDING" if attachments else "NOT_AVAILABLE",
        "document_source_name": "",
        "document_error": "",
        "rec": None, "final": None, "reasons": [],
        "finalReason": "", "policyRef": None, "checked": "원문/참가자격 미검증",
        "fit": None, "margin": None, "hard": "unknown", "ops": None, "exp": None, "score": None,
    }
    return apply_department_filter(normalized)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ProviderError("공식 API에서 예상하지 못한 리다이렉트 발생")


def _fetch_json(query: dict, transport=None, endpoint=API_URL) -> dict:
    # endpoint는 개발 코드에 하드코딩된 공식 오퍼레이션으로만 전달한다.
    if not isinstance(endpoint,str) or not endpoint.startswith("https://apis.data.go.kr/1230000/ad/BidPublicInfoService/"):
        raise ProviderError("공식 API 외 오퍼레이션 접근 거부")
    url = endpoint + "?" + urllib.parse.urlencode(query, safe="")
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    opener = transport or urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=12) as response:
            final_url = urllib.parse.urlsplit(response.geturl())
            if final_url.hostname != "apis.data.go.kr" or final_url.scheme != "https":
                raise ProviderError("공식 API 응답 주소가 다릅니다")
            raw = response.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE:
                raise ProviderError("공식 API 응답 크기 초과")
    except (OSError, TimeoutError, ValueError) as error:
        raise ProviderError("공식 API 연결 실패 또는 인증 오류") from error
    try:
        parsed = json.loads(raw)
    except (ValueError, UnicodeError) as error:
        raise ProviderError("공식 API가 JSON 응답을 제공하지 않았습니다") from error
    if not isinstance(parsed, dict):
        raise ProviderError("공식 API 구조 오류")
    return parsed


def collect(key: str, clock=None, transport=None) -> tuple[list[dict], int]:
    key = _validated_key(key)
    end = clock or datetime.now(KST)
    start = end - timedelta(days=1)
    base = {"ServiceKey": key, "type": "json", "inqryDiv": "1",
            "inqryBgnDt": start.strftime("%Y%m%d%H%M"), "inqryEndDt": end.strftime("%Y%m%d%H%M"),
            "numOfRows": str(MAX_ROWS)}
    all_notices = {}
    scanned = 0
    expected_total = None
    for page in range(1, MAX_PAGES + 1):
        document = _fetch_json({**base, "pageNo": str(page)}, transport=transport)
        header = document.get("response", {}).get("header", {})
        code = _str(header.get("resultCode"))
        if code != "00":
            raise ProviderError("공식 API 결과 오류: " + (code or "미확인"))
        body = document.get("response", {}).get("body")
        if not isinstance(body, dict):
            raise ProviderError("공식 API body 구조 오류")
        items = body.get("items")
        if isinstance(items, dict):
            items = items.get("item")
        if items is None:
            items = []
        if isinstance(items, dict):
            items = [items]
        if not isinstance(items, list):
            raise ProviderError("공식 API 공고목록 형식 오류")
        for raw in items:
            normalized = normalize(raw)
            scanned += 1
            if normalized:
                all_notices[normalized["id"]] = normalized
        count = body.get("totalCount")
        if type(count) is int:
            total = count
        elif isinstance(count, str) and count.isdigit():
            total = int(count)
        else:
            raise ProviderError("공식 API 총건수 불명확")
        if expected_total is None:
            expected_total = total
        elif total != expected_total:
            raise ProviderError("공식 API 페이지 간 총건수 변경: 재조회 필요")
        if not items and scanned < total:
            raise ProviderError("공식 API 공고 페이지 누락: 부분 수집 거부")
        if page * MAX_ROWS >= total:
            break
    else:
        if scanned < total:
            raise ProviderError("공고가 페이지 상한을 초과했습니다. 일부 조회를 전체 수집으로 저장하지 않습니다")
    if scanned != expected_total:
        raise ProviderError("공식 API 총건수와 실제 반환 행 수 불일치: 부분 수집 거부")
    return list(all_notices.values()), scanned


MAX_STORED_ATTACHMENTS = 120


def merge_attachments(saved: list, fresh: list) -> list:
    """기존 증거 우선 첨부 병합. 상한 도달 시 예외로 전체 쓰기를 중단한다."""
    if not isinstance(saved,list) or not isinstance(fresh,list):
        raise ValueError("첨부 목록 계약 오류")
    if len(saved)>MAX_STORED_ATTACHMENTS:
        raise ValueError("기존 첨부 목록 상한 초과. 자동 덮어쓰기 중단")
    merged=copy.deepcopy(saved)
    for item in fresh:
        if not isinstance(item,dict):
            continue
        url=item.get("url")
        identity=item.get("identity")
        same_url=[entry for entry in merged
                  if isinstance(entry,dict) and entry.get("url")==url] if url else []
        if identity:
            # identity가 존재하는 근거는 다른 identity/미확인 근거에 합치지 않는다.
            original=next((entry for entry in same_url
                           if entry.get("identity")==identity),None)
        else:
            # 출처/이름이 다른 동일 URL 근거도 별도 기록으로 남긴다.
            original=next((entry for entry in same_url
                if not entry.get("identity")
                and all(not (entry.get(field) and item.get(field)
                             and entry[field]!=item[field])
                        for field in ("name","source"))),None)
        if original is not None:
            for field,value in item.items():
                if (field not in original or original[field] in (None,"",[])) and value:
                    original[field]=copy.deepcopy(value)
            continue
        if len(merged)>=MAX_STORED_ATTACHMENTS:
            raise ValueError("공식 첨부 120개 초과. 원본 보존 후 수동 검토 필요")
        # URL이 같아도 별도 원문 식별자가 있으면 독립 근거로 저장한다.
        merged.append(copy.deepcopy(item))
    return merged


def update_collection(state: dict, notices: list, scanned: int, timestamp: str) -> dict:
    if not isinstance(notices, list) or not isinstance(scanned, int) or scanned < 0:
        raise ValueError("수집 결과 계약 오류")
    out = copy.deepcopy(state)
    existing = {n["id"]: n for n in out["notices"]}
    changed = 0
    for item in notices:
        if item["id"] in existing:
            old = existing[item["id"]]
            # 공식 정정은 RFP 원문을 덮지 않고 재검증 필요 여부만 기록한다.
            changed += int(mark_if_metadata_changed(old, item, timestamp))
            # 변경된 공식 메타데이터만 덮어쓰며 사람 결정 및 판단 이력은 보존한다.
            for key in ("title", "org", "cat", "budget", "end", "source_url", "observed_at",
                        "notice_kind", "notice_published_at", "qualification_deadline",
                        "procurement_classification", "procurement_code", "information_business",
                        "industry_restriction", "participation_restriction", "contract_method",
                        "requirements_status", "attachments"):
                incoming_value = item[key]
                if key == "attachments":
                    incoming_value = merge_attachments(old.get("attachments", []),incoming_value)
                if key != "attachments" and incoming_value in (None, "") and old.get(key) not in (None, ""):
                    # API 부분 응답의 공백은 기존 공식 메타데이터 삭제 신호가 아니다.
                    continue
                if old.get(key) != incoming_value:
                    old[key] = incoming_value
                    changed += 1
            # 기수집 원문과 담당자 판단을 보존한 상태에서 새 메타데이터로 분류를 다시 계산한다.
            apply_department_filter(old)
        else:
            new_item = copy.deepcopy(item)
            # 신규 공고도 같은 상한/증거 보존 정책. 초과 시 잘라 저장하지 않는다.
            new_item["attachments"] = merge_attachments([],new_item.get("attachments", []))
            existing[item["id"]] = new_item
            changed += 1
    if len(existing) > 10000:
        raise ValueError("저장 가능한 공고 수 초과")
    out["notices"] = list(existing.values())
    changed += reconcile(out["notices"], timestamp)
    for entry in out["notices"]:
        if entry.get("notice_lifecycle") == "CANCELLED":
            entry["window_status"] = "CANCELLED"
        elif entry.get("notice_lifecycle") == "SUPERSEDED":
            entry["window_status"] = "SUPERSEDED"
    out["revision"] += 1
    out["collection"] = {
        "status": "SUCCESS", "last_attempt": timestamp, "last_success": timestamp,
        "last_error": None, "last_count": len(notices), "last_scanned": scanned,
        "changed": changed,
    }
    return out


def failed_collection(state: dict, timestamp: str) -> dict:
    out = copy.deepcopy(state)
    out["revision"] += 1
    previous = out["collection"]
    out["collection"] = {
        "status": "ERROR", "last_attempt": timestamp,
        "last_success": previous.get("last_success"),
        "last_error": "공식 API 조회 실패. 이전 데이터가 유지됩니다.",
        "last_count": previous.get("last_count"),
        "last_scanned": previous.get("last_scanned"),
    }
    return out


def record_action(state: dict, request: dict, profiles: dict, timestamp: str) -> dict:
    expected = request.get("expected_revision")
    if type(expected) is not int or expected != state["revision"]:
        raise DashboardConflict("목록 또는 이력이 다른 창에서 변경되었습니다. 새로고침 후 재시도하세요")
    ident = request.get("id")
    target = next((n for n in state["notices"] if n["id"] == ident), None)
    if target is None:
        raise ValueError("알 수 없는 공고 ID")
    kind = request.get("kind")
    if kind not in ("recommendation", "human_no_bid", "human_bid", "human_hold"):
        raise ValueError("판단 유형 오류")
    reason = request.get("reason", "")
    if not isinstance(reason, str) or len(reason.strip()) > 500 or any(ord(c) < 32 and c not in "\t\n" for c in reason):
        raise ValueError("사유는 500자 이하로 입력하세요")
    reason = reason.strip()
    if kind.startswith("human_") and not reason:
        raise ValueError("담당자 결정 사유가 필요합니다")
    if len(state["history"]) >= 20000:
        raise ValueError("판단 이력 보존 한도에 도달했습니다")
    clean_policy(profiles["policy"])
    clean_weights(profiles["weights"])
    out = copy.deepcopy(state)
    entry = next(n for n in out["notices"] if n["id"] == ident)
    if kind == "recommendation":
        # 정식 분석·공고 원문·증빙이 없으므로 모든 공식 공고는 보류한다.
        status = "hold"
        reason = "공식 공고의 참가자격·원문·기업 역량/원가 확인 전 (자동 적합 판정 안 함)"
        entry["rec"] = status
        entry["reasons"] = [reason]
        actor = "규칙 기반 확인 보류"
    else:
        status = {"human_no_bid": "no_bid", "human_bid": "bid", "human_hold": "hold"}[kind]
        entry["final"] = status
        entry["finalReason"] = reason
        actor = "담당자 최종 선택 (로컬 기록)"
    entry["policyRef"] = f"판단 v{profiles['policy_version']} · 영향인자 v{profiles['factor_version']}"
    event = {
        "stamp": timestamp, "id": entry["id"], "title": entry["title"], "status": status,
        "actor": actor, "reason": reason, "version": entry["policyRef"],
        "policy_snapshot": copy.deepcopy(profiles["policy"]),
        "weights_snapshot": copy.deepcopy(profiles["weights"]),
        "source": entry["source"],
    }
    out["history"].insert(0, event)
    out["revision"] += 1
    return out


def verify_key(key: str, transport=None) -> None:
    """서비스 키만 검증. 공고를 저장하거나 전체 페이지를 수집하지 않는다."""
    key = _validated_key(key)
    clock = datetime.now(KST)
    doc = _fetch_json({
        "ServiceKey": key, "type": "json", "inqryDiv": "1",
        "inqryBgnDt": (clock - timedelta(days=1)).strftime("%Y%m%d%H%M"),
        "inqryEndDt": clock.strftime("%Y%m%d%H%M"),
        "numOfRows": "1", "pageNo": "1",
    }, transport=transport)
    envelope = doc.get("response", {})
    if not isinstance(envelope, dict) or not isinstance(envelope.get("header"), dict):
        raise ProviderError("공식 API 응답 구조 오류")
    if _str(envelope["header"].get("resultCode")) != "00":
        raise ProviderError("공공데이터포털 인증/활용신청 상태 또는 요청 제한을 확인하세요")
    if not isinstance(envelope.get("body"), dict):
        raise ProviderError("공식 API 인증 응답 본문이 없습니다")


def _validated_key(value: str) -> str:
    # API 어댑터도 URL 인코딩/제어문자 입력을 다시 검사한다.
    from procurement_credentials import clean_key
    try:
        return clean_key(value)
    except ValueError as exc:
        raise ProviderError("공식 API 인증키 형식 오류") from exc


def key_available() -> bool:
    from procurement_credentials import status
    return status()["configured"]
