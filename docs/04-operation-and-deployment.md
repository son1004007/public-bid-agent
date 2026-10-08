# 04 운영 및 배포 설계

## 현재 상태

hosting target을 아직 선택하지 않았고 runtime 배포도 하지 않았다.

## Server-side 설정

예상 설정:
- Google OAuth/OIDC client 설정
- 공공데이터 service key
- database URL/credential
- 활성화된 경우 LLM provider 설정
- session/encryption secret

실제 값은 Git에 commit하지 않는다.

## 공개 demo 배포 gate

1. production OAuth redirect/origin 검증
2. HTTPS only
3. secret storage 검증
4. DB 직접 public exposure 금지
5. authorization/cross-user test PASS
6. request/rate limit 정의
7. 외부 문서 retrieval 보안 검증
8. log의 token/개인정보 노출 검토
9. dependency/security review
10. 독립 final review

## Rollback

이전 검증 버전으로 되돌릴 수 있는 절차를 문서화한다. DB schema 변경이 시작되면 migration rollback 또는 forward recovery 전략을 별도로 정의한다.

## Observability

최소 계획:
- request correlation id
- analysis run id
- upstream API latency/error category
- agent node duration/status
- retrieval metadata
- secret/prompt를 과다 노출하지 않는 범위의 LLM usage metadata

OAuth token, API key, session secret, 전체 민감 profile을 로그에 기록하지 않는다.

## 비용 경계

hosting과 model/provider의 반복 비용은 명시한다. 별도 종량제 LLM API를 MVP 필수조건으로 만들지 않는다는 요구는 인프라 전체가 무제한 무료라는 뜻이 아니다.
