# AGW-05 / P0-02 — 공식 raw 응답과 기존 DB 정규화 digest 불변 결속

- 기준일: 2026-11-21 KST. 소유: [TASKS 최상단 P0-02](../../../TASKS.md) / [P0-01 실측](AGW-05-P0-01-LIVE-NAS-VERIFY-2026-11-20.md).
- 상태: CODE_IMPLEMENTED / SYNTHETIC_CODE_CI_PASS_SHA_7fe897c4 / NAS_REAL_SOURCE_READ_ONLY_PASS / ISOLATED_PG_MIGRATE_RESTORE_PASS / EXISTING_NAS_DB_MIGRATION_NOT_RUN / REAL_LINK_NOT_APPLIED.

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


## 6. 2026-11-21 격리 DB 배포·복구 및 실원본 검증

**인수:** ISOLATED_DB_MIGRATION_RESTORE_PASS / LIVE_SOURCE_READ_ONLY_VALIDATION_PASS / REAL_BYTES_TO_ISOLATED_DB_INSERT_NOT_RUN / LIVE_DB_MIGRATION_NOT_APPLIED.

### 격리 PostgreSQL 테스트

- 기존 NAS 앱 이미지에는 최신 ai_gateway migration 파일이 포함되어 있지 않음을 확인. 현재 서비스·DB는 변경하지 않음.
- GitHub 작업 브랜치 SHA e2756f38301cf3202e16b3d22a08dce41f8bd015를 독립 NAS /tmp에 임시 checkout, Docker bind readonly. PostgreSQL 16.15-alpine 컨테이너는 network none, 포트 publish 없음, 비승격 UID 70, cap-drop ALL, 데이터 및 임시 백업 모두 tmpfs.
- 신규 최신 Django 프로젝트 check/makemigrations check/migrate → OfficialSourceLink table과 PostgreSQL immutability trigger 각각 1 PASS. Gateway job_01M7XJ1ECR00SEP952P7F6KWW2.
- 격리 DB의 *합성* notice/version/doc/staff/OfficialSourceLink 1건 INSERT, PublicRfpAttestation 0 PASS (job_01M7XJ5QZA00V20K9978TAVYEW). 공식 원문이나 운영 비밀/기존 DB의 사용자 정보는 이 합성 기록에 포함하지 않음.
- 임시 DB pg_dump -Fc → 독립 p002_restore DB pg_restore → SourceLink 1, trigger 1, 합성 notice 1 PASS (job_01M7XJ6J5600H56MHGCHP9XVFP).
- 복원본에서 ai_gateway 0004→0003 rollback 후 table/trigger 제거 PASS, 0003→0004 재적용 후 table/trigger 재생성 PASS (job_01M7XJ789C00FFPFZB3260JKNX).
- 복원본 DB만 초기화한 뒤 앞선 pg_dump를 다시 복원하여 SourceLink 1, trigger 1, notice 1 재확인 (job_01M7XJ7W7200DDQTBKNV2BGRG9). 위 백업은 운영 백업이 아니며 테스트 종료 시 폐기.

### 실제 P0-01 공식 원본 + 운영 DB 읽기 전용 검증

- 실제 원본 notice 5,764 bytes SHA b342a3e28e32c9e9e0e4499ab939acf0d0019c3c17656f67c49c3bb965891666; 기존 공식 HWPX 894,665 bytes SHA d18a92085d7d01c5e29186b0b10a119cdeb499f70f9183823701c48a993d3dad.
- 운영 DB를 SET TRANSACTION READ ONLY로 조회해 공고번호/수치 차수, 제목, notice/document 공식 URL, canonical metadata SHA, DocumentVersion current/owner/freshness/ACL을 재검산 (job_01M7XJ2GMC004G8AAX3N1THEWY).
- 최신 코드의 load_notice_only_source_files, _manifest 및 _validate_current_link를 실제 raw notice/기존 HWPX와 운영 DB NoticeVersion/DocumentVersion에 적용: 네트워크 분리, 기존 비공개 volume/DB socket/비밀 모두 readonly, PostgreSQL READ ONLY 트랜잭션, **PASS**. 공식 raw SHA와 기존 canonical SHA는 서로 다름을 다시 확인했고 문서 SHA/공식 출처는 일치 (job_01M7XJ8TWB00G561K2Y3FNHFP8).
- 운영 DB에 현재 OfficialSourceLink table **없음**, ai_gateway 0004 migration **미적용**, 해당 기존 DocumentVersion 1건 유지 확인 (job_01M7XJA8PN00GGE063VNNXYAPB).
- 격리 PostgreSQL/tmpfs와 pinned checkout은 종료·제거됨, 운영 public-bid-mvp-pg-rfp-web 컨테이너 running 유지. 최초 종료 직후 inspect는 즉시 제거 시차로 불일치하였으나 후속 read-only 관측에서 임시 자원 모두 없음 확인 (job_01M7XJBN0Y006FX2D5H4YDFX8C + 후속 확인).

### 잔여 승인·릴리스 경계

- 공식 raw 원본을 격리 DB에 실제 INSERT하는 혼합 도구 요청은 안전 검사에서 차단되어 **NOT_RUN**. 합성 데이터의 DB 실삽입과 실제 raw/운영 DB read-only 검증을 합쳐 실원본 INSERT가 끝났다고 주장하지 않음.
- 기존 운영 DB 0004 마이그레이션 및 실데이터 SourceLink INSERT를 위해서는 현재 SHA와 일치하는 설치 이미지, 운영 DB·비공개 media·capture 원본의 일관된 백업/격리 복원, 운영자 권한·롤백·인수 승인이 별도로 필요함. 이번 합성 DB 백업 테스트는 운영 데이터의 복구 근거가 아님.
- P0-03 기존 DB 재추출 및 P0-04 staff PUBLIC/별도 provider_export 승인·AI 호출은 전부 NOT_RUN. 중앙 credential USER ACTION #26, PR #5 Draft/회사 data1/구독 공유·자동 스케줄 제한 유지.

## 7. 2026-11-21 운영 반영 가능성 추가 관측 (변경 없음)

- Gateway 개인 NAS 비승격 SSH read-only 관측: `job_01M7XQHRZ20042J8SDZ43DY1CT`에서 기존 bid 컨테이너 6개 실행 중. `public-bid-mvp-pg-rfp-web`의 현재 배포 이미지에는 확인된 경로의 `ai_gateway/migrations/0004_official_source_link.py`가 없음. 확인 명령의 탐색 경로 외 임의 레이아웃의 부재까지 증명하는 것은 아님.
- `job_01M7XQR92800SFKFN723XY1XFR`: PostgreSQL과 RFP 웹 컨테이너 모두 RUNNING. PostgreSQL 데이터/소켓은 Docker volume, RFP 웹은 별도 secret read-only·media·PG socket mount. Docker 24.0.2, PostgreSQL pg_dump/pg_restore 16.15 도구 존재 확인. 비승격 환경에서 Docker PATH를 `/usr/local/bin/docker`로 명시한 읽기 전용 조회만 수행.
- **운영 DB·비공개 media·capture 원본의 동일 시점 백업과 독립 복원은 아직 NOT_RUN**. DB 도구가 설치된 사실은 데이터·파일 복원 인수가 아님. 최신 배포 이미지 pin/권한·자격증명/회전 및 rollback window 검증 후에만 0004/real mapping 적용.
- 중앙 [USER ACTION #26](https://github.com/son1004007/ai-agent-workflow-playbook/issues/26) 열림(PR #5 release 한정). 운영 서비스와 DB 변경/재시작, 외부 포트·자동 스케줄·보안 정책 변경 0.
- 별도 진행 가능한 P0-04 코드의 공식 raw/canonical SHA 검증 결함을 보완. synthetic [code SHA `0c1e1ac7`](https://github.com/son1004007/public-bid-agent/commit/0c1e1ac73151ecdd25db0a8e83238bd9945cdf4a)에서 [Server foundation CI](https://github.com/son1004007/public-bid-agent/actions/runs/44843275144) Windows/Linux/PostgreSQL 441 tests each PASS. **실제 운영 migration/attestation/모델 호출의 PASS 아님**.
