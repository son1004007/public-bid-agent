# 01 Requirements

## Status

`READY WITH ASSUMPTIONS` for design; `NOT READY` for public production deployment.

## Requirement precedence

```text
latest explicit owner instruction
> applicable law / external service terms
> project security and data rules
> approved owner engineering policy
> this requirement document
> architecture/design preference
```

## MVP functional requirements

### REQ-AUTH-001 - Google sign-in

A user can authenticate with Google and the backend verifies the identity before creating an application session.

Acceptance:
- unauthenticated protected API requests are rejected;
- client-supplied user identifiers are not trusted as identity;
- logout/session expiry behavior is explicit.

### REQ-PROFILE-001 - organization profile

An authenticated user can maintain a profile containing only the information required for bid-fit analysis, such as technology capabilities, organization type, region and known certifications/qualifications.

Acceptance:
- profile ownership is enforced server-side;
- unknown fields may remain unknown;
- absence of information is not converted to a negative fact.

### REQ-BID-001 - official notice discovery

The service retrieves public procurement notices through an official public API adapter and normalizes them into an internal domain model.

Acceptance:
- source identifier and source URL are retained;
- API failure is distinguishable from an empty result;
- duplicate notices are handled deterministically.

### REQ-BID-002 - AI/software relevance

The service identifies likely AI/software opportunities and records why an item was included.

Acceptance:
- deterministic keyword/rule baseline exists;
- LLM classification, if used, is evaluated separately from the baseline;
- false-positive/false-negative evaluation set is maintained.

### REQ-DOC-001 - source document ingestion

The service may retrieve relevant public notice/RFP/specification documents for analysis.

Acceptance:
- retrieval has allowlisted source policy, timeout, redirect, file-size and file-type controls;
- source metadata and original reference are retained;
- retrieved text is treated as untrusted data.

### REQ-RAG-001 - evidence retrieval

Relevant source passages can be retrieved for a specific bid.

Acceptance:
- chunks retain document/page/section/source metadata when available;
- retrieval evaluation is recorded against a small labeled set;
- no claim of quality is made without measured evidence.

### REQ-AGENT-001 - fit analysis workflow

The agent compares source requirements with known user profile facts and produces:
- `SUITABLE`
- `NEEDS_REVIEW`
- `UNSUITABLE`

Acceptance:
- each material conclusion includes evidence or explicitly says evidence is unavailable;
- missing required user facts produce questions or `NEEDS_REVIEW`;
- model output cannot directly mutate the user profile or submit a bid.

### REQ-AGENT-002 - workflow state

The workflow supports search, source retrieval, eligibility extraction, technical-fit comparison, missing-information handling and final synthesis as explicit states/nodes.

Acceptance:
- node transitions are testable;
- retries/timeouts are bounded;
- external-tool failure does not become a fabricated result.

### REQ-STREAM-001 - progress streaming

Long-running analysis exposes bounded progress/result events to the React client.

Acceptance:
- event schema is versioned or explicitly typed;
- reconnect/error behavior is defined;
- one user's events cannot be read by another user.

### REQ-LLM-001 - replaceable LLM boundary

Agent code depends on a project LLM interface rather than a hard-coded API credential mode.

Acceptance:
- provider-specific auth is isolated;
- tests can use deterministic fake/stub inference;
- application startup does not expose provider credentials to the browser.

### REQ-LLM-002 - Codex target

Codex is the preferred reasoning-model target.

Status: `PLANNED / SUPPORT CONSTRAINT PENDING`.

Public remotely hosted per-user ChatGPT/Codex connection must remain disabled until current official OpenAI support and terms for that deployment are verified.

## Non-functional requirements

### REQ-SEC-001

Secrets are server-side only and excluded from Git, logs and frontend bundles.

### REQ-SEC-002

Retrieved documents cannot supply system instructions, authorize tool calls, change access control, or override project policy.

### REQ-SEC-003

All persistent user-owned records are scoped by authenticated server-side identity.

### REQ-TRACE-001

A displayed bid analysis retains enough source metadata to reproduce which public notice/documents supported it.

### REQ-LIC-001

Project-authored code/documentation are Apache-2.0. Third-party/public data retain their original terms and attribution requirements.

### REQ-COST-001

MVP should avoid mandatory separately metered LLM API cost. Any fallback that creates external usage cost requires an explicit design decision before implementation.

## Explicit non-goals for MVP

- actual electronic bid submission
- certificate signing
- payment
- contractual commitment
- automatic legal eligibility determination
- autonomous company registration or qualification changes
- Kubernetes/microservices solely for portfolio breadth
- fine-tuning solely to satisfy a technology checklist
