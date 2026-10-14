# RFP 요구사항 구조화 1단계: 개인 Windows PC 로컬 실제 적용·검증

- 수행일: 2026-10-15, Asia/Seoul
- 실행 장치: `TD-kiseok` (Windows 개인 PC; 공개 서버 아님)
- 개발 브랜치: `feat/sprint1-search-demo`, 적용 코드 `e02dfbc` 및 문서 fast-forward `3a7fb51`.
- 사용자 결정: [DECISIONS.md](../../DECISIONS.md) D-10(7일 API 실패 사전 진단 제외), D-11(Stage 1), D-12(다음 단계 사용자 결정).
- **결과: 읽기 전용 RFP 구조화 API와 실제 Chrome E2E 로컬 적용 PASS. 사용자 UI 최종 승인, `main` 통합, 인터넷 공개는 별도.**

## 1. 작업 시작 전 확인

- 2026-10-15 06:45경 Remote Desktop Commander에서 `TD-kiseok` Online 확인.
- 로컬 저장소 원래 `e02dfbc`, Git 작업 트리 깨끗함. 원격 브랜치에는 이후 문서 2개 커밋만 추가되어 `git fetch` 후 `git merge --ff-only`로 `3a7fb51` 반영; 소스 변조·강제 덮어쓰기 없음.
- 포트 `127.0.0.1:8765`의 LISTEN 프로세스가 없어, 이미 존재하던 개인 PC의 `start-public-bid-agent.cmd`를 사용해 로컬 서버를 기동. 서버의 JSON 저장 루트·개인 키 설정은 기존 설정 유지.
- 작업 전에 비공개 개인 PC 파일 **로컬 JSON 40개와 RFP `rfp_fulltext` 캐시 124개, 총 164개** 각각의 SHA-256 기준값을 **PC 임시 파일에만** 저장. 공개 GitHub에 데이터·키·원문 내용·절대경로/해시 목록을 기록하지 않음.
- **시점별 실측:** 실제 저장 공고 `3,777건` (이전 3,049건은 10월 13일 당시 기록이며 지금 수집 증분과 세부 변동 원인은 이번 단계에서 별도 조사하지 않음).

## 2. 실제 개인 PC 데이터 기반 HTTP 검증

- `GET /api/dashboard`, `GET /api/dashboard/recommendations`, `GET /api/dashboard/rfp-coverage`: 각각 **200**.
- 현재 공고 중 `notice_lifecycle=CURRENT`, 비STALE, RFP 추출 완료이고 `fulltext_ref`가 있는 **65건**을 식별. 실제 원문 캐시가 존재하고 출처 검증을 통과한 한 공고로 `GET /api/dashboard/rfp-requirements?id=...` 검증.
- 실제 반환은 `schema_version=1`, `RULE_BASED_TEXTUAL_EVIDENCE_ONLY`, **8개 카테고리**, 원문 근거 표현 후보 **31건**, 출처 RFP **1개**. 원본 PDF/HWP 페이지를 추정하지 않고 `page=null`, 추출 문자 offset 및 원본 SHA를 제공하며 회사 법적 참가자격은 `UNVERIFIED`로 유지.
- `CANCELLED`와 `SUPERSEDED` 공고는 `EXCLUDED_NOTICE` 반환, `STALE` 현행 공고는 `STALE_RFP`로 분석 보류. 잘못된 ID **400**, 없는 공고 ID **404**.
- 위 결과는 원문 관련 단어/표현 후보 탐지이지 법적 참가·업종 충족·기술 수행능력·적정 예산을 검증한 것이 아님. `rfp_review_status=STALE` 8건의 자동 해제도 수행하지 않음.

## 3. 실제 Google Chrome 브라우저 수직 E2E

Windows에 설치된 Chrome을 별도 임시 사용자 프로필/headless CDP로 실행해 아래 실제 사용자 흐름을 확인.

1. `/decision-preview` 렌더와 실제 공고 3,777건 표시: **PASS**.
2. 수집관리 화면 및 기존 RFP 순차 분석 패널 접근: **PASS**.
3. 공고 목록의 `전체 상세보기` 버튼 클릭 → 전체 상세 화면: **PASS**.
4. 검증 가능한 실제 공식 RFP가 연결된 공고의 `참가자격·과업 확인` 탭 → **`공식 RFP 요구사항 구조화` 패널 표시: PASS**.
5. `RFP 요구사항·출처 근거 확인` 버튼 실제 클릭 → `EVIDENCE_CANDIDATES`, 출처 및 문자 위치 관련 문구 렌더: **PASS**.
6. 브라우저에서 대시보드·추천·RFP-coverage GET: **200/200/200**.
7. 모바일 에뮬레이션 너비 `390px`에서 문서 가로 넘침 없음: **PASS**.
8. 기존 홈 화면 정상 렌더: **PASS**.

원문 실제 발췌나 개인/회사 정보는 공개 검증 로그에 싣지 않음.

## 4. 데이터 무결성

- 초기 SHA-256 기준값 대비 브라우저/API 분석 뒤 다시 파일 내용 전부 SHA 계산:
  - **40개 비공개 JSON 40/40 일치**.
  - **124개 RFP fulltext 캐시 124/124 일치**.
  - 추가·삭제·내용 변경 **0건**. API 및 화면 검증은 READ_ONLY.
- 원본을 자동 이관하거나 재추출하지 않았고, 사람 결정·RFP 텍스트·과거 이력을 덮어쓰지 않음. 등록 API 키와 저장 data root 설정 변경 없음.

## 5. 테스트·Codex 검수·릴리스 경계

- 소스 버전 `e02dfbc`: 이전 Windows CPython 3.12 전체 **274 PASS**, RFP 전용 16 PASS, 독립 Codex 1/2차 NO_GO 지적 보완 뒤 3차 **GO**, GitHub Actions CI 성공. 현재 PC의 동일 코드로 로컬 서버/Chrome 실제 검증.
- 2026-10-15 Windows CPython 3.12 전체 회귀 **274/274 PASS** (108.156초), `node --check frontend/public/dashboard-live.js` **PASS**, `scripts/check_documentation_sync.py` **PASS**. 독립 Codex 최종 GO와 GitHub CI 코드 검증 성공 확인. 출처 코드 변경이 없는 문서 추가는 이전 Codex GO 변경 범위 밖의 새 런타임 행위가 없음.
- **로컬 기능 `LOCAL_APPLIED` / `CHROME_E2E_VERIFIED`**, 단일 사용자 개인 Windows localhost 환경에서만 확인.
- **`USER_UI_APPROVED`는 아님**: 사용자가 브라우저 화면을 직접 확인하고 다음 방향을 정해야 한다.
- **`MAIN_MERGED` / `PUBLIC_RELEASED`는 아님.** 공개 인터넷 인증/멀티유저/직접 입찰 제출·외부 AI 자동 추천 기능은 범위 밖.
- 7일 공식 API 일시 실패 원인 조사, 예약 수집 고장 진단, STALE 8건 재검증, 2단계 부서 적격/역량 비교, RAG/LangGraph 의미 검토는 이 단계에서 수행하지 않음.

## 재현 및 참고 문서

- [결정사항](../../DECISIONS.md)
- [RFP 구조화 설계/근거](../design/RFP_REQUIREMENTS_SLICE_2026-10-13.md)
- [Codex 검수](RFP_REQUIREMENTS_CODEX_REVIEW_2026-10-14.md)
- [이전 온라인 복구 후 작업 체크리스트](../implementation/RFP_STAGE1_LOCAL_ACCEPTANCE_2026-10-15.md)
- 테스트 `local_app/test_rfp_requirements.py`, HTTP `GET /api/dashboard/rfp-requirements?id=...`.
