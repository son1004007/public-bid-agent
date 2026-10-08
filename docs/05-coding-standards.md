# 05 코드 작성 표준

## 상태

React/TypeScript + FastAPI 초기 구현을 위한 프로젝트 로컬 기준이다.

이 문서는 개인 취향을 프레임워크 규칙처럼 강제하지 않는다. React, TypeScript, FastAPI, Python 및 OWASP의 현재 공식 문서를 우선 근거로 사용하고, 프로젝트 고유 규칙은 요구사항과 보안 경계 때문에 필요한 경우에만 추가한다.

공통 개인 표준은 기본 규칙으로 계속 적용한다:
- personal-engineering-handbook/standards/implementation.md
- testing.md
- security.md
- ai-assisted-development.md
- code-review.md

프레임워크/버전에 따라 달라지는 동작은 구현 시점의 공식 문서를 다시 확인한다.

## 외부 기준과 적용 근거

- React 공식 Rules of React: Components와 Hooks의 순수성, render 중 side effect 금지, props/state 불변성, Rules of Hooks를 적용한다.
  - https://react.dev/reference/rules
  - https://react.dev/learn/synchronizing-with-effects
- TypeScript 공식 문서: 신규 코드베이스에서 strict type checking을 기본으로 적용한다.
  - https://www.typescriptlang.org/docs/handbook/2/basic-types
  - https://www.typescriptlang.org/tsconfig/strict
- FastAPI 공식 문서: 큰 애플리케이션은 APIRouter와 dependency를 사용해 관심사를 분리하고, async/def는 실제 I/O 라이브러리의 비동기 지원 여부에 따라 선택한다.
  - https://fastapi.tiangolo.com/tutorial/bigger-applications/
  - https://fastapi.tiangolo.com/tutorial/dependencies/
  - https://fastapi.tiangolo.com/async/
  - https://fastapi.tiangolo.com/tutorial/security/
- Python 공식 typing 문서: 공개 계약과 경계의 타입 표현에 표준 typing 기능을 우선한다.
  - https://docs.python.org/3/library/typing.html
- OWASP Cheat Sheet Series: 서버 입력 검증, SSRF 및 외부 문서 처리 보안의 기준으로 사용한다.
  - https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html
  - https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html
  - https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html

외부 기준과 프로젝트 규칙이 충돌하는 것처럼 보이면 버전과 실제 threat model을 확인하고 ADR로 결정한다.

## 1. 공통 규칙

### CS-COMMON-001 - 파일 우선 설계 계약

의미 있는 소스 파일은 `AGENTS.md`와 공통 구현 표준에서 정의한 파일 상단 설계 계약을 가져야 한다. 설계 내용은 **한글 문장으로 먼저 작성하거나 갱신한 뒤 구현**한다. 클래스명, 함수명, 프로토콜명, 상태값 등 코드 식별자는 영문을 유지할 수 있다.

### CS-COMMON-002 - dependency direction

Domain/application rules must not depend on React, HTTP transport details, Google OAuth payload shapes, G2B raw payloads, LangChain/LangGraph concrete objects, or database driver objects.

External/framework details are translated at adapters/boundaries.

### CS-COMMON-003 - explicit contracts

Inputs, outputs, error semantics, ownership, side effects, timeout/retry and state transitions must be represented by types/schemas/tests rather than informal assumptions.

### CS-COMMON-004 - no speculative infrastructure

Do not add Redis, Kafka, Kubernetes, Celery, separate vector services, microservices, generic repository frameworks, or elaborate DI containers until a requirement justifies them.

### CS-COMMON-005 - source vs analysis

Types and persistence must make it possible to distinguish:
- official/source facts;
- parsed/extracted facts;
- user-provided facts;
- AI-generated interpretation;
- unknown/unverified facts.

Do not collapse them into one free-form text field when the distinction affects a decision.

## 2. Python / FastAPI 규칙

### PY-001 - baseline

- Python 3.12+ unless a verified dependency constraint requires otherwise.
- Type hints for public functions and application/domain boundaries.
- Pydantic models at API/config/external-data validation boundaries.
- Do not pass raw `dict[str, Any]` through domain/application layers when a stable contract exists.

### PY-002 - package responsibilities

Initial backend shape:

```text
backend/app/
  api/              HTTP routes and API schemas
  application/      use cases / orchestration
  domain/           domain models, rules, states
  infrastructure/
    auth/            Google identity/session adapters
    procurement/     G2B adapters
    persistence/     SQLAlchemy/PostgreSQL adapters
    llm/             provider adapters
    retrieval/       embedding/vector retrieval adapters
  agent/             LangGraph workflow/state/nodes
  core/              configuration, errors, logging primitives
```

A package may be simplified or merged if implementation evidence shows the boundary adds no value.

### PY-003 - FastAPI routes

Routes should:
1. validate transport input;
2. obtain server-derived authenticated actor;
3. call one application use case;
4. map known application errors to the API contract;
5. return explicit response schemas.

Do not put procurement parsing, eligibility rules, vector retrieval, prompt construction, DB transaction orchestration, or authorization-by-object-ID directly in route functions.

### PY-004 - async

Use `async` for actual asynchronous boundaries such as HTTP/database/streaming libraries that support it. Do not convert CPU-bound or purely synchronous domain logic to async for appearance.

Never call blocking network/file work directly on the event loop.

### PY-005 - errors

Use project/domain exceptions for expected failures. Convert them at boundaries. Never expose raw traceback, SQL/database exception, OAuth response, model error or secret-bearing upstream payload to the client.

### PY-006 - persistence

- SQLAlchemy 2.x style is the initial ORM/data-access choice unless ADR changes it.
- Transactions are owned by an application-level use case/unit-of-work boundary, not scattered implicitly across route handlers.
- User-owned queries include server-derived ownership scope.
- DB constraints protect durable invariants where appropriate.
- Migrations require review and rollback/forward-recovery consideration.

### PY-007 - external adapters

G2B/Google/model adapters:
- validate upstream responses;
- set bounded timeouts;
- classify retryable vs non-retryable failures;
- do not retry unsafe/non-idempotent operations blindly;
- preserve source IDs needed for traceability;
- do not leak vendor payloads into domain contracts.

### PY-008 - agent

LangGraph state must use explicit typed state/contracts.
Nodes should have one decision/responsibility where practical.
Tool/LLM outputs are untrusted and validated before they affect persistent state or eligibility decisions.
Deterministic rules remain outside prompts when they can be implemented reliably in code.

## 3. React / TypeScript 규칙

### TS-001 - baseline

- TypeScript strict mode.
- Avoid `any`; use `unknown` at untrusted boundaries and narrow/validate it.
- Components receive typed props.
- API contracts are centralized rather than redefined independently per component.

### TS-002 - frontend shape

Initial shape:

```text
frontend/src/
  app/          app bootstrap, providers, routing
  pages/        route-level composition
  features/     user-facing feature modules
  components/   reusable presentation components
  api/          typed backend client/contracts
  auth/         client auth/session UX
  hooks/        genuinely reusable hooks
  lib/          small framework-independent utilities
```

Do not create a global abstraction layer merely to mirror backend layering.

### TS-003 - server authority

The frontend may improve UX but is not authoritative for:
- authenticated user identity;
- authorization;
- bid eligibility;
- source provenance;
- ownership;
- security validation.

Never trust hidden/disabled UI controls as authorization.

### TS-004 - state

Prefer local/component state for local concerns.
Introduce shared state only for genuinely shared lifecycle state.
Server state should be modeled as server state rather than copied into multiple independent stores.

### TS-005 - effects

Use effects for synchronization with external systems, not for deriving values that can be calculated during render. Clean up subscriptions/streams/timers.

### TS-006 - error/loading/empty states

Every remote-data screen defines:
- loading;
- empty;
- recoverable error;
- unauthorized/session-expired;
- success.

Long-running analysis additionally defines reconnect/cancel/terminal failure behavior according to the API contract.

### TS-007 - evidence UI

Fit conclusions must visually distinguish:
- source evidence;
- user profile fact;
- AI interpretation;
- unknown/needs-review.

A user must be able to navigate from a material conclusion to its source reference when available.

## 4. 포맷과 정적 검사

Initial intended checks:

Backend:
```text
ruff check .
ruff format --check .
mypy backend/app
pytest
```

Frontend:
```text
eslint
TypeScript typecheck
frontend tests
production build
```

Exact commands/configuration become authoritative only after the project is bootstrapped and verified.

## 5. 주석과 문서

- File header: local design contract.
- Function/class comments: durable business/security/failure reasons where names/types are insufficient.
- Inline comments: non-obvious why/constraint only.
- No line-by-line narration.
- No stale guarantees.
- TODOs require a reason and trackable removal condition when they represent material debt.

## 6. 변경 완료 체크

Before claiming a code change complete:
- requirement ID or explicit user request is known;
- file design contract agrees with implementation;
- trust/authorization boundary reviewed;
- failure and external I/O behavior reviewed;
- relevant tests added/updated and actually run;
- static checks/build run as applicable;
- shared independent-review policy satisfied;
- docs/current state updated only when truth changed.
