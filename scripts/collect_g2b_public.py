"""공식 용역공고 읽기 전용 수집기. 24시간 범위, 부분 응답 거부.
입력: stdin 인증키(로그/argv 금지). 출력: 공개 메타데이터만 JSON, 오류는 고정 코드.
경계: 공식 HTTPS 고정 endpoint, proxy/redirect 차단, DB/사용자 자료 접근 없음.
실패: nonzero 및 스냅샷 미사용; 자동 반복 호출은 실행기 책임.
"""
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "local_app"))
from dashboard_backend import KST, collect, _NoRedirect, ProviderError


def safe_link(value, number, revision):
    if not isinstance(value, str) or len(value) > 1000 or any(ord(c) < 33 or c == "\\" for c in value):
        return ""
    try:
        p = urlsplit(value)
        if (p.scheme != "https" or p.hostname != "www.g2b.go.kr" or p.port not in (None, 443)
            or p.username is not None or p.password is not None or p.fragment
            or p.path != "/link/PNPE027_01/single/"
            or not re.fullmatch(r"[A-Za-z0-9_=-]+&[A-Za-z0-9_=-]+", p.query)):
            return ""
        pairs = parse_qsl(p.query, keep_blank_values=True, strict_parsing=True, max_num_fields=2)
        args = dict(pairs)
        if len(pairs) != 2 or set(args) != {"bidPbancNo", "bidPbancOrd"}:
            return ""
        order = args["bidPbancOrd"]
        if args["bidPbancNo"] != number or not re.fullmatch(r"[0-9]{1,5}", order) or int(order) != revision:
            return ""
        return urlunsplit(("https", "www.g2b.go.kr", p.path,
                           urlencode({"bidPbancNo": number, "bidPbancOrd": order}), ""))
    except (ValueError, TypeError):
        return ""


def deadline_utc(value):
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=KST).astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            pass
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return value
    return ""


def project(notices, scanned, end):
    rows = {}
    if type(scanned) is not int or not 0 <= len(notices) <= scanned <= 100000:
        raise ValueError("COUNT")
    for item in notices:
        no, order = item["bid_no"], item["bid_order"]
        if item["source"] != "G2B_OFFICIAL_API" or not re.fullmatch(r"[A-Za-z0-9-]{4,32}", no) or not re.fullmatch(r"[0-9]{1,5}", order):
            raise ValueError("IDENTITY")
        order = int(order)
        budget = str(item.get("budget", "")).replace(",", "")
        row = {"id": f"G2B-{no}-{order}", "bid_no": no, "bid_order": str(order), "source": "G2B_OFFICIAL_API",
               "title": item["title"][:500], "org": item["org"][:300], "budget": int(budget) if re.fullmatch(r"\d{1,15}", budget) else None,
               "end": deadline_utc(item.get("end")), "notice_kind": str(item.get("notice_kind", ""))[:60],
               "source_url": safe_link(item.get("source_url"), no, order)}
        old = rows.get(no)
        if old:
            revision = int(old["bid_order"])
            if order < revision:
                continue
            if order == revision and old != row:
                if "취소" in old["notice_kind"] and "취소" not in row["notice_kind"]:
                    continue
                if "취소" not in row["notice_kind"] or "취소" in old["notice_kind"]:
                    raise ValueError("CONFLICT")
        rows[no] = row
    if len(rows) > 10000:
        raise ValueError("BOUND")
    return {"rows": sorted(rows.values(), key=lambda r: r["bid_no"]), "scanned": scanned,
            "unique_revisions": len(notices), "window_end": end.isoformat()}


if __name__ == "__main__":
    try:
        key = sys.stdin.read(2049).strip()
        if not key or len(key) > 2048:
            raise ValueError("KEY")
        end = datetime.now(KST)
        notices, scanned = collect(key, clock=end, transport=urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect()))
        del key
        print(json.dumps(project(notices, scanned, end), ensure_ascii=False, separators=(",", ":")))
    except Exception:
        # Provider errors may contain credentialed URLs via their exception chains.
        print("G2B_COLLECTION_FAILED", file=sys.stderr)
        sys.exit(1)
