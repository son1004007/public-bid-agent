# RFP 후보 표시 상한 누락 가시화 - 2026-10-16

- 사용자 결정: `DECISIONS.md` D-17 (후속 작업 순차 진행)
- 구현 단위: 검증된 본문에 규칙으로 잡혔지만 **유형별 5건 표시 상한**으로 노출하지 못한 추가 표현 후보의 수치 표시
- 변경: `local_app/rfp_requirements.py`, `frontend/public/dashboard-live.js`, `frontend/public/rfp-evidence-summary.js`, 테스트 및 CI 계약
- 기존 9유형 및 `schema_version=2` 유지. 기존 응답 필드를 제거하지 않은 하위 호환 추가임
- `requirements[].omitted_count`, `omitted_candidate_count`, `candidate_display_limit_per_category` 추가
- 본문 SHA-256+발췌 문자열 기준으로 **같은 유형 내** 중복 제외. 서로 다른 원문 SHA의 동일 발췌는 서로 다른 문서 후보로 계수
- 공식 첨부/원문 SHA 결속 후의 최대 2문서·각 44,000자 텍스트 범위 안에서만 계수함. 2문서 이후와 파서 누락·44,000자 초과 부분, 규칙이 아예 못 찾은 문장의 수를 의미하지 않음
- 상한 초과 시 `source_coverage=PARTIAL`; 카테고리별/전체 생략 수는 **RFP 전체 요건 개수나 Precision/Recall이 아님**
- 읽기 전용 RFP 조회/원본 캐시 경계 유지. 입찰 자격·실적·공수·원가·사람의 최종 결정은 계산하지 않음

## 2026-10-16 테스트 및 검수 이력

- Windows 기존 CPython 3.12 가상환경: 2026-10-16 전체 `python -m unittest discover -s local_app -p 'test_*.py' -q` **279건 OK**, 종료 0 (다중 문서 테스트 포함; 이후 HTTP 차단 응답 테스트를 추가하여 관련 19건 재검사 PASS)
- Node `node --test scripts/test_rfp_evidence_summary.cjs`: **3건 PASS**; 구 API 필드 부재, 양수·0·음수·null·비정수 등을 구분
- `node --check` (2 JS 파일), `git diff --check` PASS. 실제 Chrome UI 별도 확인 전에는 UI E2E PASS를 주장하지 않음
- Codex 읽기 전용 **1차 NO_GO** (`01a142dd-e2cf-7531-b693-cae49240372e`): 구현 로직의 직접 결함은 발견하지 않았으나 다중 문서/차단 HTTP/UI 호환 테스트 보강 요청. Codex의 Windows read-only sandbox는 자체 테스트 실행을 금지했으므로 테스트 증거는 별도 Windows 직접 실행과 분리
- 원본 RFP·비공개 JSON·API 키·개별 파일명/해시 목록을 GitHub나 Codex 입력으로 전달하지 않음
- Codex 2차 읽기 전용 재검수 `01a142dd-e2cf-7531-b693-cae49240372e`: **GO, 차단 지적 0건**. 추가된 파일이 로컬 HTTP 서버에서 제공되지 않는 문제를 후속 통합 확인에서 발견해 `server.py` 정적 GET 라우트를 보완함.
- Codex 3차 최종 범위 검수 `01a142e9-5a4d-7e93-8828-b8f946997304`: **GO, 차단 지적 0건**. 경로/Host/CSP/JS MIME/브라우저 스크립트 순서/HTTP 테스트와 비공개 자료 미노출 확인.
- 최종 변경 후 Windows 전체 Python **279/279 OK, exit 0**; HTTP 포함 RFP 관련 **19/19 OK**; Node UI **3/3 PASS**; 두 JS 구문·Git diff 검사 PASS. Codex 자체 테스트는 Windows read-only 정책으로 실행 불가했고, 별도 실제 Windows 회귀 결과를 근거로 사용함.
- 기존 8765 서버의 소유 PID·잠금·운영 데이터 위치를 확인한 후 해당 서버만 재기동. GET `/decision-preview`, `/rfp-evidence-summary.js`, `/dashboard-live.js` 모두 **HTTP 200**.
- 실제 비공개 현행·비STALE RFP 한 건의 읽기 전용 API 집계: `schema_version=2`, **9유형, 표시 19건·상한 생략 14건·2개 출처**, `source_coverage=PARTIAL`. 공고 ID/원문/파일명/개별 SHA는 이 문서에 기록하지 않음. 이 값은 전체 누락률이 아님.
- 로컬 기존 비공개 JSON **40개**, RFP 캐시 **124개**, 합계 164개 파일의 **전후 SHA-256 집계 일치**, 원본 변경·삭제·추가 없이 검증함. SHA 목록이나 집계 원문은 공개하지 않음.
- 실제 Chrome GUI 조작과 사용자 UI 최종 승인·법적 적격 판정·Stage 2 실자료 비교는 별도 미완료.
- 이번 변경은 실시간 수집·7일 API 과거 실패 원인 조사를 포함하지 않음
