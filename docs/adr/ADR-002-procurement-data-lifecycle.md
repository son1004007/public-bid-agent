# ADR-002 나라장터 데이터 식별·개정·접수상태·출처 URL

- 상태: **설계 계약 보완(실제 API 필드 매핑 대기)**
- 검수 대응: 초기 DSR-004, 재검수 R2-005/R2-008
- 참고: https://www.data.go.kr/data/15129394/openapi.do 및 https://www.data.go.kr/data/15129437/openapi.do
- **주의:** 아래 내부 필드 이름은 실제 공공데이터 API 필드명이 아니다. 실제 API 표본을 확인한 뒤 정규화 어댑터에 매핑한다.

## 원천 저장과 개정 모델

1. `RawNoticeSnapshot`: 출처 식별자, 관측 시각, 원본 바이트 해시, 파서 버전, 수집 응답 오류 상태. 수집 응답에 서명 URL/개인정보가 있으면 raw payload를 무조건 영구 보관하지 않는다. 원본 해시와 허용된 최소 내용만 별도 보안 정책으로 보관한다.
2. `NoticeIdentity`: 원천의 하나의 공고 정체성. `source_system + natural_key` 조합을 도메인 키로 삼으나, **natural_key 실제 필드는 계약 표본 후 확정**한다.
3. `NoticeRevision`: `revision_id`, `notice_identity`, `source_revision_id`(있을 때), `supersedes_revision_id`, `revision_kind`(`ORIGINAL/CORRECTION/UNKNOWN`), `observed_at`, `content_hash`.
4. `content_change_observation`: checksum 변경·서식 차이 등 관측 사실. 이 이벤트만으로 정정/취소/마감 의미를 자동 확정하지 않는다.
5. **`availability_status` 별도 필드**: `OPEN/CLOSED/CANCELLED/UNKNOWN`, 원천 상태 문자열, 결정 근거, `status_observed_at`, `last_checked_at`, `stale_after`. 정정된 공고도 `OPEN` 또는 `CLOSED`일 수 있다.
6. `source_freshness`: 특정 분석이 참조한 source revision과 최신 확인 revision의 비교 결과 `CURRENT/STALE_SOURCE/UNKNOWN`. 과거 분석의 실행 성공 상태는 변경하지 않는다.
7. `deadline_raw`, 확인된 시간대, `deadline_utc`, `retrieved_at_utc`를 분리한다. 시간대가 확인되지 않으면 자동으로 `OPEN` 확정하거나 지원 가능으로 표시하지 않는다.
8. 개정·취소·상태 변화 또는 의미 있는 원문 변경 발생 시 과거 `AnalysisRun`과 그때의 문서/근거 버전은 **불변 이력**으로 남긴다. 새로운 최신성 projection을 통해 재검토 필요 또는 추천 제외를 표시한다.
9. 확실한 `EMPTY`와 `PARTIAL`, `UPSTREAM_ERROR`, `RATE_LIMITED`, `SCHEMA_DRIFT`, `STALE_CACHE`를 구분한다. 커서·페이지 중복/누락과 upstream 데이터 오류를 조용히 0건으로 바꾸지 않는다.

## 수집용 URL과 표시용 URL 분리

- `fetch_endpoint`: 비밀키가 포함될 수 있는 서버 내부 일시적 요청 대상. 서버 설정과 공식 ID에서 구성하며 **로그·저장·응답·원문 근거에 저장하지 않는다**.
- `canonical_source_url`: 사용자에게 공개 가능한 공식 원문 링크. credential/signature/일회성 토큰/민감 추적 query·fragment가 없는 allowlisted 주소만 저장·표시한다.
- 원천이 토큰 포함 임시 다운로드 URL만 제공하면 이를 화면에 노출하지 않고, 공식 공고 상세 페이지의 공개 URL을 근거 링크로 사용한다. 표시 URL을 안전하게 만들 수 없으면 비공개로 유지하고 링크 불가 상태로 표시한다.
- URL 정책은 scheme·host/port, 허용 path/query 키 목록, 비밀정보 패턴, proxy/redirect 및 오픈 리다이렉트 경계를 포함한다. raw API 응답에 포함된 민감 URL도 안전한 내부 범위에서만 처리한다.
- `display_url`은 원본 fetch URL에서 무조건 문자열 치환해서 만들지 않고 공식적으로 알려진 공고 식별자와 허용된 경로로 생성한다. secret redaction 실패는 fail closed다.
- HTTP 로그와 분석 trace에서는 query/path 기반 credential이 남지 않도록 별도 검증한다.

## 실제 API 표본 조사 게이트

- 정상 공고, 원천에 확인된 변경/정정/취소 표본, 서로 다른 페이지와 빈 결과/부분 실패를 읽기 전용 확인한다. 실제 예시가 없으면 합성 fixture로 명확히 구분한다.
- 공고 번호/차수/원천 자연키/첨부 ID/마감 시각/시간대/상태 코드의 실제 의미는 외부 공식 문서와 관찰된 응답을 함께 확인한다.
- 동기화 규칙은 정정 후 `OPEN`, 정정 후 `CLOSED`, 정정 후 `CANCELLED` 및 `UNKNOWN`을 모두 허용해야 한다.
- 원문 재배포·보존/임베딩 이용 조건이 불명확하면 허용된 최소 메타데이터와 원문 링크만 유지한다.

## 테스트

같은 공고의 revision, checksum 변화만 있는 경우, 정정 후 OPEN/CLOSED/CANCELLED, deadline timezone 미정, 잘못된 페이지, 원천 지연 및 타 사용자 분석 결과와의 최신성 projection 분리를 시험한다. 서명 URL/가상 서비스 키가 DB·로그·브라우저·분석 결과에 남지 않음을 검증한다.

## 현재 유효 공고 선택: EffectiveNoticeProjection — R3-001

단순히 '마지막으로 수집한 revision'을 현재 공고로 사용하지 않는다. 서버에서 다음 계약으로 `EffectiveNoticeProjection`을 생성한다.

1. `notice_identity`에 연결된 revision을 출처가 제공하는 **검증된 revision 순서 및 supersedes 관계**로 정렬한다. 원천 수정 시각과 수집 시각은 보조 근거이며, 단독 현재본 선택 기준이 아니다.
2. revision 그래프는 중복 식별, 순환 참조, 복수 말단 분기, 상충하는 선후 관계를 검사한다. 정정 차수/순서가 공식 원천에서 확인되지 않거나 최신본을 하나로 식별할 수 없으면 `effective_revision=UNKNOWN`으로 처리한다.
3. `last_successful_complete_sync`는 필요한 페이지/커서 전체를 성공적으로 수집한 경우에만 갱신한다. partial/error/rate limit 후의 캐시를 최신 원문이라고 표시하지 않는다. `as_of`와 원천 관측시각을 결과에 보여준다.
4. `source_freshness`는 현재 유효 revision과 특정 분석의 원문 revision이 일치하고 완전 동기화·허용 보관 기간을 만족할 때만 `CURRENT`다. 그 밖에는 `UNKNOWN` 또는 `STALE_SOURCE`이며 `SUITABLE`을 금지한다.
5. `availability_status`는 원천이 표시한 접수/취소 상태와 별개로 기록하고, `submission_window_status`는 서버가 **확인된 UTC 마감시각과 현재 UTC**를 비교해 `OPEN/CLOSED/UNKNOWN`으로 계산한다. 서버 시계 동기화 이상·시간대 미확정·마감 전후 허용 오차 구간은 `UNKNOWN`으로 처리한다.
6. `availability_status=CANCELLED/CLOSED`이거나 `submission_window_status=CLOSED`이면 실제 접수 가능한 공고로 표시하지 않는다. 원천이 `OPEN`이라고 주장해도 확인된 마감이 지났다면 마감 판단을 우선한다.
7. 공개 추천 가능 조건은 **유효 revision 단일 확정 + complete sync 신뢰 + `availability_status=OPEN` + `submission_window_status=OPEN` + `source_freshness=CURRENT`**의 동시 충족이다. 다른 경우 `UNKNOWN/NEEDS_REVIEW` 혹은 명시적인 '마감/취소' 상태를 표시하고 긍정 추천을 제한한다.
8. 문서·조건·마감이 정정되면 이전 분석의 실행 상태/근거 이력은 유지하면서 최신성 projection을 변경한다. 역순 동기화 중에도 이전 분석의 최신성을 낙관적으로 승격하지 않는다.

테스트: 역순 도착, 중복, supersedes cycle, branch, 상충 상태, partial pagination, 오래된 캐시, 정정 후 OPEN/CLOSED/CANCELLED, 마감 직전·직후, 시간대 불명확, 서버 시계 오차. 실제 API의 revision 표현을 관찰하기 전 이 알고리즘이 원천에서 완전히 검증됐다고 주장하지 않는다.
