# AGW-05 / P0-02 — 공식 raw 응답과 기존 DB 정규화 digest 불변 결속

- 기준일: 2026-11-21 KST. 소유: [TASKS 최상단 P0-02](../../../TASKS.md) / [P0-01 실측](AGW-05-P0-01-LIVE-NAS-VERIFY-2026-11-20.md).
- 상태: CODE_IMPLEMENTED / SYNTHETIC_CODE_CI_PASS_SHA_7fe897c4 / NAS_REAL_SOURCE_READ_ONLY_PASS / EXISTING_NAS_DB_MIGRATION_NOT_RUN / REAL_LINK_NOT_APPLIED.

## 1. 원인 / 설계

기존 [importer.py](../../../server/bid_server/procurement/importer.py)의 NoticeVersion.source_payload_digest는 정규화 메타데이터 행의 canonical SHA-256입니다. P0-01의 조달청 HTTP 응답 전체 원본 바이트 SHA-256과 다른 값입니다. 동일 필드에 덮어쓰면 기존 공고 멱등성·정정 이력을 파괴하므로 금지합니다.

신규 [OfficialSourceLink 모델](../../../server/bid_server/ai_gateway/models.py)은 현재 NoticeVersion에 PROTECT FK, 기존 DocumentVersion에 OneToOne/PROTECT로 연결합니다. 메타데이터 SHA, 공식 raw 응답 SHA/size, 원본 capture ID/manifest key, 기존 HWPX SHA/size/storage key, 원래 공식 차수 문자열(000), 기록자/기록 시각을 별도로 기록합니다. 현재 버전이 0인 경우 공식 000과 숫자상 동등성을 검증합니다. 별도 새 NoticeVersion 또는 기존 Decision을 생성/수정하지 않습니다.

새 [0004 migration](../../../server/bid_server/ai_gateway/migrations/0004_official_source_link.py)은 PostgreSQL에서 UPDATE/DELETE를 거부하는 트리거를 설치합니다. 일반 Django ORM update/delete/bulk_update 및 기존 row save/delete도 차단합니다. privileged DDL/TRUNCATE까지 완전히 막는다는 뜻은 아니므로 DB 역할/백업·감사는 운영 승인에서 별도 검증합니다.

## 2. 구현 / 검증 계약

- [official_source_link.py](../../../server/bid_server/ai_gateway/official_source_link.py): 실 raw notice/document 바이트와 P0-01 immutable manifest의 SHA·크기·capture ID·공식 번호/차수·HWPX ZIP·storage key·UNREVIEWED 상태 검증, current NoticeVersion·공고 취소/정정·title conflict·문서 FK/owner/freshness·공식 URL 재검증. 동일 문서 버전의 다른 capture는 SOURCE_CAPTURE_CONFLICT로 보류합니다.
- 기본 apply=False는 DB 읽기 전용 검산(쓰기 잠금 없음), 명시 apply=True만 Notice→Version→Document 잠금 순으로 새 SourceLink row를 생성합니다. 동일 바이트 replay는 기존 row 반환. 공개 승인, 모델 전송, 조직 자료 공유는 모두 별도입니다.
- load_notice_only_source_files는 NAS 승인된 두 private root의 SHA 기반 파생 이름만 읽습니다. POSIX 0700 디렉터리/0600 일반 파일·symlink/hardlink 거부/8MiB 제한. 기존 RFP HWPX는 복제하지 않습니다.
- [신뢰된 운영자 명령](../../../server/bid_server/ai_gateway/management/commands/reconcile_official_g2b_source.py)은 PostgreSQL DB 이름, 기존 document ID, verified capture ID, staff operator ID, 비공개 root 2개를 확인한 후 기본 dry-run입니다. 관리자 터미널의 실제 인증/OS 권한은 별도이며 operator ID 입력만으로 결재권을 얻는 것이 아닙니다.

## 3. 격리 환경 실행 예시 — 운영 DB 적용 지시 아님

    python server/manage.py reconcile_official_g2b_source --expected-db-name VERIFIED_ISOLATED_DB --operator-id VERIFIED_STAFF_UUID --document-version-id VERIFIED_DOC_UUID --capture-id VERIFIED_64_HEX_CAPTURE_ID --capture-root PRIVATE_CAPTURE_ROOT --private-media-root PRIVATE_MEDIA_ROOT

검증만 할 때 SOURCE_LINK_DRY_RUN_VALID입니다. 승인된 테스트 DB, 실제 백업·롤백 점검, 권한 검증 이후 동일 명령에 --apply를 추가한 경우에만 mapping 기록합니다. 실제 기존 NAS DB에는 이번 P0-02 migration/insert를 적용하지 않았습니다. CLI에 공식 API key 입력·네트워크 호출 기능은 없습니다.

## 4. 실제 NAS 증거 (read-only, 변경 없음)

- 비승격 개인 NAS Docker 일회성 컨테이너, network none, 기존 DB/socket/secret/media/원본 archive 전부 read-only, PostgreSQL SET TRANSACTION READ ONLY.
- 기존 P0-01 raw notice 5,764bytes SHA-256 b342a3e28e32c9e9e0e4499ab939acf0d0019c3c17656f67c49c3bb965891666 이 기존 NoticeVersion.source_payload_digest와 **다름**을 실측했습니다.
- 동일 공고번호, 수치 차수, 제목, 최신 공고 포인터, DocumentVersion의 기존 SHA·storage key·소유자/ACL/freshness, manifest 무복제는 모두 일치했습니다. 해당 공고의 기존 NoticeVersion 이력은 **2개**입니다.
- Gateway evidence: job_01M7XC404100Y0KQR7614K9TF7. 이번 실제 경로는 신규 Django model 설치 전의 읽기 전용 자료 대조이며 SourceLink row 생성/실 DB migration은 아닙니다.

## 5. 검증 및 후속

- [합성 회귀](../../../server/tests/test_ai_gateway_official_source_link.py): dry-run/replay/메타 SHA 분리, 같은 차수 충돌, 취소/정정/stale/owner/ACL·원본 조작, POSIX raw file reader 권한/무복제, ORM 불변 및 PostgreSQL UPDATE trigger 오류·savepoint rollback.
- PostgreSQL nullable owner_user 외부 조인 FOR UPDATE, 트리거 test savepoint rollback, Windows POSIX 저장소 오류 우선순위 문제를 수정했습니다. 정확 코드 SHA 7fe897c4ff7681a51d6132238cbb7aec54eda203: [core 94/94 PASS](https://github.com/son1004007/public-bid-agent/actions/runs/44817182658), [Django Windows/Linux/PostgreSQL 각 431건 PASS](https://github.com/son1004007/public-bid-agent/actions/runs/44817182690). PostgreSQL migration/schema check, raw SQL UPDATE trigger 거부, 3개 OS 플랫폼 회귀가 CI에서 확인되었습니다. 이는 기존 NAS 운영 DB 적용/실데이터 row INSERT 증거가 아닙니다.
- 다음 P0-03: 표/각주 누락 PARTIAL, source locator·offset 유지한 UTF-8 1800byte 이하 Chunk 분할, coverage.complete 허위 승인 금지.
- P0-04 BLOCKER: 기존 public_source.py는 raw 응답 digest를 NoticeVersion canonical digest와 직접 대조해 실공고를 승인할 수 없습니다. P0-04에서 OfficialSourceLink 재검증과 staff 명시 승인으로 변경하기 전 PUBLIC packet/provider egress는 OFF입니다.
- 운영 release/회사 data1/모델 자동 실행/AGY 위임/기존 예약은 승인 전 OFF. PR #5 미병합 유지.
