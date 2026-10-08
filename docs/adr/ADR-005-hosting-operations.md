# ADR-005 공개 서비스 배포·복구·운영 경계

- 상태: **배포 원칙 채택 / 실제 호스팅·비용·검증은 미정**
- 관련 지적: DSR-012, DSR-013
- 범위: React + FastAPI + PostgreSQL을 사용하는 소규모 공개 포트폴리오 데모.

## 결정

1. MVP는 한 개의 FastAPI modular monolith와 React 정적 자산을 HTTPS reverse proxy 뒤에 배치한다. Kubernetes, 서비스 메시, 별도 메시지 브로커는 실증된 필요가 없으면 설치하지 않는다.
2. 공개 edge는 HTTPS만 허용하고 인증 콜백 URL, origin, cookie host, 외부 API 허용 목적지는 배포 환경별 설정으로 관리한다. 내부 DB 포트를 인터넷에 직접 노출하지 않는다.
3. HTTP request와 분석 실행별 correlation ID를 저장한다. 로그에는 credential, Google 토큰, 개인정보 원문, 기업 프로필 본문, 전체 RFP 프롬프트를 넣지 않는다.
4. 환경변수와 비밀정보를 분리하고 저장소에는 `.env.example`만 공개한다. 배포 전 비밀정보 유출 점검을 실행한다.
5. 사용자·원천 데이터는 `authoritative`(Google `sub` 참조, 사용자 프로필·사용자 입력, 분석/상태 이력), `rebuildable`(검색 index/embedding, 재다운로드 가능한 허용 자료), `external`(공식 원천 공고 자체)로 구분한다.
6. 사용자 프로필과 analysis metadata 등 복원 불가능한 데이터는 암호화된 정기 백업으로 보호한다. 시험 목적의 초기 **RPO 24시간, RTO 24시간을 목표값**으로 두되 측정 전 달성했다고 주장하지 않는다.
7. DB schema 변경 시 migration 전 백업, 기존 앱 버전과의 호환 기간, 실패 시 forward recovery 또는 안전한 rollback 전략을 문서화한다. 자동 파괴형 migration은 사용하지 않는다.
8. 데이터 삭제는 ADR-008의 백업 보존 상한까지 포함해 집행한다. public demo일지라도 이용 안내/데이터 삭제 방식/문의 경로를 공개한다.
9. 외부 공공 API, 문서 파서, LLM의 오류율과 응답 지연, 남은 호출 예산을 관찰하되 비용 정보나 보안을 과장하지 않는다.
10. AI provider를 설정할 수 없어도 공고 검색 및 근거 링크 조회가 동작해야 한다. AI 버튼을 무조건 성공으로 표시하지 않는다.

## 배포 선행조건

- Google OAuth 앱 등록과 실제 콜백·쿠키·HTTPS·CSRF E2E
- 사용자 간 객체 접근/분석/SSE 격리 E2E
- 공고 API·첨부파일 출처 약관 확인과 실패 격리
- 데이터 삭제/백업 복원·migration·rollback 연습
- 요청/사용자별 rate limiting, 분석 예산, 로그 민감정보 방지
- 기능 범위에 맞는 정확성 평가와 independent final review

## 미확정 사항

클라우드 제공자, 비용 상한, 백업 저장소, 배포 도메인과 사용자 수 제한은 운영 전 별도 확정한다. 호스팅이 미정이어도 코드 레이어/비밀 관리/복구 원칙은 변하지 않는다.

## 공개 장기 분석 worker의 내구성과 남용 방지 — R2-003/R2-Q02

- 공개 분석 실행은 FastAPI 요청이나 일회성 메모리 background task와 분리한다. PostgreSQL job 테이블과 소규모 별도 worker 프로세스가 `run_id/actor_id/version/lease_owner/lease_expires_at/heartbeat_at/cancel/idempotency_key`를 관리한다([ADR-007](ADR-007-analysis-state-evaluation.md)).
- DB 원자적 claim 및 lease 만료·재획득을 통해 웹 프로세스 재시작 후에도 상태가 보존되게 설계한다. terminal 상태와 결과 저장은 CAS/version 검사 후 처리하며, 중복 청구 가능성을 포함한 외부 도구 멱등성을 검증한다.
- 배포 재시작 시 새로운 worker가 만료 작업을 회수하고, 예산을 이미 초과했거나 계정이 탈퇴/취소된 run은 재개하지 않는다. 취소·실행 상태는 공개 화면에 DB 기준으로 표시한다.
- 비로그인 공고 조회를 허용하는 경우 **공개 읽기 API**에 대해서도 IP 기반/전역 요청 한도, 동시 연결 상한, 캐시/서버 기원 제한, 트래픽 관찰과 비로그인 첨부 수집 거부 등을 배포 환경에 따라 결정한다. 프록시가 넘기는 `X-Forwarded-For`는 신뢰한 프록시 목록에서만 해석하고 임의 client header는 rate limit key로 신뢰하지 않는다.
- 비로그인에게 과도한 문서 다운로드/AI 분석 비용이 발생하지 않도록 검색과 열람 외의 자원 사용 작업은 로그인·자원 예산을 선행한다.
- 검증: worker 종료/재시작, 동시 claim, lease 만료, 취소 중 외부 응답, migration 중 실행, 비로그인 IP/헤더 위조/캐시 장애/동시 요청에 대한 한도 테스트.
