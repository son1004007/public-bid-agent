"""공식 공고번호/차수·취소종류를 기존 저장 공고에 안전하게 재적용.

개발용 preview 기본; --apply 옵션은 공식 메타데이터의 수명주기만 갱신한다.
외부 HTTP·AI·DPAPI 없음. 기존 RFP/판단/첨부·원본을 삭제하지 않는다.
"""
import argparse
import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from dashboard_backend import read as read_dashboard
from json_transaction import transaction
from notice_lifecycle import reconcile
from release_lease import guard_ready, pin_directories
from scheduled_collection import atomic_write, DEFAULT_ROOT, verify_release


def reconcile_local(root, *, apply=False):
    root = Path(root)
    with pin_directories(root), transaction(root, timeout=15):
        verify_release(root)
        before = read_dashboard(root / "dashboard.json")
        after = copy.deepcopy(before)
        changes = reconcile(after["notices"], datetime.now(timezone.utc).isoformat())
        statuses = {}
        for n in after["notices"]:
            status = n.get("notice_lifecycle", "UNVERIFIED")
            statuses[status] = statuses.get(status, 0) + 1
            if status in ("CANCELLED", "SUPERSEDED"):
                n["window_status"] = status
        if apply and changes:
            after["revision"] += 1
            atomic_write(root / "dashboard.json", after)
        return {"status": "APPLIED" if apply else "PREVIEW",
                "notices": len(after["notices"]), "changes": changes,
                "states": statuses, "written": bool(apply and changes)}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = reconcile_local(args.data_dir, apply=args.apply)
    except (ValueError, RuntimeError, OSError, TimeoutError, TypeError):
        print(json.dumps({"status": "ERROR", "category": "LOCAL_DATA_OR_RELEASE"}),
              file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
