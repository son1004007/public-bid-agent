# 01 요구사항

## 상태

설계 기준: `READY WITH ASSUMPTIONS`
공개 운영 기준: `NOT READY`

## 우선순위

```text
최신 사용자 지시
> 법률/외부 서비스 약관
> 프로젝트 보안/데이터 규칙
> 승인된 개인 개발 표준
> 이 요구사항
> 설계 선호
```

## MVP 기능 요구사항

### REQ-AUTH-001 Google 로그인

Google OIDC/OAuth 기반 로그인 후 backend가 신원을 검증하고 애플리케이션 세션을 만든다.

검수:
- 미인증 보호 API 거부
- client가 전달한 user id/role을 권한 근거로 신뢰하지 않음
- logout/session expiry 정의

### REQ-PROFILE-001 기업/기술 프로필

로그인 사용자는 입찰 적합성 분석에 필요한 기업/기술 정보를 관리한다.

검수:
- server-side ownership
- 모르는 값은 UNKNOWN 유지
- 정보 부재를 부적합 사실로 변환하지 않음

### REQ-BID-001 공식 공고 탐색

공식 공공 API를 통해 입찰공고를 조회하고 내부 표준 모델로 변환한다.

검수:
- 공식 source id와 원문 참조 유지
- API 장애와 검색결과 0건 구분
- 중복 공고 결정적으로 처리

### REQ-BID-002 AI/SW 관련성

AI/SW 사업 후보를 식별하고 포함 이유를 기록한다.

검수:
- deterministic keyword/rule baseline 존재
- LLM 분류 사용 시 baseline과 별도로 평가
- false positive/negative 평가 데이터 유지

### REQ-DOC-001 공고/RFP 문서 수집

분석에 필요한 공식 공고/RFP/규격 문서를 제한적으로 가져온다.

검수:
- 허용 출처, redirect, timeout, 크기, 형식 제한
- 원 출처 metadata 유지
- 문서 내용은 untrusted data로 처리

### REQ-RAG-001 근거 검색

특정 입찰의 관련 원문 구간을 검색한다.

검수:
- 가능한 경우 문서/페이지/섹션/source metadata 유지
- 작은 labeled set으로 retrieval 평가
- 측정 전 품질 보장 표현 금지

### REQ-AGENT-001 적합성 분석

결과 상태:
- `SUITABLE`
- `NEEDS_REVIEW`
- `UNSUITABLE`

검수:
- 중요한 결론마다 근거 또는 근거 없음 명시
- 사용자 정보가 부족하면 질문 또는 NEEDS_REVIEW
- 모델 출력이 사용자 프로필을 임의 변경하거나 실제 입찰을 실행할 수 없음

### REQ-AGENT-002 명시적 workflow

검색, 근거수집, 요구조건 추출, 프로필 비교, 부족정보 질문, 최종 합성을 명시적 상태/node로 관리한다.

검수:
- 상태 전이 테스트 가능
- retry/timeout bounded
- tool 장애를 정상 결과로 조작하지 않음

### REQ-STREAM-001 진행상황 스트리밍

장시간 분석은 인증된 사용자에게 SSE로 진행/결과 이벤트를 전달한다.

검수:
- event schema 명시
- 오류/재연결 정책
- 사용자 간 event 격리

### REQ-LLM-001 교체 가능한 LLM 경계

Agent는 특정 credential 방식에 직접 결합하지 않는다.

검수:
- provider 인증 격리
- 테스트용 deterministic fake provider 가능
- browser에 provider secret 미노출

### REQ-LLM-002 Codex 목표

Codex는 선호 추론 모델이다.

상태: `PLANNED / SUPPORT CONSTRAINT PENDING`

공개 원격 서비스에서 사용자별 ChatGPT/Codex 연결이 공식 지원되는지 확인하기 전에는 활성화하지 않는다.

## 비기능 요구사항

- REQ-SEC-001: secret은 server-side only.
- REQ-SEC-002: 외부 문서는 시스템 지시/권한/도구 정책을 변경할 수 없다.
- REQ-SEC-003: 사용자 소유 데이터는 server-derived identity로 scope한다.
- REQ-TRACE-001: 분석 결과에서 공식 원문 근거를 추적할 수 있어야 한다.
- REQ-LIC-001: 프로젝트 작성 코드/문서는 Apache-2.0, 제3자 데이터는 원 권리/조건 유지.
- REQ-COST-001: 별도 종량제 LLM API 비용을 MVP 필수조건으로 만들지 않는다.

## MVP 제외

- 실제 전자입찰 제출
- 인증서 서명
- 결제/계약
- 공식 법적 자격 판정
- 기업 자격 자동 변경
- 포트폴리오 키워드만을 위한 Kubernetes/microservice/fine-tuning
