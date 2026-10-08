# 04 Operation and Deployment

## Current status

No deployment target has been selected and no runtime has been deployed.

## Configuration classes

Expected server-side configuration:
- Google OAuth client configuration
- public-data API service key
- database URL/credentials
- LLM-provider configuration when enabled
- session/encryption secrets

Actual values must never be committed.

## Public demo gates

Before Internet exposure:
1. production OAuth redirect/origin configuration verified;
2. HTTPS only;
3. secret storage verified;
4. database not directly exposed publicly;
5. authorization/cross-user tests pass;
6. request/rate limits defined;
7. external document retrieval controls pass;
8. logs reviewed for token/PII leakage;
9. dependency/security review completed;
10. independent final review completed.

## Rollback

Deployment design must provide a documented way to return to the previous verified application version. Database migrations must be designed separately before persistent schema changes are introduced.

## Observability

Minimum planned signals:
- request correlation ID;
- analysis run ID;
- upstream API latency/error category;
- agent node duration/status;
- retrieval result metadata;
- bounded LLM usage metadata that does not expose prompts/secrets unnecessarily.

Do not log OAuth tokens, API keys, session secrets or full sensitive user profiles.

## Cost boundary

Hosting and any model/provider usage that creates recurring cost must be explicit. The MVP requirement is to avoid mandatory separately metered LLM API usage; this does not imply unlimited or zero-cost infrastructure.
