# ADR-001 Google 인증, 세션, 객체 권한 및 SSE

- 상태: **설계 채택(구현·운영 미검증)**
- 관련 지적: DSR-002, DSR-003, Gemini F-02/F-05
- 검증 근거: https://developers.google.com/identity/openid-connect/openid-connect
- 전제: React와 FastAPI를 동일한 공개 origin으로 제공하는 BFF 방식. 실제 도메인·OAuth 콘솔 설정은 배포 전 확인한다.

## 결정

1. React는 인증 화면만 담당한다. 브라우저에 Google access/refresh/ID token이나 앱 세션 비밀을 저장하지 않는다.
2. FastAPI가 Google OIDC **Authorization Code Flow**를 시작하고 콜백을 받으며, 서버에서 인증 코드를 교환한다. redirect URI는 사전 등록값과 정확히 일치해야 하며 허용 redirect 대상만 사용한다.
3. 로그인 시도마다 예측 불가능한 일회용 `state`와 OIDC `nonce`를 생성하고, 가능하면 PKCE S256 code verifier/challenge를 적용한다. 이 프로젝트에서는 일관성을 위해 **PKCE S256을 필수**로 한다. 서버에 보관한 인증 시도와 callback의 state를 대조하고 1회 소비한다.
4. Google ID Token의 서명과 허용 알고리즘/JWKS, issuer, audience, expiration, nonce, 필요 시 azp 및 시간 관련 claim을 검증한다. JWKS 캐시와 갱신 실패는 안전하게 거부하며 토큰 검증 실패는 로그인 실패다.
5. 사용자 식별의 안정적인 키는 검증된 Google `sub`와 issuer 조합이며, 이메일 주소·사용자 제공 id는 권한 키로 사용하지 않는다.
6. 검증 이후 **서버 측 opaque 세션**을 생성한다. 충분한 엔트로피의 세션 식별자만 `__Host-session` 쿠키에 저장하고 DB에는 해시로 매핑한다. 쿠키는 `HttpOnly; Secure; SameSite=Lax; Path=/`, Domain 미설정이다. 배포 환경에서 HTTPS 및 `__Host-` 사용 가능 여부를 검증한다.
7. 로그인/권한상승 시 세션을 새로 발급하여 고정 공격을 방지한다. 서버 측 세션 폐기, 명시적 로그아웃, 유휴 30분 및 절대 8시간 만료를 **초기 설계값**으로 채택하고 테스트/운영 요구에 맞게 검증 후 조정한다.
8. 모든 상태 변경 요청은 서버가 발급하고 앱 세션과 결합한 CSRF 토큰의 헤더 검증과 정확한 Origin 검사로 보호한다. `GET`은 상태를 변경하지 않는다. 인증 callback은 일회용 state로 별도 보호한다. CORS는 허용된 origin만 설정하며 wildcard+credentials 조합을 금지한다.
9. API는 세션에서 `actor_id`를 도출한다. 클라이언트의 `user_id`, `role`, `tenant_id`는 신뢰하지 않는다.

## 소유권 계약

| 리소스 | 읽기 | 변경/삭제 | 부가 조작 |
|---|---|---|---|
| Profile | 본인만 | 본인만 | 서버 actor 기준 |
| AnalysisRun | 소유자만 | 소유자만 | 실행·취소·재개 시 재검증 |
| Question/Answer | 해당 run 소유자만 | 해당 run 소유자만 | 타 사용자 답변/재개 금지 |
| EvidenceSet/Claim | 해당 run 소유자만 | 불변 snapshot 원칙 | 공식 공개 원문 자체는 별도 공개 가능 |
| SSE subscription | 연결된 run 소유자만 | 해당 run 소유자만 | 최초 연결 및 모든 재연결 검사 |

- DB query/application service는 `(actor_id, resource_id)`를 인자로 받고 권한 있는 집합에서 조회한다. 임의 ID 추측 불가만으로 보호하지 않는다.
- 타 사용자 리소스 ID는 정보 노출을 피하도록 일반적인 404 응답으로 처리하고, 권한 오류와 내부 오류를 기록상 구분한다.
- 공개 데이터 조회는 비로그인으로 제공할 수 있지만 사용자별 분석·질문·SSE에는 소유권을 적용한다.

## SSE 계약

- 초기 연결은 동일 출처 쿠키 세션을 사용한다. `EventSource`가 Authorization 사용자 지정 헤더를 제공한다고 가정하지 않는다.
- 별도 bearer token이나 API key를 URL query에 넣지 않는다. 1회용 ticket은 필수가 아니며 다른 origin이 필요한 ADR이 생기면 재평가한다.
- `GET /api/analysis-runs/{run_id}/events`에서 actor와 run 소유권을 검증한다. `Last-Event-ID`는 순번만 제공하며 다른 run의 이벤트 선택자로 사용하지 못한다.
- 이벤트는 `run_id`, 증가하는 `sequence`, `type`, `timestamp`, 최소 상태 payload로 정의한다. `Last-Event-ID`에 따른 재전송은 **같은 run의 허용된 범위**에 제한한다.
- 서버에서 event를 최대 N개 또는 TTL 동안 보존하고, 오래된 cursor에는 명시적 resync 경로(`GET /api/analysis-runs/{run_id}`)를 제공한다. 정확한 보존 상한은 부하 측정 후 확정한다.
- 네트워크 연결 종료가 분석 취소를 의미하지는 않는다. 취소는 CSRF로 보호된 별도 POST 및 run ownership 검사 후 수행한다.

## 요구되는 검증

state/nonce/PKCE 실패, redirect mismatch, ID Token 서명·iss·aud·만료 오류, session fixation/rotation, CSRF/Origin, 로그아웃 후 접근, 양 사용자 간 profile/run/question/SSE/cancel 교차 요청과 재연결을 테스트한다. 인증 토큰과 CSRF 토큰은 로그에 남기지 않는다.

## 계정 삭제 시 인증 무효화 및 재가입 — R2-007

- 계정 삭제는 단순 로그아웃보다 강한 작업이다. 삭제를 시작하면 관련 세션 전부, 미완료 로그인 state/nonce/PKCE 시도, 실행/질문/SSE 접근을 폐기한다. 진행 중인 worker는 ownership 및 계정 상태를 재검증하고 결과 저장을 거부한다.
- 같은 Google `issuer + sub`로 다시 로그인한 사용자는 별도의 새 내부 사용자 ID를 받아야 하며 이전 탈퇴 계정의 자원을 자동 회수하지 못한다.
- DB 복원 시 세션/소유권이 함께 복구되어도 서비스 재개 전에 별도 삭제 저널을 재적용해야 한다. 상세 저장/보존 정책은 [ADR-008](ADR-008-profile-privacy.md)을 따른다.
- E2E: 삭제 후 옛 쿠키, 삭제 중 콜백, 삭제 후 동일 계정 재가입, 오래된 백업 복원 및 사용자 간 이전 소유권 접근 차단.

## 기존 SSE 연결의 지속적 권한 검증 — R3-003

- 서버는 연결 시작/재연결뿐 아니라 **이벤트를 전송하기 직전** 서버 세션 active/expiry, 계정 `ACTIVE` 여부, 해당 run 소유권과 취소/탈퇴 상태를 검사한다.
- 세션이 발급/폐기될 때 변경하는 `session_generation` 또는 `account_access_version`을 연결 맥락에 포함한다. 로그아웃, 계정 삭제, run 권한 철회가 발생하면 이전 generation으로의 이벤트 전송을 차단한다.
- SSE 연결은 최대 30분을 초기 상한으로 하고, 최소 15초마다 heartbeat와 유효성 검사를 수행한다. 메시지를 보낼 때 검사 주기에 관계없이 권한을 다시 확인한다. 유효하지 않으면 즉시 stream을 종료한다.
- terminal 이벤트 전달 후 stream 종료. 민감한 프로필 원문/전체 AI 프롬프트를 SSE payload에 넣지 않으며, 동일 run의 필요한 상태 정보만 전달한다.
- E2E: 열린 SSE 연결 상태에서 logout, 절대/유휴 세션 만료, 계정 DELETING, 소유권 박탈, run 취소를 실행하고 **재연결 없이도 그 이후의 이벤트가 전달되지 않는지** 검증한다.

## 고위험 계정 조작의 최근 인증 — R3-008

계정 삭제, 계정 전체 데이터 export, 외부 모델 연결/해제는 일반 세션만으로 실행하지 않는다. Google 재인증 또는 지원되는 최근 인증 증명으로 **직전 10분 이내의 확인된 사용자 인증**을 요구하고, 짧은 수명의 일회용 작업 nonce와 명시적 확인을 적용한다. 재인증 방식은 Google의 실제 OIDC 지원·`auth_time` 확인 및 브라우저 E2E를 통과한 경우에만 배포하고, 실패/취소/재사용 nonce는 작업 거부로 처리한다.


## HTTP 응답 캐시와 사용자 격리 — R4-005

인증된 API 응답은 서버 ownership 검사와 별개로 CDN·프록시의 공유 캐시 유출을 막아야 한다.

- `PUBLIC_CACHEABLE`: 개인 정보가 없는 공식 공고 목록만 제한적 TTL 및 출처 버전 기준으로 공유 캐시할 수 있다.
- `AUTHENTICATED_PRIVATE`: 프로필, 분석, 질문, 근거, 계정 조회 API 응답은 `Cache-Control: private, no-store`로 설정하고 프록시/CDN 공유 캐시에서 제외한다.
- `STREAMING`: SSE는 `Cache-Control: no-store, no-transform`, reverse proxy buffering/cache 해제, 최초 연결과 메시지 전송 시 권한 검증을 적용한다.
- `EXPORT_DOWNLOAD`: 사용자 자료 export는 `Cache-Control: private, no-store`, 짧은 수명과 1회용 전송 권한을 적용하고 요청마다 계정·소유권을 검증한다.
- `Vary: Cookie`만으로 사용자별 자료 보호를 대신하지 않는다. service worker의 오프라인 캐시에도 개인정보·분석 결과를 저장하지 않는다.
- 실제 reverse proxy/CDN을 통과하는 두 사용자 테스트에서 캐시 적중·미적중, 로그아웃·탈퇴 후 조회, export·SSE의 공유 캐시·buffering 차단을 검증한다.


## SSE의 실행 취소와 접근 권한 철회 구분 — R4-007

- 계정 삭제·로그아웃·세션 만료·소유권 회수는 **접근 권한 철회**이므로 추가 이벤트를 발송하지 않고 연결을 종료한다.
- 권한이 유지된 사용자가 자신의 실행을 취소한 경우 `CANCELLED` terminal event를 해당 run에 발행한 뒤 종료한다.
- 네트워크 단절로 terminal event 전달이 보장되지 않을 수 있으므로 클라이언트는 소유권이 검증되는 `GET /api/analysis-runs/{run_id}`를 최종 상태 확인 경로로 사용한다.
- event sequence와 재연결 cursor는 멱등 처리하고 다른 run의 이벤트 접근을 차단한다.

## Google OIDC의 최소 동의 범위 — R4-008

- 초기 scope는 `openid`만 요청하고 검증된 issuer와 `sub`를 앱 내부 식별자로 사용한다.
- `email`, `profile` scope는 실제 필요성·이용자 고지·데이터 최소화를 별도 승인하기 전 요청하지 않는다.
- 응답에 포함된 필요 없는 이름·이메일·사진 등 claim은 저장·로그하지 않는다.
- 실제 Google 콘솔 설정과 동의 화면은 배포 전 확인한다.
