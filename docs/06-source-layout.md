# 06 소스 구조 설계

## 목적

구현 전에 초기 repository 경계를 정의한다. 아래 폴더가 실제 구현되었다는 의미가 아니다.

```text
public-bid-agent/
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

  docs/
    adr/

  .github/workflows/
  docker/
  docker-compose.yml
  .env.example
```

## 경계

### frontend

표현과 사용자 상호작용을 담당한다. authorization이나 입찰 적합성을 최종 판정하지 않는다.

### backend/api

HTTP/SSE transport contract를 담당한다.

### backend/application

use case orchestration과 transaction 범위를 담당한다.

### backend/domain

안정적인 입찰/프로필/분석 개념과 deterministic rule을 담당한다. 특별한 ADR이 없으면 FastAPI, SQLAlchemy, Google, G2B, LangChain, LangGraph에 의존하지 않는다.

### backend/infrastructure

외부 기술/서비스 adapter를 담당한다.

### backend/agent

AI workflow/state machine을 담당한다. authorization, persistence, network safety 정책을 우회할 수 없다.

## 변경 원칙

실제 구현에서 빈 계층이나 단순 pass-through가 생기거나 circular dependency를 강제하면 구조를 단순화하고 이유를 기록한다. 문서에 폴더가 있다는 이유만으로 유지하지 않는다.
