# 05 Coding Standards

## Status

Project-local baseline for the initial React/TypeScript + FastAPI implementation.

Shared owner standards remain authoritative defaults:
- personal-engineering-handbook/standards/implementation.md
- testing.md
- security.md
- ai-assisted-development.md
- code-review.md

Framework/version-specific behavior must be checked against current official documentation when implemented.

## 1. Common rules

### CS-COMMON-001 - file-first design contract

Substantive source files must have the top-of-file design contract defined in `AGENTS.md` and the shared implementation standard. Write/update it before implementation.

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

## 2. Python / FastAPI

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

## 3. React / TypeScript

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

## 4. Formatting and static checks

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

## 5. Comments and documentation

- File header: local design contract.
- Function/class comments: durable business/security/failure reasons where names/types are insufficient.
- Inline comments: non-obvious why/constraint only.
- No line-by-line narration.
- No stale guarantees.
- TODOs require a reason and trackable removal condition when they represent material debt.

## 6. Change checklist

Before claiming a code change complete:
- requirement ID or explicit user request is known;
- file design contract agrees with implementation;
- trust/authorization boundary reviewed;
- failure and external I/O behavior reviewed;
- relevant tests added/updated and actually run;
- static checks/build run as applicable;
- shared independent-review policy satisfied;
- docs/current state updated only when truth changed.
