# ADR-007 적합성 판정·Agent 실행 상태·평가 기준

- 상태: **최소 판정 불변조건과 실행 예산 채택(수치·성능 검증 전)**
- 관련 지적: DSR-007, DSR-009, DSR-010

## 참가요건과 기술 적합성 분리

1. 각 공고의 참가요건을 `Requirement`로 분리하고 `MANDATORY`/`OPTIONAL`/`UNKNOWN_PRIORITY` 우선순위를 표시한다.
2. 각 항목의 비교 결과는 `SATISFIED`, `CONFLICT`, `UNKNOWN`, `NOT_APPLICABLE`로 한정한다. 이를 생성한 규칙/모델 버전과 근거 passage ID를 함께 기록한다.
3. **필수 참가요건 중 `UNKNOWN`이 하나라도 있으면 `SUITABLE`을 내리지 않는다.** 확인된 상충이 있으면 `UNSUITABLE`, 결론을 낼 근거가 부족하면 `NEEDS_REVIEW`로 판정한다. 법적 참가자격의 최종 보장이 아니라는 표시를 결과 바로 근처에 둔다.
4. 참가자격과 기술 적합성은 화면/데이터에서 별도로 나타낸다. 기술 유사도가 높아도 참가자격의 미확인을 덮지 못한다.
5. 계약 상의 예외·OR·AND 조건, 기간, 금액, 공동수급, 제출 조건 등이 분석되지 않으면 해당 항목은 `UNKNOWN`이다. 내부 모델은 법적 확정으로 변환하지 않는다.
6. 프로필 정보 누락은 `CONFLICT`가 아니라 `UNKNOWN`이다. 기한/공고 최신성을 확인할 수 없으면 결과를 `NEEDS_REVIEW`로 낮춘다.

## 분석 실행 상태

- `QUEUED` → `RUNNING` → `WAITING_FOR_USER` → `RUNNING` → `SUCCEEDED` 또는 `NEEDS_REVIEW`.
- 모든 비완료 상태에서 `CANCEL_REQUESTED` → `CANCELLED` 가능하며, `FAILED`, `TIMED_OUT`, `STALE_SOURCE`를 별도 상태로 유지한다.
- 정당하지 않은 재개, 만료된 질문, 중복 응답 또는 다른 사용자 답변은 상태 변경 불가다.
- `run_id`와 resume nonce를 결합해 중복 재개를 idempotent 처리하고, 늦게 도착한 외부 tool 결과는 이미 terminal 상태인 run을 변경하지 않는다.
- 공고 개정이 발생하면 원래 결과를 덮어쓰지 않고 `STALE_SOURCE` 표시와 재실행 필요를 보여준다.

## 자원 사용 및 도구 권한

- 외부 도구는 `search_bid_notices`, `get_bid_notice`, `get_bid_documents`, `get_prior_specification` 등 **고정된 typed allowlist** 내에서만 접근한다. 모델에 임의 shell, SQL 실행, 임의 URL fetch 권한을 주지 않는다.
- 분석 1건의 **초기 설계 상한**: 문서 최대 3개, 외부 도구 호출 최대 12회, LLM 호출 최대 4회, follow-up 질문 최대 2회, 상태 전이 최대 30회, 전체 wall-clock 최대 180초, 요청 모델 토큰 예산 최대 16000. 추론 공급자 제약과 실제 비용에 맞춰 운영 전 조정하며 0/무제한은 허용하지 않는다.
- 동일 오류의 재시도는 최대 1회, 일시 장애에는 bounded exponential backoff. 재시도 가능 작업도 중복 실행/중복 청구가 없는지 확인한다.
- 질문 대기 TTL은 초기 **24시간**으로 정한다. 만료 시 `NEEDS_REVIEW`로 종료하며 제한된 사용자 재시작 정책을 제공한다.
- SSE 클라이언트 연결 해제는 작업 취소를 의미하지 않는다. 취소 API는 server-side owner 검사 및 cancellation token 전파에 따라 실행한다. 실제 LLM 과금 취소 가능 여부는 provider별 검증 후 표시한다.

## 검증 및 출시 판정

- 버전 관리된 공개 평가 표본에 AI/SW 관련성, 필수요건 누락, 상충·UNKNOWN, 문서 버전 변화, 검색 근거 부정확성, 비정상 툴 출력 및 prompt injection을 포함한다.
- 학습/프롬프트 설계 샘플과 검증 샘플을 분리하고 어노테이션 기준·검토자·불일치 조정을 기록한다.
- 측정 대상은 `relevance precision/recall`, 필수요건 누락, passage retrieval recall, 유효한 evidence link 비율, 최종 판정별 혼동행렬이다.
- 초기 최우선 출시 안전성 게이트는 **근거 없이 필수조건 충족을 단정하지 않을 것**, **UNKNOWN을 SUITABLE로 승격하지 않을 것**, **잘못된 원문/사용자에 대한 근거 연결을 거부할 것**이다.
- 정량적 임계치는 작은 표본의 baseline 결과와 위험도 검토 후 승인한다. 수치가 정해지기 전에는 측정 완료/품질 보장을 주장하지 않는다.
