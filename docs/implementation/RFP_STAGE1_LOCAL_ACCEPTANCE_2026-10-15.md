# RFP 요구사항 구조화 1단계: 로컬 적용·인수 검증 체크리스트

- 기준일: 2026-10-15 (Asia/Seoul)
- 대상: 개발 브랜치 `feat/sprint1-search-demo`, 검증 완료 코드 `e02dfbc`
- 사용자 결정: [DECISIONS.md](../../DECISIONS.md) D-10~D-12. **7일 공식 API 오류 분석 제외**, Stage 2 자동 진행 금지.
- 현재 상태: `IMPLEMENTED + TESTED + CODEX_REVIEWED + GITHUB_CI_SUCCESS`. **`LOCAL_APPLIED` 및 `CHROME_E2E_VERIFIED` 아님.**
- 미완료 사유: 2026-10-15 05:45 KST에 개인 PC `TD-kiseok` Remote Desktop Commander가 Offline (마지막 연결 약 5시간 전) 상태여서 서버 제어, 보존 데이터 점검 및 실제 Chrome 클릭을 실행할 수 없었다. SynologyNAS는 온라인이나 Windows 개인 PC 환경을 대체할 수 없음.
- GitHub Actions [e02dfbc CI 성공](https://github.com/son1004007/public-bid-agent/actions/runs/38468571311).
- Windows CPython 3.12 전체 회귀 274 PASS, RFP 구조화 16 PASS, 독립 Codex 세 번째 검수 GO (신뢰된 개인 Windows localhost 범위). GitHub CI 성공은 실사용 로컬 적용을 뜻하지 않는다.

## 1. PC 온라인 복구 뒤 실행할 순서

### A. 최신 커밋/서버/스케줄 확인 (읽기 전용)

1. 연결된 `TD-kiseok`에서 프로젝트 Git 작업 디렉터리의 `git status --porcelain`, `git branch --show-current`, `git rev-parse HEAD`를 확인한다. 원격 `feat/sprint1-search-demo`의 `e02dfbc` 이상이 실제 PC에 있는지 확인한다. 더 새 변경이 있으면 덮어쓰지 않고 재확인한다.
2. `127.0.0.1:8765` LISTEN 프로세스의 PID와 실제 명령행이 이 저장소 `local_app/server.py`인지 확인한다. 다른 프로세스를 종료하지 않는다.
3. Windows Task Scheduler `PublicBidAgent-OfficialCollection`의 실동작/최근 변경 및 비공개 사용자 원본 JSON revision을 확인한다. API 오류 원인 분석은 사용자 요청으로 제외한다.
4. `%LOCALAPPDATA%/PublicBidAgent/Lab/user-json`에 있는 모든 JSON과 `rfp_fulltext` 청크 캐시의 SHA-256 매니페스트 및 필요시 별도 백업을 확보한다. 공개 GitHub에 해시 원본 파일, 경로, 문서명, 키, 사용자 정보 등을 기록하지 않는다.

### B. 실제 서버 변경 (사전 검수 범위만)

1. 현재 정상 서버의 운영 코드를 추적하고 Git 코드를 `feat/sprint1-search-demo` 최신 **검수된 버전**과 비교한다. 예기치 않은 변경/잠금/보관 자료 차이가 있으면 중단한다.
2. 자동 수집 스케줄러와 동시 저장을 방지할 수 있는 타이밍 및 기존 코드의 잠금·저널 안전 계약을 지킨다. JSON을 migration/backfill하지 않는다.
3. 서버 프로세스 명령행으로 PID 소유를 확인한 후 **해당 프로젝트 소유 프로세스만** 종료하고 기존 `start-public-bid-agent.cmd`로 재시작한다. 원본 JSON 및 RFP 청크를 직접 수정하거나 삭제하지 않는다.
4. GET `/`, `/decision-preview`, `/api/dashboard`, `/api/dashboard/recommendations`, `/api/dashboard/rfp-coverage`가 정상 응답인지 확인한다.

### C. 읽기 전용 GET·실제 Chrome 수직 E2E

1. `GET /api/dashboard`에서 공식 공고 중 **현행, RFP 추출 상태 EXTRACTED, rfp_review_status != STALE, source attachment/fulltext_ref 검증 가능한 공고**를 새로 선택한다. 2026-10-13 당시 수치(3,049건/66개 후보)는 시점별 기록이며 고정 ID를 재사용하지 않는다.
2. `GET /api/dashboard/rfp-requirements?id=<선택한 ID>`를 요청해 `requirements.schema_version=1`, `analysis_mode=RULE_BASED_TEXTUAL_EVIDENCE_ONLY`, 카테고리 8개, `page=null`, 원본 SHA 및 추출 텍스트 `offset_start/offset_end`, 부분 자료 경고, `legal_eligibility=UNVERIFIED`를 확인한다.
3. `/decision-preview` 실제 Chrome에서 목록 → 상세보기 → `참가자격·과업 확인` → `RFP 요구사항·출처 근거 확인` 버튼 클릭. 표현 후보와 파일명·SHA·문자 위치가 표시되고 원본 페이지/필수 자격을 확정하지 않는지 확인한다.
4. 취소/구차수/STALE 공고는 API가 `EXCLUDED_NOTICE`/`STALE_RFP`을 반환하며 RFP 원문 요건을 확정하지 않는지 확인한다. 무결성 오류·공고 없음·잘못된 ID는 명시적 오류여야 한다.
5. 기존 공고 목록·상세보기·수집관리 패널과 모바일 폭 390px 렌더링이 정상인지 함께 검증한다.

### D. 불변성 확인과 문서 완료 처리

1. A의 읽기 전용 원본 SHA 목록과 C 이후 private JSON 및 RFP 캐시 SHA를 비교한다. 자동 공식 수집이 병행하여 합법적으로 변경한 JSON이 있다면 해당 revision과 의도된 변경을 구분하고 단순 해시 불일치를 곧바로 사용자 데이터 훼손으로 단정하지 않는다.
2. `test_rfp_requirements.py` 포함 전체 CPython 3.12 회귀, `node --check frontend/public/dashboard-live.js`, `scripts/check_documentation_sync.py`를 실행하고 결과를 별도 공개 가능한 비식별 보고서에 기록한다.
3. Codex GO의 코드 범위를 벗어난 실제 변경이 있으면 별도 Codex 독립 검수 후 적용한다. 이번 읽기 전용 배포의 중단/복원 경로를 남긴다.
4. `CURRENT_STATE.md` / `TASKS.md`에서 **검증 증거가 확보된 항목만** `LOCAL_APPLIED` / `CHROME_E2E_VERIFIED` / `USER_UI_APPROVED` 상태로 변경한다. 사용자 UI 승인 없이 승인되었다고 기록하지 않는다.

## 2. 변하지 않는 의미/보안 규칙

- 이 기능은 정규식 기반 **8개 범주의 원문 표현 후보 탐지**, 의무/선택·법적 참가자격·실적·인력/원가·수익성의 최종 판정이 아니다.
- 공식 첨부 URL+파일명 identity와 문서 원본 SHA-256, RFP 캐시 SHA, 증거 파일명/추출 문자 위치를 결속한다. 원본 PDF/HWP 페이지 번호가 없다면 `page=null`.
- 공식 첨부 최대 400, 추출 증거 기록 최대 120, 실제 분석 문서 최대 2개. 초과 시 `PARTIAL`/경고를 남기며 완전성을 과장하지 않는다.
- RFP 본문/기존 담당자 판단/이력/DPAPI 키 및 비공개 인력 자료를 공개 저장소/외부 Codex 검수에 제공하지 않는다.
- 7일 공식 수집 오류의 별도 원인 분석, STALE 8건 자동 재검증, 다음 Stage 2/3 AI 구현, 인터넷 공개, `main` 병합은 이번 로컬 검증 범위 밖이다.
