# 03 테스트 및 검증 계획

## 현재 상태

설계 단계이며 **실행한 테스트가 없다(NOT RUN)**. 테스트 계획은 기능을 검증했다는 뜻이 아니다.

## 테스트 증거 기본 형식

각 테스트는 요구사항 ID, 설계 ADR, 커밋 SHA, 실제 명령/환경, 날짜, 기대값, 결과(`PASS/FAIL/NOT RUN/BLOCKED`), 실패 로그의 비밀정보 제거, 재현 가능한 fixture 버전을 함께 기록한다. 합성 fixture는 실제 공공 API 응답이라고 주장하지 않는다.

## 인증·세션·인가 — REQ-AUTH / REQ-SEC-OWNER

- 콜백 `state`/OIDC `nonce`/PKCE S256 오류, 변조·재사용, 잘못된 redirect URI
- ID Token의 서명/issuer/audience/expiration, 키 회전, 요청 상관관계 실패 시 안전한 거절
- 쿠키 HttpOnly/Secure/SameSite/Domain/Path, 세션 유휴·절대 만료 및 로그인 후 rotation
- 로그아웃 후 세션 재사용, session fixation, CSRF 토큰 부재/변조, 타 origin POST/credentialed CORS
- 서로 다른 두 사용자 fixture에서 profile, analysis run, 질문 응답, 근거, cancel, SSE 재연결 교차 접근 거부
- `Last-Event-ID` 다른 run 범위 공격, 인증 취소 후 EventSource 재연결 거부

## 공식 공고 API 및 데이터 상태 — REQ-BID

- 실제 공공 API 응답의 id, 변경 차수, 정정/취소, 첨부, 마감 표본을 read-only로 검증하고 fixture 생성
- 정상 결과/0건/partial pagination/중복/기간·타임존 경계/schema drift/rate limit/timeout/4xx/5xx
- raw snapshot과 normalized revision hash·parser version 보존, 재수집 후 변경 감지
- 변경 공고 분석 결과 `STALE_SOURCE` 처리, 취소 공고의 지원 가능 판정 방지
- 불분명한 날짜·원천 상태·서버 오류가 `UNKNOWN` 또는 명시적 오류로 유지되는지 검사

## 안전한 첨부 수집과 격리 파서 — REQ-DOC

- 허용 공식 출처/허용되지 않은 URL, scheme/port/host, DNS/IP 변조, redirect 이동, proxy 우회
- URL encoding, TLS 인증, streaming 크기·시간 초과, MIME/매직바이트 불일치, 암호화/손상 PDF
- 병렬 과다 문서, parser OOM/hang/crash, 최대 페이지/텍스트 길이, 격리 parser의 네트워크 차단
- ZIP/HWP 등 미지원 자료의 안전한 거부, 인용 오류가 전체 서비스 장애로 전파되지 않는지
- 악성 문서에 포함된 '다른 사용자 정보 조회/임의 도구 호출' 프롬프트 주입이 데이터로만 처리되는지

## 근거 추적과 요건 추출 — REQ-EVIDENCE / REQ-RAG

- document byte hash, parser version, passage ID, source link, 원문 offset 또는 위치 불명확 상태 유지
- LLM이 임의 생성한 passage ID, 다른 문서/버전/사용자의 ID를 인용하면 거절
- 정정·재파싱·chunk 순서 변경 후에도 과거 결과의 버전이 변경되지 않음
- 원문 저장 불가·근거 검색 실패/정보 없음이 임의 긍정 판정으로 변환되지 않음
- 공개 평가 표본의 문서 버전/라이선스/어노테이션 기준·검토자·불일치 처리와 retrieval quality 측정

## 적합성 및 Agent 실행 — REQ-AGENT

- 필수 참가조건 충족/충돌/UNKNOWN, 기술 적합성과 참가자격 분리, 사용자 프로필 미입력
- AND/OR/예외조항/금액/기간, 근거 상충, stale document, 근거 없는 확정 판정 금지
- 도구 호출 횟수/문서 바이트/모델 토큰·상태 전이·시간 상한, 비용·재시도 제한
- 무한 follow-up 루프, TTL 만료, 두 번 resume, 늦은 모델 응답, 취소 전파, 이미 완료된 run의 변경 방지
- 위조한 tool 출력이나 모델 명령으로 임의 shell/SQL/URL fetch·권한 변경 불가능함을 확인

## LLM 제공자·비용·비밀정보 — REQ-LLM

- `disabled`일 때 AI 사용 불가를 정직하게 표시하고 기본 검색·문서 근거 기능은 정상
- `fake` 결과는 실사용 추론/정확도 평가로 표시하지 않음
- 허용 provider 테스트는 공식 원격 사용자별 동의·회수·사용 한도 확인 후 수행
- token/쿠키/프로필/원문 프롬프트 누출 점검, 사용자별 비용·실패 상태 분리
- embedding 미설정에서 서비스가 실패하지 않고 검색 baseline으로 동작

## 개인정보 및 운영 복구 — REQ-PRIV / REQ-OPS

- 계정 삭제 후 profile, run, 질문, cache, vector 인덱스, 백업 복원 삭제 목록 반영
- 분석 보존 TTL 및 로그 민감정보 노출 여부 확인
- 공개 서비스에서 HTTPS, 비공개 DB, 정량적 rate limit, backup·restore, migration rollback/forward recovery
- 실행 중 재시작, 외부 API 장애, 복구 버전과 DB schema 호환성 smoke

## 평가 및 실제 공개 승인

버전된 표본으로 AI/SW 분류 precision/recall, 필수요건 추출 누락, passage retrieval recall, 판정 혼동행렬과 근거 연결 유효성을 구분한다. 품질 임계치는 실제 baseline 뒤 근거를 기록하고 확정한다. **필수조건 UNKNOWN을 SUITABLE로 승격시키거나 존재하지 않는 근거를 확정적으로 제시하면 출시 실패**로 판정한다.

공개 AI 서비스 완료 선언 전:
- 실제 Google 로그인 및 두 사용자 간 데이터 격리
- 실제 공공 공고 검색·정정/취소 처리·원문 링크
- 공식 허용된 PDF의 안전한 추출과 유효 근거가 달린 결과 1건 이상
- 실제 허용된 LLM 사용자·요금·인증 경로 확인 및 실추론 시험
- 제한/비밀정보/복구/삭제/취약점 점검, 독립 **최종** 리뷰 통과

임베딩·LangGraph·SSE·MCP를 구현하지 않았다면 구현했다고 주장하지 않는다.
