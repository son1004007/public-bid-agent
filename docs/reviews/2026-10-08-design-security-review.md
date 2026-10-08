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

## 실행 상태

`BLOCKED`

### 사유

현재 ChatGPT 실행 환경에서 정책에 지정된 AGY/Gemini 독립 reviewer를 호출할 수 있는 tool/connector가 확인되지 않았다.

구현 agent인 현재 ChatGPT가 자신의 설계를 다시 검토한 결과를 독립 리뷰라고 기록하지 않는다.

## 구현 agent의 사전 보안 점검 - 독립 리뷰가 아님

다음은 reviewer finding이 아니라 독립 리뷰 전 입력 품질을 높이기 위한 사전 점검이다.

### PRE-01 외부 문서 SSRF 경계

상태: 설계에 반영됨.

- 공식 source allowlist 우선
- redirect 통제
- URL canonicalization
- 필요 시 DNS/IP destination 검증
- bounded timeout/size/type

근거: OWASP SSRF Prevention Cheat Sheet.

### PRE-02 문서 parser/resource 위험

상태: 설계에 반영됨.

파일 형식/크기 제한과 parser resource 제한이 요구된다. 구현 시 PDF/HWP 등 실제 허용 형식을 ADR에서 좁혀야 한다.

### PRE-03 인증과 객체 권한

상태: 설계에 반영됨.

Google 로그인 성공과 user-owned object authorization을 분리하고 server-derived identity로 판정한다.

### PRE-04 AI prompt injection

상태: 설계에 반영됨.

RFP/공고 내용은 instruction이 아니라 untrusted data다. 모델 출력은 profile 변경, authorization, 실제 입찰 action을 직접 수행할 수 없다.

### PRE-05 Codex 인증/비용 가정

상태: 미확정이지만 fail-closed.

공개 remote hosting에서 사용자별 ChatGPT/Codex 인증을 지원한다고 가정하지 않고 공식 지원 확인 전 비활성화한다.

### PRE-06 embedding provider

상태: 미확정.

Codex reasoning 사용 가능성과 embedding capability를 같은 것으로 가정하지 않는다. ADR-003에서 비용/라이선스/운영조건을 확인해야 한다.

## 다음 gate

독립 reviewer가 연결되면 reviewer에게 구현 agent의 PRE 결론을 정답으로 주입하지 않고 다음을 제공한다.

1. 사용자 요구사항
2. 현재 설계 문서 원문
3. 공통 개발/보안/review 정책
4. 외부 공식 근거
5. 리뷰 기준: correctness, trust boundary, auth/session, SSRF/document parsing, prompt injection, data isolation, privacy, cost/operability, testability

finding은 BLOCKER / MAJOR / MINOR / NIT / QUESTION으로 받고 정책에 따라 reconciliation한다.

독립 설계 리뷰가 PASS 또는 blocking finding 해결 상태가 되기 전에는 substantive 구현을 시작하지 않는다.
