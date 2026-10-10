# 현재 개발 상태

- 기준일: 2026-10-09
- 대상: son1004007/public-bid-agent
- 개발 브랜치: feat/sprint1-search-demo / Draft PR #1
- 사용자 우선순위: **설계 → UI 퍼블리싱 → 사용자 화면 검증 → 프런트엔드 수정 → 백엔드 세부 구현**
- 현재 단계: **독립 실행 공고→참여→제출→결과→회고 통합 UI 퍼블리싱 작성 / 사용자 피드백 대기 (UI_PROPOSED)**
- backend: 초기 합성 공고 API와 테스트 11개 기존 구현을 유지. 더 이상 백엔드 확장하지 않음.
- frontend: 기존 React/FastAPI 코드 보존. `frontend/public/bid-management-preview.html`을 **현재 검토 대상**으로 추가했고 `ui-review.html` 목록에서 연결. 과거 `bid-detail-review.html`은 구버전 시안으로 보존.
- 신규 시안은 브라우저 메모리 수기 상태만 다루며 서버 저장·공식 조회·개별 업체 입찰내역 조회가 아니다.
- 실공고 연동, Google 로그인, RAG/LLM, 실제 행정자격 판정, 외부 서비스 배포: 미구현/비활성.
- 공통 UI 퍼블리싱 우선 정책: personal-engineering-handbook의 Draft PR #1, **아직 검수/승인 전**.

## 사용자가 확인할 퍼블리싱 범위

- 공고 탐색 / 상세 검토 / 임시 검토 보관함 / 화면 검증 메뉴
- **공고별 상세 화면**: 기본정보, 행정 참가자격, 제안서·평가배점, 제출 수기 기록, 낙찰·기술/가격 점수, 수주 이력 표
- 제출/점수 수기 입력의 값 검증, 모든 자료의 합성·미확인 표기
- 합성 공고 8건, 검색어 및 AI/SW/DATA 필터
- 선택한 공고의 기술·사업 요건 예시
- 0건/오류 화면 시뮬레이션
- 데스크톱·모바일 반응형 레이아웃, 키보드 동작 기본 확인
- 화면 검증 체크리스트

설계 자료는 **합성 fixture**이며 실제 공공 입찰 정보가 아니다. 브라우저 밖으로 데이터를 전송하거나 서버·DB에 보존하지 않는다.

## 실행 및 검증 상태

- 최초 Sprint 1 백엔드: 로컬 pytest 11 PASS (2026-10-09).
- 최초 Sprint 1 PR CI: Python 및 TypeScript/Vite 빌드 PASS (GitHub Actions 37885735328).
- GitHub Actions push [37894035152](https://github.com/son1004007/public-bid-agent/actions/runs/37894035152) 및 PR [37894040200](https://github.com/son1004007/public-bid-agent/actions/runs/37894040200): **PASS**. Python 백엔드 테스트, TypeScript/Vite 빌드, 독립 UI 정적 HTML JavaScript 구문·안내문·외부 자원 참조 검사, 번들 내 퍼블리싱 파일 포함 여부를 확인했다. 사용자 화면 적합성 승인/브라우저 E2E를 대체하지 않는다.
- 사용자 검증용 시안과 일치하는 별도 정적 데모는 로컬 브라우저에서 화면/상호작용을 사전 점검했으나, GitHub 파일의 정식 시각 검수 및 사용자 승인은 여전히 미완료.
- 별도 AGY/Gemini 의미 검수: **NOT RUN (REVIEW_DEBT)**. Draft PR 유지 및 main 병합/릴리스 금지.
- 기존 R1~R4 설계 검수 및 정정 ADR은 삭제하지 않음.

## 다음 작업

1. 사용자가 [UI 화면 검증 가이드](docs/ui/SCREEN_REVIEW_GUIDE.md)와 공고별 [상세·제출·결과 시안](frontend/public/bid-detail-review.html)을 직접 확인하도록 안내.
2. 페이지/탐색/상세/보관함/모바일/빈 결과·오류에 대한 사용성 피드백 수집.
3. 사용자 결정에 따라 화면과 API 응답 데이터 계약 수정.
4. UI 검증 뒤 해당 화면의 필요 기능부터 백엔드 구현을 이어감.
5. 변경 단위 독립 검수·실제 테스트 및 필요 시 별도 사용자 승인 후 main 통합을 판단.

## 근거 문서

- [화면 검증 가이드](docs/ui/SCREEN_REVIEW_GUIDE.md)
- [독립 HTML 퍼블리싱 시안](frontend/public/ui-review.html)
- [애자일 개발 절차](docs/07-agile-development-workflow.md)
- [기존 Sprint 1 실행 기록](docs/implementation/SPRINT1_RUNBOOK.md)
- [다른 채팅/AI용 인수인계](docs/implementation/CONTINUE_IMPLEMENTATION_PROMPT_2026-10-09.md)
- [보안·독립 검수 정책](https://github.com/son1004007/personal-engineering-handbook/blob/main/REVIEW_POLICY.md)

## 2026-10-09 상세 퍼블리싱 추가

- 목록에서 `전체 상세·제출·낙찰 관리` 링크로 이동.
- 상세 페이지 6개 화면: 기본정보/참가자격/제안서·평가/제출 관리/낙찰·평가점수/진행 이력.
- 제출 기록은 `미확인/미제출/제출했다고 기록/접수증을 사람이 확인했다고 기록`로 구분하며 공식 접수 확인을 주장하지 않음.
- 평가점수는 입력값과 만점의 유효성을 검사하며 미공개·미입력 점수를 0으로 환산하지 않음.
- 공식 조사: `docs/research/2026-10-09-bid-lifecycle-management.md`. 공식 공공 API는 개찰·낙찰·계약을 제공하지만, 내 기업이 제출했다는 사실과 개별 기술점수는 별도의 증빙/공개 조건이 필요.
- 새 HTML 상세 퍼블리싱의 GitHub Actions push run [37900354978](https://github.com/son1004007/public-bid-agent/actions/runs/37900354978) 및 PR run [37900360576](https://github.com/son1004007/public-bid-agent/actions/runs/37900360576): PASS. 백엔드 tests, frontend Vite typecheck/build, 정적 JS 및 독립 HTML 파일 포함 검증을 통과. 독립 최종 검수 및 실제 GitHub 버전의 브라우저 E2E는 NOT RUN.

## 2026-10-09 사용자 방향 동의: 입찰 전체 과정 관리

- 사용자 피드백: 공고 탐색뿐 아니라 **발굴 → 참여/미참여 판단 → 제안서·가격입찰서 각각 제출 확인 → 개찰·낙찰/계약 → 기술·가격 점수와 수주/미선정 회고**로 확장하는 방향에 동의했다.
- **승인된 것은 기능 방향과 진행 방식이다.** 현재 6개 탭의 UI 구성/문구/상호작용 전체 승인이나 실제 외부 API/개인정보·보안 설계 승인으로 해석하지 않는다. UI 상태는 `UI_PROPOSED / USER_FEEDBACK_PENDING` 유지.
- 추가 화면 설계 시 가격입찰서와 기술제안서 각각의 제출/접수 확인 상태·근거를 분리한다. 공고별 제출 요건이 다르므로 필수 여부 자체도 공식 공고를 기준으로 판정한다.
- 참여하지 않기로 한 이유, 담당자 및 준비 단계, 제출 확인 결과, 개찰·낙찰·계약의 별도 상태, 기술/가격별 공개 또는 통보 점수, 점수 미확인 상태, 실패 원인과 개선사항을 **최종 UI 시안 검토 대상**으로 둔다.
- 서버 데이터 저장 및 공식 정보 자동 확인/수주 확정은 여전히 미구현이며, 개인·업체 비공개 기록은 공개 저장소의 합성 시안에 넣지 않는다.

## 2026-10-09 P0 통합 입찰관리 UI 퍼블리싱

- 현재 주요 검토 화면: `frontend/public/bid-management-preview.html`. HTML/CSS/바닐라 JS 단일 파일로 외부 서버·React/npm 없이 브라우저에서 작동한다.
- 대시보드: 8건 가상 입찰기회, 검색/분야/참여결정 필터, 결정·제출·수주 집계, 공고별 상세 이동.
- 참여 결정: Bid/No-Bid + 사유(미참여 필수), 담당자, 단계, 내부 준비일, 판단 근거.
- **제출 확인 분리:** 기술제안서와 가격입찰서마다 해당 공고 요구 여부/제출수기/접수증 확인수기/근거/확인일 구분. 실제 계정/공식 API 조회는 없음.
- 결과: 공고 전체 개찰/낙찰 상태와 우리 회사 선정, 계약 상태, 근거 유형을 서로 분리.
- 점수: 기술/가격 값·만점과 근거 유형, 입력 검증. 미확인은 0점으로 처리하지 않음.
- 회고: 미참여·미선정 원인, 개선·후속 조치. 결과/회고 대시보드에서 요약.
- 시안 조작: `가상 진행 사례 채우기`, `시안 초기화`; 브라우저 새로고침 시 자료가 사라진다. 회사 비공개 정보·실제 입찰 서류 입력 불가.
- **검증 상태:** UI 소스 작성, GitHub PR CI/실제 브라우저 동작 및 모바일 QA 결과는 최신 실행 증거로 별도 판단. 사용자 화면 승인 및 AGY 독립 최종 검수는 여전히 `NOT RUN` / `UI_PROPOSED`.
- 다음 작업: 화면의 검색, 참여 결정, 서류별 제출/접수, 점수 검증, 결과/회고, 모바일 동선에 대한 사용자 검증 → UI 수정 → 필요 데이터/API 계약 설계.

## 2026-10-09 통합 입찰관리 UI CI 및 브라우저 검증 결과

- GitHub Actions PR run [37904121398](https://github.com/son1004007/public-bid-agent/actions/runs/37904121398): frontend 타입 검사·Vite 빌드·3개 정적 HTML 검사 및 기존 backend pytest 모두 **PASS**.
- GitHub Actions 아티팩트: `bid-management-ui-preview` (ID `11603641894`) / 외부 운영 배포가 아닌 다운로드 가능한 HTML 묶음.
- HTML 3개를 CI 아티팩트에서 확보해 로컬 Chromium Playwright로 직접 시나리오 검증 **17/17 PASS**. 검사 항목: 8건 목록/집계, 가상 사례, 미참여 사유 필수, 제안서 접수 증빙 필수, 제안서/가격서 상태 독립, 점수 범위 및 출처, 회고 반영, 초기화, 콘솔 페이지 오류 0, 390px 모바일 가로 넘침 없음, 기존 목록의 새 화면 연결.
- Chromium은 HTML 문서를 `page.set_content`로 로딩해 가상 사용자 조작을 확인했으며 로컬 HTTP 서버/공개 배포를 수행하지 않았다. 브라우저 E2E 전체 경로/Google OIDC/실제 나라장터/인증·권한은 테스트하지 않았다.
- **UI 사용자 직접 검수: PENDING, 독립 최종 의미 검수: NOT RUN (REVIEW_DEBT)**. Draft PR #1 유지, `main` 병합 및 공개 운영 배포 미실행.

## 2026-10-09 사용자 개인 Codex 계정 선택 시안

- 최신 명시 요구: Public Bid Agent 사용자마다 **자신의 ChatGPT/Codex 계정을 선택해서 AI 분석에 사용할 수 있도록** UI 추가.
- `frontend/public/ai-account-preview.html`: 화면 내 AI 사용 안 함 / 내 ChatGPT-Codex 계정 선택 방식, 가상 A/B 계정 전환·가상 계정 추가·초기화, AI 요금제 사용 권한 요청 의향·공개 데이터만 전송 옵션, 실제 인증 미연결 상태를 구분.
- `frontend/public/bid-management-preview.html` 대시보드/메뉴, `ui-review.html` 목록, React 초기 앱에서 해당 화면으로 링크 추가.
- UI 시안 계정 정보: **합성 이름과 임시 메모리만 사용**. OAuth, 실제 계정 목록 조회/연결, 사용자 이메일·API 토큰 수집/보관, AI 요청·실제 비용/요금제 차감 없음.
- 공식 조사: `docs/research/2026-10-09-chatgpt-account-integration.md`. OpenAI의 Sign in with ChatGPT는 로컬 OSS용 사용자별 계정 등록·전환 및 사용자 승인 사용량 공유를 지원하지만, 공개 원격 웹서비스 적용은 별도 승인 대상.
- 후속 백엔드/인증 개발은 공식 원격 연동 승인/허용 여부 확인, OAuth/OIDC PKCE/state/nonce, ID token 검증, 계정/워크스페이스/권한 분리, 안전한 token 보관·폐기, 사용량 한도/예산과 데이터 격리 검증 뒤 진행.
- 화면 사용성 승인 `UI_PROPOSED`, 이번 변경의 독립 최종 검수 `NOT RUN/REVIEW_DEBT`로 유지.

## 2026-10-09 개인 Codex 계정 시안 검증 증거

- GitHub Actions push [37917254772](https://github.com/son1004007/public-bid-agent/actions/runs/37917254772) 및 PR [37917259804](https://github.com/son1004007/public-bid-agent/actions/runs/37917259804): **success**, Python backend pytest, React/Vite 빌드 및 오프라인 HTML JavaScript 정적 검사 통과.
- CI 산출물 `bid-management-ui-preview` artifact ID `11610855568` (신규 `ai-account-preview.html` 포함 HTML 4개). 외부 배포가 아니라 검토용 다운로드 파일이다.
- CI 아티팩트의 신규 계정 시안을 Chromium Playwright로 메모리 페이지 로드/인터랙션 테스트: **16/16 PASS**, 브라우저 pageerror **0**, 390px 모바일 가로 넘침 없음. 로그인 비활성·가상 A 선택·사용권한 의향 미승인·가상 계정 추가/전환·초기화·새 문서 로딩 상태 폐기·입찰관리 사이드바 링크를 포함.
- 전체 인증 E2E/실제 OpenAI OAuth·모델 사용 및 사용자 UI 승인, 독립 최종 검수: **NOT RUN**. 기존 REVIEW_DEBT 및 Draft PR 게이트 유지.

## 2026-10-09 Bid/No-Bid 영향인자 입력 화면 퍼블리싱

- 사용자 요구: 독립변수(영향인자)를 입력해서 Codex/Claude의 상호 검토와 **사용자 참여 결정**에 적용해야 한다.
- 공고별 관리의 **영향인자 평가** 탭 추가: 6개 공고별 필수조건 충족/미충족/미확인/해당없음, 8개 비교 인자의 1~5 수기 평가+근거·출처, 예상매출/수행원가/제안비용, 공고 기술·가격 배점.
- 추천 지표는 모든 Gate 확인·8개 인자 입력 때만 가중합 예시로 산출하고, 법적 적격·낙찰 확률/모델 분석으로 표시하지 않는다. 사용자 최종 결정은 별도 Bid/No-Bid 화면.
- 아직 실제 Codex/Claude/모델 API·RAG 연동 없음. 가상 두 AI의 **미실행 자리표시자**만 제공하며 자동 AI 의견을 꾸며내지 않음.
- 상세 변수 정의/근거/후속 LangGraph 계약: `docs/design/BID_NO_BID_FACTORS.md`. 실제 회사 자료 입력 금지.
- 필수 Gate·평가인자·지표의 수치는 공개 제품 시연용 가설로, 사용자/실제 사례 검토 전 정책·통계적 추천 정확도는 미확인.
- 본 UI 작업은 기존 공개 배포 불가, 사용자 UI 검토/독립 최종 검수 대기 상태 유지.

## 2026-10-09 Bid/No-Bid 영향인자 UI 검증 결과

- GitHub Actions push [37921415790](https://github.com/son1004007/public-bid-agent/actions/runs/37921415790) / PR [37921419837](https://github.com/son1004007/public-bid-agent/actions/runs/37921419837): **SUCCESS**. 최신 합성 HTML 4개 퍼블리싱 정적 검사, JS `node --check`, Vite 빌드, 기존 FastAPI pytest 정상.
- PR head `f1ffbbe1e981237e7615e803422998dad907f6a5`의 CI 산출물 ZIP `bid-management-ui-preview` (artifact `11611952655`)을 별도 확보, Chromium 브라우저에서 `page.set_content` 로드해 18개 조작 점검 **PASS**. 포함 항목: 빈 상태/메뉴/필수조건 근거 오류/6개 Gate+8개 인자/가중점수 80·100/가상 이익률 25%/사용자 결정 미변경/두 AI 미실행/기술·가격 배점 합계 거부/필수요건 실패 시 점수 미산출/공고별 입력 격리/브라우저 JS 오류 0/모바일 390px 가로넘침 없음.
- Chrome `file://` 접근은 컨테이너 정책상 차단돼 로컬 브라우저 자동시험은 `page.set_content` 방식이다. GitHub Pages 또는 사용자 실제 인터넷 브라우저/데이터 연동/인증 E2E 테스트를 의미하지 않는다.
- 영향인자 가중치 20/15/15/15/10/10/10/5 및 참여 검토 75·55 임계치는 *임의 퍼블리싱 시연 정책*이며 통계적 정확도나 실제 경쟁력·수익성 증빙이 없다.
- 여전히 `UI_PROPOSED / USER_FEEDBACK_PENDING`, AGY 독립 최종 의미 검수 `NOT RUN/REVIEW_DEBT`, `main` 병합/운영 배포 미실행.

## 2026-10-09 로컬 우선 JSON/AI 추출 전환 (최신 지시)

- 사용자: 영향인자를 직접 채우는 것이 아니라 **프롬프트·업로드 문서를 AI가 읽고 가정/근거/미확인 값을 초안으로 채운 후, 사람은 오류를 수정**하게 한다.
- 앱의 모든 상태·문서 추출 텍스트·AI 초안·수기 보정·사용자 최종 결정은 개인 PC JSON 파일에 저장한다. **로컬 저장이 AI 공급자 전송을 의미하지는 않으며**, 명시적 분석 시 선택한 공급자로 전송한다.
- 로컬 실행: Python 표준 라이브러리 localhost 앱 `local_app/server.py`, 접속 `http://127.0.0.1:8765/`, 저장 `~/.public-bid-agent-local/cases.json` (경로 환경 변수로 변경 가능). HTML/JS는 로컬 서버만 제공.
- 지원: text/markdown/csv/json 파일, pypdf PDF, python-docx DOCX (업로드 바이너리 미보관·추출 텍스트만 보관). HWP/HWPX/OCR 미지원. PDF/DOCX 파서는 현재 외부 비신뢰 파일 완전 격리 미구현.
- AI 실행: 실제 설치/로그인되어 있는 Codex CLI / Claude Code CLI 중 하나/둘을 선택하고 외부전송에 동의하면 제한된 서브프로세스로 요청 시도. AI 성공/실패/미설치를 구분하고 결과가 없는데 더미 결론을 만들지 않음.
- 로컬 단일 PC의 JSON에만 앱이 저장하지만 **Codex/Claude 도구 자체의 캐시·세션·원격 모델 제공자의 보존 정책은 별도**임. 절대 '전체 데이터를 오프라인에서만 처리'했다고 주장하지 않는다.
- AI가 만든 원문 근거/점수는 수기 확인 전 `verified=false`이며 사람이 기존 검증한 값은 자동 덮어쓰기 불가. 권고와 결정 별도.
- APMP 자료의 Go/No-Go·경쟁 우위·공고준비 비용·발주 목적·수익 및 조달청 계약 방식 검토를 반영한 8 Gate/12 비교 인자. 기준은 `docs/research/2026-10-09-local-first-ai-extraction.md`.
- 현재 단계: 신규 로컬 실행 MVP 코드 작성; CI/직접 브라우저 검증 및 사용자 승인/독립 리뷰는 별도 증거 전까지 **PENDING**. 이전 공개 웹 UI는 보존되고 본 변경으로 출시/공개 배포가 허용된 것이 아님.

## 2026-10-09 로컬 앱 구현 검증

- 최신 구현 커밋 `d097edc0652671d389d104bb32d5346ab65a37ef` — Python localhost Handler HTTP 속성 충돌 수정.
- GitHub Actions PR [37927086638](https://github.com/son1004007/public-bid-agent/actions/runs/37927086638): `success`, backend 기존 pytest, 로컬 JSON/HTTP unittest **8개 PASS**, frontend TypeScript/Vite 빌드 및 JS `node --check`, 기존 퍼블리싱 검사 PASS.
- 로컬 실행 ZIP: Actions run 37927086638 artifact `local-python-bid-agent` (ID 11613449792), source 6개 파일. 해당 ZIP을 내려받아 Python 3.13에서 unittest 8개 및 Node 문법 검사를 다시 통과.
- 로컬 Python 서버를 `127.0.0.1:8766`으로 실제 실행하고 직접 HTTP/JSON/CSRF 테스트는 성공. Chromium 환경에서는 localhost 직접 탐색이 플랫폼에서 차단됨(`ERR_BLOCKED_BY_ADMINISTRATOR`). 브라우저 화면 검사는 `set_content`와 모의 프런트엔드 fetch 결과로 분리 수행; 공고 생성/설명 저장/영향인자 입력 UI 등 핵심 UI 조작 성공, 모바일 390px 스크롤 가로 넘침 없음, page JS 오류 0. **실제 browser-to-localhost E2E 미검증**.
- 실제 Codex·Claude CLI 인증으로 수행하는 모델 분석은 **NOT RUN**. 이번 테스트는 실제 AI로 원문을 전송하지 않았으며 CLI 실행에서 계약/인증/JSON 생성 여부는 사용자 PC 검증 필요.
- 업로드 PDF/DOCX는 아직 완전한 별도 샌드박스가 없으므로 신뢰 불가능한 문서 처리는 개발 단계. 실제 기밀 회사 자료 운영 사용은 승인·보안 검수 전 HOLD.
- LangChain/RAG 및 LangGraph의 두 AI 상호 반론·상태 보존·중단/재개: **NOT IMPLEMENTED**. 현재는 독립 Codex/Claude 의견 요청과 사람 결정 분리용 MVP.
- 사용자 직접 UI 승인 `UI_PROPOSED`, AGY/Gemini 독립 최종 검수 `NOT RUN / REVIEW_DEBT`, `main` 병합/운영 배포 금지.

## 2026-10-09 실제 문서 형식 확장 구현

- 사용자 요구: 기존 UI는 유지하고 구현 단계로 진입. Excel(.xlsx/.xlsm/.xls), 일반 및 스캔 PDF 한국어 OCR, HWP 5.x, HWPX 지원.
- 코드: `local_app/extractors.py` (파일 형식 식별, ZIP 폭탄/크기/페이지 제한, PDF 텍스트+로컬 Tesseract OCR 자동 분기, Excel 시트별 셀 값, HWPX XML 본문, Apache-2.0 `python-hwpx`의 HWP 5.x 텍스트, DOCX 표 포함), `server.py` (별도 추출 subprocess + JSON 추출방식/경고 저장), `app.js`/`index.html` (UI 업로드 형식 및 경고 표시).
- 지원 범위: 파일당 10 MiB, PDF 40페이지/OCR 12페이지, Excel 최대 24시트·2500행·90열, ZIP 총 해제 35MiB/최대 750개 엔트리, 파일당 추출 텍스트 44,000자. 문서 전체를 무제한 분석했다고 주장하지 않음.
- OCR: Python 패키지 외에 Tesseract 실행 파일+한국어 `kor` 언어팩 사용자 PC 설치 필수. 모델 API를 통한 OCR이 아니라 **로컬 OCR**.
- 구형 HWP: `python-hwpx>=6.6,<7`의 HWP 5.x 파서 사용. 암호화/배포용/DRM HWP, HWPX 이미지/수식 등 한계. AGPL `pyhwp`는 직접 의존성으로 포함하지 않음.
- 코드/자동화: `local_app/test_extractors.py` 형식별 테스트, `local_app/test-requirements.txt` CI 테스트 의존성, 다운로드 아티팩트 업데이트.
- 이 변경은 업로드 바이너리를 업무 JSON에 저장하지 않고 추출된 텍스트·방식·오류경고·잘림 여부만 기록한다. Codex/Claude AI 전송은 사용자 명시 동의 이후 별개 경로.
- **검증 게이트:** GH CI 성공 여부/실 HWP·XLS 테스트는 실제 run evidence로 확인. 외부 악성 파일에 대한 완전한 OS 격리나 실제 사용자의 CLI 교차 검토/인증/정확도는 별도 미완료.

## 형식별 검증 및 파서 수정 (2026-10-09)

- 초기 CI HWP 테스트에서 python-hwpx의 TextExtractor가 ZIP HWPX 전용이라 실패. `HwpxDocument.open(path)`로 변경 후 HWP5 실바이너리 생성/재추출 테스트 통과 (커밋 `b5c1e176a5020717181620dcabf3b7a17688d6fb`).
- [GitHub CI 37932735254](https://github.com/son1004007/public-bid-agent/actions/runs/37932735254) push: frontend/backend SUCCESS, 로컬 문서 unittest 19개 중 18개 PASS + 1개 OCR Tesseract 미설치 skip. 실 HWP5·XLS 읽기 PASS.
- 로컬에서는 Tesseract+kor로 이미지 PDF OCR 시험 통과. CI에도 Korean Tesseract 설치 단계 추가하여 후속 run에서 19개 전부 검증하도록 함.
- 실제 다양한 기관 문서의 HWP 특수기능, 이미지 표/수식, OCR 숫자·표 재현율은 미검증. 중요한 사업 조건은 원문 직접 확인 필요.

## 최종 문서 파서 테스트 (2026-10-09)

- [GitHub PR CI run 37933016608](https://github.com/son1004007/public-bid-agent/actions/runs/37933016608): **frontend/backend SUCCESS**.
- `python -m unittest discover -s local_app -p 'test_*.py' -v`: **19 PASS / 0 SKIP**. 한국어 Tesseract 설치 후 스캔 PDF OCR, HWP 5.x 바이너리 생성/재추출, XLS 및 XLSX, HWPX, PDF, HTTP 파일 저장, ZIP 압축 제약 포함.
- CI의 `local-python-bid-agent` 산출물에 실행 코드, 의존성, README, 테스트 파일 모두 포함.
- 실제 기관별 대용량 RFP의 일부 이미지/복잡한 표, OCR 숫자 인식 정확도, 사용자 로컬 Codex/Claude CLI 계정 인증은 미검증. OS sandbox·AGY 독립 보안검수, 사용자 화면 승인, main 병합 및 인터넷 운영 배포도 별도 게이트.

## 2026-10-09 Python/라이선스 점검 및 로컬 2-AI 그래프

- 기준 인터프리터: CPython 3.12.x. GitHub Actions 3.12, `.python-version` 3.12, 루트/로컬 README 가상환경 명령 통일. 3.12.15 보안 릴리스는 source-only로 Windows 바이너리 설치 가이드는 공식 가용성 주의.
- 직접 의존성 Apache-2.0 호환성 점검: BSD/MIT/Apache-2.0/PIL MIT-CMU. PDFium 포함 패키지/전이 의존성 재배포 NOTICE는 별도 게이트. 공식 링크 `docs/DEPENDENCIES_AND_LICENSES.md`.
- `local_app/cross_review.py`에 실제 LangGraph StateGraph 독립 분석 → 상대 의견 재검토 최대 1회씩 → 기계적 이견/공통점 비교 로직 추가. LangChain Core ChatPromptTemplate 활용.
- `/api/analyze`는 사용자 동의 검증 후 그래프 실행. 분석 중 JSON 파일 lock을 놓고, 원문이 변경된 경우 오래된 결과를 거부. AI 결과는 미검증 초안이며 사용자 최종 결정 자동 변경 금지.
- UI에는 모델별 의견과 교차검토 이견/근거를 표시. 실제 모델 계정 연동/외부 요청 성공은 사용자 PC에서 검증 필요.
- 전체 구조/실행방법 루트 README에 기록, 코드 변경 커밋 시 루트·로컬 README 동시 갱신 CI 차단 규칙 적용 (`scripts/check_documentation_sync.py`).
- 새 테스트 결과/CI 상태는 해당 SHA의 실제 run 확인 후 표기, 독립 보안·사용자 최종 승인 미완료.

## 2026-10-10 Codex 전용 검증 개발

- Claude Code 유료 계정이 없는 환경을 지원하도록 Codex 단독 분석 모드 명확화. 기존 LangGraph의 단일 공급자 경로를 사용, 교차검토 상태는 만들어내지 않음.
- 회사 노트북 실제 테스트에서 Windows `shutil.which('codex')`가 npm extensionless shim을 선택해 WinError 193 확인. `codex.cmd` 사용으로 수정.
- 이어진 실제 CLI에서는 개인 기본 모델 `gpt-6.1-sol`이 ChatGPT 구독 인증 Codex에서 지원되지 않음을 확인. 사용자 설정을 변경하지 않고 프로젝트 호출에 `-m gpt-5.6-terra` 명시 및 임시 세션 `--ephemeral` 적용.
- 실제 Codex 호출·AI JSON 생성/저장 E2E는 별도 시험 결과 확인 필요. 회사 정보 없이 합성 입찰만 사용.

## 2026-10-10 회사 노트북 Codex 단독 실제 E2E 통과

- 사용자 계정에 Claude Code 유료 사용권이 없어 Codex 단독 모드를 실제 시험. 합성 가상 입찰공고만 사용, 회사 업무 자료 전송 없음.
- Windows Python 3.12 + Codex CLI 0.154.0 + ChatGPT 인증: 기존 npm `codex` 실행은 WinError 193, 기존 모델 `gpt-6.1-sol`은 Codex 인증에서 HTTP 400. 앱에서 `codex.cmd` + `gpt-5.6-terra` + read-only/ephemeral/user config 무시로 해결. 최소 JSON 원격 요청 직접 성공.
- 개발 브랜치 `778e2b047c09b7d3a488c7a8aa452d4809039c78` 회사 노트북 `PublicBidAgent\\Lab`에 fast-forward, Python 로컬 unittest **27 PASS**, Node 구문 검사 PASS, GitHub Actions PR run `37987914612` SUCCESS.
- 실제 HTTP `/api/new` → `/api/save` → `/api/analyze` (`providers=[codex],consent=true`) 성공, 약 21.2초. Codex 결과 `status=success`, `recommendation=hold`, Gate 8개 / Factor 12개, `ai_draft` 생성과 로컬 JSON 저장 확인. LangGraph `cross_review.status=single_or_failed`; 사용자 결정 `undecided` 보존.
- 테스트 서버 8769 중지. 실사용 로컬 서버 8765 실행, 바탕화면 `Public Bid Agent (Local)` 런처 별도 설치, HTTP 200 및 loopback 127.0.0.1 확인. 실사용 데이터 `%LOCALAPPDATA%\\PublicBidAgent\\Lab\\user-json\\cases.json`, 테스트 데이터는 별도 `codex-synthetic-test-data`.
- 실제 Claude 및 2-AI 교차검토 E2E 미수행, 보안 독립 최종 검수/회사 실무 문서 OCR 정확도 미완료. 대외 운영 또는 main 병합하지 않음.

## 2026-10-10 실제 공고 수기 표본과 평가 입력

- 나라장터 공고 3건 메타데이터/전재문을 공개 재게시 서비스에서 수기 확인: `R26BK01745574-000`, `R26BK01747372-000`, `R26BK01759604-001`.
- 공식 나라장터 공고 첨부 직접 다운로드 시 회사 노트북/컨테이너 환경에서 403 또는 접속 오류로 원본 검증 불가. 해당 자료는 `source_quality=third_party_republication`이며, 공고/원문 사실과 가상 업체 내부 상태를 별도로 기록.
- 가상의 부서 능력/법적 등록/인력/원가가 다른 시나리오 4개 작성. 모든 '가상 기업'은 사용자 실제 재직 부서에 관한 사실 진술이 아니다.
- 검증 fixture: `local_app/fixtures/public_tenders_2026_10_10.json`. 공고 원문 전재의 LLM 사업은 AI 코어 RAG 구현이 **과업 제외**, 운영·서비스 연동이 주로 요구됨. 하나의 재게시 출처에서 입찰마감 14:00 vs 공고 메타데이터 10:00 충돌하여 더 빠른 10:00으로 일단 가정하고 확인 필요.
- 현시점에는 아직 실제 공고의 Codex 판단 검증 결과를 작성하지 않음. 정상 호출 및 결과 비교를 수행한 뒤 채운다.

## 실제 공고 3건·가상 부서 4개 Codex 실분석 완료 (2026-10-10)

- PC 별도 합성 데이터 `public-notice-mvp-synthetic-data`에서 네 번의 실제 Codex 구독 모델 실행(사용자 계정, 합성 부서 조건만). 각각 18.7초/31.6초/27.0초/21.4초, CLI SUCCESS 4/4, Gate 8개·Factor 12개 출력 4/4, 미검증 ai_draft JSON 저장, 실제 사용자 decision=undecided 유지.
- R26BK01745574-000 가상 대기업: 참가 유형 불일치 등 AI가 필수 Gate 2개 실패를 추출했지만 `recommendation=hold`이고 `reason` 빈값.
- R26BK01747372-000 가상 약한 팀: 과학 시뮬레이션 인력 부족 Gate 1개 실패·보류. 동일 공고 가상 전문팀: 실패 Gate 0, 미확인 7, 보류.
- R26BK01759604-001 가상 클라우드팀: RFP 미확인으로 필수 Gate 모두 unknown, 평가인자 점수 0/12, 보류.
- 따라서 단순 model.recommendation으로는 참가 결격 위험과 증빙 부족을 차별화하지 못하는 결함 확인, `local_app/decision_support.py` 보수적 위험표시와 모델 사유 누락 감지/사용자 보정 후 재산정 도입.
- 미해결: 공식 G2B 원문 403(전재 자료 근거 한계), 모델 사유 빈값, 과거 낙찰 데이터 부재로 실제 '수주 확률' 예측 불가. 정식 독립 검수와 main 병합은 별도 판단.

## 2026-10-10 최신: 수기 공고 분석 완주 / MERGE HOLD

- 실제 공고 3건(수기 전사), 가상 회사·부서 조건 4개, 사용자 PC Codex AI 실행 4/4 SUCCESS. 결과 Y1 raw hold 4, 참고 Gate 위험: provisional no-bid 2 / 추가 증빙 hold 2, 사용자 Y2 undecided 4. 모델별 사유 문자열 전부 공란으로 안전 경고 노출.
- `decision_support.py` UI 및 백엔드 GET/POST 로컬 HTTP 재검증 4/4 PASS, 36개 Python 회귀 테스트, GitHub CI run 37997843667 SUCCESS.
- 사용자용 Windows 로컬앱 8765 `[검증 사례·실제공고/가상 업체]` 4개 데이터 이관, JSON 백업 수행 후 HTTP 200/4건/127.0.0.1 확인. 실제 사용자 회사 데이터는 사용하지 않음.
- 공공 공고의 공식 원본 첨부 403, 재게시 마감 충돌, Codex 판단 근거 부족 및 AI 원시 reason 누락 한계 남음.
- AGY/Gemini 및 Codex의 독립 최종 코드 검수가 원격 read-only command 권한 차단으로 미완료. 별도 유효 review 결과 없음. 글로벌 정책상 `REVIEW_DEBT / MERGE HOLD`로 남기며 위험 권한 우회 금지.
- 상세 재현 기록: `docs/reviews/MVP_PUBLIC_BID_E2E_2026-10-10.md`. 다음 작업: 안전한 독립 검수 해결→필요시 수정/재검수→main 병합→자동 수집 Sprint.

## 2026-10-10 독립변수 확인 UX 개선

- 4건의 로컬 가상부서 분석 데이터 재확인: AI `ai_draft`에는 모든 8 Gate와 12 Factors의 제안 및 근거가 존재하나 수기 `factors`에는 아직 score가 저장되지 않아 기존 UI는 'AI 초안 적용' 전까지 공백을 보여주었음.
- 기존 데이터에서 **위험 통제 risk 점수의 방향 역전**을 발견: 수행위험이 매우 높다는 근거인데 5점으로 반환된 사례가 있었음. 과거 결과는 변경하지 않고 미검증 상태로 둠. 신규 AI 프롬프트에 risk/bid_cost 등 모든 Factor 5점=유리한 상태 및 reason 필수 안내 추가.
- 화면에 `AI 독립변수 20개 및 추출 근거 (읽기 전용, 미검증)`를 추가해 공고 선택만으로 원본 Gate/Factor/근거 표시, 사용자 편집/결정에 부작용 없음.
- 변경의 CI/PC 실제 응답 검증 및 독립 최종 검수는 해당 변경 SHA별 실행 증거 확인 필요.

## 2026-10-10 팀장용 독립변수 입력문서 가이드 추가

- 기존 8 Hard Gates/12 Soft Factors를 외부발주 자료(입찰공고/RFP)와 실제 회사 보유 자료(입찰자격/실적·인력/원가·제안계획)의 **5개 문서 묶음**에 연결. 문서별 보유 담당자, 예시, 누락 시 요약 방안, 정보 등급, 20변수별 확인 질문 포함.
- 단일 데이터 사전 `local_app/document_guide.json`, 앱 첫 화면(공고 선택 전에도 접근)에서 독립변수→필요 문서/미확인 질문 가이드. 서버 GET `/document-guide.json`, 사용자별 상태 변경/모델 호출 없음.
- 안내 목적만 구현: 자동 문서 종류 식별·출처 인용 정합성·자동 문서 체크리스트 작성은 미구현. 실제 내부자료를 개인 ChatGPT/Codex에 전송하지 않고 허가/비식별 수기요약을 안내.
- CI artifact에 문서 매핑 및 현재 실제 실행에 필요한 decision_support.py 등 파일 포함하도록 패키징 경로 수정.
- 새 변경의 Windows 로컬/CI 증거 및 독립 코드 검수 결과는 확인 후 별도 기록. 기존 Draft PR main 병합 HOLD 유지.

## 2026-10-10 회사 운영정보/원가계산 단위 구현

- 회사 운영정보를 재사용 가능한 별도 로컬 `operations.json`으로 설계. role/MM 단가·가용, 간접비율·위험충당률 입력. 초기값은 **빈 직무 목록(실회사 정보 없음)**; 가상 fixture로 검증.
- 공고별 투입 MM·외주비·경비·제안준비비·공급가(VAT 제외), 수익/이익률 계산 엔진 추가. revision 동시 수정 충돌(409), 이전 견적 기준 버전 표시, 용량/입력값 엄격 검증, 원가 데이터 LLM 자동 전송 금지.
- 이번 수직 슬라이스의 실행·검수 결과는 실제 검증 후 확인할 것. 기존 수기 실공고 검증·입찰 최종 결정 기록은 변경하지 않음.
- 회사 원가/직원 개인 급여를 실데이터로 저장하거나 외부 전송하지 않았음. 보안 정책 승인 이전에는 가상 프로필만 사용.
- 기존 독립 리뷰 미완료로 main Draft PR HOLD 유지.

## 2026-10-10 운영 장부 범위 확장

- 원가 기준 외에 회사 영업·수행·재무·인력/협력사 운영자료 8종 수집/확인 메타데이터 관리(`registers`) UI와 JSON 모델 구현. 원본 파일/개인급여는 수집하지 않고, 담당 부서·비식별 요약·출처 문서명·검증일만 보관. 수집/요약 완료를 구분.
- 실제 회사정보는 입력하지 않으며 자동 Codex 전송하지 않음. 사용자 판단과 원가계산은 운영자료 요약에 따라 자동으로 변화하지 않는다.

## 2026-10-10 개발 브랜치 CI 회귀 관리

- 운영자료 날짜 검증 정규식의 잘못된 이스케이프를 로컬 실패 테스트로 발견·수정. 이어진 코드 한 줄짜리 fix 커밋이 루트/로컬 README 동시 변경 의무를 지키지 않아 push CI의 README gate 실패 확인(동일 SHA PR CI는 SUCCESS).
- 이 의미 있는 날짜 보정/추가 테스트 변경에서 두 README를 함께 갱신해 push CI 재검증. 과거 workflow failure 기록은 삭제/숨기지 않음.

## 2026-10-10 운영정보 원가/8종 운영자료 실제 검증 결과

- `ops-cost-synthetic-e2e` 합성 데이터에서 기준정보 revision 0→1→2, 인건비 27,000,000원, 예상 총원가 37,805,000원, 이익 12,195,000원(24.4%), 원가 재산정 구버전 상태 및 CSRF 필수 보호 검증. 인가되지 않은 실제 회사/고객 데이터 입력 없음.
- 추가 8종 자료 메타데이터(재무 reviewed, 파이프라인 needs_refresh, 나머지 미확인 6개) 로컬 저장 성공. 초기 사용자용 운영정보는 여전히 비어 있음.
- Windows 50개 unittest PASS, JS syntax PASS, GitHub push CI 38040046052 및 PR CI 38040049212 SUCCESS. CSRF 경계 테스트 1회 WinError 10053 간헐 실패 기록, targeted/full 재실행 PASS (관찰 필요).
- 실제 사용자 로컬 앱 8765 재시작, 기존 4개 합성 공고·최종결정 보존, UI HTML·JS·8종 운영자료 제공 200·loopback 확인. 브라우저 실제 인터랙션/레이아웃 검수는 NOT RUN.
- 상세 [운영정보 E2E 보고서](docs/reviews/OPERATIONS_COST_E2E_2026-10-10.md). AGY/독립 Codex 의미 검수 미완료로 Draft PR #1 및 main merge HOLD.

## 2026-10-10 새 화면 요구 반영: 공고 목록 중심 UX

- 사용자 요구: AI·데이터분석 공고를 정기 수집 → 목록에 표시 → 사용자가 버튼으로 참여여부 판별 → 판단기준과 8+12 영향인자를 별도 버전형 프로필로 저장 → 불참 항목의 이유/근거·사용 프로필·판단 이력 확인.
- 퍼블리싱 단계 구현: `frontend/public/bid-decision-dashboard-preview.html` (HTML/CSS/JS 정적, 백엔드 의존 없음), 기존 로컬앱 `/decision-preview` 경로와 첫 화면 안내 링크. 리스트·단건/일괄 판단·가상 수집·두 프로필 편집 및 가중치 검증·이력 필터·불참 근거 상세·반응형. 모든 데이터 합성/메모리 임시이며 수집·판별·영구저장·AI 연동은 실제 구현하지 않음.
- 사용자에게 먼저 화면 확인 요청. UI_APPROVED 아님. 실제 나라장터 수집 스케줄러, 실제 프로필 DB/JSON 모델, 검증 가능한 법적 Gate, 실제 입찰 참여 최종결정 이력은 차기 스프린트로 보류.

- 시안 코드 자동검증 1차에서 새로고침 안내 문구와 테스트 불일치 발견. 수정하면서 12개 Factor 가중치 프로필이 화면의 재판별에 실제로 반영되도록 가상 weightedFit() 시뮬레이터를 추가하고, 불참 최종결정에 별도 담당자 사유 입력을 요구하여 기록을 분리함. 사용자 검증 전까지 MOCK_ONLY.

- 독립 시안 Chrome headless DOM에서 공고 목록/프로필이 초기 렌더링되지 않는 결함 발견: 기존 로컬 서버의 CSP `script-src 'self'`가 HTML 인라인 코드를 차단. 보안 헤더를 완화하는 대신 별도 JS로 분리하고 로컬 동일출처 GET 라우트를 추가. 브라우저 실행 검증 진행 상태는 별도 기록.

## 2026-10-10 공고 의사결정 UI 퍼블리싱 최종 동작 상태

- 사용자 요청대로 목록 중심·정기 수집 계획·단건/일괄 판단(가상)·참여 판단 기준 Profile·8 Gate/12 Factor Profile·불참 사유 및 판단 이력 5개 영역을 정적 HTML+외부 JS로 구현.
- Windows Node JS 구문 검사 PASS, 정적 시안 Python 검사 3개 PASS, 실제 Chrome headless DOM 8개 공고행/5개 KPI/12개 가중치 컨트롤 생성 PASS, localhost /decision-preview HTTP 200, CSP 유지. GitHub push/PR CI 38049729286/38049733578 SUCCESS.
- 전체 Windows Python 53테스트 수행 중 기존에 반복된 CSRF negative-case URLopen WinError 10053 2개가 간헐 발생. 시안 범위 별도 테스트는 PASS; 기존 Windows 로컬 HTTP test 간헐 실패 추적 지속.
- Chrome headless에서 기본 렌더링을 확인했으나 실제 사용자 클릭 기반 브라우저 자동 E2E와 UI_APPROVED는 NOT RUN. 기존 로컬 JSON 사례는 시안 GET 동작으로 수정되지 않음. merge HOLD, 백엔드 기능은 UI 확인 후 구현.

## 2026-10-10 공고 전체 상세 화면 시안

- 사용자 요청: 공고 목록에서 상세보기 눌렀을 때 실제 어떤 내용이 표시되는지 구현. 별도 `view-full-detail` 화면, 4개 탭(기본/참가자격·과업/영향인자·사업성/결정·불참·이력), 원문·첨부 미수집 표시, 공고·프로필 동일 합성 상태로 목록/상세/이력 흐름 연결.
- 상세보기 자체는 단순 렌더링이며 AI/수집/서버 저장·판단 상태변경 없음. 실제 자동수집과 모델 분석·원문 증빙·프로필 서버 저장은 여전히 미구현. 화면 시연 데이터는 브라우저 탭 메모리만.
- 새 상세 화면의 테스트/브라우저 클릭 검증은 변경 후 확인하여 기록. main 병합 미실시, 독립 의미·보안 검수 필요.
