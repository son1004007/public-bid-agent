# AGW-15 | 구현 공통 계약 — Django 모델·API·상태 전이·Adapter 시그니처

- 상태: **IMPLEMENTATION_SPEC_ONLY / NOT_RUN** (2026-11-20)
- 대상 기술: 기존 server Django/DRF/PostgreSQL + Celery job/outbox 설계. 실제 존재하는 모델·migrations·settings와 충돌 여부는 구현 착수 시 확인.
- 이 문서는 AGW-01, AGW-03~10, AGW-12의 **구체적인 코드·응답 계약**을 한 곳에서 모은 구현 안내이며, 다른 코드/문서의 보안 정책을 완화하지 않습니다.

## 1. 관계형 스키마 / 제약 (설계 DDL 의사코드)

- provider_identity(id UUID PK, user_id FK, provider ENUM CODEX|CLAUDE, enabled BOOL, auth_state ENUM, policy_state ENUM, availability_state ENUM, os_identity_ref opaque string, cli_version string?, verified_at UTC?, auth_epoch INT, revision INT, created_at UTC). UNIQUE(user_id,provider). credential/session token 컬럼 **존재하면 안 됨**.
- session_binding(id UUID PK, identity_id FK, notice_id FK, purpose ENUM ANALYSIS|ISSUE_REVIEW, issue_key nullable, provider_session_id opaque encrypted-at-rest or protected metadata, last_notice_version_id FK, session_epoch INT, state ENUM NEW|ACTIVE|PAUSED|RECOVERABLE|RESET_REQUIRED|ARCHIVED, lease_owner opaque, fencing_token BIGINT, lease_until UTC?, last_success_at UTC?, archived_at UTC?). **활성 partial unique** (identity_id,notice_id,purpose,coalesce(issue_key,'')) WHERE archived_at IS NULL. SQL INDEX/nullable semantics는 실제 PostgreSQL migration에서 확인. 각 행 변경에 conditional CHECK(issue_key is not null ↔ purpose ISSUE_REVIEW).
- analysis_run(id UUID PK, created_by_id FK, notice_version_id FK, snapshot_hash CHAR64, prompt_version VARCHAR, mode ENUM NO_AI|SINGLE_CODEX|SINGLE_CLAUDE|DUAL_INDEPENDENT, status ENUM, idempotency_key, request_digest, created_at, updated_at). UNIQUE(created_by_id,notice_version_id,idempotency_key); request digest 충돌은 409.
- analysis_revision(id UUID PK, run_id FK, identity_id FK, session_id FK, schema_version, input_digest CHAR64, result_digest CHAR64, validated_json JSONB, validation_status, created_at); UNIQUE(run_id,identity_id,result_digest). immutable INSERT-only; 중복 결과는 기존 revision reference 반환.
- comparison(run_id FK, left_revision_id FK, right_revision_id FK, state, typed_diffs JSONB, evaluated_at, reviewed_by FK?, human_resolution VARCHAR?); 두 revision의 run_id와 snapshot 반드시 일치하는 serializer/service 검증.
- issue_review(id UUID PK, comparison_id FK, issue_key, reviewer_session_id FK, round_count INT DEFAULT 0, status, bounded_claim_digest, reviewed_by FK?); UNIQUE(comparison_id,issue_key,reviewer_session_id). round_count 0..1.
- FKs는 기존 NoticeVersion, User/Membership, JobAttempt, AuditEvent를 참고하고 실제 이름·auth_epoch를 확인 후 Django migrations로 생성. 기존 운영 테이블 구조 추측해 코드 자동 생성하지 않습니다.

## 2. API 요청/응답 샘플 (단지 제안 계약)

```http
POST /api/v1/ai/runs
Cookie: existing authenticated Django session
X-CSRFToken: <existing anti-CSRF token>
Idempotency-Key: <client-generated-uuid>
Content-Type: application/json

{"notice_version_id":"<approved-notice-version-uuid>","requested_mode":"AUTO"}
```

- 서버에서 권한/회사 자료 전송 정책/실행기 0-1-2 READY 판정 후 snapshot 생성. 클라이언트가 임의 evidence_id·provider_session_id를 전달하여 scope 확대할 수 없습니다.
- 성공(202 Accepted, 0개면 retrieval-only 200/202는 구현 시 기존 envelope 기준으로 확정):

```json
{"run_id":"<uuid>","plan_mode":"DUAL_INDEPENDENT","state":"QUEUED","snapshot_hash":"<sha256-hex>","providers":["CODEX","CLAUDE"],"next_action":"POLL"}
```

- GET /api/v1/ai/providers: `{"items":[{"provider":"CODEX","enabled":true,"auth_state":"AUTHENTICATED","availability_state":"READY","reason_code":null,"checked_at":"..."}]}` — 인가된 로그인 사용자 프로필만 조회.
- GET /api/v1/ai/runs/{id}: `state` + revision metadata + evidence references; full provider session ID/CLI raw stdout 금지.
- GET /api/v1/ai/runs/{id}/comparison: `{"state":"DISAGREEMENT","diffs":[{"requirement_id":"REQ-001","kind":"LEGAL_ELIGIBILITY","left":"MET","right":"UNKNOWN","evidence_ids":["..."]}],"requires_human_review":true}`.
- 인증 절차 시작/서버 내 셸 노출을 표방하는 REST endpoint는 AGW-00 정책/AGW-02 격리/AGW-03 공급자 로그인 검증 전에 구현하지 않습니다.

## 3. AnalysisResultV1 고정 최소 예시

```json
{
  "schema_version": "bid_analysis_v1",
  "run_id": "<uuid>",
  "provider": "CODEX",
  "notice_version_id": "<uuid>",
  "corpus_snapshot_id": "<uuid>",
  "snapshot_sha256": "<64-char lowercase hex>",
  "prompt_version": "bid_v1",
  "requirements": [{
    "requirement_id": "RFP-REQ-001",
    "assessment": "UNKNOWN",
    "evidence_ids": [],
    "missing_evidence_ids": ["COMPANY-CERT-01"],
    "rationale_short": "공식 증빙을 확인하지 못했습니다."
  }],
  "risks": [{
    "risk_type": "MISSING_EVIDENCE",
    "severity": "HIGH",
    "requirement_ids": ["RFP-REQ-001"],
    "evidence_ids": [],
    "summary": "인증서 확인 필요"
  }],
  "unknowns": [{"requirement_id":"RFP-REQ-001","reason":"UNVERIFIED"}]
}
```

- 실제 uuid/sha 등은 서버 issued. `requirements`는 서버가 생성한 requirement_id 집합의 부분집합으로 허용할 경우 누락된 필수 ID는 별도 UNKNOWN 자동 표기.
- 임의 `provider` 값은 클라이언트/AI가 작성했더라도 신뢰하지 않고 JobAttempt와 OS session identity에 결속.
- raw 원가/인건비, 개인·비공개 회사 자료, secret/token, arbitrary shell args/URL, 타 provider 전체 대화 내용을 결과 JSON에 허용하지 않습니다.
- 정밀 스키마/Pydantic validator 구현 시 min/max string, enum, extra=forbid, size/depth limits, RFC3339 timestamps, nullable status를 명시. 금액은 JSON output 결론 대신 Decimal SQL 재계산.

## 4. ProviderAdapter 인터페이스 (의사코드)

```python
from typing import Protocol, TypedDict

class ProviderAdapter(Protocol):
    def capabilities(self, runtime: str) -> dict: ...
    def readiness(self, identity_id: str) -> dict: ...
    def execute(self, job_id: str, session_binding_id: str, request_path: str,
                output_schema_path: str, fence: int) -> dict: ...
    def classify_failure(self, exit_code: int, sanitized_status: dict) -> str: ...
```

- adapter.execute 내부에서 OS command 실행은 AGW-02 sandbox-runner만 담당. API layer와 웹 browser는 공식 CLI auth/token/session home에 접근하지 않습니다.
- Codex/Claude 각각 resume/start 벡터와 stdout wrapper가 달라 각 adapter에서 독립 파서 구현. MCP는 내부 승인된 transport를 사용할 수 있지만 **MCP 자체가 모델 추론 권한이나 구독 비용 면제를 뜻하지 않음**.
- 기존 provider 세션 유효하면 resume, 없거나 RESET_REQUIRED로 사람/정책 확인된 경우만 새 session. 기존 ISSUE_REVIEW와 ANALYSIS는 절대 합치지 않습니다.

## 5. Run 및 Session 상태 전이 핵심 규칙

```text
NO_AI: 0 READY -> RAG/SQL ONLY
SINGLE_CODEX/SINGLE_CLAUDE: exactly 1 READY -> 1 revision -> NOT_CROSS_VALIDATED
DUAL_INDEPENDENT: 2 READY -> 2 separate first-pass revisions -> deterministic comparison
DUAL missing second revision -> PENDING_SECOND_RESULT or DEGRADED_SINGLE
DUAL disagreement -> ISSUE_REVIEW (bounded claims, max one additional round) -> HUMAN_REVIEW if unresolved
session NEW -> ACTIVE -> PAUSED -> RESUMING -> ACTIVE
AUTH_REQUIRED/QUOTA_LIMITED/NETWORK_TEMPORARY -> session ID retained
SESSION_MISSING/CONTEXT_CONTAMINATION/OWNERSHIP_CONFLICT -> RESET_REQUIRED, manual review; no silent new session
```

- 상태 전이 변경은 transaction과 fencing token을 사용. 중단된 CLI 호출의 결과 불명을 '실패했으니 재실행'으로 치환하지 않음.
- 모든 저장 결과는 run_id·notice_version·snapshot_hash·provider·actor·schema_version으로 감사 추적.
- 기존 Bid/No-Bid 권한은 업무 사용자/승인자에게만 유지.

## 6. 의무 계약 테스트 인덱스

- AGW-01 2명×2개 부서 ACL, unique/revision; AGW-02 사용자 OS home/세션 경계.
- AGW-03 로그인 만료, 정책 취소, quota, CLI_MISSING; AGW-04 동일 ID resume 3회/두 concurrent resume 거부.
- AGW-05/09 schema/evidence/snapshot mismatch, stale notice, invalid JSON/unknown fields; AGW-06/07 stdout JSON wrapper/usage/error parsing.
- AGW-08 READY 0/1/2, partial failure, outbox redelivery; AGW-10 falsified evidence and agreeing-but-wrong; AGW-11 peer transcript leak/round<=1.
- AGW-12 UI 390/1440, role, errors; AGW-13 same SHA CI + 승인 staging E2E + 복구; AGW-14 gold set/out-of-sample accuracy and latency.
- 실제 모델/서버 실행은 공급자 약관 및 조직 승인 후만, 없으면 mock-only PASS / REAL_NOT_RUN으로 구분합니다.
