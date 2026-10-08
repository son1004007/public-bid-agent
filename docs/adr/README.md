# 아키텍처 결정 기록(ADR)

본 디렉터리는 `public-bid-agent`의 설계 결정을 한글로 설명합니다. **설계 문서가 존재한다는 사실은 코드 구현 또는 보안 테스트 통과를 의미하지 않습니다.**

모든 결정은 Codex 독립 설계 리뷰의 지적사항과 사용자 요구를 반영한 설계안입니다. 실제 공공 API, Google OAuth, LLM 원격 이용조건, 파일 처리·배포 환경이 검증되지 않은 부분은 별도 검증 게이트로 남겨 두었습니다.

| ADR | 주제 | 상태 |
|---|---|---|
| [ADR-001](ADR-001-auth-session-ownership.md) | Google OIDC, 세션, 객체 권한, SSE | 설계 채택 / 구현 전 |
| [ADR-002](ADR-002-procurement-data-lifecycle.md) | 나라장터 공고 식별·정정·취소·마감 | 설계 채택 / 원천 필드 검증 전 |
| [ADR-003](ADR-003-evidence-retrieval.md) | 원문 근거·RAG·임베딩 | 근거 계약 채택 / 공급자 미정 |
| [ADR-004](ADR-004-llm-auth-cost.md) | ChatGPT/Codex 인증·비용·미허용 시 동작 | 조건부 설계 / 원격 연동 미승인 |
| [ADR-005](ADR-005-hosting-operations.md) | 운영·배포·백업·복구 | 원칙 채택 / 대상 미정 |
| [ADR-006](ADR-006-document-ingestion-security.md) | 안전한 첨부파일 수집·PDF 파서 | 설계 채택 / 구현 전 |
| [ADR-007](ADR-007-analysis-state-evaluation.md) | 보수적 적합성 분석·Agent 예산·평가 | 설계 채택 / 수치 검증 전 |
| [ADR-008](ADR-008-profile-privacy.md) | 비민감 프로필·보존·삭제 | 설계 채택 / 운영 검증 전 |

## 검토 문서

- [초기 Codex 검수 원문](../reviews/2026-10-08-codex-raw.md)
- [검수 지적사항 조정](../reviews/2026-10-08-review-reconciliation.md)
- [요구사항](../01-requirements.md), [아키텍처](../02-architecture.md), [테스트 계획](../03-test-plan.md), [운영 계획](../04-operation-and-deployment.md)

## 구현 승인 원칙

실제 원천 데이터와 이용조건이 불명확하면 `UNKNOWN`으로 유지합니다. 독립 리뷰에서 발견된 신뢰 가능한 `BLOCKER` 또는 미해결 `MAJOR`가 있으면 구현 및 공개 배포 범위에 맞게 `HOLD`로 기록합니다. 독립 최종 구현 리뷰는 설계 리뷰와 별도로 수행합니다.
