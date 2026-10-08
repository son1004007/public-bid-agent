# 02 Architecture

## Status

Draft architecture. MEDIUM/HIGH risk due to public exposure, authentication, external content retrieval and AI interpretation. Independent design/security review is required before implementation.

## Context

```text
Browser
  |
  | HTTPS
  v
React + TypeScript
  |
  | authenticated API / SSE
  v
FastAPI
  |
  +-- Auth / user boundary
  +-- Bid application service
  +-- Agent application service
  |
  +--> PostgreSQL
  |      +-- users
  |      +-- organization_profiles
  |      +-- bid metadata
  |      +-- analysis runs
  |      +-- evidence metadata
  |      +-- pgVector embeddings
  |
  +--> LangGraph workflow
  |      +-- search
  |      +-- classify relevance
  |      +-- retrieve source
  |      +-- extract requirements
  |      +-- compare profile
  |      +-- ask for missing facts
  |      +-- synthesize cited result
  |
  +--> Tool boundary / MCP adapter
  |      +-- G2B bid notice API
  |      +-- G2B prior specification API
  |
  +--> LLM provider interface
         +-- deterministic test provider
         +-- Codex adapter (conditional)
```

## Why a modular monolith first

The MVP uses one backend deployment and one database. Separate deployable microservices would increase operational complexity without proving a user requirement.

Internal boundaries remain explicit so procurement adapters, document ingestion and LLM providers can be replaced independently.

## Frontend

React + TypeScript responsibilities:
- authentication UX;
- profile editing;
- bid search/filter;
- analysis progress;
- evidence-backed result rendering;
- source links;
- explicit unknown/needs-review presentation.

The browser never receives public-data API service keys, model credentials or refresh tokens.

## Backend

FastAPI owns:
- authenticated identity;
- authorization/ownership;
- external API orchestration;
- normalization;
- analysis-run lifecycle;
- SSE authorization;
- persistence;
- LLM/tool boundaries.

Async I/O is used where it provides measurable benefit for external API/document calls. It is not a requirement to make all code asynchronous.

## Agent workflow

Initial LangGraph state:

```text
START
 -> normalize_query
 -> search_notices
 -> filter_active
 -> classify_ai_software
 -> select_candidates
 -> fetch_evidence
 -> extract_requirements
 -> compare_profile
 -> [missing material facts?]
       yes -> request_user_input -> compare_profile
       no  -> synthesize_result
 -> END
```

Deterministic code should own:
- authentication/authorization;
- date comparisons;
- numeric thresholds when explicitly parsed;
- source identifiers;
- deduplication;
- file/network safety controls;
- persistence and ownership.

LLM reasoning may assist:
- semantic AI/software relevance;
- requirement extraction from prose;
- capability-to-requirement comparison;
- explanation/synthesis.

## RAG

PostgreSQL + pgVector is the initial retrieval store to avoid a separate vector service.

Each chunk should retain:
- bid identifier;
- source document identifier;
- original source reference;
- page/section when available;
- content hash;
- ingestion timestamp;
- parser/version metadata.

Embedding model/provider is intentionally undecided until implementation planning because Codex reasoning authentication does not automatically establish an embedding capability.

## MCP/tool boundary

MCP is used only if it improves a real tool boundary. The initial conceptual tools are:

- `search_bid_notices`
- `get_bid_notice`
- `get_prior_specification`
- `get_bid_documents`

The backend remains responsible for authorization, network safety and normalized contracts. An MCP server must not become a bypass around those controls.

## Authentication

Application auth:
- Google OAuth/OIDC;
- backend validates identity and creates/validates application session;
- user-owned records use server-derived user identity.

LLM provider auth:
- separate from Google identity;
- optional/conditional;
- tokens, if supported, are server-side encrypted secrets;
- remote-hosting support must be verified before enabling per-user Codex connection.

## Public-data ingestion security

External documents are untrusted.

Required controls before public deployment:
- source-host policy;
- DNS/IP/redirect checks appropriate to chosen fetcher;
- connect/read/total timeouts;
- maximum response/file size;
- supported MIME/file types;
- parser isolation/resource limits where practical;
- content hashing/deduplication;
- no execution of document content;
- prompt-injection boundary in agent prompts and tool policy.

## Deployment shape

Initial target:

```text
Internet
 -> HTTPS reverse proxy / hosting edge
 -> React static assets
 -> FastAPI
 -> PostgreSQL + pgVector
```

Exact provider is `UNKNOWN` and intentionally not selected yet.

## Major ADRs to write during implementation

- ADR-001 session model for Google sign-in
- ADR-002 procurement API/attachment retrieval boundary
- ADR-003 embedding provider
- ADR-004 Codex authentication mode
- ADR-005 public hosting and secret storage
