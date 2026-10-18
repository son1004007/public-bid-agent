"""예약 수집 실행기: 공식 API 7일 중첩 조회 후 기존 로컬 공고 안전 병합.

입력: Windows 현재 사용자 DPAPI 키, 비공개 JSON 데이터 폴더.
출력: collection 상태와 공고 최신 메타데이터. 비밀키·원문 로그 출력 없음.
실패: API 한 구간이라도 실패하면 공고/사람 판단 원본 불변, 실패 메타데이터만 표시.
동시성: 서버와 공통 .dashboard-rfp.lock 직렬화; 조회 중 잠금을 잡지 않음.
경계: localhost 개인 PC, 명시 --apply만 쓰기. RFP 원문 자동 전송/AI 호출 없음.
불변: 조회기간 중복 제거 중 관측한 동차수 취소를 후속 일반 응답으로 해제하지 않는다.
"""
import argparse
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dashboard_backend import (
    KST, ProviderError, collect as collect_day, read as read_dashboard,
    update_collection, failed_collection, preserve_cancellation
)
from json_transaction import transaction
from procurement_credentials import CredentialError, active_key
from release_lease import acquire_guard, reject_reparse, guard_ready, pin_directories

DEFAULT_ROOT = Path(os.environ.get(
    "PUBLIC_BID_LOCAL_DATA", str(Path.home() / ".public-bid-agent-local"))).expanduser()
JOURNAL = ".rfp-release-transaction.json"


class CollectionFailed(Exception):
    """외부 응답 또는 로컬 영속성 실패. 비밀/원천 본문 포함 금지."""


def verify_release(root):
    # A completed-but-corrupted two-file release must not be masked by the collector.
    guard_ready(root)
    acquire_guard(root)
    journal = Path(root) / JOURNAL
    if journal.exists():
        state = json.loads(journal.read_text(encoding="utf-8"))
        if state.get("status") != "COMPLETED":
            raise CollectionFailed("미완료 배포 저널이 있어 공고 갱신을 거부했습니다")


def atomic_write(path, obj):
    path = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", newline="\n", dir=path.parent,
            prefix=".scheduled-collection-", suffix=".tmp", delete=False,
        ) as stream:
            temporary = stream.name
            json.dump(obj, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        reject_reparse(path)
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def fetch_window(key, *, days=7, at=None, collector=collect_day):
    if type(days) is not int or days not in (1, 7):
        raise ValueError("공식 공고 수집 기간은 1일 또는 7일만 허용")
    end = at or datetime.now(KST)
    if end.tzinfo is None:
        raise ValueError("수집 시점은 타임존 정보가 필요")
    end = end.astimezone(KST)
    results = {}
    scanned = 0
    # 오래된 구간부터 호출하여 같은 공고 정정본은 최신 데이터를 우선한다.
    for offset in range(days - 1, -1, -1):
        for attempt in range(2):
            try:
                items, count = collector(key, clock=end - timedelta(days=offset))
                break
            except ProviderError:
                if attempt:
                    raise
                time.sleep(1)
        if type(count) is not int or count < 0 or not isinstance(items, list):
            raise CollectionFailed("공식 API 수집 건수 또는 형식 오류")
        scanned += count
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                raise CollectionFailed("공식 공고 ID 오류")
            results[item["id"]] = preserve_cancellation(results.get(item["id"]), item)
    # 이전 일자 오류/빈 페이지를 정상적인 전수 수집으로 저장하지 않는다.
    if scanned < len(results):
        raise CollectionFailed("공고 수집 응답 수와 고유 공고 수 불일치")
    return list(results.values()), scanned, end


def sync_once(root, *, days=7, apply=False, collector=collect_day,
              key_provider=None, clock=None):
    if key_provider is None:
        key_provider = active_key
    root = reject_reparse(root)
    if not root.is_dir():
        raise CollectionFailed("공고 데이터 폴더가 없습니다")
    with pin_directories(root):
        verify_release(root)
    key = key_provider()
    if not key:
        raise CollectionFailed("공공데이터포털 인증키가 설정되지 않았습니다")
    items, scanned, end = fetch_window(key, days=days, at=clock, collector=collector)
    result = {"status": "DRY_RUN" if not apply else "SUCCESS",
              "unique": len(items), "scanned": scanned,
              "lookback_days": days,
              "window_end": end.isoformat()}
    if not apply:
        return result
    timestamp = datetime.now(timezone.utc).isoformat()
    # API 구간 수집은 잠금 외부; 이 시점의 최신 JSON에서 병합하여 사람의 결정을 보존한다.
    with pin_directories(root), transaction(root, timeout=30):
        verify_release(root)
        path = root / "dashboard.json"
        try:
            current = read_dashboard(path)
            fresh = update_collection(current, items, scanned, timestamp)
            fresh["collection"]["lookback_days"] = days
            fresh["collection"]["mode"] = "SCHEDULED_INCREMENTAL"
            fresh["collection"]["window_end"] = end.isoformat()
            atomic_write(path, fresh)
        except (OSError, ValueError, TypeError, KeyError):
            raise CollectionFailed("공고 최신 결과 저장에 실패했습니다") from None
    result["revision"] = fresh["revision"]
    result["changed"] = fresh["collection"]["changed"]
    return result


def safe_mark_failed(root):
    # 서비스·다른 작성자를 방해하거나 손상된 JSON을 덮어쓰지 않는다.
    for attempt in range(2):
      try:
        root = reject_reparse(root)
        with pin_directories(root), transaction(root, timeout=3):
            verify_release(root)
            previous = read_dashboard(root / "dashboard.json")
            failed = failed_collection(previous, datetime.now(timezone.utc).isoformat())
            atomic_write(root / "dashboard.json", failed)
        return True
      except (OSError, RuntimeError, ValueError, CollectionFailed, TimeoutError):
        if attempt == 0:
            time.sleep(1)
    return False


def main(argv=None):
    parser = argparse.ArgumentParser(description="Public Bid Agent 공식 공고 예약 수집")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--days", type=int, choices=(1, 7), default=7)
    parser.add_argument("--apply", action="store_true",
                        help="기존 JSON에 반영. 미지정 시 API 조회만 수행")
    args = parser.parse_args(argv)
    try:
        report = sync_once(args.data_dir, days=args.days, apply=args.apply)
    except (ProviderError, CredentialError, CollectionFailed, OSError, RuntimeError,
            TimeoutError, ValueError, TypeError) as exc:
        failure_recorded = safe_mark_failed(args.data_dir) if args.apply else False
        # 예외 chaining에 키 포함 URL이 있을 수 있으므로 외부 상세내용을 출력하지 않는다.
        print(json.dumps({"status": "ERROR",
                          "category": "API" if isinstance(exc, ProviderError) else "LOCAL_OR_CREDENTIAL",
                          "failure_state_saved": failure_recorded},
                         ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
