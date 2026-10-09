# Public Bid Agent 구현 지속 지시서 (2026-10-09)

## 사용자 원문

> 구현진행해줘. 구현할때 애자일 이외 구현방식은 지켜줘.
>
> 내 확인이 필요한건 니가 적절하게 선택해서 판단해. 불안하면 신뢰할수 있는 인터넷 검색자료를 기준으로해.
>
> 지금 프롬프트를 md로 저장해서 다른 채팅이나 ai가 따를수 있게해.

## 목적

새 ChatGPT 대화 또는 다른 AI/Codex가 사용자의 설명을 반복 요구하지 않고 Public Bid Agent 개발을 안전하게 이어받게 한다. 이 문서는 사용자의 실행 지시와 판단 위임 범위를 기록하는 인수인계 문서다. 법률·상위 정책·최신 사용자의 명시 지시를 대신하지 않는다.

## 저장소와 읽기 순서

- 대상: son1004007/public-bid-agent
- 중앙 규칙: son1004007/ai-agent-workflow-playbook/CONTROL.md
- 중앙 등록부: son1004007/ai-agent-workflow-playbook/config/repositories.yml
- 대상 AGENTS.md → AI_CONTEXT.md → CURRENT_STATE.md → TASKS.md → docs/07-agile-development-workflow.md
- 작업 관련 docs/01-requirements.md, docs/02-architecture.md, docs/03-test-plan.md, docs/04-operation-and-deployment.md, docs/05-coding-standards.md와 ADR.
- 개인 공통 규칙: son1004007/personal-engineering-handbook/REVIEW_POLICY.md, OPERATING_MODEL.md, standards/implementation.md, standards/react-fastapi.md, standards/testing.md, standards/security.md, standards/ai-assisted-development.md, standards/code-review.md.
- 최종 커밋/작업 브랜치/PR, 실제 소스코드와 테스트, Actions, Review debt, 실행 증거를 별도로 확인한다. 오래된 상태 문서보다 최근 실행 근거를 우선한다.

## 작업 방법

1. **애자일 구현:** 백로그에서 가장 작은 사용자 가치의 수직 기능을 선택하고 구현 → 테스트 → 독립 검수 → 수정/회귀 테스트 → 상태 기록을 반복한다. 전체 상세 설계/전체 Codex 재검수의 완료를 구현 착수 조건으로 삼지 않는다.
2. **애자일 이외 기존 기준은 유지:** 한글 소스 상단 설계 계약, 입력·출력·실패/상태/권한 계약, 실제 테스트, 공식 문서 확인, dependency/license, 보안, 신뢰경계, 독립 검수 및 배포 게이트를 생략하지 않는다.
3. **사용자 판단 위임:** 가역적이고 안전한 세부 설계/폴더/기술 옵션·합성 테스트·화면 구성은 AI가 스스로 타당한 선택을 하고 구현한다. 사용자의 결정이 반드시 필요한 비용 발생, 법적 약관 수락, 외부 서비스 권한, 개인정보 공개/저장, 운영환경 변경은 승인을 추정하지 말고 해당 기능만 보류한다.
4. **불확실성 처리:** 버전·API 동작·규정·보안 통제를 추측하지 않는다. 신뢰할 수 있는 공식 개발 문서, 패키지 공식 registry, 공개 API 실제 응답, 최소 안전한 read-only 실험을 우선한다. 검증할 수 없다면 UNKNOWN/NOT RUN/BLOCKED를 기록한다.
5. **개발/배포 분리:** 공개 GitHub 저장소에 아직 미완성인 소스코드를 커밋할 수 있다. 다만 작업 중 코드와 운영 릴리스는 다르며, 개인 공통 독립 검수 게이트가 완료/merge/release를 제한하는 경우 작업 브랜치/PR에서 진행한다.
6. **절대 금지:** API 키, OAuth 토큰, 쿠키, 영업비밀/회사 고객 비공개 소스·데이터의 커밋·로그·외부 개인 AGY 전송. 실제 입찰 제출·서명·결제·계약 행위. Google 로그인만으로 ChatGPT 사용자 모델 권한을 가진 것으로 처리.
7. **검수:** 논리적 변경 단위로 기존 REVIEW_POLICY의 독립 검수 의무를 지킨다. 개인 AGY/Gemini 검수 또는 허용된 별도 검수자가 불가능하면 검수 부채를 명시하고 완료/운영 릴리스 판정을 하지 않는다. AI finding은 증거로 calibration하고 무한 재검수를 피한다.
8. **종료 기록:** 코드 커밋, 수행한 테스트와 실행 버전, 실제 GitHub CI 결과, 미구현/미검증, 남은 위험, 다음 작업, 사용자만 할 수 있는 조치를 CURRENT_STATE.md/TASKS.md에 정확히 기록한다. 상태 조작 또는 테스트 통과 허위 주장 금지.

## 추가 사용자 우선순위 (2026-10-09 15시 이후)

> 백엔드 보다 퍼블부터 구현해. 설계가 적합한지 내가 검증하기 위해. 깃헙 다른 레포에 설계 후 퍼블 작업부터 해야 설계 검증을 보다 정확하게 할 수 있다는 내용 추가해줘.

이후 새 채팅/AI는 추가 백엔드 작업보다 `frontend/public/ui-review.html` 시안을 먼저 사용자에게 제시하고 `docs/ui/SCREEN_REVIEW_GUIDE.md`에 따라 피드백을 받는다. 단순 GitHub 파일을 만든 것만으로 화면 설계 승인이 완료되었다고 주장하면 안 된다. 다른 GitHub 저장소의 재사용 작업 기준은 `personal-engineering-handbook` 제안 PR #1이며 독립 검수/승인 전 상태로 유지한다.

## 스프린트 및 다음 실행

- **현재 P0:** 백엔드와 독립적인 화면 퍼블리싱/사용자 설계 검토. `frontend/public/ui-review.html` 및 `docs/ui/SCREEN_REVIEW_GUIDE.md`를 우선한다.
- Sprint 1의 기존 React+TypeScript / FastAPI 합성 공고 목록·검색·상세 UI, 테스트와 CI는 보존하지만 화면 검증 전 추가 백엔드 구현은 후순위다. 합성 공고는 실제 나라장터 데이터가 아니며 접수 및 최신 상태는 UNKNOWN으로 표시.
- 공식 입찰공고 API 연계는 제공 조건, 실제 필드, 인증/키 사용, 정정·취소·첨부 응답 확인 후 별도 작업 단위로 진행. 테스트용 API 키를 커밋하지 않는다.
- Sprint 2: 공공 원문 이용 조건 확인, 공식 출처 PDF 근거 추출 및 위험 격리.
- Sprint 3: 기술 적합도와 공식 행정 참가자격 검증 분리.
- Sprint 4: 공식 승인된 실제 LLM 경로만 활성화. 비용/동의/제공자 검증 전 disabled; LangGraph/RAG/MCP/SSE는 실제 필요성이 입증된 경우.
- Sprint 5: Google OIDC 로그인, 사용자별 격리, 삭제/복구, 공개 운영 게이트.
- 현재 코드와 CI가 완성되지 않은 상태라면 실제 상태를 먼저 확인하고 미완료 부분부터 구현·검증한다. 다음 채팅에서는 사용자가 같은 설명을 되풀이하지 않도록 저장소를 먼저 읽고 실행한다.
