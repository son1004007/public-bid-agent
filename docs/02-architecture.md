# 02 아키텍처 설계

## 상태

초안. 공개 서비스, 인증, 외부 문서 수집, AI 판단을 포함하므로 MEDIUM/HIGH risk다. 구현 전 독립 설계/보안 리뷰가 필요하다.

## 전체 구조

```text
Browser
  |
  | HTTPS
  v
React + TypeScript
  |
  | 인증 API / SSE
  v
FastAPI
  |
  +-- 인증/사용자 경계
  +-- 입찰 application service
  +-- Agent application service
  |
  +--> PostgreSQL + pgVector
  |
  +--> LangGraph
  |      +-- 검색
  |      +-- AI/SW 관련성 분류
  |      +-- 근거 수집
  |      +-- 요구사항 추출
  |      +-- 프로필 비교
  |      +-- 부족정보 질문
  |      +-- 근거 포함 결과 생성
  |
  +--> 조달 Tool/MCP 경계
  |      +-- 나라장터 입찰공고 API
  |      +-- 나라장터 사전규격 API
  |
  +--> LLM Provider
         +-- 테스트용 deterministic provider
         +-- Codex adapter (공식 지원 확인 후)
```

## 배포 단위

MVP backend는 modular monolith로 시작한다. Microservice 분리는 현재 사용자 요구를 증명하지 못하면서 운영 복잡도만 증가시키므로 적용하지 않는다.

## Frontend 책임

React/TypeScript는 다음을 담당한다.
- 로그인 UX
- 기업/기술 프로필 편집
- 입찰 검색/필터
- 분석 진행상황
- 근거 포함 결과 표시
- 공식 출처 이동
- UNKNOWN/NEEDS_REVIEW 명시

browser에는 조달 API service key, 모델 credential, refresh token을 전달하지 않는다.

## Backend 책임

FastAPI는 다음을 소유한다.
- 인증된 사용자 identity
- authorization/ownership
- 외부 API orchestration
- 내부 모델 normalization
- 분석 실행 lifecycle
- SSE authorization
- persistence
- LLM/tool trust boundary

## Agent workflow

```text
START
 -> 질의 정규화
 -> 공고 검색
 -> 유효기간/상태 필터
 -> AI/SW 관련성 분류
 -> 후보 선정
 -> 공식 근거 수집
 -> 참가/기술 요구사항 추출
 -> 사용자 프로필 비교
 -> [중요 정보 부족?]
      yes -> 사용자 질문 -> 다시 비교
      no  -> 근거 포함 결과 생성
 -> END
```

### deterministic code가 담당할 것

- 인증/인가
- 날짜 비교
- 명시적으로 파싱 가능한 수치 조건
- source id
- 중복 제거
- 외부 파일/network 보안
- persistence/ownership

### LLM이 보조할 수 있는 것

- AI/SW 의미 관련성
- 자연어 요구조건 추출
- 역량과 요구조건 의미 비교
- 사용자 설명 생성

## RAG

초기 retrieval store는 PostgreSQL + pgVector다.

chunk metadata:
- bid id
- source document id
- 원 출처
- 가능한 경우 page/section
- content hash
- ingestion timestamp
- parser/version

Embedding provider는 아직 결정하지 않는다. Codex 추론 인증이 embedding 기능까지 제공한다고 가정하지 않는다.

## Tool/MCP 경계

MCP는 실제 tool 경계를 개선할 때만 사용한다.

후보 tool:
- `search_bid_notices`
- `get_bid_notice`
- `get_prior_specification`
- `get_bid_documents`

MCP가 authorization, network safety, normalized contract를 우회해서는 안 된다.

## 인증

### 애플리케이션 인증

Google OIDC/OAuth를 사용한다. backend가 identity를 검증하고 user-owned object는 server-derived user id로 판정한다.

### LLM 인증

Google identity와 별도다. 사용자별 Codex/ChatGPT 연결은 공식적인 공개 원격 hosting 지원 여부를 확인한 뒤 ADR로 확정한다.

## 외부 문서 수집 보안

공고/RFP는 untrusted input이다.

공개 배포 전:
- 허용 source host 정책
- URL parsing/canonicalization
- redirect 통제
- DNS/IP 목적지 검증이 필요한 범위 결정
- connect/read/total timeout
- 최대 응답/파일 크기
- 허용 MIME/file type
- parser resource 제한
- hash/dedup
- 문서 내용 실행 금지
- prompt injection 경계

OWASP SSRF 지침에 따라 임의 URL fetch보다 공식 source allowlist를 우선하고, redirect가 검증을 우회하지 않도록 한다.

## 배포 형태

```text
Internet
 -> HTTPS edge/reverse proxy
 -> React static assets
 -> FastAPI
 -> PostgreSQL + pgVector
```

hosting provider는 아직 결정하지 않는다.

## 구현 전 필요한 ADR

- ADR-001 Google 로그인/session 방식
- ADR-002 조달 API 및 첨부문서 수집 경계
- ADR-003 embedding provider
- ADR-004 Codex 인증 방식
- ADR-005 public hosting/secret storage
