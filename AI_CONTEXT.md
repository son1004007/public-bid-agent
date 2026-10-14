# AI 개발 작업 안내 - Public Bid Agent

> **다른 AI/Codex가 이 저장소를 처음 읽을 때**
>
> 1. [AGENTS.md](AGENTS.md)와 전역 `son1004007/ai-agent-workflow-playbook/CONTROL.md` (보안·검수·구현 기준)
> 2. **[DECISIONS.md](DECISIONS.md)** (사용자의 확정 의사결정, 명시적 제외 범위, 다음 단계 승인 경계)
> 3. [CURRENT_STATE.md](CURRENT_STATE.md) (시점별 구현/검수·로컬 반영 증거), [TASKS.md](TASKS.md) (남은 작업)
> 4. 실제 저장소 `feat/sprint1-search-demo`의 최신 소스·커밋·CI 및 로컬 실행 상태
>
> 과거 파일의 오래된 수치보다 최신 실행 증거가 우선이다. **결정사항은 DECISIONS.md를 단일 원본으로 관리하며, 시점별 수치와 검수 결과를 사용자 결정으로 오해하지 않는다.**

## 1. 현재 프로젝트/실행 아키텍처

- 목적: 공식 나라장터 용역공고 전체 수집 → 공고 상세/RFP 추출·분석 → 실제 부서의 입찰자격·실적·기술·인력·원가와 비교 → 사람의 참여 결정·제출·평가·수주 추적을 지원하는 근거 기반 웹서비스.
- **현 기준 웹:** `http://127.0.0.1:8765/decision-preview`; `local_app/server.py` (Windows CPython 3.12, 127.0.0.1 전용) + `frontend/public/bid-decision-dashboard-preview.html` + `frontend/public/dashboard-live.js`. 현재 비공개 로컬 JSON 데이터와 SHA 결속 RFP 캐시 사용.
- `frontend/` React와 `backend/` FastAPI 코드는 별도 개발·시안 자산이다. 실제 인터넷 공개 서비스/Google 로그인/원격 계정·다중 사용자는 아직 운영 중이지 않다.
- 서비스 로컬 데이터는 비공개 사용자 PC에 두며, 회사 문서/인력·원가/DPAPI API 인증키를 GitHub나 Codex 검수 입력으로 전송하지 않는다.
- 기존 LangGraph와 Codex/Claude CLI 수동 교차 검토는 제한적 별도 기능으로, 모든 공고에 실제 LLM 기반 AI 추천이 서비스된다는 뜻이 아니다.

## 2. 날짜·검증 단위를 명확히 구분한 현황

### 2026-10-15 RFP 원문 우선 UI 개선 (D-15)

- 사용자 요청에 따라 RFP 요구사항 표현 후보는 전체 너비 원문 세로 목록으로 보여 주고, 원본 파일·SHA-256·추출 문자 위치 등은 각 항목별 기본 접힌 네이티브 `details/summary`에서만 펼쳐 본다. 다른 `requirementRow` 기능/API/원본 자료는 변경하지 않음.
- 실제 Windows Chrome 공식 공고 → 상세 → RFP 구조화: 원문 후보 31건, 메타정보 접힘 31/31, 펼치기·접기 PASS, 모바일 390px 가로 넘침 없음. Python 전체 274 PASS, 비공개 파일 164/164 SHA-256 기존 기준값과 일치. **Codex 신규 UI 변경 독립 검수 1차 NO_GO CSS 격리 지적 수정 후 2차 GO**. [UI 변경·검증](docs/reviews/RFP_ORIGINAL_FIRST_UI_2026-10-15.md).

### 2026-10-15 최신 로컬 운영 및 검증

- **로컬 서버·실제 Chrome 검증 완료:** `TD-kiseok`의 기존 로컬 시작 스크립트로 127.0.0.1:8765 기동. 공식 공고 3,777건(CURRENT 3,263/CANCELLED 201/SUPERSEDED 313), STALE RFP 10건. RFP fulltext 참조가 있는 현행·비STALE 공고 65건.
- RFP 요구사항 구조화 읽기 전용 GET에서 8개 유형/원문 표현 후보 31개/출처 문서 1개, 파일 SHA 및 추출 문자 위치, `page=null`, 법적 적격 `UNVERIFIED` 확인. 취소·구차수·STALE 분석 보류 및 잘못된 ID 처리 확인.
- **Chrome 실제 UI:** 공고 목록→상세→참가자격·과업→RFP 요구사항 근거 조회 버튼과 출력 PASS. 모바일 390px PASS. 비공개 JSON 40개 + RFP 캐시 124개 **SHA-256 164/164 동일**, Python 전체 **274 PASS**, JS·문서 동기화 PASS, Codex 독립 GO, GitHub CI 성공.
- **상태:** `LOCAL_APPLIED` + `CHROME_E2E_VERIFIED`. 사용자 화면 최종 승인, `main` 병합, 인터넷 공개, 다음 Stage 2와 보류된 7일 API 실패 원인 조사는 미수행. [실제 검증 보고](docs/reviews/RFP_STAGE1_LOCAL_ACCEPTANCE_2026-10-15.md).

### 2026-10-13 실제 로컬 운영에 반영된 사실 (당시 기록)

- 공식 공고 저장 **3,049건**: `CURRENT 2,653`, `CANCELLED 167`, `SUPERSEDED 229`. 정정/취소 반영 뒤 구차수와 취소 공고를 기본 추천에서 제외했다.
- 중요 메타 변경으로 원문 확인이 필요한 RFP `STALE 8건`: 원문·판단·이력 보존, 재확인 전 추천/구조화 보류.
- 매일 오전 09시 Windows Task Scheduler (`PublicBidAgent-OfficialCollection`)가 현재 사용자 로그인 조건으로 등록됐다. **첫 예약 실행의 성공 여부는 현재 연결된 PC에서 재확인**해야 한다. 첫 7일 수집 실패 원인 진단은 사용자가 명시적으로 제외했으며 같은 문제가 다시 발생한 경우에만 별도 논의한다.
- 현재의 규칙 기반 추천은 상세 검토 순위이고 법적 입찰 가능·수주 확률·회사 적격성 확정이 아니다.
- 근거: [정정·취소 확인](docs/reviews/OFFICIAL_AMEND_CANCEL_LOCAL_VERIFY_2026-10-13.md), [자동수집](docs/reviews/AUTO_G2B_COLLECTION_2026-10-13.md).

### 2026-10-13~14 RFP 요구사항 구조화 1단계: 당시 소스 검수 기록

- `local_app/rfp_requirements.py`: 공식 첨부 identity/원본 SHA-256/개인 PC의 44,000자 RFP 청크에서 **8개 유형의 원문 표현 후보** 추출; 누락/절단 경고와 추출 텍스트 시작·끝 offset, `page=null` 반환.
- `GET /api/dashboard/rfp-requirements?id=...` / 상세 화면 `RFP 요구사항·출처 근거 확인` 버튼 추가 개발. 취소·구차수·STALE 공고 분석 보류, AI 추론/법적 필수요건 확정 없음, 소스 저장·외부 전송 없음.
- 실제 비공개 데이터 **후보 66건 중 균등 20건** 샘플: 원문 표현 후보 **561건**, 텍스트 일부 보존 4건, 오류/0건 0. 구체적인 문서 내용은 공개 repo에 기록하지 않았다.
- **Windows 회귀 274 PASS, Codex NO_GO 지적 3종 수정 후 독립 최종 GO** (신뢰된 개인 Windows localhost 전제). 소스·테스트 검수와 **실제 PC 서버 재시작/브라우저 새 버튼 확인/로컬 적용**은 서로 다르며 뒤 항목은 2026-10-15 최신 로컬 검증 절에 확인 결과가 기록됐다.
- 근거: [설계](docs/design/RFP_REQUIREMENTS_SLICE_2026-10-13.md), [대표 20건 검증](docs/reviews/RFP_REQUIREMENTS_LOCAL_EVIDENCE_2026-10-13.md), `local_app/test_rfp_requirements.py`.

## 3. 현재 승인/보류 범위

- **결정됨:** RFP 구조화 1단계를 실제 근거와 함께 검증한다. 원본 페이지나 확정 참가요건을 만들어내지 않는다. 직전 자동 수집 API 오류 진단을 선제 진행하지 않는다.
- **사용자 다음 결정 대기:** 부서 역량 비교, LangGraph/RAG 기반 의미 추천, STALE 8건의 안전 재검증, 공식 변경이력/별도 공고번호 재공고 매칭, 인터넷 공개·멀티유저.
- 소스 변경 시 루트와 `local_app/README.md` 동기화, 애자일 작은 구현 단위·합성/실제 자료 분리 검증, **Codex만 독립 검수**를 적용한다. 사용자 승인 전 `main` 병합·전체 인터넷 릴리스 선언을 하지 않는다.

## 4. 이전 날짜 기록을 읽는 기준

과거 문서(예: 2026-10-09~12)의 `공고 2,223건`, `자동 수집 미구현`, `정정/취소 미반영`은 **당시 시점 기록**이다. **현재 상황으로 재사용하지 말 것.** 최신 사용자 결정은 `DECISIONS.md`, 실행 상태는 `CURRENT_STATE.md`, 다음 단계는 `TASKS.md`와 실제 repo/CI/PC 증거로 판단한다.
