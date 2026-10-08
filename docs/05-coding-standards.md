# 05 React·TypeScript·FastAPI 코드 작성 표준

## 적용 범위와 기준

이 문서는 React/TypeScript 웹 화면과 Python/FastAPI 백엔드의 **설계 및 구현 예정 기준**이다. 구현·정적검사·테스트를 실행했다고 주장하지 않는다.

- 전역 공통 규칙: `personal-engineering-handbook/standards/implementation.md`, `standards/react-fastapi.md`, `standards/security.md`, `standards/testing.md`, `standards/ai-assisted-development.md`
- React 공식 문서: https://react.dev/reference/rules 및 https://react.dev/learn/synchronizing-with-effects
- TypeScript 공식 strict: https://www.typescriptlang.org/tsconfig/strict
- FastAPI 공식 문서: https://fastapi.tiangolo.com/tutorial/bigger-applications/ , https://fastapi.tiangolo.com/tutorial/dependencies/ , https://fastapi.tiangolo.com/async/ , https://fastapi.tiangolo.com/tutorial/security/
- Python 공식 타입 표준: https://docs.python.org/3/library/typing.html
- OWASP 입력 검증: https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html
- OWASP SSRF: https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html
- OWASP 외부 파일: https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html

다음 규칙 중 파일 상단 한글 설계 계약, 프로젝트 계층 구조, 특정 라이브러리의 선택은 **프로젝트 결정 사항**이지 공식 프레임워크의 강제 규칙이 아니다. 버전/보안 위험에 따라 설계를 바꾸면 ADR로 근거를 남긴다.

## 1. 공통 코드 규칙

### CS-COMMON-001 구현 전 파일 상단 설계 계약

업무 규칙, 인증·인가, DB 저장, 외부 API, AI/RAG/Agent, 배포·보안 등의 의미 있는 소스 파일은 **파일의 상단에 한글 설계 계약을 구현 전에 작성**한다.

포함 항목: 목적·책임, 입력·출력, 신뢰 경계·권한, 상태 변경·부작용, 오류·시간 제한·재시도, 핵심 불변조건, 관련 요구사항/테스트/설계. 구현·테스트·계약이 바뀌면 같은 변경에서 모두 수정한다. 단순 자료형, 자동 생성 파일, 사소한 재노출 파일은 생략할 수 있다.

### CS-COMMON-002 의존 방향

도메인과 응용 규칙을 React/HTTP transport, Google 원시 OAuth 응답, 나라장터 원시 API 응답, 특정 LangChain/LangGraph 모델, DB driver 객체에 결합하지 않는다. 외부 기술은 adapter 경계에서 명시적 내부 모델로 변환한다.

### CS-COMMON-003 명시적 계약

입력 허용 범위·반환/오류 의미·서버 소유권·상태 전이·side effect·시간 제한·재시도를 타입/스키마/테스트에서 검증 가능하도록 표현한다.

### CS-COMMON-004 필요 이상의 인프라 도입 금지

성능이나 요구사항 근거 없이 Redis, Kafka, Kubernetes, Celery, 별도 vector 서비스, MSA, 복잡한 DI 컨테이너를 도입하지 않는다.

### CS-COMMON-005 사실·추출·AI 해석 분리

공식 원문 사실, 파싱으로 추출한 사실, 사용자 입력, AI 해석, 확인 불가능 정보를 명시적으로 구별한다. 사용자 결정에 영향을 주는 상태는 단일 자유 텍스트로 합치지 않는다.

### CS-COMMON-006 독립 검수와 완료 증거

설계/구현 변경은 프로젝트 독립 리뷰 규칙을 따르며, 완료 주장은 실제 정적검사·테스트·실행 결과로만 뒷받침한다. 사용자·외부 데이터는 민감도에 맞는 권한과 전송 정책을 따른다.

## 2. Python 및 FastAPI

### PY-001 기본 규약

- Python 3.12 이상을 초기 목표로 하고 사용 라이브러리 호환성을 확인한 뒤 고정한다.
- 공개 API, 응용 서비스, 도메인 경계에 type hint를 사용한다.
- 요청/응답, 설정, 외부 API 입력 검증에는 Pydantic 모델을 사용한다.
- 내부 안정적 계약이 있는 데이터를 `dict[str, Any]`로 무분별하게 전달하지 않는다.

### PY-002 패키지 책임

```text
backend/app/
  api/              FastAPI router 및 요청/응답 스키마
  application/      유스케이스 및 트랜잭션
  domain/           공고/근거/판정/상태 불변조건
  infrastructure/
    auth/           Google 및 세션 연계
    procurement/    나라장터 데이터 어댑터
    documents/      허용 출처 수집 및 격리 파서
    persistence/    SQLAlchemy/PostgreSQL 연계
    llm/            조건부 AI 공급자
    retrieval/      검색/선택적 임베딩
  agent/            필요 시 명시적 분석 작업 상태
  core/             설정/오류/로그 공통 구성
```

실제로 역할 없는 추상 계층이 생기면 더 단순하게 합치고 사유를 기록한다.

### PY-003 FastAPI route

요청 입력 검증, 서버 세션의 actor 확인, 응용 유스케이스 호출, 알려진 오류의 HTTP 계약 변환, 응답 스키마 반환만 수행하도록 유지한다. 공고 파싱, AI prompt 생성, DB transaction 관리, 객체 권한 판정을 route 내부에 숨기지 않는다.

### PY-004 비동기 및 블로킹 작업

실제 비동기 HTTP/DB 라이브러리 사용 시에만 `async`를 선택한다. 블로킹 파일/네트워크/CPU 파싱을 event loop에 넣지 않는다. PDF 같은 복잡한 외부 문서는 제한된 별도 실행 경계에서 처리한다.

### PY-005 오류·비밀정보

예상 가능한 실패는 도메인/응용 오류 형식으로 표시하고 API 경계에서 일관된 상태·오류 코드로 변환한다. traceback, SQL 오류 원문, OAuth 응답, API key, 모델 토큰, 개인정보를 외부 응답/로그에 노출하지 않는다.

### PY-006 DB와 거래 경계

- SQLAlchemy 2.x 스타일은 초기 선택이며 실제 라이브러리 버전은 구현 시 확인한다.
- 트랜잭션과 idempotency는 응용 유스케이스에서 관리한다.
- 사용자별 DB 조회/변경은 `(actor_id, resource_id)` 소유권 검증을 포함한다.
- 공고 revision, 원문 hash, 근거 link의 영속 불변조건은 적절한 DB constraint로 보호한다.
- schema migration의 롤백/전진 복구, 기존 앱과의 호환성을 고려한다.

### PY-007 외부 API 및 파일 수집

원천 응답 스키마 검증, 제한된 연결/읽기/전체 timeout, 재시도 가능/불가 오류 분리, 공고 ID/원문 출처/수집 버전 유지를 적용한다. 임의 URL 수집을 금지하고 [ADR-006](adr/ADR-006-document-ingestion-security.md)의 allowlist·DNS/IP·redirect·파일/파서 제한을 따른다.

### PY-008 Agent 및 LLM

작업 상태는 명시적 타입과 종료 상태를 갖는다. 각 node는 가능한 한 한 가지 책임을 갖고, 입력·출력·상태 변경·취소·재시도·사용 예산을 지킨다. 도구와 모델 출력은 비신뢰 데이터이므로 판정·근거 ID/권한 반영 전에 반드시 검증한다. 결정적 규칙은 프롬프트 대신 코드에 배치한다.

## 3. React 및 TypeScript

### TS-001 타입 엄격성

TypeScript의 `strict` 설정을 기본값으로 한다. 임의 `any` 사용을 제한하고, 외부 입력은 `unknown`에서 스키마 검증·타입 축소 후 사용한다. 컴포넌트 props와 API 계약은 타입으로 표현한다.

### TS-002 화면 책임

```text
frontend/src/
  app/         앱 시작/라우팅/공통 공급자
  pages/       페이지 수준 조합
  features/    사용자 기능별 화면
  components/  재사용 가능 UI
  api/         타입 지정된 backend client
  auth/        로그인/세션 UX
  hooks/       실제로 재사용되는 hook
  lib/         작은 순수 유틸리티
```

백엔드의 디렉터리를 기계적으로 복제하지 않으며 필요하지 않은 전역 상태 계층은 만들지 않는다.

### TS-003 서버 권한 우선

브라우저는 신원·권한·입찰 적합성·원문 근거·데이터 소유권의 최종 결정자가 아니다. 숨겨진 버튼/비활성 UI/임의 query parameter는 보안 제어가 아니며 서버가 매 요청에서 권한을 검증한다.

### TS-004 React state

컴포넌트 내부 관심사는 지역 상태에 둔다. 여러 컴포넌트 간 실제 공유가 필요한 경우에만 공유 상태를 도입한다. 서버 데이터는 중복된 독립 저장소에 복제하지 않는다. render는 순수해야 하며 props/state를 직접 변조하지 않는다.

### TS-005 Effect와 자원 정리

Effect는 외부 시스템 동기화에 사용하며 렌더링 중 계산 가능한 값을 파생시키기 위해 남용하지 않는다. 구독/SSE/timer 등의 정리를 구현하고 재연결·로그아웃 시 권한 변화를 반영한다. Hook 호출 규칙을 지킨다.

### TS-006 화면 상태

모든 비동기 조회 화면에서 loading, empty, retryable error, unauthorized/session-expired, success 상태를 구별한다. 분석 기능이 있으면 작업 대기/취소/정보 부족/재연결/실패를 분명히 표시한다. `UNKNOWN`과 `NEEDS_REVIEW`를 숨기지 않는다.

### TS-007 원문 근거 표시

공식 공고 원문, 사용자 프로필 정보, AI가 추론한 내용, 확인되지 않은 내용을 시각·문구로 구분한다. 중요한 판단을 클릭해 가능한 범위의 공식 원문/문서 버전과 연결할 수 있도록 한다. 실제 입찰 자격 확정인 것처럼 표현하지 않는다.

## 4. 포맷·정적 검사 계획

현재는 명령어를 실행하지 않았다. 도구 설치 후 실제 경로와 버전에 맞춰 확정한다.

백엔드 예정:
```text
ruff check .
ruff format --check .
mypy backend/app
pytest
```

프런트엔드 예정:
```text
eslint
TypeScript typecheck
frontend tests
production build
```

## 5. 주석과 변경 완료

- 파일 상단에는 간결한 한글 설계 계약을 작성한다.
- 함수/클래스 주석은 코드 자체로 드러나지 않는 업무·보안·실패 조건을 설명한다.
- 단순 코드 내용을 줄마다 반복 설명하지 않는다.
- 실제로 검증하지 않은 성능·보안 보장을 주석에 작성하지 않는다.
- TODO에는 사유와 제거 조건을 기록한다.
- 요구사항과 코드 계약·테스트·독립 검수 결과가 일치하고 필요한 정적검사/테스트를 **실제 실행한 후**에만 완료라고 표시한다.

## 6. 비신뢰 문자열의 React 렌더링 규칙 — R3-004

- RFP/공고에서 추출한 문구, 모델 생성 결과, 사용자 프로필 문자열은 **기본적으로 JSX text node**로 렌더링한다. `dangerouslySetInnerHTML`, 임의 HTML 해석 또는 사용자 제공 Markdown의 raw HTML 활성화는 금지한다.
- 초기 MVP에서는 원문/모델 출력의 Markdown HTML 렌더링을 지원하지 않는다. 추후 도입한다면 명시적인 HTML/URL allowlist, 검증된 sanitizer, escape 테스트, 보안 리뷰를 통과해야 한다.
- 링크는 서버에서 허용된 `canonical_source_url`만 클릭 가능한 값으로 사용한다. 브라우저에서도 `https:`/공식 호스트를 검사하여 `javascript:`, `data:`, HTML 이벤트 핸들러, 임의 open redirect를 활성화하지 않는다.
- 외부 출처 링크는 `rel="noopener noreferrer"` 및 안전한 `target` 정책을 사용한다. CSP는 `default-src 'self'`, 제한된 `script-src`, `object-src 'none'`, `base-uri 'self'` 등을 공개 호스팅 환경에 맞게 검증하고 unsafe inline 실행을 허용하지 않는다.
- 브라우저 E2E에서 합성 PDF/모델 출력의 `<script>`, SVG/event attribute, malformed Markdown 및 위험 스킴을 주입하여 DOM 스크립트·임의 navigation·인증된 요청이 실행되지 않는지 확인한다.
