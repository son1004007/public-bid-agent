# ADR-002 공공 입찰 원천 데이터와 공고 생명주기

- 상태: **설계 채택(실제 API 필드 매핑은 검증 대기)**
- 관련 지적: DSR-004, Gemini F-04
- 자료: https://www.data.go.kr/data/15129394/openapi.do 및 https://www.data.go.kr/data/15129437/openapi.do
- 제한: 실제 API 응답과 공고 차수/정정/취소 필드의 존재를 아직 검증하지 않았다. 아래 필드는 **내부 표준 계약**이지 공공 API 실제 필드 이름이 아니다.

## 결정

1. 수집 어댑터는 원천별 `source_system`, `source_record_id`, 원문 URL, 수집 시각, HTTP 상태와 응답 checksum을 보존한다.
2. 원문 `RawNoticeSnapshot`은 API 응답의 원문 바이트 해시, 관측 시각, 출처, 파서 버전 및 출처별 식별 정보를 보존한다. 정규화된 `NoticeRevision`과 분리한다.
3. 동일 사업의 식별자 `notice_identity`와 개정 `revision_identity`를 구분한다. **실제 composite natural key는 표본 계약 테스트 후 확정**한다. 원천의 '차수' 표현을 임의로 가정하지 않는다.
4. 개정 여부는 원천 개정/정정/취소 필드가 있으면 그 근거를 사용하고, 없는 경우 원문 checksum 변경을 발견하더라도 원천 의미를 단정하지 않는다. `UNKNOWN` 상태로 수동 확인한다.
5. 내부 상태는 `OPEN`, `CLOSED`, `CORRECTED`, `CANCELLED`, `UNKNOWN`을 사용하지만 원천 상태와 일대일 대응한다고 가정하지 않는다. 분류 근거·판정 일시를 함께 저장한다.
6. 마감 시각은 `deadline_raw`, `deadline_timezone_source`, 해석된 `deadline_utc`, `retrieved_at_utc`를 구분한다. 원천 시간대를 증명할 수 없으면 `UNKNOWN`으로 두고 '지원 가능'을 확정하지 않는다. 마감 경계에서는 원천 재조회한다.
7. `last_checked_at`과 `stale_after` 기준을 둔다. 최초 구현에서 stale 허용 시간은 **공고 표시에 명시하고 운영에서 검증할 설정값**이며 보장된 실시간성을 주장하지 않는다.
8. 정정·취소 또는 의미 있는 내용 변경을 감지하면 이전 `AnalysisRun`은 불변 이력으로 남기되 `STALE_SOURCE`로 표시하여 최신 판단으로 제공하지 않고, 재분석 필요를 알린다.
9. 취소·마감 여부가 확인되지 않거나 API 조회 실패 시 지원 가능하다는 긍정 판정을 내리지 않는다.
10. 검색 결과 `EMPTY`는 검증된 완전한 페이지 결과가 0건일 때만 사용한다. `UPSTREAM_ERROR`, `PARTIAL`, `RATE_LIMITED`, `SCHEMA_DRIFT`, `STALE_CACHE`를 다른 상태로 관리한다.
11. 공식 API 이용조건, 원문 링크, 원천 데이터의 보존 및 재배포 제한은 출처별로 기록한다. 라이선스가 불명확한 자료를 공개 저장소에 복제하지 않는다.

## 표본 조사 게이트

실제 조달청 API의 응답을 최소한 정상 공고, 동일/변경 공고, 페이지 처리, 결과 없음, 오류, 첨부 URL 사례별로 읽기 전용 확인한다. 사용 가능한 실제 정정·취소 예시가 없다면 fixture는 명확히 **합성 데이터**로 표시한다. API key나 민감한 원문은 리뷰 산출물에 기록하지 않는다.

## 테스트

원천 key 충돌, 동일 공고의 재수집, 개정/취소, checksum 변화와 의미 상태 분리, 날짜 시간대 모름, 마감 경계, 페이지 중복, 부분 결과, schema drift, API 실패 후 stale snapshot의 경고 동작을 검증한다.
