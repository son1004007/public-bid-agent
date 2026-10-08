# 00 Project Context

## Problem

Public procurement portals expose useful bid data, but a developer or software company still has to search notices, open attachments/RFPs, identify AI relevance, read participation restrictions, compare technical requirements, and decide whether the opportunity deserves deeper review.

Public Bid Agent aims to reduce that review cost without pretending to make an official procurement decision.

## Product goal

Given a user's organization/technology profile, find active public AI/software procurement opportunities and return evidence-backed fit analysis.

## MVP user

A software company, independent developer, or technical reviewer evaluating public AI/software opportunities.

## Primary user outcome

The user can answer:

1. Is this notice actually related to AI/software work?
2. Is it still actionable?
3. What are the important participation requirements?
4. What technical capabilities are requested?
5. Which known organization capabilities match or do not match?
6. Which material facts are still unknown?
7. Where in the official source did the conclusion come from?

## Sources

### SRC-001 - owner requirements

Confirmed from project conversation on 2026-10-08:

- public web service
- React frontend
- Google SSO desired
- Codex preferred as the actual reasoning model instead of separately billed OpenAI API usage
- future per-user Codex/ChatGPT connection desired
- service should be publicly accessible for portfolio testing
- use public procurement data
- focus on AI-related public bid opportunities

### SRC-002 - global engineering control

`son1004007/ai-agent-workflow-playbook/CONTROL.md`

### SRC-003 - engineering review policy

`son1004007/personal-engineering-handbook/REVIEW_POLICY.md`

### SRC-004 - G2B bid notice API

Public Data Portal: `조달청_나라장터 입찰공고정보서비스`

Current portal information checked 2026-10-08:

- REST
- JSON/XML
- free
- real-time update
- unrestricted use range shown by the portal
- development/operation approval: automatic
- development traffic: 1,000 calls
- provides bid notice list/detail and related restriction information by procurement work category

Source: https://www.data.go.kr/data/15129394/openapi.do

### SRC-005 - G2B prior specification API

Public Data Portal: `조달청_나라장터 사전규격정보서비스`

It exposes prior specifications by procurement category and includes specification-file information.

Source: https://www.data.go.kr/data/15129437/openapi.do

## Constraints

- Public repository: no employer/client confidential material.
- No actual bid submission in MVP.
- No secrets in repository or client bundle.
- Source data and AI interpretation must remain distinguishable.
- AI analysis must expose uncertainty and source evidence.
- Public remote Codex/ChatGPT-plan authentication is not assumed supported until verified against current official OpenAI documentation.
