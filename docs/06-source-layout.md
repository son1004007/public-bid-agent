# 06 Source Layout

## Goal

Define the initial repository shape before bootstrap. This is a design boundary, not proof that the directories are implemented.

```text
public-bid-agent/
  AGENTS.md
  AI_CONTEXT.md
  CURRENT_STATE.md
  TASKS.md
  README.md
  LICENSE
  NOTICE

  docs/
    00-project-context.md
    01-requirements.md
    02-architecture.md
    03-test-plan.md
    04-operation-and-deployment.md
    05-coding-standards.md
    06-source-layout.md
    adr/

  frontend/
    src/
      app/
      pages/
      features/
      components/
      api/
      auth/
      hooks/
      lib/
    tests/

  backend/
    app/
      api/
      application/
      domain/
      infrastructure/
        auth/
        procurement/
        persistence/
        llm/
        retrieval/
      agent/
      core/
    tests/
      unit/
      integration/
      contract/

  .github/
    workflows/

  docker/
  docker-compose.yml
  .env.example
```

## Boundary rules

### frontend

Owns presentation and interaction. It cannot make authoritative authorization/eligibility decisions.

### backend/api

Owns HTTP/SSE transport contracts only.

### backend/application

Owns use-case orchestration, transaction scope and calls into domain/ports.

### backend/domain

Owns stable bid/profile/analysis concepts and deterministic rules. No FastAPI, SQLAlchemy, Google, G2B, LangChain or LangGraph imports unless a later ADR demonstrates a justified exception.

### backend/infrastructure

Owns replaceable external technology adapters.

### backend/agent

Owns the explicit AI workflow/state machine. It can call application/domain ports but cannot bypass authorization/persistence/network safety policies.

## Initial deployment unit

Frontend and backend may be built separately, but backend remains a modular monolith. PostgreSQL/pgVector is the only planned persistent data service for MVP.

## Change rule

If implementation reveals that this layout creates empty/pass-through layers or forces circular dependencies, change the design deliberately and record the reason. Do not preserve folders solely because this document predicted them.
