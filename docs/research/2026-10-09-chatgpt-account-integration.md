# 사용자 자신의 ChatGPT/Codex 계정 선택과 AI 요청 연동

- 조사일: 2026-10-09
- 출처: OpenAI 공식 개발자 문서/Help Center
- 대상: 공개 GitHub `public-bid-agent`, 프런트엔드 웹 UI와 향후 원격 호스팅 서비스를 구분
- 현재 상태: **계정 선택/사용 권한 의향 UI만 구현; 실제 OAuth/모델 요청 미구현·미승인**

## 1. 확인된 공식 기능

OpenAI `Sign in with ChatGPT`은 사용자 계정 로그인(identity)과 사용자 요금제 기반 AI 요청 권한(token sharing)을 서로 구분한다.

- **오픈소스/로컬 실행 앱**: 각 사용자가 ChatGPT 계정을 선택해 인증하고, 요금제 사용 권한을 별도로 승인할 수 있는 경로가 문서화되어 있다. `@siwc/local` 및 공식 예제는 계정 목록·선택·추가·재연결을 다룬다.
- 공개/원격 호스팅 또는 상용 앱: **지원은 선정된 파트너/승인 대상**. 공개 오픈소스 GitHub 저장소라는 이유만으로 원격 다중 사용자 서비스의 구독 사용 권한이 자동 허용되는 것은 아니다.
- Codex app-server 연동: 사용자에게서 승인된 OAuth access token을 사용해 Responses API에 요청하는 예시를 공식 문서가 제공하지만, 여기서도 **선행 공식 사용 자격과 각 사용자 토큰 격리**가 필요하다.
- ChatGPT 로그인만으로 모델 호출/요금제 사용이 자동 허용되지 않는다. token 공유 권한을 별도로 확인해야 한다.
- OAuth/Responses를 통한 요청은 사용자별 요금제 정책/사용량 한도의 영향을 받을 수 있으며 실제 이용 가능 여부는 요청 성공으로 확인해야 한다. 무료 무제한 API라고 주장하지 않는다.

## 2. 제품 설계

### 사용자 화면

1. AI 기능 사용 안 함.
2. 내 ChatGPT / Codex 계정 선택: 현재 앱 사용자에게 연결된 별도의 OpenAI 계정(최초엔 없음) 목록.
3. 계정 추가, 연결/재연결, 활성 계정 변경, 연결 해제.
4. 로그인 계정과 **AI 요금제 사용 권한 승인**을 분리해 표시: 연결됨/미연결/동의 안 함/사용량 제한/연결 만료.
5. AI가 실행될 때 실제 사용 중인 계정(검증된 안전한 표시명) 및 관리·사용량 페이지 연결.
6. 사용자 소유 공고/제출/평가 기록과 OpenAI 인증 계정은 별개 소유권/데이터 경계 유지.

### 검증될 때까지 적용할 보안 조건

- 원격 공개 서비스 승인 또는 공식 허용 배포 형태가 확인되기 전 **실제 로그인 UI 비활성화**, 비밀정보/토큰 입력 차단.
- 승인 후 OAuth Authorization Code + PKCE, `state`, `nonce`, ID token 서명·issuer·audience·exp·subject 검증.
- 로컬 OSS에서는 `client_id` 등록을 검증된 사용자 + workspace에 묶고 안정적인 `ext_agent_host_id`를 유지. 계정 전환 시 다른 계정 토큰을 덮어쓰지 않는다.
- 실제 원격 웹서비스는 앱별 공식 발급 client credentials/redirect allowlist 등 적용되는 인증 계약과 tenant 별 scope 검증 필요. 로컬 loopback 콜백을 인터넷 공개 웹서비스에 임의로 재사용하지 않는다.
- Access/refresh token은 브라우저 localStorage, public 저장소, 로그, HTML, URL에 저장/노출하지 않는다. 프로덕션에서 인증·인가와 안전한 서버측 비밀 보관이 선행되어야 한다.
- 권한 거부/만료/재인증/사용량 한도/계정 전환 경쟁/연결 해제에서 허가받지 않은 모델 요청을 보내지 않는다.
- 사용자 소유 비공개 제안서와 가격입찰정보는 사용권한 및 외부 전송 정책 확인 전 AI에 보내지 않는다.
- 실제 API 비용, 요금제 공유 여부, 모델 제공 범위, 재판매/원격 서비스 계약은 공식 승인 후 검증.

## 3. UI mock 실제 범위

- `frontend/public/ai-account-preview.html`: `off`/본인 계정 선택, 가상 계정 2개 및 추가/전환·초기화, 별도 구독 사용 의향/공개 공고만 전송 의향 체크, 미연결/미승인 상태 상시 표시.
- 이 페이지는 인증정보/이메일/API 키 입력이 없고, 외부 네트워크 및 브라우저 영속 저장이 없다. 사용자를 실제 로그인했다고 주장하지 않는다.
- `Continue with ChatGPT`는 disabled. 다른 페이지에서 시안으로 이동만 가능하다.

## 4. 공식 근거

- [Sign in with ChatGPT Quickstart](https://developers.openai.com/siwc/quickstart)
- [오픈소스 요금제 사용 개요](https://developers.openai.com/siwc/token-sharing-open-source)
- [로컬 오픈소스 앱 계정 등록·전환·PKCE](https://developers.openai.com/siwc/token-sharing-open-source/sign-in)
- [오픈소스 통합 Cookbook (2026-09-28)](https://developers.openai.com/cookbook/articles/sign-in-with-chatgpt)
- [Codex app-server OAuth 사용](https://developers.openai.com/siwc/token-sharing-open-source/codex-app-server)
- [공개 호스팅 웹사이트의 승인 조건](https://developers.openai.com/siwc/website)
- [사용자 요금제 관리](https://help.openai.com/en/articles/20001542-using-your-chatgpt-plan-in-other-apps-and-sites)

## 5. 다음 검증 게이트

1. 웹서비스 공개 배포 형태와 SIWC 원격 웹사이트 파트너 적격성/승인 상태 확인.
2. 승인된 경우 최소 scope, 로그인/토큰 갱신, 계정/워크스페이스 분리, 사용량/권한 취소, 모델 선택/요청, 장부/예산 정책 설계 및 독립 검수.
3. 사용자가 계정 선택 UI 흐름을 검토한 뒤 화면 수정. 기존 공개 API/입찰 관리 UI 검토를 계속하고 백엔드 개발은 그 뒤로 둔다.
