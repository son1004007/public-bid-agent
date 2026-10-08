# Codex 초기 설계 리뷰 13건 - 설계 변경 대응표

- 최초 독립 리뷰 대상: `49f556c2dbeed4ba4faaa793cbd337ff5bfcc379`
- 1차 Codex 원문: [2026-10-08-codex-raw.md](2026-10-08-codex-raw.md)
- 독립 수정본 재검수 대상: `dd7150609817954ea54178c6a2e3c79ad6f1def8`
- 상태 의미: **설계 반영**은 문서에 계약/게이트를 추가했다는 뜻이며, **독립 승인이나 실제 구현·테스트 PASS를 뜻하지 않는다**.

| ID | 초기 판정 | 실제 수정한 설계 | 재검수 전 상태 |
|---|---|---|---|
| DSR-001 | MAJOR | [01 요구사항](../01-requirements.md), [현재 상태](../../CURRENT_STATE.md): READY 제거·HOLD, 구현 단계 분리 | 수정, 재검수 필요 |
| DSR-002 | MAJOR | [ADR-001](../adr/ADR-001-auth-session-ownership.md): OIDC state/nonce/PKCE, token 검증, 쿠키·CSRF·로그아웃 | 수정, 구현 테스트 필요 |
| DSR-003 | MAJOR | [ADR-001](../adr/ADR-001-auth-session-ownership.md): profile/run/question/evidence/SSE 소유권 표 및 취소·재연결 | 수정, 구현 테스트 필요 |
| DSR-004 | MAJOR | [ADR-002](../adr/ADR-002-procurement-data-lifecycle.md): raw/normalized, 정정·취소, stale, 마감 시각·partial 처리 | 수정, 실제 API 필드 확인 필요 |
| DSR-005 | MAJOR | [ADR-006](../adr/ADR-006-document-ingestion-security.md): 허용 출처, DNS/IP/redirect, 파일 상한·격리 PDF parser | 수정, 보안 테스트 필요 |
| DSR-006 | MAJOR | [ADR-003](../adr/ADR-003-evidence-retrieval.md): SourceDocumentVersion→Passage→Claim/EvidenceLink 불변 참조 | 수정, 데이터·품질 테스트 필요 |
| DSR-007 | MAJOR | [ADR-007](../adr/ADR-007-analysis-state-evaluation.md): 상태 전이·예산·취소·resume·tool allowlist | 수정, 실행 테스트 필요 |
| DSR-008 | MAJOR | [ADR-004](../adr/ADR-004-llm-auth-cost.md): 공개 원격 추론 제한, ChatGPT 플랜 지원 조건, disabled/fake/approved 분리 | 수정, 외부 승인 여부 미확인 |
| DSR-009 | MAJOR | [ADR-007](../adr/ADR-007-analysis-state-evaluation.md): mandatory UNKNOWN의 SUITABLE 금지, 기술·참가자격 분리 | 수정, 판정 테스트 필요 |
| DSR-010 | MAJOR | [ADR-003](../adr/ADR-003-evidence-retrieval.md), [ADR-007](../adr/ADR-007-analysis-state-evaluation.md), [03 테스트](../03-test-plan.md): 평가셋/릴리스 안전조건 | 수정, 실제 baseline 미측정 |
| DSR-011 | MAJOR | [ADR-008](../adr/ADR-008-profile-privacy.md): 비민감 프로필, 전송 allowlist, 보존/삭제/백업 회전 | 수정, 운영 검증 필요 |
| DSR-012 | MINOR | [ADR-005](../adr/ADR-005-hosting-operations.md): authoritative/rebuildable 데이터 분류와 RPO/RTO 가정·복구 전략 | 수정, 복구 테스트 필요 |
| DSR-013 | MINOR | [01 요구사항](../01-requirements.md), [02 아키텍처](../02-architecture.md): 작은 vertical slice와 기술 단계적 도입 | 수정, 실제 구현 전 |

## 남은 승인의 의미

1. 독립 Codex가 최신 설계의 **실제 신규/잔여 결함**을 검사한다.
2. 검증 가능한 누락은 문서를 고치고 새로운 커밋에서 재검토한다.
3. 공식 외부 API 필드, 배포 환경, 사용자별 모델 연동 참여 승인, 모델 정확도는 문서 작성만으로 확정할 수 없다. 해당 단계에서 E2E가 필요하다.
4. 실제 서비스 구현 후의 독립 최종 리뷰와 출시 보안 검증은 별도 단계다.
