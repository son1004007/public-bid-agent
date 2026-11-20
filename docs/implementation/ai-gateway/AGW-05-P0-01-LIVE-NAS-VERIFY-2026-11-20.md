# AGW-05 / P0-01 — NAS 기존 공개 RFP 원본·DB·공식 API 재검증 (2026-11-20)

- 상태: **EXISTING_RAW_5_OF_5_READ_ONLY_PASS / LIVE_OFFICIAL_1_OF_5_PASS / RAW_API_PERSIST_NOT_DONE / PUBLIC_ATTESTATION_OFF**
- 작업: [TASKS.md 최상단 통합 실행 큐](../../../TASKS.md) 01(P0). 개인 NAS만. 기존 보호 원본/DB/세션/기존 앱/계정/스케줄 변경하지 않음.
- 최초 원본 근거: [NAS 실첨부 수집·추출 회복 이력](../../../CURRENT_STATE.md)의 2026-11-19 HWPX 5건/파싱 5건, 갱신된 실제 수치와 구별.
- 실행 및 증거: Gateway 비승격 NAS `son1004007` SSH, 현재 실행 `public-bid-mvp-pg-rfp-web` 컨테이너 `nobody(65534)`, 별도 PostgreSQL socket 및 private-media Docker volume. DB는 Django ORM 트랜잭션에서 PostgreSQL `SET TRANSACTION READ ONLY`. 원본 바이트는 SHA 계산 외 미출력/미복사. 실측 작업의 Gateway durable job은 아래 참조.

## 1. 기존 NAS 보호 원본 5건 — 검증 결과

| 공고 끝 5자리 (공개 identity) | 원본 SHA-256 접두 12자 | 크기(byte) | 최신 Chunk 수 | 최신 추출 상태 | 범위 |
| --- | --- | ---: | ---: | --- | --- |
| 38843 | `d18a92085d7d` | 894,665 | 5,073 | PARSED / text-only | 표·각주 충실도 미확인 |
| 38997 | `d72eba521b4f` | 1,273,431 | 879 | PARSED / structured | 표 33개; 별도 `complete` 근거 없음 |
| 39165 | `b1d34223ed80` | 509,610 | 2,573 | PARSED / text-only | 표·각주 충실도 미확인 |
| 39523 | `f59c44f8c7c5` | 676,879 | 3,622 | PARSED / text-only | 표·각주 충실도 미확인 |
| 40072 | `0c74c8fa3c75` | 657,097 | 2,447 | PARSED / text-only | 표·각주 충실도 미확인 |
| **계** | **5/5** | **4,011,682** | **14,594** | **5 PARSED** | **1 structured, 4 text-only** |

- **5/5 PASS:** 보호된 private-media의 기존 `.hwpx` 파일 실제 존재, 일반 파일·ZIP 컨테이너, POSIX `0600`, 바이트 재해시 SHA-256=저장 파일명=DB `DocumentVersion.sha256`, DB 크기 일치.
- **5/5 PASS:** `Document.notice`↔`DocumentVersion.notice_version` FK 일치, 최신 `Notice.current_version` 결속, `source=G2B_OFFICIAL_API`, `freshness=CURRENT`, 해당 version 취소/정정 아님. `owner_user` 존재 / `shared_read_approved=False` (해제하지 않음).
- **5/5 PASS:** 공식 첨부 URL은 `www.g2b.go.kr`의 고정 다운로드 경로·5개 필수 질의변수로 구성, DB 공고번호·차수와 일치. **공고 차수 표시만 DB `0`, G2B 공식 URL `000`으로 다름. 수치 `int(...)` 기준 동일한 차수**이며 문자열 단순 비교 FAIL은 오류 판정이다.
- 최신 5 추출의 `coverage` JSON에 `complete` 속성은 **0/5**. 구조화 1개 warnings 0, text-only 4개는 모두 `PUBLIC_RFP_TEXT_ONLY_TABLE_LAYOUT_AND_FOOTNOTE_LINKS_UNVERIFIED` 경고 1건. `PARSED`를 완전 추출/공개 승인으로 승격시키지 않는다. 실제 소속/권한 및 추출 본문 전체 품질 평가까지 완료했다는 뜻 아님.
- **기존 파일 중복 다운로드/복제/수정, DB update, 운영 배포 없음.** SHA 증거는 실행 시점의 read-only 관측이며 이후 변경 불변성은 별도 재검증 필요.

## 2. 실제 조달청 공식 네트워크 GET — 최초 공고 1건

- 공식 원문: [공공데이터포털 조달청 나라장터 입찰공고정보서비스](https://www.data.go.kr/data/15129394/openapi.do), API `/getBidPblancListInfoServc02` 및 공식 첨부 목록 `/getBidPblancListInfoAtchFileInfo02`. 조회기준 `inqryDiv=2`, 공고번호·차수, 전체 응답 원본 바이트에 대해 해시 계산. 예전 응답/합성 fixture 사용하지 않음.
- 기존 개인 NAS에 보관된 **URL-인코딩된 API 인증키**를 읽기 전용 비밀 볼륨으로만 마운트한 일회성 비승격 Docker 검증 프로세스에서 사용. 서비스키 원문/인코딩값/URL은 명령줄·stdout·Git·문서에 출력하지 않음. `--read-only`, `--cap-drop ALL`, `no-new-privileges`, 메모리 제한, 고정 HTTPS URL, 무프록시/무리다이렉트, 8MiB 상한, `--rm`. 회사 데이터/모델/계정 관련 무관.
- **공고 공식 GET PASS:** HTTP 200 JSON, 1건 공고번호 및 수치적 차수 일치, **5,764 byte**, 원본 전체 바이트 SHA-256 **`b342a3e28e32c9e9e0e4499ab939acf0d0019c3c17656f67c49c3bb965891666`**.
- **실제 공식 첨부 GET PASS:** 894,665 byte HWPX ZIP, SHA-256 **`d18a92085d7d01c5e29186b0b10a119cdeb499f70f9183823701c48a993d3dad`**, 기존 NAS 38843 공고 보관본과 동일.
- **독립 첨부 목록 GET PASS:** `getBidPblancListInfoAtchFileInfo02` 응답 2,443 byte, `totalCount=5` / 반환 5건, `atchFileUrl` 목록에 위 첨부의 원본 다운로드 URL이 **전체 host/path/query identity 기준 정확히 존재**함. 신규 임의 URL 위조 아님.
- **실측 범위:** 공식 API/첨부 목록의 최신 교차 검증은 **5개 중 1개만** 실행. 나머지 4개는 2026-11-19 공식 다운로드 기록 및 2026-11-20 기존 바이트·DB 링크 검증이며 오늘의 추가 공식 재조회 4/5는 NOT_RUN.
- **아직 불충족:** 5,764-byte 공식 API 원본은 실행 중 메모리에서만 검사하고 **영속 비공개 root에 보관하지 않았음**. 신규 `official-g2b-capture` manifest·불변 storage key, DB의 raw/API↔canonical digest reconciliation, 검토자 PUBLIC 승인/공급자 export 승인은 **모두 NOT_DONE**. 운영 preview의 기존 문서/권한을 임의 변경하지 않음.

## 3. P0-01 중 발견한 신규 실제 결함 및 CI

- **재현:** 기존 승인된 collector-key 파일은 `%` URL-인코딩 문자열. 최초 검증 요청이 이미 인코딩된 키를 `urlencode`해 이중 인코딩하면서 공식 GET 실패. DNS/TLS/호스트는 각각 정상 응답(공식 API 루트 HTTP 400, 공식 G2B 루트 HTTP 200); 한 번만 정규화한 키로 실제 API HTTP 200 및 원본 일치 PASS.
- **수정:** [official_g2b_capture.py](../../../server/ai_gateway_core/official_g2b_capture.py)의 `_normalized_service_key`에서 원키/1회 URL-인코딩키 모두 지원. 잘못된 `%` escape 또는 디코딩된 control characters는 네트워크 전에 거부. 요청 URL만 메모리 생성, 키 원문/요약/manifest 출력 금지.
- **회귀:** [test_ai_gateway_official_capture.py](../../../server/tests/test_ai_gateway_official_capture.py)에 두 인증키 표현의 query값 동등성, 잘못된 escape/control 응답 차단 추가.
- 정확 코드 SHA `c74cc96fd`의 GitHub Actions [AI Gateway core run 44691630002](https://github.com/son1004007/public-bid-agent/actions/runs/44691630002) **91 tests PASS**, [Server foundation run 44691631513](https://github.com/son1004007/public-bid-agent/actions/runs/44691631513) **Windows/Linux/PostgreSQL 각각 415 tests PASS**, job all success. 합성 CI와 위 실제 NAS API GET는 다른 증거다.
- 실측 Gateway jobs: `job_01M7VTVYGG0046EDXDDPWD7T6E`(runtime discovery), `job_01M7VVQ8PG00BYCNHSRA7X6XHM`(첫 API 실패), 최종 공식 재조회/목록 검증은 Gateway 별도 durable execution 기록. 공개 Git에는 실제 비밀 파일 경로·토큰·문서 본문·기존 사용자 ID를 쓰지 않음.

## 4. 재개 및 안전한 다음 작업

1. **P0-01 잔여:** 이미 보유한 5건 원본을 **복제하지 않고** 1건의 공식 HTTP 원본을 승인된 NAS 별도 비공개 불변 파일·manifest로 원자 보관하는 계약 구현/실증. 공식 공고 raw SHA와 DB canonical metadata digest는 별개 정본. 실제 신규 `persist` 보호 저장은 NOT_DONE이므로 전체 P0-01 완료로 표시하지 않음.
2. **P0-02:** raw notice capture identity ↔ 기존 최신 `NoticeVersion` ↔ `DocumentVersion` 불변 별도 source mapping. 동일차수 중복·cancel/correction·source drift·rollback/권한 확인. 현재 `NoticeVersion.source_payload_digest`를 raw SHA로 직접 덮어쓰지 않는다.
3. **P0-03:** 4개 text-only의 표·각주·source locator/coverage 증명, 1800-byte 이하 분할 및 `complete` 거짓 승인 차단.
4. **P0-04/05:** 운영자 공개 판정은 별도의 staff 원본 승인/명시적 export와 권한·보안 정책이 충족된 후. 실제 AI 서비스 다중 사용자 실행/회사 data1/기존 스케줄 변경·AGY 위임·모델 호출은 계속 OFF.
