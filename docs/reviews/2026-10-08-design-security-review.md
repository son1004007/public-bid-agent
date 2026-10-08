# 2026-10-08 독립 설계/보안 리뷰 기록

## 대상

- docs/00-project-context.md
- docs/01-requirements.md
- docs/02-architecture.md
- docs/03-test-plan.md
- docs/04-operation-and-deployment.md
- docs/05-coding-standards.md
- docs/06-source-layout.md
- AGENTS.md

## 요구되는 reviewer

개인 개발 정책 `REVIEW_POLICY.md`와 `ai-assisted-development.md`에 따라 MEDIUM/HIGH 개인 프로젝트는 구현 agent와 독립된 semantic reviewer의 설계 리뷰가 필요하다.

## 실행 상태 (2026-10-08 갱신)

**독립 설계 리뷰 실행 완료 / 설계 승인 `HOLD`**

최초 기록 시점에는 ChatGPT에서 독립 reviewer 연결을 확인하지 못해 `BLOCKED`였으나, 이후 기존 SynologyNAS의 Desktop Commander 연결을 복구하고 `agy`의 Gemini 3.1 Pro와 NAS의 Codex CLI로 각각 독립 리뷰를 실행했다.

- 대상 커밋: `49f556c2dbeed4ba4faaa793cbd337ff5bfcc379`
- [Gemini 원문 및 실행 식별자](2026-10-08-agy-gemini-raw.md)
- [Codex 원문 및 실행 식별자](2026-10-08-codex-raw.md)
- [주요 지적사항 조정 및 후속 작업](2026-10-08-review-reconciliation.md)

리뷰 실행 여부와 설계 승인 여부는 다르다. 주요 `MAJOR` 후보가 미해결이므로 구현 승인 상태는 `HOLD`다.

## 구현 agent의 사전 보안 점검 - 독립 리뷰가 아님

다음은 reviewer finding이 아니라 독립 리뷰 전 입력 품질을 높이기 위한 사전 점검이다.

### PRE-01 외부 문서 SSRF 경계

사전 점검에서 원칙 수준으로 반영되었다고 보았으나, 독립 리뷰에서는 상세 계약 보완이 요구됐다.

- 공식 source allowlist 우선
- redirect 통제
- URL canonicalization
- 필요 시 DNS/IP destination 검증
- bounded timeout/size/type

근거: OWASP SSRF Prevention Cheat Sheet.

### PRE-02 문서 parser/resource 위험

사전 점검에서 원칙 수준으로 반영되었다고 보았으나, 독립 리뷰에서는 상세 계약 보완이 요구됐다.

파일 형식/크기 제한과 parser resource 제한이 요구된다. 구현 시 PDF/HWP 등 실제 허용 형식을 ADR에서 좁혀야 한다.

### PRE-03 인증과 객체 권한

사전 점검에서 원칙 수준으로 반영되었다고 보았으나, 독립 리뷰에서는 상세 계약 보완이 요구됐다.

Google 로그인 성공과 user-owned object authorization을 분리하고 server-derived identity로 판정한다.

### PRE-04 AI prompt injection

사전 점검에서 원칙 수준으로 반영되었다고 보았으나, 독립 리뷰에서는 상세 계약 보완이 요구됐다.

RFP/공고 내용은 instruction이 아니라 untrusted data다. 모델 출력은 profile 변경, authorization, 실제 입찰 action을 직접 수행할 수 없다.

### PRE-05 Codex 인증/비용 가정

상태: 미확정이지만 fail-closed.

공개 remote hosting에서 사용자별 ChatGPT/Codex 인증을 지원한다고 가정하지 않고 공식 지원 확인 전 비활성화한다.

### PRE-06 embedding provider

상태: 미확정.

Codex reasoning 사용 가능성과 embedding capability를 같은 것으로 가정하지 않는다. ADR-003에서 비용/라이선스/운영조건을 확인해야 한다.

## 현재 다음 게이트

1. [리뷰 조정 기록](2026-10-08-review-reconciliation.md)에 따라 인증, 권한, 공고 버전, 문서 수집, 근거 모델, 실행 예산, 비용/LLM 경로 설계를 보완한다.
2. 독립 리뷰의 원시 심각도를 사실로 확정하지 않고 객관적인 실패 경로와 최신 공식 문서로 검증한다.
3. 설계상 주요 지적사항을 해소하고 승인 기록을 남기기 전에는 substantive 구현을 시작하지 않는다.
4. 구현 후 테스트와 독립 최종 리뷰는 별개로 수행한다.
