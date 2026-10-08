# 03 Test Plan

## Status

Planning baseline. No tests have run yet.

## Test principles

Tests trace to requirement IDs where practical. Separate deterministic backend correctness from model-quality evaluation.

## Unit

- notice normalization and deduplication
- active/expired date handling
- profile comparison primitives
- evidence reference construction
- state transition decisions
- unsupported/malformed external payload handling

## Auth/security

- protected API without session -> rejected
- forged client user ID -> ignored/rejected
- cross-user profile/analysis access -> rejected
- cross-user SSE subscription -> rejected
- secret values absent from frontend/config output/log fixtures
- malicious retrieved text cannot alter authorization/tool policy

## External API contract

With recorded/synthetic fixtures:
- success
- empty response
- rate limit
- timeout
- malformed payload
- upstream 4xx/5xx
- duplicate/changed notice

Live API smoke tests are separate and require configured service credentials.

## Document ingestion

- disallowed host
- redirect boundary
- unsupported MIME
- oversized file
- timeout
- duplicate hash
- parser failure
- prompt-injection text retained as data, not instructions

## Agent workflow

Use deterministic fake LLM responses for state-machine tests:
- suitable
- unsuitable
- missing profile fact -> follow-up
- upstream tool failure
- retrieval returns no evidence
- bounded retry exhausted
- resume after user input

## Retrieval evaluation

Maintain a small labeled public-data evaluation set:
- query
- expected document/passage
- top-k retrieval result
- hit-rate/recall-oriented metric

Do not publish a retrieval-quality claim before running the evaluation.

## Model evaluation

Maintain a labeled set for:
- AI/software relevance
- requirement extraction
- fit classification

Compare at least against a deterministic baseline where meaningful.

## E2E

Before public-demo claim:
- Google sign-in
- profile save/read isolation
- real public notice search
- one complete evidence-backed analysis
- SSE isolation
- source-link rendering
- logout/session expiry
- restart/persistence behavior

## Evidence recording

Every verification report uses:
- commit SHA
- exact command or runtime probe
- date
- PASS / FAIL / NOT RUN / BLOCKED
- scope and known limitation
