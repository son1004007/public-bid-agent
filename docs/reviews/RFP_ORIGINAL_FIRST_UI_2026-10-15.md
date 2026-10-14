# RFP 근거 원문 우선 UI 개선 및 검증 (2026-10-15)

- 대상: `feat/sprint1-search-demo` / `http://127.0.0.1:8765/decision-preview`
- 결정 원본: [DECISIONS.md](../../DECISIONS.md) D-15
- 범위: **실제 RFP 근거 표현 후보 화면의 표시 방식만 변경**, JSON/API 응답 스키마·RFP 캐시·수집기·사람 판단/이력은 그대로.
- 원래 문제: 기존 `.requirementRow`는 3열 CSS이나 RFP 구조화 코드는 2요소만 출력해 출처 메타정보가 약 130px 열로 과도하게 좁아지고 SHA-256 해시가 반복돼 원문 읽기를 방해함.

## 구현

1. `frontend/public/dashboard-live.js`: 공식 RFP 요구사항 패널에서 원문 표현 후보를 `article.rfpEvidenceItem > p.rfpOriginalText`에 전체 너비로 표시.
2. 각 원문 표현 아래 `details.rfpEvidenceSource > summary` 기본 접힘. 펼치면 `dl`의 원본 파일, SHA-256, 추출 문자 위치, 원본 페이지 미확인, 근거 범위 및 사람 검증 필요 표시.
3. `frontend/public/bid-decision-dashboard-preview.html`: **RFP 전용 클래스로 CSS 격리**. 다른 인력요건/역량 점검 `.requirementRow` 레이아웃은 변경하지 않음.
4. HTML5 기본 `details/summary`를 이용해 키보드 조작·접기/펼치기 동작을 브라우저에 위임하고, HTML 문자열 주입 대신 기존 `el()` DOM text 노드를 사용.
5. 분석 범위·규칙 기반 후보·필수조건 및 법적 적격 미확인 경고 유지. 원본 페이지를 새로 추정하지 않음.

## 실제 Chrome 검증 (실제 로컬 사용자 데이터, 2026-10-15)

- 공식 공고 3,777건 목록 → 세부 공고 → `참가자격·과업` → `RFP 요구사항·출처 근거 확인` 실행.
- 검증된 RFP 1문서에서 원문 후보 **31건**, **31개 원문 표시 및 31개 출처 details 모두 기본 접힘**.
- 첫 출처 `summary` 클릭 펼치기 → 파일/SHA-256/추출 텍스트 위치·페이지 미확인 읽기 → 재클릭 접기: **PASS**.
- 모바일 viewport 너비 390px, document scrollWidth 390px: **가로 넘침 없음 PASS**.
- 실제 캡처: 사용자 PC의 OS 임시폴더에만 01 목록, 02 상세, 03 기본 접힘, 05 펼친 출처, 06 모바일 화면 보관. 캡처나 공고 RFP 원문을 공개 GitHub에 포함하지 않음.
- 첫 임시 E2E 스크립트는 이전 화면의 **항상 보이는 '문자 위치'**라는 문자열을 기다려 타임아웃. 새 화면은 문자 위치가 정상적으로 **기본 접힘**이므로, 검증 조건을 `details` DOM 요소의 존재와 `open` 상태로 수정한 후 재검증 PASS. 앱/API 버그는 아니었음.

## 범위와 후속 판정

- 로컬 Chrome 렌더링은 확인했으나, 사용자가 화면을 최종 승인했다고 기록하지 않음.
- 이 작업으로 RFP 의미 분석·요건 누락·법적 적격성·면허/실적/인력의 회사별 적합성은 해결되지 않음.
- **Codex 1차 독립 검수 `NO_GO` (Medium):** 일부 CSS 선택자가 RFP 패널 범위로 한정되지 않아 잠재적인 다른 화면 영향이 있다고 지적. `.rfpEvidenceItem`, `.rfpOriginalText`, `.rfpEvidenceSource`, `.rfpEvidenceMetadata` 및 모바일 선택자 모두 `.rfpEvidencePanel`을 접두어로 사용하도록 보완.
- 위 개선 이후 실제 Chrome 31건 기본 접힘/열기·닫기/모바일 390px 수직 E2E를 재실행해 **PASS**. 수정 후 Windows 전체 Python **274/274 PASS (111.432초)**, JS 구문 검사·문서 동기화·`git diff --check` PASS.
- **Codex 2차 읽기 전용 독립 재검수 `GO`**: RFP 새 선택자 전체(모바일 포함)가 `.rfpEvidencePanel` 아래로 제한됨, 전체 너비 원문/기본 접힘, DOM `textContent` 사용, 참가자격 미확정 표시, API·저장 데이터·인력요건 기존 화면 변경 없음 확인. Codex는 실제 Chrome/전체 회귀를 실행하지 않았으며 두 항목은 별도의 Windows 검증 결과임.
- **비공개 원본 불변 검증:** 사용자 PC에 보관된 로컬 JSON 40개와 RFP fulltext 캐시 124개를 적용 전 기준 SHA-256과 다시 대조해 **164/164 일치, 추가·삭제·수정 0건**. GitHub에는 원문·SHA 목록·비공개 경로/계정 정보 미포함.
- 사용자 지시에 따라 7일 배치 API 과거 오류 원인 진단, Stage 2, main 병합, 외부 출시를 수행하지 않음.
