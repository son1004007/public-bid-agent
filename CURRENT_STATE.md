# Current State

- Date: 2026-10-08
- Phase: planning / architecture
- Repository: public
- License: Apache-2.0
- Runtime implementation: NOT STARTED
- Tests: NOT STARTED
- Deployment: NOT STARTED
- Independent design review: PENDING

## Confirmed

- Repository exists as `son1004007/public-bid-agent`.
- Project-authored code/documentation use Apache-2.0.
- Public procurement/third-party content is not relicensed by this repository.
- Primary product direction is public AI/software procurement discovery and evidence-backed fit analysis.
- Official G2B bid notice OpenAPI is available from the Korea Public Procurement Service through data.go.kr; it is REST, JSON/XML, free, real-time, and automatically approved for development/operation accounts according to the current portal entry.

## Pending before implementation

1. Independent design/security review required by owner policy.
2. Confirm exact OpenAPI operations/fields needed for service-type notices and attachment access.
3. Confirm Google OAuth production configuration and redirect/origin policy from current official docs.
4. Confirm current OpenAI/Codex user-auth deployment constraints before enabling per-user ChatGPT connection on a remotely hosted public service.
5. Choose initial hosting target only after cost/security/secret-storage constraints are documented.
