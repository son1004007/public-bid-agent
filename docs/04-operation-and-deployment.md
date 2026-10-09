# 04 운영 및 배포 설계

## 현재 상태

**호스팅 대상, 실제 배포, 백업/복구 테스트 모두 미정 및 미실행.** 이 문서의 공개 운영 게이트는 애자일 로컬 개발 착수 조건이 아니다. 실제 사용자에게 특정 기능을 공개하는 시점에 활성 기능과 관련된 통제를 검증한다([애자일 실행 기준](07-agile-development-workflow.md)).

## 서비스 구성과 환경

- HTTPS edge/reverse proxy → React 정적 웹 → FastAPI BFF/API → 비공개 PostgreSQL. 하나의 backend로 시작한다.
- Google OAuth/OIDC client ID·client secret, 공공데이터 service key, 세션 비밀, DB 자격증명, 승인된 모델 provider 인증정보는 서버 전용 보안 저장소를 사용하며 Git에 기록하지 않는다.
- `.env.example`에는 변수 이름과 안전한 예시만 작성한다.
- 같은 origin/redirect URI/Google 콘솔 설정과 `__Host-` 세션 쿠키·CSRF 정책을 실제 배포 주소에서 시험한다.
- 실제 사용 가능한 모델 제공자 없는 경우 API 전환 없이 `disabled` 모드와 안내 문구를 제공한다. 앱 전체를 무단 Codex 계정에 결합하지 않는다.

## 보호 장치

1. 요청, 계정 및 `AnalysisRun`별 실행·도구·모델 요청 횟수, 처리 시간, 문서 바이트 예산은 [ADR-007](adr/ADR-007-analysis-state-evaluation.md)에 따른다.
2. 공공 API 및 공식 문서 다운로드에는 서버 측 allowlist/timeout/크기/MIME/redirect/DNS·IP 제한과 격리 파서를 적용한다([ADR-006](adr/ADR-006-document-ingestion-security.md)).
3. 로그인 성공만으로 데이터 접근을 허용하지 않고 Profile·AnalysisRun·Question·EvidenceSet·SSE 구독·취소에 대해 객체 소유권을 검증한다([ADR-001](adr/ADR-001-auth-session-ownership.md)).
4. 원문/요건/모델 출력의 출처 상태를 구분하고 공고 수정이나 취소 시 분석을 stale로 표시한다([ADR-002](adr/ADR-002-procurement-data-lifecycle.md)).
5. AI 모델과 외부 parser에는 사용자 권한 결정이나 비밀 설정 변경을 허용하지 않는다.

## 개인정보·로그·권리

- 인증 토큰, 세션/CSRF 키, API 키, 민감정보, 프로필 본문 또는 전체 프롬프트는 로그에 저장하지 않는다.
- `correlation_id`, `run_id`, 요청/외부 API 지연과 안전한 오류 범주만 기록한다. fetch URL의 서명 query/path와 임시 token은 로그·DB·화면 링크에 기록하지 않으며 공개 canonical URL을 별도 생성한다.
- 사용자 프로필 최소수집, 공식 PDF의 제3자 정보, 30일 분석 결과 보존과 백업 순환, 별도 삭제 저널 및 재가입 시 새 내부 사용자 ID 계약은 [ADR-008](adr/ADR-008-profile-privacy.md)에 기록한다. 실제 운영 전 고지·삭제·복원 테스트와 일치시킨다.
- 제3자 공고/RFP는 저작권·재배포·임베딩 조건을 독립적으로 확인하며 공개 GitHub에 파일 원본을 임의 업로드하지 않는다.

## 복구·운영 품질

- 데이터 분류: 사용자 프로필과 계정 연결/분석 기록은 `authoritative`, 검색 인덱스와 복원 가능한 파생 자료는 `rebuildable`, 공공 API 원천 자료는 `external`이다.
- 초기 복구 목표는 **RPO 24시간 / RTO 24시간**으로 설정하지만 실제 측정 전 보장하지 않는다.
- migration 전 백업, backward-compatible 배포, 오류 시 롤백/forward recovery, 계정 삭제 후 별도 보호된 삭제 저널의 복원 시 재적용을 시험한다. 공개 장기 분석은 FastAPI 요청과 분리된 PostgreSQL lease/heartbeat/CAS worker 경계로 관리하며 중복 실행·취소 경쟁을 검증한다.
- request ID, analysis run ID, 외부 API 오류, parser 오류, 비용/토큰 범주를 진단하며 개인정보/secret 로그 저장은 금지한다.
- 제공자별 인증 승인, 비용 한도, 사용자 동의/철회, rate limit을 실제 운영에서 확인한다. 비로그인 공개 검색은 별도 IP·전역 동시성·캐시·reverse proxy 신뢰 정책으로 남용을 막는다.

## 개발과 배포의 별도 승인

- **개발 단계:** 로컬/합성 fixture·비공개 데모와 공개 GitHub 소스코드 수정은 단계적으로 진행한다. 커밋했다고 사용자 서비스에 배포했다고 주장하지 않는다.
- **활성 기능의 출시:** API/인증/AI/개인정보 등 실제 켜진 기능에 해당하는 체크리스트와 독립 검수를 충족해야 한다. 미구현 기능은 OFF로 고정하고 사용자에게 제공 중이라고 표현하지 않는다.
- **공개 AI 추론:** 별도 공식 모델 사용 자격 및 예산·보안 검증이 끝나기 전에는 비활성 상태를 유지한다.
- **전체 서비스 출시:** 아래 체크리스트의 모든 관련 항목과 사용자 승인을 통과해야 한다.

## 공개 서비스 출시 게이트

- [ ] 법률·서비스 약관 및 공식 API 이용/원문 보존·재배포 조건 확인
- [ ] Google OIDC state/nonce/PKCE·ID Token·HTTPS·쿠키·CSRF/CORS E2E
- [ ] 다중 사용자 권한·SSE/취소·재연결 안전성 테스트
- [ ] 실제 공공 API 스키마/정정·취소·마감 시각 계약 테스트
- [ ] 공식 PDF 수집 SSRF/파서 격리/과대 파일 제한 테스트
- [ ] 원문 근거 추적·불확실 상태·평가 결과 검증
- [ ] 데이터 보존·삭제·백업/복원, 기밀/로그 노출 검증
- [ ] 배포 HTTPS edge/DB 접근·모니터링/비용 한도 확인
- [ ] 실제 공개 원격 LLM 사용 허용 여부 확인(미허용이면 AI 기능 비활성 고지)
- [ ] 테스트 기록/최종 독립 코드 리뷰/사용자 승인

## 비용 경계

호스팅과 모델 사용량의 정액/종량 비용을 구분해 기록한다. 별도 종량제 API 비용이 MVP 필수조건이 아니라는 사용자 요구를 운영 전체가 완전 무료라는 뜻으로 해석하지 않는다.

상세 배포 원칙과 미확정 운영 목표는 [ADR-005](adr/ADR-005-hosting-operations.md)를 따른다.

## Codex R3 배포 선행조건

- 최신 공고 유일성·완전 동기화·마감 UTC 충돌을 fail-closed로 처리하는지 검증한다.
- 스캔·표·부분 PDF 추출 시 원문 요건 포괄성 실패를 명시한다.
- 열린 SSE 연결의 세션 철회 후 이벤트 전송 차단을 시험한다.
- React 기본 텍스트 렌더링, 공식 HTTPS 원문 링크 allowlist 및 CSP·XSS 브라우저 테스트를 통과한다.
- 후속 질문·답변의 비민감 enum 입력 제한과 개인정보/기업기밀 비수집을 검증한다.
- 실제 공개 모델 이용 시 영속적인 입력·출력 토큰/재시도 예약 장부와 사용자별·전역 한도가 설정되어 있어야 한다.
- 외부 모델 계정 연결·해제/계정 삭제/전체 export는 최근 인증과 1회용 승인 확인을 통과한다.

## Codex R4 공개 배포 게이트

- [ ] 공식 공고별 `SyncCoverage`와 authoritative detail refresh 검증
- [ ] 자기신고 항목과 행정적 요건 공식 검증 분리 및 오인 방지 UI 확인
- [ ] 다중 사용자·provider·서비스 전체 원자적 예산 예약 E2E
- [ ] 프로필/분석/근거/export/SSE의 CDN 공유 캐시·buffering 격리 E2E
- [ ] 계정 삭제 직전 외부 provider 요청 취소 및 늦은 응답 차단·보존 고지 검증
- [ ] 실제 선택한 Google OIDC 최소 scope·동의 화면 확인
