# ADR-007 적합성 판정, 실행 수명주기, 평가 및 작업 예산

- 상태: **설계 계약 보완(실행·성능 검증 전)**
- 검수 대응: 초기 DSR-007/009/010, 재검수 R2-001/002/003
- 목적: 참가조건 누락·상태 혼용·재시작 후 중복 실행으로 잘못된 결과를 주는 위험을 줄인다.

## 1. 요구조건 비교와 결과 필드 분리

요건별 기본 데이터:

- `priority`: `MANDATORY`, `OPTIONAL`, `UNKNOWN_PRIORITY`
- `assessment`: `SATISFIED`, `CONFLICT`, `UNKNOWN`, `NOT_APPLICABLE`
- `evidence_state`: `PROPOSED`, `STRUCTURALLY_VALIDATED`, `SEMANTICALLY_REVIEWED`, `REJECTED` ([ADR-003](ADR-003-evidence-retrieval.md))
- `kind`: 법적·행정적 참가요건 또는 기술·구축 역량 요건(분류 불가 시 `UNKNOWN_KIND`)

추출된 요건의 중요도가 불명확하면 **`UNKNOWN_PRIORITY`이며 `SUITABLE`을 금지**한다. 명시적인 예외나 `NOT_APPLICABLE` 판정도 원문 근거로 검증하지 못하면 `UNKNOWN`으로 처리한다.

별도 결과 축:

- `eligibility_verdict`: `NO_KNOWN_CONFLICT`, `MANDATORY_CONFLICT`, `NEEDS_REVIEW`
- `technical_fit_verdict`: `MATCH`, `PARTIAL`, `MISMATCH`, `UNKNOWN`
- `overall_verdict`: `SUITABLE`, `NEEDS_REVIEW`, `UNSUITABLE`
- `availability_status`와 `source_freshness`는 각각 ADR-002의 독립 필드이며 overall verdict와 섞지 않는다.

### 보수적 집계 순서(우선 적용되는 첫 행)

| 우선순위 | 확인된 요건 및 출처 상태 | 참가/기술 결과 | 최종 결과 |
|---|---|---|---|
| 1 | 유효 원문 projection이 단일 확정되지 않거나 동기화가 불완전, `source_freshness`가 `CURRENT`가 아니거나 `availability_status` 또는 `submission_window_status`가 `OPEN`이 아님 | 원문 유효성·접수 가능성을 별도 표시 | `NEEDS_REVIEW` (닫힘/취소 공고는 추천 제외) |
| 2 | 최신 공고의 필수 참가요건이 의미상 검증된 근거와 함께 `CONFLICT` | `MANDATORY_CONFLICT` | `UNSUITABLE` |
| 3 | `UNKNOWN_PRIORITY`, `UNKNOWN_KIND`, 필수요건 `UNKNOWN`, 근거 의미 검증 미완료 또는 `extraction_completeness`가 `COMPLETE`가 아님 | `NEEDS_REVIEW` | `NEEDS_REVIEW` |
| 4 | 필수조건 미충족 없음, 선택조건만 `CONFLICT`이거나 기술 평가가 `PARTIAL/MISMATCH/UNKNOWN` | 필수조건 판정과 기술 판정 분리 | `NEEDS_REVIEW` |
| 5 | 모든 필수요건 충족/정당한 `NOT_APPLICABLE`, 분류 누락 없음, `EffectiveNoticeProjection` 확정, 출처 `CURRENT`, 접수·마감 `OPEN`, 문서 추출 `COMPLETE`, 기술 `MATCH`, 중요한 근거가 의미 검증됨 | `NO_KNOWN_CONFLICT` + `MATCH` | `SUITABLE` (법적 자격 보장 아님) |
| 기본 | 그 밖의 모든 정보 부족/상충/추출 실패 | `NEEDS_REVIEW` 또는 `UNKNOWN` | `NEEDS_REVIEW` |

**반드시 지킬 불변조건:** 
- 임의 `OPTIONAL + CONFLICT`만으로 `UNSUITABLE`을 내리지 않는다.
- `UNSUITABLE`은 **현재 유효한 공고 버전에서** 근거가 확인된 **MANDATORY 조건 충돌**일 때만 사용한다. 기술상 필수조건은 `MANDATORY`로 분류돼야 충돌로 집계한다.
- 잠재적인 필수 참가조항의 추출 또는 분류 범위가 검증되지 않았다면 `SUITABLE` 대신 `NEEDS_REVIEW`로 표시한다.
- 사용자가 제공한 프로필 값이 없으면 `UNKNOWN`; 사용자가 제공하지 않았다는 사실이 부적합의 근거가 아니다.
- 결과 UI에서 참가자격과 기술 적합성, 접수 상태, 출처 최신성을 모두 별도로 보여준다.

## 2. 서로 독립된 세 가지 상태 축

| 축 | 허용 상태 |
|---|---|
| `run_execution_status` | `QUEUED`, `RUNNING`, `WAITING_FOR_USER`, `SUCCEEDED`, `FAILED`, `TIMED_OUT`, `CANCELLED` |
| `overall_verdict` | `SUITABLE`, `NEEDS_REVIEW`, `UNSUITABLE`, `NOT_EVALUATED` |
| `source_freshness` | `CURRENT`, `STALE_SOURCE`, `UNKNOWN` |

실행 상태가 `SUCCEEDED`여도 판정이 `NEEDS_REVIEW`일 수 있다. 원문이 사후 정정되면 `run_execution_status`와 해당 결과 snapshot은 수정하지 않고 **별도 최신성 projection**의 `source_freshness`만 `STALE_SOURCE`로 갱신한다.

전이 계약:

- `QUEUED -> RUNNING` (유효한 worker claim 성공)
- `RUNNING -> WAITING_FOR_USER` (질문 발급 후 lease 해제)
- `WAITING_FOR_USER -> QUEUED` (소유자, 질문 TTL, idempotency 검증 후 resume)
- `RUNNING -> SUCCEEDED/FAILED/TIMED_OUT`
- `QUEUED/RUNNING/WAITING_FOR_USER -> CANCELLED` (권한 확인 후 취소 처리)
- `SUCCEEDED/FAILED/TIMED_OUT/CANCELLED`는 terminal이며 재개·늦은 출력으로 바뀌지 않는다. 재분석은 **새 run ID**를 생성한다.

`CANCEL_REQUESTED`는 별도 명령/취소 플래그이며 완료 상태로 사용하지 않는다. run 상태 변경은 `expected_version` CAS와 소유자·worker lease 검사를 통과해야 한다. 중복 질문 응답, 취소 중 늦은 모델 응답, 원문 정정 중 질문 응답은 원래 스냅샷 버전을 유지하거나 새 분석이 필요함을 표시한다.

## 3. 장기 작업 실행과 서버 재시작

- **비공개 PoC**는 하나의 짧은 동기식/fixture 실행만 허용하며 재시작 시 작업 지속을 보장하지 않는다. 공개 서비스와 혼동하지 않는다.
- **공개 분석**에는 FastAPI request lifespan에서 분리된 별도 worker 실행 경계를 둔다. 임의 프로세스 내 `BackgroundTasks` 실행 성공만으로 내구성을 주장하지 않는다.
- PostgreSQL `analysis_jobs` 테이블에 `run_id`, `owner_id`, `version`, `lease_owner`, `lease_expires_at`, `heartbeat_at`, `cancellation_requested_at`, `idempotency_key`, `attempt_count`를 저장한다.
- worker는 DB에서 원자적 claim(`WHERE ... AND lease_expires_at < now()` 등의 조건과 상태 검증) 후 제한된 lease 동안 실행하고 heartbeat로 갱신한다. 장애 시 만료된 claim은 예산 범위 내에서 안전하게 재획득한다.
- 각 외부 요청/파싱/모델 출력 저장은 run·단계 기준 idempotency key로 중복 반영을 방지한다. 외부 모델 자체의 과금 중복 가능성은 provider 계약/취소 검증 없이는 완전 방지했다고 주장하지 않는다.
- 예약된 모델 호출 예산, 실제 사용 예산, worker 재실행을 연결한다. 외부 도구 호출 전에 취소·원천 버전·예산을 다시 확인한다.
- SSE 재연결은 worker 생존과 별개로 PostgreSQL에 기록된 소유자별 상태·이벤트 순번에서 복구한다. 단순 polling을 사용하더라도 동일한 상태 DB를 사용한다.
- Redis/Celery를 전제로 하지 않는다. worker 종류와 배포/복구는 ADR-005에 연계한다.

## 4. 제한된 도구 권한과 예산

- 고정된 typed tool allowlist만 허용. 임의 shell, SQL 실행, 임의 URL 다운로드 금지.
- 분석 1회 초기 상한: 공식 PDF 3개, 외부 tool 호출 12회, LLM 호출 4회, 후속 질문 2회, 전이 30회, 총 실행 180초, 요청 토큰 16000. 외부 I/O 재시도 최대 1회.
- 질문 대기 TTL 초기 24시간. 사용자 응답 시 재개하려면 actor ownership, 원천 snapshot freshness, run version, 예산을 다시 확인한다.
- user/day 및 서비스 전체 글로벌 호출 한도는 실제 비용과 공개 호스팅 정책을 검증한 뒤 확정한다. 0/무제한은 허용하지 않는다.

## 5. 판정·실행·근거 평가

- 필수조건 `UNKNOWN_PRIORITY`, 선택요건 `CONFLICT`, 필수요건 `CONFLICT`, 부분 기술 적합성, 기한 불명확, 근거 의미 검증 불가를 모두 진리표 fixture에 포함한다.
- 동일 run의 상태 전이 CAS, worker 동시 claim, lease 만료, 완료 직전 취소, 취소 후 외부 응답, 질의 대기 중 정정, 완료 후 정정 및 중복 resume 경쟁 테스트를 수행한다.
- 모델 관련성, 요건 추출 누락, passage 검색, 근거 의미 검증, 최종 판정의 평가셋과 회귀 테스트를 분리한다. baseline 측정 전 정확도 성과를 주장하지 않는다.
- 필수조건 불확실성을 감춘 `SUITABLE`, 다른 문서·사용자의 잘못된 근거 연결, 의미상 관련 없는 근거로 긍정 판정을 확정한 경우는 출시 실패 기준이다.

## 제한된 후속 질문과 답변 계약 — R3-005

- 후속 질문은 모델이 임의 문장을 직접 사용자에게 노출하는 자유 형식이 아니라, 서버가 승인한 **질문 유형과 데이터 스키마**로만 발급한다. 초기 허용 유형: `TECH_SKILL_CHOICE`(비민감 기술 목록 중 선택), `EXPERIENCE_RANGE`(범위만), `CERT_EXISTS`(예/아니요/모름), `YES_NO_UNKNOWN`.
- 질문 제안도 서버에서 `type`, `allowed_options`, `source_requirement_id`, `sensitivity`, `valid_until`을 검증한다. 임의 자유 텍스트 답변·파일 첨부·링크 입력은 초기 MVP에서 **제공하지 않는다**.
- 사업자·주민등록번호, 담당자/고객 연락처, 비공개 프로젝트명·고객 목록, 실제 계약서·재무원문, 내부 코드·URL·자격증명·제안서는 입력 및 외부 모델 전송 대상이 아니다. 해당 정보가 필요한 필수요건은 `NEEDS_REVIEW`와 수동 공식 확인 안내로 종료한다.
- 사용자가 선택한 답은 **사용자가 제공한 주장**이며 검증된 자격 증거가 아니다. 서버는 이 입력만으로 법적 참가자격을 확정하지 않는다.
- 질문/답변 자료는 [ADR-008](ADR-008-profile-privacy.md)의 보존·삭제·export 및 LLM 허용 필드 목록 대상이다. 모델로 전송할 때도 승인된 enum 값/최소한의 요건 ID만 허용한다.
- 테스트: 모델이 고객사 실적 원문이나 계좌/사업자정보를 요청하는 질문을 제안한 경우 거절, 사용자 응답의 금지 값·임의 문자열 거절, 계정 삭제·마감/취소 시 답변 폐기, log·DB·모델 payload 확인.

## 영속적인 사용량 장부(budget ledger) — R3-006

- 분석 1건에 `RunBudget`과 `UsageAttempt`의 **PostgreSQL 영속 장부**를 둔다. `run_id`, `attempt_id`, `provider`, `step_id`, `idempotency_key`, `reservation`, `actual_usage`, `started_at/finished_at`, `status`를 구분한다.
- 제한하는 항목: 입력 토큰, 출력 토큰, 총 토큰, 모델 호출 **시도 횟수(실패·재시도 포함)**, 도구 호출, 처리 문서 수/바이트, `active_execution_seconds`, `waiting_for_user_seconds`, 사용자/일·서비스 전체 예산. 상한은 무제한이 아니어야 하고 공급자 실제 사용량과 비용을 검사한 뒤 공개 AI 실행 전에 확정한다.
- 기존 '요청 모델 토큰 16000'은 **입력+출력 합산 예약 상한 16000/분석**으로 명확히 한다. 각 모델 호출에는 `max_output_tokens`(초기 2048)와 입력 예산을 함께 적용한다. 공급자가 이를 지원하지 않거나 출력 상한을 보증하지 못하면 해당 provider는 활성화하지 않는다.
- `active_execution_seconds` 초기 상한 180초는 실제 worker 실행 시간의 누적값이다. 질문 대기 24시간은 별도 `waiting TTL`이며 active 예산을 초기화하지 않는다. wall-clock 시작~종료 최대 수명도 별도 제한한다(초기 25시간).
- 호출 직전 DB 원자 트랜잭션으로 `attempt_id`에 **최대 예상 사용량을 예약**하고 잔여 예산이 부족하면 호출하지 않는다. 호출 후 실제 provider 사용량으로 조정(reconciliation)하되 **시도 횟수와 이미 소비한 사용량은 단조 증가**한다.
- timeout·네트워크 장애·중복 worker·lease 회수 뒤 사용량을 확인할 수 없으면 **예약 상한을 소모한 것으로 보수적으로 처리**하고 같은 idempotency key로 중복 청구·결과 반영을 최소화한다. 과금/실사용량 보장은 provider의 실제 API 계약 확인 전에는 주장하지 않는다.
- 사용자별 일일 한도 및 전체 서비스 전역 동시 실행/비용 제한이 설정·검증되기 전에는 `approved_remote` AI 호출 모드를 공개하지 않는다. 초과 시 `LIMIT_EXCEEDED`를 사용자에게 표시하고 기존 분석 결과를 임의 성공으로 변경하지 않는다.
- 테스트: 출력을 포함한 한도, 재시도·timeout·취소 직후 늦은 usage, provider usage 누락, 동시 작업 예약, waiting 이후 resume, worker 재시작 뒤 원래 장부 복원 및 초과 요청 거부.
