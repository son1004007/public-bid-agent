"""조달 공고 및 문서 이관 계약.
목적: 레거시 JSON 공고를 읽기 전용으로 파싱하여 공고·버전·문서 엔터티로 멱등하게 영속화한다.
경계: 원본 JSON 파일을 수정하지 않으며(read-only), 외부 LLM/원격 호출 없이 내부 트랜잭션으로 완결한다.
부작용: 신규/변경 공고 시 Notice 행 잠금(select_for_update) 하에 NoticeVersion 생성 및 LegacyIdentity 갱신.
실패: 트랜잭션 오류 시 전체 롤백. dry_run=True 시 DB 변경 없이 시뮬레이션 결과만 반환.
관련: docs/server-migration/17-domain-and-postgresql-contract.md §6, 20-acceptance-and-open-decisions.md (A05, A06, A15).
"""
import hashlib
import json
import re
from datetime import datetime, timezone as dt_timezone
from typing import Any
from django.db import transaction
from django.utils import timezone
from .models import (
    Notice,
    NoticeVersion,
    Document,
    DocumentVersion,
    LegacyIdentity,
    DeadlineStatus,
    DocumentFreshness,
)


def compute_canonical_digest(payload: Any) -> str:
    """원문 페이로드의 정규화된 canonical SHA-256 해시를 산출한다."""
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def parse_budget(val: Any) -> int | None:
    """예산 금액을 정수 원 단위로 안전하게 변환한다."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return int(val)
    if isinstance(val, str):
        cleaned = val.replace(",", "").replace("원", "").strip()
        try:
            return int(float(cleaned))
        except ValueError:
            return None
    return None


def parse_deadline(deadline_raw: str | None) -> tuple[datetime | None, str]:
    """공식 마감일시 문자열을 보수적으로 파싱한다.

    - 날짜+시각 확인 시: (datetime(UTC), DeadlineStatus.PARSED)
    - 날짜만 확인 시: (datetime(UTC 00:00:00), DeadlineStatus.DATE_ONLY) - 임의 시각 보충 없음
    - 미확인/파싱불가 시: (None, DeadlineStatus.AMBIGUOUS)
    - 과거 시각인 경우: DeadlineStatus.EXPIRED로 표기
    """
    if not deadline_raw or not str(deadline_raw).strip():
        return None, DeadlineStatus.UNKNOWN

    raw = str(deadline_raw).strip()
    dt = None
    status = DeadlineStatus.UNKNOWN

    formats_with_time = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
    ]
    for fmt in formats_with_time:
        try:
            parsed = datetime.strptime(raw, fmt)
            dt = timezone.make_aware(parsed, dt_timezone.utc) if timezone.is_naive(parsed) else parsed
            status = DeadlineStatus.PARSED
            break
        except ValueError:
            pass

    if dt is None:
        formats_date_only = ["%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"]
        for fmt in formats_date_only:
            try:
                parsed = datetime.strptime(raw, fmt)
                dt = timezone.make_aware(parsed, dt_timezone.utc) if timezone.is_naive(parsed) else parsed
                status = DeadlineStatus.DATE_ONLY
                break
            except ValueError:
                pass

    if dt is None:
        return None, DeadlineStatus.AMBIGUOUS

    # 기한 경과 여부 점검
    if dt < timezone.now():
        status = DeadlineStatus.EXPIRED

    return dt, status


class LegacyNoticeImporter:
    """레거시 공고 JSON 데이터를 도메인 모델로 멱등하게 수입/이관하는 서비스."""

    def __init__(self, source_system: str = "LEGACY_BID03", dataset: str = "SAMPLE_NOTICES"):
        self.source_system = source_system
        self.dataset = dataset

    def import_notices(
        self,
        notices_data: list[dict],
        snapshot_ref: str = "",
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """복수의 공고 항목을 원자적으로 또는 시뮬레이션으로 이관한다."""
        results = {
            "total_records": len(notices_data),
            "created_notices": 0,
            "created_versions": 0,
            "created_documents": 0,
            "created_doc_versions": 0,
            "idempotent_skipped": 0,
            "errors": [],
            "dry_run": dry_run,
        }

        # dry_run일 경우 단일 rollback 트랜잭션으로 실행
        if dry_run:
            try:
                with transaction.atomic():
                    for item in notices_data:
                        self._process_single_notice(item, snapshot_ref, results)
                    # dry_run 완료 시 예외를 발생시켜 롤백 강제
                    raise _DryRunRollback("DRY_RUN_COMPLETED")
            except _DryRunRollback:
                pass
            return results

        # 실제 이관 실행
        with transaction.atomic():
            for item in notices_data:
                try:
                    self._process_single_notice(item, snapshot_ref, results)
                except Exception as exc:
                    results["errors"].append({
                        "legacy_id": item.get("id") or item.get("bid_no"),
                        "error": str(exc),
                    })
                    raise exc

        return results

    def _process_single_notice(
        self,
        item: dict,
        snapshot_ref: str,
        results: dict[str, Any],
    ) -> NoticeVersion:
        """단일 공고 레코드를 처리한다."""
        legacy_id = str(item.get("id") or item.get("bid_no") or "").strip()
        if not legacy_id:
            raise ValueError("공고 식별자(id 또는 bid_no)가 누락되었습니다.")

        source = str(item.get("source_type") or item.get("source") or "G2B_OFFICIAL_API").strip()
        notice_number = str(item.get("bid_no") or legacy_id).strip()
        source_revision = str(item.get("bid_order") or item.get("order") or "").strip() or None

        title = str(item.get("title") or "제목 없음").strip()
        buyer = str(item.get("organization") or item.get("buyer") or item.get("org") or "발주기관 미상").strip()
        source_url = str(item.get("source_url") or "").strip()
        budget_amount = parse_budget(item.get("budget"))
        department_categories = list(item.get("department_categories") or [])
        # 자동 도메인 키워드 태깅 보완 (AI / DATA / SW)
        if re.search(r"(AI|인공지능|LLM|SLLM|머신러닝|딥러닝|생성형|초거대|Agent|에이전트|파운데이션|Foundation)", title, re.IGNORECASE) and "AI" not in department_categories:
            department_categories.append("AI")
        if re.search(r"(데이터|빅데이터|마이데이터|데이터셋|데이터베이스)", title, re.IGNORECASE) and "DATA" not in department_categories:
            department_categories.append("DATA")
        if re.search(r"(소프트웨어|시스템|플랫폼|구축|개발|유지관리|유지보수|정보화|클라우드|전산)", title, re.IGNORECASE) and "SW" not in department_categories:
            department_categories.append("SW")
        extra_data = {
            "category_evidence": item.get("category_evidence"),
            "score": item.get("score"),
            "rec": item.get("rec"),
            "final": item.get("final"),
            "classification_version": item.get("classification_version"),
        }

        # 취소 및 정정 여부 판별
        notice_kind = str(item.get("notice_kind") or item.get("kind") or "")
        cancellation = bool(item.get("cancellation") or "취소" in notice_kind or item.get("notice_lifecycle") == "CANCELLED")
        correction = bool(item.get("correction") or "정정" in notice_kind or "변경" in notice_kind)

        # 마감일시 처리
        deadline_raw = item.get("end") or item.get("deadline") or item.get("qualification_deadline") or ""
        deadline_at, deadline_status = parse_deadline(deadline_raw)

        observed_at_str = item.get("lifecycle_observed_at") or item.get("observed_at")
        if observed_at_str:
            observed_at, _ = parse_deadline(observed_at_str)
        else:
            observed_at = timezone.now()
        if not observed_at:
            observed_at = timezone.now()

        # canonical digest 계산
        digest = compute_canonical_digest(item)

        # 1. LegacyIdentity 조회하여 동일 스냅샷/내용 멱등성 검사 (A15)
        legacy_identity = (
            LegacyIdentity.objects.filter(
                source_system=self.source_system,
                dataset=self.dataset,
                entity_type="Notice",
                legacy_id=legacy_id,
            )
            .select_for_update()
            .first()
        )

        if legacy_identity and legacy_identity.digest == digest:
            # 내용 및 해시가 완전히 동일함 -> 추가 생성 없이 스킵
            results["idempotent_skipped"] += 1
            return NoticeVersion.objects.get(id=legacy_identity.target_id)

        # 2. Notice 조회 또는 생성 (source, notice_number 기준)
        notice, created_notice = Notice.objects.select_for_update().get_or_create(
            source=source,
            notice_number=notice_number,
        )
        if created_notice:
            results["created_notices"] += 1

        # 3. 새로운 version_seq 결정 (단조 증가, 과거 버전 보존 A05)
        last_version = notice.versions.order_by("-version_seq").first()
        version_seq = (last_version.version_seq + 1) if last_version else 1

        # 4. NoticeVersion 생성
        notice_version = NoticeVersion.objects.create(
            notice=notice,
            version_seq=version_seq,
            source_revision=source_revision,
            observed_at=observed_at,
            title=title,
            buyer=buyer,
            source_url=source_url,
            deadline_raw=str(deadline_raw),
            deadline_at=deadline_at,
            deadline_status=deadline_status,
            cancellation=cancellation,
            correction=correction,
            budget_amount=budget_amount,
            department_categories=department_categories,
            extra_data=extra_data,
            source_payload_digest=digest,
        )
        results["created_versions"] += 1

        # 5. Notice current_version 포인터 갱신
        notice.current_version = notice_version
        notice.save(update_fields=["current_version", "updated_at"])

        # 6. LegacyIdentity 갱신 또는 생성
        if legacy_identity:
            legacy_identity.target_id = notice_version.id
            legacy_identity.digest = digest
            legacy_identity.snapshot_ref = snapshot_ref
            legacy_identity.save(update_fields=["target_id", "digest", "snapshot_ref", "updated_at"])
        else:
            LegacyIdentity.objects.create(
                source_system=self.source_system,
                dataset=self.dataset,
                entity_type="Notice",
                legacy_id=legacy_id,
                target_id=notice_version.id,
                snapshot_ref=snapshot_ref,
                digest=digest,
            )

        # 7. 첨부 문서 및 버전 처리 (A06)
        attachments = item.get("attachments") or []
        for att in attachments:
            self._process_single_attachment(notice, notice_version, att, results)

        return notice_version

    def _process_single_attachment(
        self,
        notice: Notice,
        notice_version: NoticeVersion,
        att: dict,
        results: dict[str, Any],
    ) -> DocumentVersion:
        """단일 첨부 문서를 처리하고 SHA-256 변경 시 새 DocumentVersion 생성 및 과거 버전 STALE 처리 (A06)."""
        logical_key = str(att.get("logical_key") or att.get("name") or att.get("file_name") or "ATTACHMENT").strip()
        source_attachment_id = str(att.get("id") or att.get("attachment_id") or "").strip() or None
        # A metadata digest is not a digest of the source file.
        declared_digest = str(att.get("sha256") or att.get("hash") or "").strip().lower()
        sha256 = declared_digest if re.fullmatch(r"[0-9a-f]{64}", declared_digest) else ""
        raw_size = att.get("size_bytes") or att.get("size") or 0
        if isinstance(raw_size, bool) or not re.fullmatch(r"[0-9]{1,18}", str(raw_size)):
            raise ValueError("Invalid attachment size.")
        size_bytes = int(raw_size)
        source_identified = bool(sha256 and size_bytes > 0)
        media_type = str(att.get("media_type") or "application/octet-stream").strip()
        source_url = str(att.get("url") or att.get("source_url") or "").strip()

        document, created_doc = Document.objects.select_for_update().get_or_create(
            notice=notice,
            logical_key=logical_key,
            defaults={"source_attachment_id": source_attachment_id},
        )
        if created_doc:
            results["created_documents"] += 1

        # 기존 버전들 조회
        last_doc_version = document.versions.order_by("-version_seq").first()

        if (source_identified and last_doc_version
                and last_doc_version.sha256 == sha256
                and last_doc_version.size_bytes == size_bytes
                and last_doc_version.media_type == media_type):
            # 동일한 파일 해시인 경우 기존 버전 유지
            return last_doc_version

        # 새로운 파일 바이트 관측: 이전 최신 버전들을 STALE로 전환 (A06: 과거 버전 불변 보존)
        if source_identified:
            document.versions.filter(freshness=DocumentFreshness.CURRENT).update(
                freshness=DocumentFreshness.STALE
            )
        else:
            # An unverified observation must not assert that known bytes changed.
            document.versions.filter(freshness=DocumentFreshness.CURRENT).update(
                freshness=DocumentFreshness.REVIEW_REQUIRED
            )

        doc_seq = (last_doc_version.version_seq + 1) if last_doc_version else 1
        new_doc_version = DocumentVersion.objects.create(
            document=document,
            notice_version=notice_version,
            version_seq=doc_seq,
            sha256=sha256,
            size_bytes=size_bytes,
            media_type=media_type,
            source_url=source_url,
            freshness=DocumentFreshness.CURRENT if source_identified else DocumentFreshness.UNVERIFIED,
        )
        results["created_doc_versions"] += 1
        return new_doc_version


class _DryRunRollback(Exception):
    """dry-run 시뮬레이션 완료 후 롤백을 위한 내부 예외."""
    pass
