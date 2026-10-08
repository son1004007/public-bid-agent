# 01 요구사항 및 검수 계약

## 현재 상태와 적용 우선순위

- 현재: **설계 수정 진행 중 / 구현 승인 보류(HOLD)**. 문서만 작성되었으며 코드·실서비스·평가를 검증하지 않았다.
- 우선순위: 법률·계약·데이터 이용조건 > 사용자 최신 요구 > 프로젝트 보안·개발 규칙 > 이 요구사항 > 기술 선호.
- 구현 착수 전 승인: [검수 지적사항 조정](reviews/2026-10-08-review-reconciliation.md) 및 [ADR 결정](adr/)에 따라 실질적인 MAJOR 설계 위험을 해소해야 한다.
- 실제 공공 API 필드·LLM 원격 호스팅 허용 여부·공개 배포 환경은 외부 검증 전 사실로 확정하지 않는다.

## 제품 목표와 단계

- **목표 서비스**: 실제 공개 AI/SW 공공 입찰공고를 탐색하고, 기업의 확인된 기술·참가요건과 비교하여 **공식 원문 근거가 있는 AI 보조 분석**을 제공한다.
- **PoC 0 (제한적, 공개 서비스 아님)**: 사용 권한이 확인된 실제 공고 표본/합성 fixture로 공고 원문→요건→근거 연결→규칙 기반 검토의 관통 흐름을 검증한다. 모델 fake 결과를 실제 AI 추론이라고 표시하지 않는다.
- **MVP 1 (공개 검색·검토)**: 승인된 공개 API 조회·검색·원문 링크·비민감 프로필·판정 상태·근거 검토 기능 제공. LLM 경로가 허용되지 않으면 AI 분석을 명시적으로 비활성화한다.
- **목표 MVP 2 (AI 서비스)**: 공식적으로 허용되는 모델 인증/비용 방식 확보 후 AI 요건 추출·의미 관련성·적합성 분석을 서비스한다. 실제 추론/평가/비용/보안 E2E 전에는 AI 서비스 완료를 선언하지 않는다.
- 초기에는 PDF 하나와 공고 API 하나로 제한한다. pgVector, MCP, SSE, LangGraph는 요구/효과가 검증될 때 순차 적용한다.

## 기능 요구사항

### REQ-AUTH-001 Google 로그인 및 세션

Google OIDC Authorization Code Flow의 서버 인증, 신원 검증, 세션 생성/폐기를 제공한다. 설계 계약은 [ADR-001](adr/ADR-001-auth-session-ownership.md).

검수:
- state/nonce/PKCE, redirect URI, ID Token 서명·issuer·audience·만료 검증 실패 시 로그인 거절
- opaque server-side session, HttpOnly/Secure/SameSite/CSRF/Origin 및 로그아웃·만료·회전 동작 확인
- 클라이언트가 제공한 ID, email, role을 권한 근거로 사용하지 않음

### REQ-PROFILE-001 비민감 기업/기술 프로필

이용자는 기술·참가요건 비교에 필요한 최소 비민감 필드를 관리한다. [ADR-008](adr/ADR-008-profile-privacy.md).

검수:
- 사용자 소유권을 server-derived actor로 판정
- 알 수 없는 정보는 UNKNOWN; 미입력을 부적합으로 단정하지 않음
- 개인정보 최소수집·정정·삭제·계정 탈퇴와 데이터 파기 검증

### REQ-SEC-OWNER-001 사용자별 리소스 권한

분석·질문·근거·SSE·취소 등 각 리소스 접근/변경 권한을 [ADR-001 권한 행렬](adr/ADR-001-auth-session-ownership.md)에 따라 검사한다.

검수:
- 타 사용자 run_id, analysis_id, question_id 사용한 조회·수정·재개·취소·SSE를 거부
- 소유권은 ID 난수성이나 단순 로그인 여부와 독립적으로 검증

### REQ-BID-001 공식 공고 탐색·정규화

실제 조달청 공식 API 응답을 검증한 뒤 내부 공고 모델에 변환한다. [ADR-002](adr/ADR-002-procurement-data-lifecycle.md).

검수:
- 원천 ID와 원문 스냅샷·해시·관측시각·파서 버전 보존
- 개정·정정·취소·마감 및 분석 결과 stale 처리
- 시간대 불명확 시 마감/지원 가능성 확정 금지
- 진짜 0건과 API 실패·partial page·schema drift·rate limit 구분
- 실제 API 필드는 contract fixture로 확인 전 구현 확정 금지

### REQ-BID-002 AI/SW 공고 관련성

AI 및 SW 관련 공고 후보를 분류하고 포함 근거를 기록한다.

검수:
- 정규 규칙/키워드 baseline 유지
- AI 분류는 허용 모델·실제 평가 완료 후 활성화
- 적합/부적합 예시와 false positive/negative 사례를 버전된 평가셋으로 구분

### REQ-DOC-001 제한된 원문·RFP 수집

초기 MVP는 검증된 출처의 PDF만 제한적으로 파싱한다. [ADR-006](adr/ADR-006-document-ingestion-security.md).

검수:
- 서버가 조회한 허용 첨부 식별자만 사용, 임의 URL fetch 금지
- 허용 scheme/host/port/IP, DNS/rebinding/redirect/proxy/TLS 경계 검증
- timeout, streaming byte/문서 수/타입/페이지·파서 리소스 상한 테스트
- 격리 파서의 오류/과다 입력을 전체 서비스 장애로 전파하지 않음
- 미지원 포맷/불명확한 이용조건은 수집 거부하고 명시적 제한 노출

### REQ-EVIDENCE-001 원문과 판단 추적

결론마다 원문 버전과 위치, 출처, 증명 상태를 연결한다. [ADR-003](adr/ADR-003-evidence-retrieval.md).

검수:
- SourceDocumentVersion → ParsedArtifact → Passage → Requirement → Claim → EvidenceLink 추적
- LLM이 가짜 근거 ID를 생성해도 서버가 거부
- 원문 개정/파서 변경 후에도 과거 결과의 근거 버전은 불변
- 미검색/근거 없음은 충족 사실로 치환하지 않음

### REQ-RAG-001 근거 검색과 평가

단순 검색 baseline을 먼저 측정한다. 벡터 검색은 필요한 경우 도입한다.

검수:
- 공개 출처·원문 버전이 기록된 작은 평가 표본으로 검색 결과 검증
- 임베딩 공급자·차원·라이선스·비용·데이터 전송은 승인된 [ADR-003](adr/ADR-003-evidence-retrieval.md) 결정 뒤 추가
- 평가 전 정확도/재현율 성과를 주장하지 않음

### REQ-AGENT-001 보수적인 적합성 분석

최종 판단은 `SUITABLE`, `NEEDS_REVIEW`, `UNSUITABLE`로 한정하되 참가자격과 기술 적합성을 따로 보여준다. [ADR-007](adr/ADR-007-analysis-state-evaluation.md).

검수:
- 필수요건 UNKNOWN이면 SUITABLE 금지, 실제 상충이 확인되면 UNSUITABLE
- 사용자 입력 부족은 CONFLICT가 아닌 UNKNOWN
- 공식 법적 자격 보장이 아니며 모든 핵심 결론에는 유효 근거 또는 근거 없음 표시
- 사용자 프로필을 모델 출력으로 수정하거나 실제 입찰 행위 실행 금지

### REQ-AGENT-002 제한된 작업 흐름

공고 검색, 공식 근거 획득, 참가요건 추출, 프로필 비교, 후속 질문, 결과 생성을 명시적 상태로 처리한다.

검수:
- [ADR-007](adr/ADR-007-analysis-state-evaluation.md)의 도구 allowlist, 호출/토큰/시간/상태전이 예산, retry, cancel, resume, idempotency 적용
- 프롬프트 주입으로 도구 정책/권한/예산이 변경되지 않음
- tool 실패를 정상 결과 0건으로 위장하지 않음

### REQ-STREAM-001 사용자별 진행상황

SSE는 필요한 경우 도입하며 초기 MVP는 polling 대체가 가능하다.

검수:
- 이벤트 계약·재연결·오래된 cursor·실행 취소 계약 명시
- 동일 출처 쿠키 세션과 분석 실행 소유권을 연결/재연결 시 검사
- URL에 bearer token, 세션 키 또는 모델 인증정보를 넣지 않음

### REQ-LLM-001 교체 가능한 AI 경계

Agent는 provider 자격증명을 도메인에 결합하지 않으며 `fake / disabled / approved` 실행 모드를 제공한다.

검수:
- 테스트용 deterministic fake, 무권한 실행 실패, 브라우저 비밀키 비노출
- 개인정보·회사정보 외부 전송 전 승인된 필드만 allowlist
- 모델 장애·사용 한도 초과·접근 철회 시 사용자에게 정확한 상태 전달

### REQ-LLM-002 ChatGPT/Codex 기반 실제 AI 서비스 희망

사용자별 ChatGPT 플랜 활용을 우선 검토하되 공개 원격 호스팅 서비스에 적용 가능하다는 공식 승인/지원 확인 전에는 비활성화한다. [ADR-004](adr/ADR-004-llm-auth-cost.md).

검수:
- 사용자 API key/개인 세션을 무단 수집·공유하지 않음
- 오픈소스 로컬 실행과 공개 원격 서비스의 적용 조건 구분
- 실제 인증/동의/사용 한도/철회 E2E 후에만 AI 기능 표시

## 비기능·운영 요구사항

- REQ-SEC-001: secret은 서버 전용. 로그·브라우저·저장소에 전파 금지.
- REQ-SEC-002: 공고/RFP와 LLM 출력은 외부 데이터이며 권한·시스템 프롬프트·도구 정의 변경 불가.
- REQ-PRIV-001: 비민감 최소 프로필, 삭제/보존/외부 전송 고지는 [ADR-008](adr/ADR-008-profile-privacy.md)을 따른다.
- REQ-TRACE-001: 결과에서 공식 원문 버전과 claim-evidence 관계 추적.
- REQ-EVAL-001: 출처·버전·어노테이션 기준·실제 측정값을 분리한 평가 자료.
- REQ-OPS-001: 공개 배포 전 권한/로그/백업/복구/호출 제한 검증. [ADR-005](adr/ADR-005-hosting-operations.md).
- REQ-LIC-001: 작성 코드·문서는 Apache-2.0, 제3자 공고/첨부는 별도 조건 유지.
- REQ-COST-001: 별도 종량제 LLM API 과금을 MVP 필수조건으로 만들지 않음.

## MVP 제외

실제 입찰 제출, 전자 서명, 결제, 계약, 공식 법적 자격 확정, 회사 자격 자동 변경, 회사·고객 비공개 자료의 수집·외부 전송, 성능 입증 없는 Kubernetes/MSA/과도한 기술 도입.

## 구현 승인 전 확인

[검수 조정](reviews/2026-10-08-review-reconciliation.md)에서 실질적 MAJOR를 해소하고, 실제 API 표본과 LLM 공개 연동 제한에 대한 검증 또는 명확한 기능 비활성 경로를 확보해야 한다. 문서 변경만으로 테스트/인증/법률 준수 완료를 선언하지 않는다.
