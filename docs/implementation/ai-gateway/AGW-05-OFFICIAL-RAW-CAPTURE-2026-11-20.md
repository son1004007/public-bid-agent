# AGW-05 P0-1 — 공식 공고·첨부 원본 바이트 캡처 (2026-11-20)

## 구현 범위 / 판정

- **CODE_PARTIAL / SYNTHETIC_LOCAL_6_PASS / REAL_OFFICIAL_API_E2E_NOT_RUN / STAFF_APPROVAL_NOT_RUN**
- 공식 조달청 02 조회 오퍼레이션의 개별 공고번호/차수 응답(JSON **전체 원본 바이트**)과 지정 G2B HWPX의 **실제 HTTP 응답 바이트**를 별도로 수집한다.
- 소스: [official_g2b_capture.py](../../../server/ai_gateway_core/official_g2b_capture.py). 공식 고정 HTTPS hostname+path, 번호·차수 결속, 정확히 1건의 공식 공고, 중복 JSON key/HTTP 리다이렉트/프록시/압축/8MiB 초과 거부. 두 SHA-256 개별 산출. 임의 타 호스트·첨부 파라미터·인증정보 포함 URL은 차단.
- 운영자용 [capture_official_g2b.py](../../../scripts/capture_official_g2b.py): **수동 실행**. 원본은 CLI stdout/GitHub에 출력하지 않는다. --apply가 없으면 조회·해시만, 있으면 기존 비공개 root의 0700 하위 디렉터리에 0600 원본+manifest 보관. O_EXCL·동일 바이트 재실행 멱등·불일치 차단. 서비스키는 G2B_SERVICE_KEY 환경변수로만 읽고 인자·결과·manifest에 포함하지 않는다.
- **DB·분석 불변:** NoticeVersion, DocumentVersion, ExtractionRun, PublicRfpAttestation, AnalysisRun, AI Gateway Job, 정기 수집 및 공급자 실행은 수정하지 않는다. UNATTESTED_RAW_CAPTURE는 승인/운영 E2E 통과가 아니다.

## 운영자 수동 절차 (격리된 승인 환경에서만)

공식 첨부 URL은 기존 공식 목록/화면에서 확인한 공고번호·차수가 일치하고 HWPX여야 한다. host/path/번호·차수 결속은 강제하지만, **첨부가 실제로 해당 공고의 공식 첨부 목록에 게시되었는지는 별도 상세 오퍼레이션 검증이 필요하다**.

보호된 환경변수 G2B_SERVICE_KEY를 준비하고 다음과 같이 수동 호출한다(값은 로그/CI/GitHub에 올리지 않는다).

    python scripts/capture_official_g2b.py --notice-number NUMBER --source-revision ORDER --attachment-url 'https://www.g2b.go.kr/...공식 첨부 URL...' --attachment-name '공식확인파일.hwpx'

운영자가 격리된 Git 외부 비공개 경로를 확보한 경우 위 명령에 **--private-root PRIVATE_PATH --apply**를 추가한다. 서비스키, 원본 PDF/HWPX, 비공개 파일 경로/서비스키가 포함된 요청 URL을 공개 저장소·채팅·CI artifact에 넣지 않는다.

## 다음 미완료 P0: 원본 캡처 이후 인수 게이트

1. **실측:** 실제 나라장터 조회/첨부 GET 성공·해시·공고번호/차수·취소/정정·파일 포맷/비공개 저장 검증. 공식 [나라장터 입찰공고정보서비스](https://www.data.go.kr/data/15129394/openapi.do)는 2026-11-10부터 기간 조회 상한 7일. 기간 질의 시 분할 조회.
2. **NoticeVersion 원본 해시 저장 연결:** 현재 [live_ingest.py](../../../server/bid_server/procurement/live_ingest.py) → importer는 **정규화된 metadata row의 SHA**를 NoticeVersion.source_payload_digest로 저장한다. 실제 API 응답 원본 바이트 SHA와 다른 값이다. **현재 attestation과 자동 연결 불가.** 원본 실제 해시와 미가공 응답 storage key에 결속된 불변 새 NoticeVersion·reconcile 트랜잭션을 별도 구현한다. 이전 버전/사람 결정 보존, 동일 차수 충돌/취소 자동 덮어쓰기 금지.
3. **DocumentVersion·ExtractionRun 출처:** 기존 import_public_rfp는 owner-only, shared_read OFF로 저장하며 extractor는 coverage.complete를 자동 생성하지 않는다. 표/각주/텍스트 누락·offset·locator·1800-byte 초과 Chunk의 출처 보존 분할 검증 이후만 complete 승인을 고려한다. **임의 complete=True 금지.**
4. **직원 승인 → 모델:** 공식 원본/DB digest·공개 권한이 일치할 때에만 staff의 별도 승인. provider_export_approved는 별도 명시. 전송 직전 snapshot·권한 재검증, 사용자별 격리된 Job→SessionBinding→NAS Codex 연결은 AGW-08. 기본 OFF 유지.

## 합성 보안 검증

- [test_ai_gateway_official_capture.py](../../../server/tests/test_ai_gateway_official_capture.py): 실제 공고와 무관한 synthetic HTTP 6건. 공고번호/차수 불일치, 중복 JSON 키, 위조 호스트·첨부 URL, 잘못된 ZIP·압축 응답, 보관 재실행·변조·repo 내부 저장 거부.
- [AI Gateway core workflow](../../../.github/workflows/ai-gateway-core.yml)에서 해당 테스트 실행. GitHub CI·실제 API·NAS 운영 결과는 최신 Actions/CURRENT_STATE를 별도 확인한다.

[상위 AGW 인덱스](README.md) · [기존 AGW-05 무결성 검사](AGW-05-PUBLIC-PROVENANCE-2026-11-20.md) · [TASKS.md](../../../TASKS.md)
