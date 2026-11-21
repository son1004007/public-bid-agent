"""공식 G2B 수동 원본 수집 실행 진입점.

목적: G2B 공개 원문 GET → SHA 검증 → (명시 --apply 시에만) 저장소 외부 비공개 원본 보관.
인증: 운영자 본인 환경변수 G2B_SERVICE_KEY, argv/로그/파일/manifest 출력 금지.
제한: DB 레코드/공개 승인/분석 Job/모델/예약/실제 입찰은 변경하지 않는다.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
from ai_gateway_core.official_g2b_capture import (
    CaptureError, capture, persist, persist_notice_for_existing_document,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Review-only official RFP capture")
    parser.add_argument("--notice-number", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--attachment-url", required=True)
    parser.add_argument("--attachment-name", required=True)
    parser.add_argument("--private-root", help="Existing private root outside Git")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--existing-document-storage-key",
                        help="Verified existing private-media key; do not duplicate HWPX")
    args = parser.parse_args(argv)
    try:
        if args.apply and not args.private_root:
            raise CaptureError("STORAGE_ROOT_REQUIRED")
        if args.existing_document_storage_key and not args.apply:
            raise CaptureError("EXISTING_DOCUMENT_REQUIRES_APPLY")
        captured = capture(
            notice_number=args.notice_number,
            source_revision=args.source_revision,
            attachment_url=args.attachment_url,
            attachment_name=args.attachment_name,
            service_key=os.environ.get("G2B_SERVICE_KEY", ""),
        )
        if args.existing_document_storage_key:
            summary = persist_notice_for_existing_document(
                captured, args.private_root,
                document_storage_key=args.existing_document_storage_key,
            )
        elif args.apply:
            summary = persist(captured, args.private_root)
        else:
            summary = captured.summary()
        print(json.dumps(summary, sort_keys=True, ensure_ascii=True))
        return 0
    except CaptureError as exc:
        print(json.dumps({"status": "BLOCKED", "code": exc.code}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
