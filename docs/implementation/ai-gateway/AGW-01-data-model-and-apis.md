> **2026-11-20 구현 실측:** `server/bid_server/ai_gateway/` Django `ProviderProfile`, `SessionBinding`, `migrations/0001_initial.py`와 `GET /api/v1/ai/providers` 실행 가능한 실제 코드 반영. 본인 DB 세션만 조회·token 입력 불허·기본 NO_AI·인증 최신성/epoch/계약/환경 게이트. [Windows/Linux/PostgreSQL Django 전체 303건씩 CI 성공](https://github.com/son1004007/public-bid-agent/actions/runs/44659013442), [실행 기록](AGW-RUN-2026-11-20.md). **AnalysisRun/AnalysisRevision/Comparison DB, 사용자 공식 CLI 등록·자동 실행/세션 lease는 아직 구현되지 않음.** 아래의 모델명/필드 예시는 전체 목표안이며 이미 구현된 스키마와 같다고 간주하지 않는다.

# Provider/Session/Run/Comparison 데이터 모델·DRF 계약

- 작업 ID: AGW-01
- 상태: CODE_PARTIAL / PROFILE_SESSION_DB_READ_API_TESTED; RUN_COMPARISON_NOT_IMPLEMENTED
- 범위: public-bid-agent AI Gateway 실행기 설계. 참조 [작업 목차](README.md), [상위 세션 설계](../../server-migration/16-user-cli-session-and-blind-cross-check.md).
- 실행 정책: 중앙 CONTROL 및 대상 AGENTS 우선, 실제 회사 자료·외부 호출·data1 운영 배포는 승인 이전 차단, 별도 AI 코드 리뷰는 선택·기능/보안/회귀 검사는 필수.

## 목적
현재 Django User/Membership·공고 버전·작업 원장을 재사용해 공급자별 등록/세션/검증의 관계형 정본을 설계합니다. 기존 DB와 다른 신규 이중 원장을 만들지 않습니다.

## 권장 신규 앱과 엔터티(구현 위치 제안)
- server/ai_gateway/models.py, migrations/, serializers.py, permissions.py, views.py, urls.py, tests/.
- ProviderIdentity: id, user(FK), provider(CODEX/CLAUDE), enabled, policy_state, auth_state, availability_state, os_identity_ref, verified_at, auth_epoch, created_at. UNIQUE(user,provider). **토큰 없음**.
- SessionBinding: id, identity(FK), notice(FK), purpose(ANALYSIS/ISSUE_REVIEW), provider_session_id, session_epoch, last_notice_version(FK), state, last_success_at, lock_version, lease_owner, lease_until; 활성 키 UNIQUE(identity,notice,purpose), archive 방식 세션 교체 이력 보존.
- AnalysisRun: id UUID, owner(FK), notice_version(FK), immutable_snapshot_hash, prompt_version, plan_mode(NO_AI/SINGLE_CODEX/SINGLE_CLAUDE/DUAL_INDEPENDENT), job_state, request_digest, idempotency_key, created_at.
- AnalysisRevision: id, run(FK), identity(FK), session(FK), input_digest, json_schema_version, validated_json JSONB, result_digest, status, created_at. 결과는 UPDATE 대신 신규 revision 추가.
- Comparison: run(FK), codex_revision(FK nullable), claude_revision(FK nullable), status, field_diffs JSONB, evaluated_at, resolved_by(FK nullable), resolution_reason. 참조 revision과 run/snapshot이 일치하는 DB 검증 추가.
- IssueReview: comparison(FK), issue_key, reviewer_session(FK), bounded_claim_digest, status, reviewer_decision; 같은 issue_key 재실행은 기존 상태를 찾습니다.
- 기존 JobAttempt/Outbox/AuditEvent와 연결하고, 중복 worker/예약 재시도 계약을 재사용합니다.

## API 예시(별도 신규 API이며 기존 서버에서 구현되었다는 뜻 아님)
- GET /api/v1/ai/providers: 본인만 provider / enabled / readiness / reason / checked_at.
- POST /api/v1/ai/providers/{name}/settings: enabled만 허용, 권한/CSRF/expected_revision 필요.
- POST /api/v1/ai/runs: notice_version_id, expected_snapshot_hash, Idempotency-Key → run_id, plan_mode, state(QUEUED/BLOCKED).
- GET /api/v1/ai/runs/{id}: snapshot/revisions/status; 회사 근거/다른 사용자 정보는 범위 필터.
- GET /api/v1/ai/runs/{id}/comparison: 구조화 비교 및 검토 필요 사유. 최종 Bid/No-Bid 저장은 기존 권한 있는 업무 API를 사용합니다.
- 사용자 CLI 인증 시작 API는 AGW-03의 인증 방식 검증 전 정의하지 않습니다. 웹앱은 OAuth 토큰 받지 않습니다.

## 트랜잭션·오류
- 생성 요청 트랜잭션에서 권한·공고 버전·스냅샷을 고정하고 run + outbox 함께 커밋. 동일 user+scope+Idempotency-Key+digest 재호출은 기존 결과, digest 충돌 409.
- 타 사용자/다른 부서/미공개 원문 = 403 또는 기존 일관된 비노출 404; auth 401, 정책 차단 403, 버전 불일치 409, 입력 무효 422, 실행기 불가 503. HTTP 상태는 기존 서버 표준으로 확정합니다.
- DB 잠금 및 lease 상태는 낙관적 rev 비교+FOR UPDATE로 전이하고 인증 epoch가 바뀌면 대기 실행 중단.

## 사전 테스트/수용
- 사용자/부서 간 2×2 ACL, 공급자 두 개 UNIQUE, 동시 생성 idempotency, notice_version 수정 후 stale 차단, auth_epoch 폐기, DB migration/rollback 검증.
- 비밀/CLI raw stdout가 DB·JSON·OpenAPI·로그에 들어가지 않는지 정적/동적 검사.
- 합성 DB 테스트 PASS + migrations 점검 + 프런트 OpenAPI 계약 확정 전에는 기능 구현 완료 아님.

## 구현 의존성/다음 작업
- 이 문서는 모듈 단위 설계이며 실제 엔드포인트·DB schema·CLI 명령이 구현된 상태를 주장하지 않습니다. 바뀐 계약/버전은 구현 시 증거와 함께 이 문서를 갱신합니다.
- 다음 작업은 [AGW 작업 인덱스](README.md)의 선행 의존 관계와 기존 [HBR 작업 원장](../../../TASKS.md)을 따릅니다.
