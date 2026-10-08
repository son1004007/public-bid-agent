# Public Bid Agent

Public Bid Agent is a public portfolio project for discovering AI/software public procurement opportunities and analyzing participation fit with traceable evidence from official public sources.

> Current status: planning / architecture. No runtime implementation or public deployment has been verified yet.

## Intended flow

```text
Google sign-in
-> organization/technology profile
-> official procurement search
-> AI/software relevance filtering
-> notice/RFP evidence retrieval
-> eligibility and technical-fit analysis
-> follow-up for missing facts
-> SUITABLE / NEEDS_REVIEW / UNSUITABLE with evidence
```

## Planned architecture

- React + TypeScript
- Python + FastAPI
- LangGraph
- LangChain where justified by retrieval/LLM integration
- PostgreSQL + pgVector
- official G2B public-data adapters
- MCP-compatible tool boundary where it adds a real integration boundary
- Google SSO
- Codex as the preferred reasoning target, subject to verified deployment/authentication support
- SSE
- Docker Compose
- pytest / frontend tests / GitHub Actions

These are planned components, not implementation claims.

## MVP boundary

The project supports discovery and analysis. It does **not** submit bids, sign certificates, make payments, create contractual commitments, or claim to make an official legal eligibility determination.

## Documentation

Read in this order:

1. `AGENTS.md`
2. `AI_CONTEXT.md`
3. `CURRENT_STATE.md`
4. `docs/00-project-context.md`
5. `docs/01-requirements.md`
6. `docs/02-architecture.md`
7. `docs/03-test-plan.md`
8. `docs/04-operation-and-deployment.md`
9. `docs/05-coding-standards.md`
10. `docs/06-source-layout.md`
11. `TASKS.md`

## License

Project-authored source code and documentation are licensed under Apache License 2.0. Public procurement data, notices, RFPs, attachments, trademarks and other third-party content retain their original terms and rights. See `LICENSE` and `NOTICE`.
