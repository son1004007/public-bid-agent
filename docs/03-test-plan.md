# 03 테스트 및 검증 계획

## 상태

설계 단계 기준이다. 아직 테스트를 실행하지 않았다.

## 원칙

테스트는 요구사항과 위험에 연결한다. backend의 결정적 correctness 검증과 AI/model 품질 평가는 분리한다.

## Unit

- 공고 normalization/dedup
- 진행/마감 날짜 처리
- 프로필 비교 규칙
- 근거 reference 생성
- Agent 상태 전이
- 잘못된 외부 payload

## 인증/보안

- session 없는 보호 API 거부
- 위조한 client user id 무시/거부
- 다른 사용자 profile/analysis 접근 거부
- 다른 사용자 SSE 접근 거부
- frontend/config/log fixture에 secret 없음
- 악성 문서 텍스트가 authorization/tool policy를 변경하지 못함

## 외부 API contract

fixture 기반으로 다음을 검증한다.
- 성공
- 0건
- rate limit
- timeout
- malformed payload
- upstream 4xx/5xx
- duplicate/changed notice

실제 API smoke test는 service key가 설정된 별도 검증으로 수행한다.

## 문서 수집

- 허용되지 않은 host
- redirect 경계
- 지원하지 않는 MIME
- 과대 파일
- timeout
- duplicate hash
- parser failure
- prompt injection 텍스트가 data로만 취급되는지

## Agent workflow

deterministic fake LLM으로:
- suitable
- unsuitable
- 정보 부족 -> follow-up
- upstream tool failure
- retrieval evidence 없음
- retry 소진
- 사용자 입력 후 resume

## Retrieval 평가

작은 labeled public-data set을 유지한다.
- query
- expected document/passage
- top-k result
- hit/recall 계열 지표

실제 측정 전 품질 수치를 주장하지 않는다.

## Model 평가

다음 labeled set을 유지한다.
- AI/SW 관련성
- 요구조건 추출
- fit classification

가능한 항목은 deterministic baseline과 비교한다.

## E2E

공개 demo 완료 주장 전:
- Google 로그인
- profile 저장/사용자 격리
- 실제 공개 공고 검색
- 근거 포함 분석 1건 이상
- SSE 사용자 격리
- source link
- logout/session expiry
- restart 후 persistence

## Evidence

검증 기록에는:
- commit SHA
- 실행 명령/runtime probe
- 날짜
- PASS / FAIL / NOT RUN / BLOCKED
- 범위와 알려진 제한

을 기록한다.
