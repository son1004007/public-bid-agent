# P07 구형 검증 플래그 NO_GO/P2 수정 — 2026-10-18

상태: **IMPLEMENTED / SYNTHETIC_TESTED / 독립 재검수 대기**. 사용자 제공 NO_GO를 GO로 변경하지 않는다.

## 범위와 계약

- 기준 브랜치 `feat/sprint1-search-demo`, HEAD `afc657a`. 시작 시 앞선 P07 미커밋 소스/문서 및 미추적 `test_recommendation_draft.py`·`test_recommendation_draft.cjs`가 있었다. 기존 변경은 보존하고 이번 구형 검증 finding에 필요한 부분만 보완했다.
- `decision_support.effective_verified(item, category)`를 조언의 사용자 Gate 판정, API 요약 및 신규 저장 검증에 사용한다. 엄격한 boolean true, 비공백 문자열 근거, Gate의 pass/fail/na 또는 factor의 1~5 정수 점수를 함께 요구한다. UI의 `effectiveVerified`도 같은 조건으로 지표·미검증 개수·확인 체크박스를 계산한다. Python/JS 공백 집합 차이를 없애기 위해 양쪽 공백의 합집합(BOM 포함)을 공백으로 처리한다.
- 구형 레코드의 저장 플래그는 조회 중 수정하지 않는다. `/api/state`의 기존 `gates`/`factors`는 기록값이며 UI는 플래그만 신뢰하지 않는다. 기존 결정·사유·history·문서도 그대로 보존한다. 명시적 항목 저장 시에만 기존 저장 경로의 검증을 적용한다.
- 공백 근거의 8개 pass/12개 5점 fixture는 조언 `HOLD_UNVERIFIED`/8개, 요약 `NEEDS_REVIEW`/8개·12개/지표 null, UI 미검증 8개·12개/미산출/확인 체크 해제로 일치한다. 근거 없는 fail은 미확인으로, 근거가 있는 fail은 기존 중단 판정으로 유지한다. 정상 근거 및 na는 기존 지표 계산을 유지한다.
- 조언은 기존과 같이 Gate 위험과 AI 초안 점수 개수를 다룬다. 수기 factor만 미확인인 경우 API 요약/UI 지표를 보류하며 조언의 Gate 전용 상태 의미를 확대하지 않았다.

## 재현과 검증

- 수정 전 신규 Python 6개 테스트에서 **15 failure(하위 사례 포함)**, 신규 Node **3 FAIL**. 합성 legacy JSON 조회에서 요약 100, 실제 `render()`에서 미검증 0/0 및 100.0/100을 재현했다.
- 수정 후 신규 Python **6 PASS**, Node **3 PASS**. 빈 문자열/ASCII·Unicode 공백/BOM, 근거 타입, 엄격한 검증 플래그, 상태/점수 경계, factor만 공백, 정상 na/미충족을 검증했다.
- 관련 Python 8개 모듈 **88 PASS**, Node 3개 파일 **11 PASS**, JS 문법·`git diff --check` **PASS**. CPython **3.12.0**, Node **22.14.0**, Windows.
- 합성 임시 JSON/loopback HTTP에서 GET 저장 호출 금지·파일 바이트 불변, `/api/save` 부분 요청의 보수적 요약 및 원래 항목/최종 결정/사유/history 보존을 확인했다. CLI 호출 금지 mock을 사용했다. Node는 네트워크 없는 합성 DOM에서 실제 app.js render를 실행하고 입력 객체 전체 불변을 확인했다.

저장소 루트 PowerShell에서 Python 검증:

```powershell
$env:PUBLIC_BID_LOCAL_DATA=Join-Path $env:TEMP 'public-bid-legacy-synthetic-unused'
Set-Location local_app
python -m unittest test_legacy_verification test_recommendation_draft test_decision_support test_local test_recommendations test_operations test_decision_profiles test_document_guide
```

저장소 루트에서 UI 검증:

```powershell
node --test scripts/test_legacy_verification.cjs scripts/test_recommendation_draft.cjs scripts/test_rfp_evidence_summary.cjs
node --check local_app/app.js
git diff --check
```

이 환경의 Git 소유권 경고에는 명령 단위 `-c safe.directory=<현재 저장소 절대경로>`만 지정했다. 전역 Git 설정·시스템 보안은 변경하지 않았다. 루트/로컬 README를 함께 갱신했다. `check_documentation_sync.py`는 HEAD 커밋 쌍 검사이므로 이번 미커밋 변경 검증으로 주장하지 않는다.

## 인계와 한계

- 새 회귀 파일 `local_app/test_legacy_verification.py`, `scripts/test_legacy_verification.cjs`는 미추적 상태로 인계한다. 기존 P07 미추적 테스트 두 파일도 위 관련 실행에 포함됐으므로 orchestrator는 독립 검수 입력/후속 Git 기록에 누락하지 않아야 한다.
- 독립 Codex 재검수·전체 회귀·CI·실제 브라우저 인수·실 RFP/법적 정확성·OCR 실행 파일/언어팩 검증·운영 적용은 **NOT RUN**. 이번 테스트 통과는 P07 전체 완료/REVIEWED/RELEASED가 아니다.
- GitHub 연결로 CONTROL 및 AGENTS 지정 handbook 원본을 확인했다. 공개 소스와 합성 fixture만 사용했으며 사용자 JSON/비공개 RFP/회사 증빙을 읽거나 전송하지 않았다. 외부 모델·자동 입찰·main 변경·배포/공개·git add/commit/push 없음. D-10/P11 API 과거 실패 조사는 계속 보류한다.
