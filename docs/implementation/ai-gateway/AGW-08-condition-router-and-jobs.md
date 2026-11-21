# 0/1/2 READY 분기·중복 작업 방지·순서 제어

- 작업 ID: AGW-08
- 상태: DESIGN_READY / IMPLEMENTATION_NOT_STARTED
- 우선순위: P0; 선행 작업과 승인 조건은 [AGW 목차](README.md) 참조.
- 기존 연계: [HBR 원장](../../../TASKS.md), [사용자별 세션/교차 검증](../../server-migration/16-user-cli-session-and-blind-cross-check.md), [전역 보안·계약](../../server-migration/15-mcp-provider-executor-subscription-policy.md).
- 범위: 합성·공개 RFP와 격리 환경에서 코드/테스트 가능; 실제 CLI 로그인·회사 데이터 외부 전송·유료 모델·data1 배포는 별도 적격성·승인 전 OFF.

## 목표
사용자/공고별로 Codex와 Claude의 최신 READY를 재평가하고, 0개면 AI 없는 RAG/SQL, 1개면 단독, 2개면 독립 병렬 분석 후 교차 검증을 수행합니다. 개인 구독/실제 비용이 허용되지 않으면 2개 계획만 작성하고 실행은 BLOCKED로 남깁니다.

## 상태 결정 테이블
| Codex | Claude | plan_mode | 행동 |
|---|---|---|---|
| not READY | not READY | NO_AI | 외부 요청 0 |
| READY | not READY | SINGLE_CODEX | Codex 한 번 |
| not READY | READY | SINGLE_CLAUDE | Claude 한 번 |
| READY | READY | DUAL_INDEPENDENT | 동일 snapshot 기반 2개 독립 실행(승인된 모드) |

**READY는 AGW-03의 정책·계정·런타임 실제 상태 합성값**입니다. 단순 installed/enabled만으로 실행하지 않습니다.

## Celery/Outbox 작업 설계
1. POST AnalysisRun 시 현재 RFP version + snapshot + 정책/가용성 세대를 DB transaction으로 고정하고 각 provider 별 JobAttempt + Outbox 이벤트를 저장.
2. Broker는 중복 이벤트 전달 가능: DB unique(run_id,provider,prompt_version)와 attempt fencing token으로 멱등. 동일 user/session에 두 worker가 붙지 않도록 AGW-04 lease 사용.
3. DUAL의 두 작업은 서로의 JSON/세션을 전달하지 않으며 독립적으로 시작 가능. 병렬 동작이 정책/인프라상 불가능하면 큐에서 별도 실행하되 첫 결과는 두 번째 provider에 공개하지 않음.
4. 한쪽 성공/다른쪽 아직 미실행 → PENDING_SECOND_RESULT; 단독 성공만 한 상태로 교차 검증 성공을 표시하지 않음. quota/timeout으로 두 번째 실패 → DEGRADED_SINGLE, 이전 provider의 성공 revision 보존.
5. 외부 요청 취소는 일반적으로 완전 취소/과금 취소를 보장하지 않음. JobAttempt 상태와 outbox dedup 기록하고 소비자 CLI로 자동 전환하지 않음.
6. 실행 직전과 출력 저장 직전마다 user enabled/업무 ACL/정책/notice revision 확인. 권한 철회 후 신규 외부 I/O 차단.
7. 합성 테스트에서도 jobs 총량/동시성을 허용 세마포어로 제한하고, 복구 시 queued/outbox 중복 및 stuck lease를 회수하는 상태 전이 정의.

## Failure Matrix
- provider login expired→해당 job AUTH_REQUIRED, 다른 READY provider의 단독 결과만 보존.
- worker crash before result→UNCERTAIN_EXTERNAL_SIDE_EFFECT, 실제 재시도 전에 provider attempt 확인 또는 승인 필요.
- snapshot changed mid-run→STALE_RESULT; 검증·저장 보존하되 현 공고 최종 verdict 아님.
- concurrency/duplicate key→새 호출 대신 기존 run 반환 또는 409.
- 사용자 권한 변경→BLOCKED, 다른 사용자의 계정/공급자 자동 대여 금지.

## 인수
- 4종 READY 행렬 + 미승인/동시성/부분 성공/권한 변경/일시 네트워크/중복 이벤트 + 2개 JSON이 서로 교차 참조되지 않는지 검증.
- 실제 비용 사용 전 실행자에게 허용 mode/청구/요금제 한도 확인. 신규 무인 스케줄 활성화·기존 예약 재개 금지.

## 구현 시 변경 금지·증거
- 기존 실행기/임베딩/입찰 원본·회사 계정/사업부 집계 원가 정책/보안 차단은 보존합니다. 기능 개발 후 테스트 로그, 해당 commit SHA, 정책 승인/실제 실행 범위를 CURRENT_STATE.md에 기록합니다.
- 세부 코드 위치는 신규 server/ai_gateway 후보이며, 코드 구현 시 기존 app/serializer·작업 원장과 중복되지 않도록 실제 저장소를 재검토합니다.
