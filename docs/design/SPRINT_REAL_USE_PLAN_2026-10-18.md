# Public Bid Agent - Windows real-use Sprint 1-3 (2026-10-18)

This is the 2026-10-18 real-use delivery track, distinct from the historical synthetic Sprint 1 runbook.
Source of truth: global CONTROL.md, AGENTS.md, DECISIONS.md, CURRENT_STATE.md, TASKS.md, and P00-P11 roadmap.
Scope: Windows localhost 127.0.0.1:8765, existing official notice collection and private local JSON/RFP evidence. Development branch feat/sprint1-search-demo only.
Boundaries: protect all user-original JSON/RFP, human decisions, tokens and company information. No external confidential data transfer, actual bidding/signing, main merge, public internet release, unapproved company-data access. D-10 historical seven-day failure remains deferred.

## Sprint 1 - Official notice and RFP usable review (P04/P05)
User flow: official notice list -> current/cancelled/superseded state -> detail -> RFP evidence -> human review, clearly mark STALE, truncated and unknown.
Use existing code rather than rebuilding it. Validate parser provenance, source notice revision/attachment, legacy evidence and STALE without clearing stale automatically.
Acceptance:
- Current localhost page and JavaScript assets GET 200, and review queue/coverage/recommendations read-only APIs return valid bounded responses.
- Bad identifiers return safe 400/404 without exposing private data.
- Protected JSON/RFP cache and human decisions remain intact; compare SHA before and after testing, report counts only.
- Current Windows Python regression, JS/static frontend checks, actual browser critical path where supported.
- Separate fresh-context read-only Codex GO, commit/push development branch and verified GitHub Actions SUCCESS.
- Distinguish synthetic validation from actual original PDF/HWP page/table/OCR/footnote completeness (NOT VERIFIED).
Sprint 1 gate: code/tests/GO/CI and at least safe real local API and data-integrity verification; otherwise PARTIAL/BLOCKED and do not claim complete.

## Sprint 2 - Evidence-backed decision support (P06/P07)
User flow: show nine-category RFP expression candidate and source identity, department registration/licence/performance/staffing/effort/cost readiness, conservative recommendation reasoning.
Acceptance:
- Qualifications vs evaluation criteria vs task classification, negative and false-positive fixtures, evidence labelled UNKNOWN/CONFLICT/STALE.
- No invented company eligibility or profit; authorized evidence only, rule-based fallback, human Bid/No-Bid remains independent.
- Browser/API integration, regression, data preservation, independent Codex GO, development push and CI success.
- Real private company evidence not authorized => eligibility and profitability NOT VERIFIED.

## Sprint 3 - Human bid history and operations (P08/P09)
User flow: manual human decision -> manual submission/evaluation/award history -> reload -> backup/restore.
Acceptance:
- Atomic/revision-conflict/duplicate-safe state transitions, synthetic failure/recovery tests, never actual submission.
- Windows Chrome desktop/mobile critical flow, service smoke, data hashes, rollback and recoverability.
- Windows Task Scheduler duplicate lock, durable checkpoints, bounded retry, tested restart/login semantics and non-destructive operation.
- Gmail sender verified independently from ChatGPT Gmail; exactly-once terminal state email after actual unit/E2E/review/CI evidence.
- CI, Codex GO, licence/security review, accurate operational docs.

## Closeout
P10 main/public deployment, Google OIDC and multitenancy require explicit user approval. P11 legacy seven-day API investigation deferred by D-10.
Never mark USER_APPROVED, REAL_ORIGINAL_AUDITED, MAIN_MERGED or PUBLIC_RELEASED without specific evidence.
Record independently IMPLEMENTED, TESTED, CODEX_GO, CI_PASS, LOCAL_APPLIED, CHROME_E2E, REAL_ORIGINAL_AUDITED and BLOCKED.
Each Sprint must pass its own gate before the next Sprint can be declared started/completed.