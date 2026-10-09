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
