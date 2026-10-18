# Public Bid Agent — 로컬 실행 사용법

> **2026-10-18 P09 NO_GO/P1 격리 수정:** 합성 fixture의 `RFP_BATCH`를 임시 root의 새 manager로 교체하고 네 외부 어댑터를 차단했습니다. 기존 manager/root 접근을 거부하는 GET 회귀와 합성 RUNNING worker lock 검증을 추가하여 API 인수 **11 PASS**. Chrome 재실행은 동일한 sandbox 종료로 **BLOCKED**이며 독립 재검수는 orchestrator 인계입니다. 아래 48 PASS는 수정 전 기록으로 배치 격리를 증명하지 않습니다. [수정·재현·재검증](../docs/reviews/P09_SYNTHETIC_ACCEPTANCE_2026-10-18.md).

> **2026-10-18 P09 합성 인수 게이트:** Windows API 보안·파서·이력·복구 **48 PASS**(신규 API 8개 포함). `node scripts/test_chrome_synthetic.cjs`는 저장소 루트에서 임시 합성 서버/새 Chrome 프로필을 만들어 파일 선택과 수기 이력 저장·재조회를 검사합니다. 현재 환경은 Chrome 페이지 생성 중 종료되어 **CHROME_E2E BLOCKED**입니다. 실제 자료·운영 서버·배포에 접근하지 않으며, 독립 검수/CI 및 라이선스·사용자 인수는 별도입니다. [명령·게이트·한계](../docs/reviews/P09_SYNTHETIC_ACCEPTANCE_2026-10-18.md).

> **2026-10-18 P08 합성 이력 복구 회귀:** `test_bid_outcome_recovery.py`와 `test_release_rfp_stage.py`에서 수기 제출·평가·선정/미선정 이력의 HTTP 재조회·중복·revision 충돌, 원자 저장 실패 후 재시도, 기존 백업·복구의 이력 보존과 최신 편집/변조 거부를 검증합니다. 실행 코드·저장 형식 변경이나 이력 전용 자동 백업 추가는 없습니다. 모든 파일·복구 대상은 테스트 소유 임시 합성 데이터이며 실제 운영 적용·배포 없음, 독립 검수는 orchestrator 인계입니다. [명령·결과·한계](../docs/reviews/P08_SYNTHETIC_HISTORY_RECOVERY_2026-10-18.md).

> **2026-10-18 P07 구형 검증 NO_GO/P2 보완:** `effective_verified`를 조언·요약·저장 검증에 공통 적용하고 UI 계산/체크박스도 같은 조건을 사용합니다. 엄격한 `true`, 유효 Gate 상태 또는 1~5 정수 점수, 비공백 문자열 근거가 함께 있어야 확인 완료로 계산합니다. 기존 저장 플래그는 조회 중 재작성하지 않으며 최종 결정·이력을 보존합니다. 합성 Python **88 PASS**, Node **11 PASS**, JS/공백 검사 PASS. 독립 재검수는 orchestrator 인계이며 운영 반영·배포 없음. [실행 명령·계약](../docs/reviews/P07_LEGACY_VERIFICATION_FIX_2026-10-18.md).

> **2026-10-18 P07 NO_GO/P2 보완:** 자료 헤더 포함 90,000자 상한의 실제 범위·잘림·누락을 `model_input()`에서 공통 계산하여 프롬프트와 `input_coverage`를 만들고, 성공한 초안의 `ai_input_coverage` 및 입력 버전에 기록합니다. UI는 현재 자료의 전달 범위를 표시합니다. 미전달 인용은 거부하며 입력 잘림·누락 시 AI 조건·점수를 제외하고 `RULE_BASED_FALLBACK`/`HOLD_INPUT_INCOMPLETE`로 보류합니다(사용자 확인 미충족은 우선 유지). 사용자 최종 결정·이력 및 GET 비저장 유지. 관련 합성 Python **82 PASS**, Node **8 PASS**, JS 문법·diff 공백 검사 PASS. 독립 재검수 대기이며 아래 75/6은 수정 전 이력입니다. 실제 LLM·비공개 자료·운영 반영 없음. [계약·검증·인계](../docs/reviews/P07_SYNTHETIC_RECOMMENDATION_DRAFT_2026-10-18.md).

> **2026-10-18 P07 합성 검증:** 수동 AI 검토 화면(`/`)의 `decision_support`는 항상 `draft_state=DRAFT`이며 `source_checks`에서 인용 없음/불일치/추출 문자 일치만 구분합니다. `ai_draft_context_sha256`은 서버가 분석 입력에 결속하며 구형 초안·입력 변경은 fallback 대상입니다. 모델/의존성 누락·시간 초과에도 사용자 확인 기록의 규칙 판단을 제공하고 최종 결정·이력을 변경하지 않습니다. GET은 현재 근거를 재대조하되 저장하지 않습니다. Python **75 PASS**, Node **6 PASS**, JS 문법 PASS; 실제 LangGraph 의존성·LLM/비공개 자료/운영 반영·독립 검수는 별도입니다. [계약·실행 명령·인계](../docs/reviews/P07_SYNTHETIC_RECOMMENDATION_DRAFT_2026-10-18.md).

> **2026-10-18 P01/P06 합성 검증:** 원본 대조 후 `페이지·표·각주·OCR 검토 위치`를 펼치면 PDF 페이지별 위험과 HWPX 섹션별 표식을 볼 수 있습니다. 섹션 번호는 원본 페이지가 아니며 이미지 메타데이터 실패는 `null`(미확인)입니다. 준비도 API의 각 `checks` 항목에는 `evidence_gaps`, `data_gaps`, `required_review`, `requirement_comparison=NOT_PERFORMED`, `evidence_verification=UNVERIFIED`를 추가했습니다. 불완전한 reviewed 기록은 `EVIDENCE_RECORD_INCOMPLETE`이며 가용 MM·단가 값/직무명·증빙 본문은 반환하지 않습니다. 관련 Python **82 PASS**, 기존 Node 요약 **3 PASS**, JS 문법 PASS. 실제 회사 증빙·적격·수익성·독립 검수·브라우저 인수·운영 반영은 미검증입니다. [검증 및 인계](../docs/reviews/P01_P06_SYNTHETIC_READINESS_2026-10-18.md).

> **2026-10-18 P05 NO_GO 보완:** 식별자 전체 문자열 검증에 더해, `preserve_cancellation`을 페이지 수집·수동/예약 조회기간 중복 제거·저장 병합에 적용했습니다. 같은 배치의 동일/별칭 차수에서 관측한 취소 공고종류를 일반 응답으로 덮지 않고 다른 메타데이터는 최신 응답 정책을 유지합니다. 원문·사람 판단 보존과 추천 제외 등 합성 회귀 **91개 PASS**. STALE 자동 해제·운영 반영 없음, 독립 Codex 재검수 대기입니다. [실행 명령·검증 기록](../docs/reviews/P05_SYNTHETIC_SOURCE_SAFETY_2026-10-18.md).

> **AI/Codex에게:** 사용자 확정 결정은 [DECISIONS.md](../DECISIONS.md), 현재 실제 사용/보안 경계는 [AI_CONTEXT.md](../AI_CONTEXT.md), 검수·배포 범위는 [AGENTS.md](../AGENTS.md), 최근 실행 결과는 [CURRENT_STATE.md](../CURRENT_STATE.md)와 [TASKS.md](../TASKS.md)를 먼저 확인하십시오. 2026-10-13 이전 자료의 공고 건수는 과거 스냅샷입니다.

> **2026-10-15 로컬 실증:** 기존 127.0.0.1:8765 서버/Chrome RFP 구조화 근거 버튼·모바일 PASS, 개인 JSON/캐시 164/164 SHA 일치, 전체 Python 274 PASS. [실제 인수 검증](../docs/reviews/RFP_STAGE1_LOCAL_ACCEPTANCE_2026-10-15.md). 사용자 UI 최종 승인/외부 공개와 구분합니다.

> **새 RFP 파서 설정 fingerprint:** `extractors.extract_document`가 파서 코드 SHA·Python/관련 패키지/상한 설정·방법을 정규화한 fingerprint를 반환하며, `rfp_batch.analyze`가 유효한 스키마만 신규 EXTRACTED 증거에 기록합니다. `rfp_original_compare.compare`는 재추출 때 해당 fingerprint만 비교해 `RECORDED_CONFIG_MATCHED_OCR_BINARY_UNVERIFIED` 또는 변경/미확인을 반환. 기존 캐시·구형 증거는 갱신하지 않음. OCR 바이너리/언어팩과 실제 원문 페이지·표/각주 완전성은 증명하지 못합니다.

> **2026-10-18 P04 검수 지적 보완:** PDF fingerprint에 Pillow 버전을 포함하고, 저장·현재 provenance 모두 엄격한 schema 검증 후 비교합니다. 현재 schema의 `True`/`1.0`은 `RECORDED_CONFIG_CHANGED_OR_UNAVAILABLE`로 처리합니다. OCR 실행 파일·언어팩 버전은 `NOT_CAPTURED` 유지. 합성 비교·배치 20 PASS; 추출기 7 PASS/1 ERROR(`pytesseract` 미설치)/2 SKIPPED. 독립 재검수 대기이며 운영 반영은 하지 않았습니다.

> **프로세스 자원/영속 라벨 검증:** PDF/HWPX 위험 진단은 Windows Job Object 강제 프로세스 메모리 상한(512 MiB)/종료 연동, POSIX rlimit, 35초 제한을 적용하며 실패 시 고정 `UNAVAILABLE`. 라벨 JSON의 event exact-key schema, SHA/offset, category/source/provenance, TZ 포함 시간 기록 검증 실패 시 읽기/집계 중단. 테스트 `test_process_limits.py` 및 `test_rfp_audit_labels.py`.

> **2026-10-16 로컬 사람 검토·품질 진단:** `POST /api/dashboard/rfp-original-compare`의 SHA 재현 성공 시 `document_quality.py`를 별도 subprocess로 호출해 비식별 페이지별 텍스트 길이·이미지 수 또는 HWPX 표/각주 마커만 반환. `GET /api/dashboard/rfp-review-queue`는 공고 ID/위험 플래그만 반환. `GET /api/dashboard/rfp-audit?id=...`, `POST /api/dashboard/rfp-audit/save`는 RFP 참가자격·평가기준·과업 텍스트 후보를 수동 표시하고 **비공개 별도 JSON**에 excerpt SHA/offset/문서 SHA·공고차수/사람 라벨만 저장. 정정·중복 라벨은 근거별 최신값만 집계, 과거 기록 보존. 원본 전체 라벨·TP/FP/FN/Recall은 검증되지 않음. [단계 실행표](../docs/design/REMAINING_EXECUTION_ROADMAP_2026-10-16.md).

> **2026-10-16 RFP 운영 후속 기능:** `POST /api/dashboard/rfp-original-compare`는 선택된 파일을 루프백 CSRF·8 MiB로 제한해 메모리에서 저장 증거와 대조하며 파일 영구 보관 없음. `GET /api/dashboard/readiness?id=...`는 운영자료 **확인 상태만** 비식별 조회하고 참가자격·실제 MM/수익을 확정하지 않음. `POST /api/dashboard/outcome`은 사용자 수동으로 제출→평가→선정/미선정/철회 이력을 revision 보호하에 기록하며 기존 사람 판단은 보존. 실제 원본 전체 Recall·법적 적격·실제 제출/낙찰 확인과 구분. [현황·남은 작업](../docs/design/STAGE2_4_EXECUTION_PROGRESS_2026-10-16.md).

> **2026-10-16 원본 대조 엔진(오프라인·입력 제공 시만):** `rfp_original_compare.compare(official_attachment, extracted_evidence, loaded_fulltext_record, original_bytes, server.extract_in_subprocess)`는 원본 공식 링크 결속·SHA·캐시·**현재 지정된 로컬 파서로 재추출한 텍스트**가 저장된 결과와 일치하는지만 검사합니다. 기존 추출 당시 파서와 버전·OCR 방식이 동일하다는 뜻은 아닙니다. 검증된 `rfp_fulltext.load()` 출력과 신뢰된 로컬 subprocess 파서를 전달해야 합니다. 자동 다운로드/원본 복구/파일 저장/전송·새 API는 없습니다. 원본을 별도로 확보하지 않았다면 원본 완전성은 `NOT_VERIFIED`. [실행 및 후속 작업](../docs/design/RFP_ORIGINAL_AUDIT_PLAN_2026-10-16.md).

> **2026-10-16 추출 문자 손실 집계:** `/api/dashboard/rfp-coverage`에 `extraction_loss_all/active`와 `loss_mode=STORED_PARSER_METADATA_UNVERIFIED_ORIGINAL` 추가. 신뢰할 수 있는 형식의 `fulltext_truncated=true`, `fulltext_chars`, `fulltext_reported_chars`, 64자리 캐시 참조 메타데이터의 **신고된 미보관 문자 수 차이**만 합산하며 손실 미계산/불일치/파서 경고를 분리합니다. 기존 JSON/캐시, 자동 수집, LLM 동작은 변경하지 않습니다. [한계·테스트](../docs/reviews/RFP_EXTRACTION_LOSS_LENGTH_2026-10-16.md).

> **2026-10-16 확보 품질 진단:** 로컬 `/decision-preview` → 수집 관리 → `RFP 확보 현황 갱신`에서 `GET /api/dashboard/rfp-coverage`가 반환하는 `by_quality_all`, `by_quality_active`를 표시합니다. 인식된 전체 텍스트 캐시 **참조만** 나타내며 해당 캐시의 SHA는 이 집계에서 검사하지 않습니다. 최신성 보류/발췌/파서 경고/분석 상한을 구분하고 공고명·원문·첨부주소·개별 SHA·원가를 응답하지 않습니다. [검증 범위](../docs/reviews/RFP_QUALITY_METADATA_2026-10-16.md).

> **2026-10-16 3유형 분류 평가:** `rfp_taxonomy_benchmark.evaluate(lines, origin='SYNTHETIC')`는 라벨이 붙은 **추출 텍스트 한 줄**의 참가자격·평가기준·과업 분류에 대한 TP/FP/FN 및 P/R/F1만 숫자로 반환합니다. 외부 모델/개인 원본 읽기·저장 없음. 실제 전체 RFP 누락률/법적 적격성은 측정하지 않습니다. [평가 프로토콜](../docs/reviews/RFP_TAXONOMY_BENCHMARK_PROTOCOL_2026-10-16.md).

> **2026-10-16 표시 상한 경고:** RFP 요구사항 읽기 전용 응답은 `candidate_display_limit_per_category=5`, `omitted_candidate_count`, 유형별 `omitted_count`를 포함합니다. 중복 제외된 규칙 매칭 후보 중 화면에 생략된 건수이며 전체 RFP 요구사항 개수/Recall이 아닙니다. 5건 초과 시 `source_coverage=PARTIAL`로 표시합니다.

> **2026-10-15 RFP 후보 분류:** `GET /api/dashboard/rfp-requirements?id=...`의 schema v2는 참가자격·평가기준/선정방식·과업 요구사항을 포함한 **9개 유형**입니다. 공통으로 `TEXTUAL_SIGNAL_REVIEW_REQUIRED`, SHA 결속·원본 페이지 미확인 및 법적 적격 `UNVERIFIED`를 유지합니다. [실제 RFP 점검 보고](../docs/reviews/RFP_TAXONOMY_3WAY_2026-10-15.md).

> **2026-10-15 RFP 원문 중심 UI:** RFP 요구사항 후보를 1열 원문 목록으로 표시합니다. 원본 파일, SHA-256, 추출 문자 위치, 판정 등의 세부 근거는 각 표현 아래 기본 접힌 `출처 및 검증 정보 펼치기`에서 확인합니다. [실제 UI 검증](../docs/reviews/RFP_ORIGINAL_FIRST_UI_2026-10-15.md). 인력 요건 예비 검토의 기존 3열 레이아웃은 그대로 유지합니다.

> 기준: **CPython 3.12.x / Python 표준 로컬 HTTP 서버 / 데이터는 PC의 JSON**. 전체 현재·목표 아키텍처, 설정, 신뢰 경계는 [루트 README](../README.md) 기준입니다.

## 준비 및 실행

저장소 루트 기준으로 **Python 3.12 가상환경**을 생성합니다.

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r local_app/requirements.txt
.\.venv\Scripts\python.exe local_app/server.py
```

macOS/Linux:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r local_app/requirements.txt
.venv/bin/python local_app/server.py
```

서버 출력 주소 `http://127.0.0.1:8765/`를 브라우저에서 열고 `Ctrl+C`로 종료합니다. `PUBLIC_BID_LOCAL_DATA`로 JSON 폴더 위치를 변경할 수 있고 기본 위치는 `~/.public-bid-agent-local/cases.json`입니다. JSON 평문은 디스크 암호화·백업·운영체제 사용자 권한을 별도로 관리해야 합니다.

### PDF OCR

Python 패키지 외에 Tesseract 실행 파일 + `kor`,`eng` 언어팩을 직접 설치해야 합니다. `tesseract --list-langs`에 `kor`가 보여야 합니다.

- Windows: 공식 호환 Tesseract 배포판 설치 시 한국어 언어팩 선택, PATH 등록.
- Ubuntu/Debian: `sudo apt-get install tesseract-ocr tesseract-ocr-kor tesseract-ocr-eng`
- macOS: `brew install tesseract tesseract-lang`

## 기능 사용

1. 공고 만들기 → 프롬프트나 파일 `.xlsx/.xlsm/.xls/.pdf/.hwp/.hwpx/.docx/.txt/.md/.csv/.json` 업로드.
2. 파일 원본은 파서에 전달되며 **추출 텍스트만 로컬 JSON**에 보관합니다. 실패/페이지 제한/OCR 누락·잘림 경고를 확인합니다.
3. 사용자 컴퓨터에 설치된 Codex/Claude Code CLI를 자신의 계정으로 공식 로그인한 뒤 제공자 선택. **사용자 동의 후에만** 문서 내용을 외부 AI에 보냅니다.
4. LangGraph가 먼저 모델을 독립 실행하고, 둘 다 성공한 경우 각 모델이 상대 의견을 1회씩 검토합니다. 모델당 최대 2회, 총 4회 요청이 발생할 수 있습니다. 모델 누락/에러 시 가짜 결과를 생성하지 않습니다.
5. AI 의견의 공통점·이견을 확인하고 초안 적용 → 필요 항목만 사람이 수정·근거 확인 → 참여/보류/미참여를 직접 결정합니다. **AI 모델은 실제 법적 자격·낙찰확률이나 최종 사용자 결정을 확정하지 않습니다.**

## 코딩 및 데이터 계약

- `server.py`: 127.0.0.1 HTTP, Host/Origin/CSRF, JSON 원자 저장, 의도된 외부 모델 동의 후 LangGraph 실행.
- `extractors.py`: 오프라인 추출 프로세스, 한도 및 OCR. 운영 수준의 완전한 악성파일 격리는 아닙니다.
- `cross_review.py`: LangGraph `independent_analysis`, `peer_critique`, `evidence_comparison`. LangChain Core ChatPromptTemplate 사용. **체크포인터 기반 중단·재개와 RAG는 미구현**.
- `index.html`, `app.js`: 로컬 브라우저, 두 AI 의견·이견·사용자 최종 결정.
- `test_local.py`, `test_extractors.py`, `test_cross_review.py`: 가상 데이터로 HTTP·파서·상태 그래프 테스트.
- 직접 의존성 라이선스 및 재배포 조건: [검토표](../docs/DEPENDENCIES_AND_LICENSES.md).

### 제한

- 파일당 10MiB, 공고당 6개, PDF 최대 40쪽, OCR 최대 12쪽, Excel 최대 24시트·2500행·90열, 문서 텍스트 44,000자, 모델 입력 90,000자. 첨부 그림/수식/복잡한 표 및 OCR 숫자를 온전히 해석하지 못할 수 있습니다.
- HWP DRM/비밀번호·배포용 HWP는 지원하지 않습니다. 파서 subprocess는 제한을 받지만 완전한 OS 샌드박스가 아닙니다.
- 모델을 호출하면 선택한 AI 업체에 자료가 전송되며, CLI 자체의 인증 및 캐시/보존 정책이 적용됩니다. 실제 CLI 구독 자격·외부 프로그램 이용 약관 검증은 사용자 PC에서 별도 필요합니다.
- 네트워크 공개, 실제 전자입찰 제출, 공식 나라장터 API 및 RAG, AI 판단의 통계적 수주확률 제공은 구현되지 않았습니다.

## 테스트 및 문서 갱신

```bash
python -m unittest discover -s local_app -p "test_*.py" -v
node --check local_app/app.js
python scripts/check_documentation_sync.py
```

**앱 코드/사용법/의존성 변경 커밋마다 루트 `README.md`와 이 README를 함께 갱신**합니다. GitHub CI에서 `scripts/check_documentation_sync.py`가 이를 확인합니다. 전체 아키텍처/패키지 변경 시 `docs/02-architecture.md`, `docs/DEPENDENCIES_AND_LICENSES.md`, `CURRENT_STATE.md`도 갱신합니다.
> `requirements.txt`는 각 패키지/버전을 별도의 줄로 표기하며, LangGraph·LangChain Core 설치 결과를 CI에서 확인합니다.

## Claude 없이 Codex만 사용하기

Codex CLI 로그인(`codex login status`) 상태에서 화면의 Codex만 선택하고 Claude는 체크하지 않습니다. 자료를 등록하고 외부 제공자 전송에 동의한 뒤 AI 분석을 누르면 Codex를 1회 호출합니다. 근거 없는 값은 미검증으로 보관하며 사용자가 최종 결정을 내립니다. 이 모드에서는 교차검토가 없습니다.

Windows에서는 npm의 `codex` 쉘 스크립트를 Python subprocess로 직접 실행하면 WinError 193이 발생하므로 `codex.cmd`를 사용합니다. 실행 명령은 `codex.cmd exec --ephemeral --ignore-user-config --ignore-rules -m gpt-5.6-terra --sandbox read-only --skip-git-repo-check -`입니다. 이 모델 지정은 앱 내부 호출에만 적용하고, 개인 Codex 설정 파일은 수정하지 않습니다.

### Codex 단독 실제 검증 이력

2026-10-10 Windows 합성 입찰 HTTP E2E에서 Codex CLI 로그인으로 1회 분석 성공: Gate 8개, Factor 12개, 추천 `hold`, 사용자 결정 `undecided` 유지, JSON 저장 확인. 회사 자료는 사용하지 않았습니다. 현재 개발 브랜치에는 이 테스트의 인증키나 업무 자료가 포함되지 않습니다. `TD-kiseok` 장치에만 사용자 바탕화면 `Public Bid Agent (Local)` 바로가기가 있으며, 이 바로가기는 GitHub 배포물에는 포함되지 않습니다.

### 실제 공고 수기 검증용 샘플

`fixtures/public_tenders_2026_10_10.json`은 2026-10-10 기준 공개된 **공고 3건**(LLM Agent 운영지원, AI·SW 과학 시뮬레이션 34종, AI 서비스 실증 클라우드 고도화)과 명시적인 **가상 부서 4개 조건**을 담습니다. 공식 RFP 원본을 직접 내려받은 것이 아니므로 공고 출처·마감 상충과 미확인 자격을 단정하지 않아야 합니다. 실회사 내부 데이터로 착각하지 마세요.

### 필수조건 불일치와 보류 판단 구별

`decision_support.py`는 AI가 제출한 자격 불일치·사용자가 확인한 필수조건 위반·미검증/충돌을 분리해 입찰 권고의 **위험 표시**를 제공합니다. `REVIEW_NO_BID_PROVISIONAL`은 AI가 인식한 미검증 이슈이며 법적 결격 확정이 아닙니다. `HOLD_UNVERIFIED`는 증빙 확인 필요, `HOLD_CONFLICT`는 AI/사용자 값이 서로 다른 경우입니다. AI가 `reason`을 비워 반환하면 그 사실을 명시하고 증빙에서 확인된 항목별 근거를 표시합니다. 사용자 최종 결정은 AI가 변경하지 않습니다.

### 실제 공고 MVP 검증 사례 보기

회사 노트북 로컬 앱 `http://127.0.0.1:8765/`의 `[검증 사례·실제공고/가상 업체]` 4개 항목에서 공개 입찰공고와 **가상 부서조건**을 확인할 수 있습니다. AI Codex 실분석 결과와 안전 경고가 함께 로컬 JSON에 저장돼 있으며 최종 참여 결정은 모두 미결정입니다. [검증 보고서](../docs/reviews/MVP_PUBLIC_BID_E2E_2026-10-10.md)를 참고하세요. 개발 브랜치의 공식 원문 확인 및 독립 코드 검수 미완료로 실입찰 제출에 활용하면 안 됩니다.

### AI가 추출한 독립변수 바로 확인

`http://127.0.0.1:8765/`에서 기존 검증 공고를 선택하면 'AI 독립변수 20개 및 추출 근거'가 읽기 전용으로 펼쳐집니다. Gate 8개(참가자격 충족/실패/미확인)와 Factor 12개(1~5점/미확인·사유)를 **AI 초안 적용 전에도** 볼 수 있습니다. 원본을 수정하지 않으므로 사용자가 별도 검증한 값도 보존됩니다. 아래 'AI 초안 적용'은 편집하기 위한 별도 동작입니다. 위험 통제/제안비용 점수의 방향은 모든 점수처럼 높을수록 유리하도록 정했으며, 2026-10-10 이전 AI 점수는 방향 역전 사례가 발견되어 별도 근거 대조가 필요합니다.

### 처음 사용하는 팀장용: 어떤 문서를 넣어야 하나요?

첫 화면의 **입력 문서 가이드**를 열어 순서대로 확인합니다. 1. 나라장터 입찰공고문/정정공고, 2. 발주기관 제안요청서(RFP)/과업지시서, 3. 회사의 등록·인증·업종/기업규모 증빙, 4. 유사실적/기술력/역할별 가용인력 현황, 5. 사업별 예정원가·제안계획·수행 위험 검토 요약. 다섯 문서 **묶음**을 권장하며, 20개 독립변수마다 필요한 문서와 자료 누락 시 담당자에게 확인할 질문을 바로 보여줍니다. 실제 업로드는 공고별 최대 6개 파일로 제한됩니다. 자격/가용인력/원가 등의 최신 사실은 원문뿐 아니라 담당자 확인이 필요합니다.

**중요:** 3~5번 자료는 회사 정책상 민감·기밀일 수 있습니다. 회사의 명시적 외부 AI 제공 허용 없이는 파일 원본 및 요약도 Codex/Claude에 보내지 말고, 공개 문서+승인된 비식별/가상 정보만 사용하세요. 부족한 항목은 `unknown/null`로 유지하거나 사용자 검증란에서 확인합니다. 화면 정보의 단일 원본: `document_guide.json`; 사용 설명은 루트 README와 동기화합니다.

### 로컬 회사 운영정보와 공고별 예상원가 관리

첫 화면의 **회사 공통 운영정보**에서 직무별 1MM 월 기업부담 총원가와 가용 MM, 공통 간접비율/위험충당률을 로컬 `operations.json`에 별도 저장합니다. 회사 실데이터 대신 가상 수치로 테스트하고, 실명/개인급여·기밀정보는 무단 입력하지 않습니다. 공고를 선택하면 **공고별 투입·원가 계획**에 각 역할의 예상 MM, 외주비, 직접경비, 제안비용, 부가세 제외 예정 공급가액을 입력하고 '계산·저장'합니다. 예상 총원가/이익/이익률/공수 부족·누락 경고는 서버에서 결정적으로 산출되고 공고 JSON에 남습니다. 회사 기준정보 revision 변경 시 기존 공고 원가는 오래된 버전으로 표시되어 재산정이 필요합니다.

현재 수행 프로젝트의 인력 배치와 실제 입찰 간 중복 공수는 **자동 집계하지 않습니다**. 가용 MM은 사용자가 입력한 시점의 유효성만 담당자가 확인합니다. 운영정보는 Codex/Claude 프롬프트에 자동 포함되지 않고, AI 사용동의가 있어도 원가·급여 데이터 자동 전송은 하지 않습니다. 사용자가 직접 프롬프트에 붙여 넣는 입력은 별도로 주의해야 합니다. 회사 사전 허가 없이 실제 재무 원본은 등록하지 마세요. `operations.json`은 로컬 평문이고 Windows 파일 권한/디스크 암호화/백업정책은 사용자 관리입니다.

### 회사 운영자료 8종 수집 상태

회사 공통 운영정보 화면에서 **기타 회사 운영자료 8종**을 펼치면 보유/관리 부서, 수집 현황, 승인된 비식별 요약(최대 600자), 출처 문서명, 확인일을 입력할 수 있습니다. 각 항목은 미수집·갱신 필요·요약/출처 확인 상태이며 확인 완료에는 세 입력값이 필요합니다. 이 데이터는 **별도 로컬 JSON**에만 저장되며 Codex 전송·원가 계산에 자동 반영하지 않습니다. 사내 자료를 입력하기 전 데이터 소유자/보안정책 승인 여부를 확인하세요.

운영 장부의 `reviewed_on` 확인일은 실제 존재하는 `YYYY-MM-DD` 날짜로 검증하며, 요약·출처·확인일이 없는 자료는 `reviewed`로 표시할 수 없습니다. 가상자료로 검증하고 실제 회사 운영자료 원본은 수집하지 않습니다.

### 회사 운영정보 MVP 검증 결과

회사 노트북 가상 폴더에서 공통 2개 직무단가·공수 및 8종 운영자료를 별도로 저장하고 공고별 예상 원가/이익률 계산, 수정 버전 충돌 탐지, 기존 사용자 사례 보존을 검증했습니다. Windows Python unittest 50 PASS, 노트북 HTTP 테스트, GitHub CI PASS. [상세 실증 보고서](../docs/reviews/OPERATIONS_COST_E2E_2026-10-10.md). 실제 회사 보안 승인·실자료 검증·브라우저 클릭/모바일 UX 테스트·독립 최종 보안 리뷰 전 main 병합 금지.

### 새 공고 중심 UI 퍼블리싱 시안 (2026-10-10)

기존 로컬 앱에서 `/decision-preview`로 새 화면을 열거나 `frontend/public/bid-decision-dashboard-preview.html`을 브라우저에서 직접 엽니다. **정기 공고 수집 계획(시안) → AI/데이터 사업 합성 목록 → 공고별/일괄 참여 판단 버튼(가상 시뮬레이션) → 참여 판단 기준/영향인자 프로필(화면 메모리 임시 변경) → 불참 사유 조회·프로필 버전/판단 이력**의 사용자 흐름을 검증합니다. 8개 합성 데이터만 제공하며 실제 나라장터 수집, Codex 실행, 운영 JSON 동기화, 서버 상태 변경은 수행하지 않습니다. 기존 로컬 AI/원가 기능은 유지합니다. 사용자 UI 승인 및 독립 코드 검수 후 새 화면을 실제 서비스에 연결할 예정입니다.

정적 시안에서는 영향인자 가중치 변경이 재판별 시 가상 종합 적합도에 반영되며, 담당자 최종 불참은 별도 사유 입력이 없으면 화면 기록되지 않습니다. 실제 서버 업무 데이터·Codex 호출에는 영향이 없습니다.

정적 퍼블리싱 시안의 JavaScript는 로컬 서버의 CSP를 준수하도록 `/bid-decision-dashboard-preview.js` 별도 파일로 제공합니다. 서버 보안 헤더는 변경하지 않았습니다. 파일로 직접 열려면 HTML과 동일 폴더에 JS 파일이 있어야 합니다.

로컬 서버 `/decision-preview` 제공은 회사 노트북 실제 Chrome에서 공고 8행·현황 KPI 5개·영향인자 슬라이더 12개 DOM 생성까지 확인했습니다. 이 시안은 버튼/프로필을 브라우저 탭 메모리에서만 변경하며 실제 수집/LLM 호출/영구 프로필 저장은 수행하지 않습니다. 새로고침하면 초기화됩니다.

새 공고 시안의 목록 **상세보기**는 상태변경 없이 전체 상세 탭 4개(기본정보/자격·과업/12개 인자/참여결정·불참 이력)를 열어 보여줍니다. 탭의 내용은 합성 공고·가상 점수·미확인 원문/첨부를 구분하며, 따로 누르는 '참여 판단 시연' 버튼만 가상 권고를 계산합니다. '담당자 최종 불참 기록'은 사유 입력 시에만 탭 메모리에 보존되며 기존 사용자 로컬 cases.json은 건드리지 않습니다.

상세 판단 탭의 불참사유 입력칸은 JavaScript 동적 노드이며, 정적 파일에는 고정 입력칸이 없습니다. 변경된 테스트는 동적 생성 코드 존재를 확인합니다.

상세보기 화면 4개 탭의 Chrome 실제 클릭 검증 19개 항목 PASS. 사용자 원본 데이터 불변. 자세한 재현과 제약은 [검증 보고서](../docs/ui/DECISION_DETAIL_PREVIEW_E2E_2026-10-10.md). 실제 공고 원문/AI/프로필 저장은 연결 전입니다.

### 참여 판단·영향인자 프로필 영속화 (개발 브랜치)

`http://127.0.0.1:8765/decision-preview`의 두 프로필 저장 버튼은 PC에 `decision_profiles.json`을 생성하고 별도 버전으로 저장합니다. 새로고침하면 최신 저장 버전을 읽어 옵니다. 읽기 GET `/api/decision-profiles`, 저장 POST `/api/decision-profiles/save`은 로컬 Host·Origin·CSRF와 `expected_revision`을 확인합니다. 다른 탭에서 먼저 저장하면 409로 거절하고 새 상태를 조회합니다. 파일을 직접 열었을 때는 종전처럼 메모리 시연입니다. 저장 파일은 원자적으로 쓰지만 **평문**이므로 OS 계정 접근권한·디스크 암호화·백업 정책을 적용하세요.

현재 이 저장은 판단 기준 1개와 영향인자 가중치 프로필 1개에 한정됩니다. 공고와 결정/불참 이력은 화면 임시 합성 상태이며, 운영 원가와 사용자 AI 분석 결과가 자동으로 합쳐지거나 Codex에 전송되지 않습니다. 독립 코드 검수와 사용자 UI 승인은 아직 미완료입니다.


### 공고 대시보드 실제 서버 연동 (2026-10-11)

로컬 `http://127.0.0.1:8765/decision-preview`는 `dashboard.json`의 공식 공고만 표시하며 초기 목록은 0건입니다. 프리뷰 HTML 파일을 직접 열면 기존 합성 시안이 유지됩니다. 수집 버튼은 `DATA_GO_KR_SERVICE_KEY`가 실행 프로세스에 설정된 경우에만 공식 API를 요청합니다. 인증키는 PC 환경변수로만 지정하고 저장소나 브라우저에 기록하지 않습니다. 수집 실패는 기존 목록을 보존하고 오류로 표시합니다.

수집한 공고는 목록/상세에서 번호·차수·기관·예산·마감 등의 공식 목록 메타데이터만 표시합니다. 참가자격·과업·수익률·AI 점수는 미확인입니다. 담당자 결정은 사유 필수이며, 당시 참여 기준·가중치 프로필 스냅샷과 함께 로컬 이력에 기록합니다. API는 `/api/dashboard`, `/api/dashboard/collect`, `/api/dashboard/action`이며 읽기는 GET, 변경은 POST+Host/Origin/CSRF 검사를 적용합니다.

자동 수집 배치·Google 계정·첨부 파싱·나라장터 공식 정정/취소·실제 Codex 분석 연동은 **아직 구현되지 않았습니다**. 실키로 공식 수집에 성공했다고 간주하지 않으며 표본 인증·응답 확인과 독립 검수 후 활성 범위를 늘립니다.

`/decision-preview`의 공식 API 모드에서는 수집 상태와 상세 화면의 안내 문구를 실제 연결 상태로 교체합니다. 키 미설정과 조회 실패는 합성 데이터로 대체하지 않습니다.

Windows CSRF 거절 응답의 TCP 연결 종료를 안정화하기 위해 한도 내 POST 요청 본문을 제한시간으로 소비한 뒤 403을 반환합니다. 출처/CSRF 검사 정책은 변함없습니다.

수집 창은 최근 24시간 용역 공고를 최대 20페이지(페이지당 100행)까지 확인합니다. 불완전한 페이지 조회는 성공으로 저장하지 않습니다.


### 나라장터 인증키 웹 등록 (2026-10-11)

대시보드 /decision-preview → 수집 관리 → 나라장터 OpenAPI 인증키 설정에서 **공식 활용신청 페이지 이동, 개인 키 입력·PC 암호화 저장·1건 연결 확인·저장 키 삭제**를 수행할 수 있습니다. 원격 공개 호스팅이 아닌 Windows 사용자 로컬 127.0.0.1 전용이며 DPAPI 암호문은 `%LOCALAPPDATA%/PublicBidAgent/secrets/g2b_servicekey.dpapi`에 분리 저장합니다. 별도의 환경변수 키가 이미 존재하면 암호문 저장 키가 우선입니다. **키가 브라우저 GET 응답에 포함되거나 대시보드 JSON에 저장되지 않습니다.** 서버 실행 계정이 바뀌면 기존 DPAPI 키를 복호화할 수 없을 수 있습니다.

GET `/api/procurement-key`, POST `/api/procurement-key/save`, POST `/api/procurement-key/verify`, POST `/api/procurement-key/delete`가 추가되었습니다. 검증은 공식 API 한 페이지/1건만 조회하여 결과코드 00인지 확인합니다. 성공 시 공고 수집은 별도 버튼으로 진행하며, 활용신청/승인은 본인 계정에서 해야 합니다. `ServiceKey`는 첨부 OpenAPI v1.2 요청 필드 대소문자를 준수합니다. Windows 외 OS는 웹 등록 미지원, 기존 환경변수 설정만 가능합니다.

### 수집 기간 선택

`/decision-preview`의 `수집 관리`에서 `조회 기간`을 **최근 24시간 / 최근 7일**로 선택합니다. 실제 브라우저 요청 본문은 `{"days":1}` 또는 `{"days":7}`입니다. 기본값은 7일입니다. 서버는 지정된 각 24시간을 순차 수집하여 공고번호+차수로 중복 제거하며, 하나의 조회라도 실패하면 전체 수집을 실패로 표시하고 과거 데이터를 그대로 남깁니다. 수집 결과에는 적용 일수를 기록합니다. 실제 조달청 API에서 조회된 원본 전체 건수와 제목 필터에 해당하는 관심공고 건수는 별도입니다. AI/자격 적합성 검증은 하지 않습니다.

로컬 `test_dashboard_backend.py`는 키 공급자를 모킹해 사용자 DPAPI 키와 실제 공공 API 호출을 회귀 테스트에서 배제합니다. 실 API 호출은 별도 명시적 검증 시에만 진행합니다.

실제 API 모드에서는 합성 시안의 KPI/수집 관리 제목이 공식 API·수동 수집 상태로 교체됩니다. 실제 공고 목록의 키워드 해당 건수를 확정 적격 공고로 오해하지 않도록 안내합니다.

### 전체 용역 수집 및 공식 상세 첨부 분류

조달청 용역 1일/7일 조회는 제목과 무관하게 전체 공고를 JSON에 보존합니다. 필터는 독립된 category metadata, deadline/window, document status를 사용합니다. 회사 업종/면허/나라장터 등록을 검증하지 않은 입찰 참가자격은 미확인입니다.

로컬 API: GET /api/department-profile, POST /api/department-profile/save (버전 충돌 검사); POST /api/dashboard/enrich (공고 ID 하나), POST /api/dashboard/enrich-batch (현재 후보 최대 5개). API는 기존 loopback/Origin/CSRF 검사를 따르고 입력 URL 대신 서버에 이미 저장한 공식 첨부 URL만 사용합니다. 허용 형식 PDF/HWP/HWPX/DOCX/TXT, 8MiB, 리다이렉트 불허, 별도 추출 프로세스, 최대 12,000자 저장. 오류는 재검토 상태로 보존합니다.

검토대기 포함 기본 설정은 false입니다. 조달 분류/RFP 확인 전 generic '개발·구축'은 SW 자동 후보로 확정하지 않고 REVIEW로 유지합니다.

규칙 기반 복합 키워드(예: AI 데이터 분석 플랫폼)는 AI/DATA 복수 카테고리 근거로 분류합니다. 담당자 최종 Bid/No-Bid 이력은 재분류 시에도 유지합니다.

로컬 신규 화면에서 부서 프로필 비동기 로드 전 일시적인 검토대기 과다 표시를 막기 위해 JS 기본 include_review를 false로 통일합니다. 검토대기는 별도 화면 필터에서 계속 접근할 수 있습니다.

상세 문서 일괄 확인은 현재 사용자가 선택한 부서 분야의 CANDIDATE만 최대 5건씩 처리하고 공공조달 분류·제안요청서/과업지시서 링크가 있는 공고를 우선합니다. 분류 불명(REVIEW)은 단건 개별 추출로 확인할 수 있습니다.

### 공식 추가 상세 API

POST /api/dashboard/related 는 저장된 공고 ID 하나에 대해 고정 나라장터 API의 면허 제한/지역 제한/e발주 첨부 3회 읽기 요청을 실행합니다. 응답을 검증해 license_restrictions/region_restrictions/attachments/related_status 필드에 저장하며, 법적 자격은 계속 UNVERIFIED입니다. 한 오퍼레이션이라도 오류나 페이지 누락이면 이전 내용을 보존합니다.

## 2026-10-11 RFP 재개형 배치 (로컬 개발 브랜치)

기존 `/decision-preview`의 **수집 관리** 화면에서 공식 RFP 순차 분석을 1·3·10·25건씩 시작, 중단, 재개하고 실패한 공고만 재시도할 수 있습니다. 작업은 1개씩 실행하고 기본 3초 간격을 둡니다. 진행률은 `GET /api/rfp-batch`에서 확인하고, 원본 공고 `dashboard.json` 외에 `rfp_batch.json`에 작업 상태를 기록합니다. 서버를 재시작하면 진행 상태를 복구하고 수동 재개할 수 있습니다. 성공 문서의 출처·SHA-256·본문 발췌는 공고 상세에서 확인할 수 있습니다. 첨부 파일과 e발주 상세는 공식 공개 사이트/API에만 접근하며 별도 LLM 전송은 하지 않습니다. 성공한 추출은 법적 참가자격 충족을 의미하지 않습니다. 설계·안전 한도는 [RFP 순차 배치 설계](../docs/design/RFP_RESUMABLE_BATCH_2026-10-11.md) 참고. 배포 및 main 병합은 독립 검수·사용자 UI 승인 후에만 수행합니다.

## 검토대기 공고 재탐색 (2026-10-11)

기존 REVIEW 분류 공고에 대해 `GET /api/dashboard/discovery`에서 공식 정보화사업 여부, 조달 분류, 과업문서 링크와 사업명 신호의 근거를 저장 없이 재평가하고 상위 30건을 기존 **수집 관리** 화면에 표시합니다. 실제 공식 2,080건 중 **227건이 메타데이터 상세 검토 우선순위**에 해당합니다(규칙 초안; 사업 수행·참가자격 적합 확정 아님). 추가 발굴된 `G2B-R26BK01763641-000` 순천향대학교 통합 학습경험플랫폼(LXP) 구축(1단계) 용역은 **RFP 검토 필요**로 유지합니다. 이 과정에서 검토대기 원본/담당자 결정을 변경하지 않습니다. 운영·유지보수와 개발의 비중 확인은 상세 문서와 담당자 검토 단계에서 수행합니다.

## 비식별 인력·가정 원가 연계 (2026-10-11)

`GET /api/workforce`는 로컬 사용자 데이터 디렉터리의 `workforce.json`에서만 비식별 인력 프로필을 읽고, 역할·내부 초중고 등급·검증 전 기술 가정·가용 MM 상태·가정 연봉 원가를 집계합니다. 기존 공고 대시보드의 **수집 관리**에서 명시적인 조회 버튼을 누르면 직원 코드별 임시 담당분야와 월 원가표를 확인할 수 있습니다. 공개 Git에는 인력 명단·등급 분포·원가 가정을 업로드하지 않습니다. 개인별 가용 MM `null`은 미정이며 기존 회사 원가계획도 해당 직무를 `NEEDS_REVIEW`로 취급합니다. 인력 정보는 외부 AI로 전송하지 않습니다. 신규/기존 `operations.json` 자동 덮어쓰기 없이 로컬에서만 별도 원가표를 연결합니다. 명세: [로컬 비공개 인력 관리 설계](../docs/design/WORKFORCE_PRIVATE_PROFILE_2026-10-11.md). 실무 자격·가용성·실제 매출/원가 검증과 독립 코드 검수 및 사용자 승인 전까지 공식 적합/수익 확정에 사용하지 않습니다.

### 검수 보완: 담당분야, 조회 권한, 원가 기준 (2026-10-11)

- 담당분야는 공개 코드에 정의된 범용 분류값 중에서 선택하며, 소속·실명·고객명 등의 자유서술을 인력 필드에 기록할 수 없도록 검증합니다. 로컬 매핑 자체는 공개하지 않습니다.
- `/api/workforce` 기본 응답은 총인원·역할·등급별 집계만 반환합니다. 별칭별 상세는 로컬 대시보드의 명시적 조회에서 `/api/workforce?detail=1`과 세션 내 CSRF 토큰을 함께 전달해야 접근합니다. 로컬 서버는 127.0.0.1 바인딩입니다.
- 기본 직무 `cost_basis`는 기존 월 총원가 계약 `FULLY_LOADED`와 호환하며, 사용자 제공 가상 연봉은 `SALARY_ONLY`로 별도 표시합니다. 급여만 반영됐거나 실제 공수가 미정이면 참고 노동원가는 표시하지만 `expected_profit_krw`와 `expected_margin_pct`는 `null`로 표시합니다. 법정 부담금·퇴직급여·간접비 확인 전 이익 확정은 금지합니다.
- 인력 공수는 0.01MM로 정규화하며, 등록된 사업 수행 인력이 없는 경우 가용 상태는 NOT_CONFIGURED입니다.

### 로컬 인력 상세 기본 비활성화

현재 기본 /api/workforce는 집계만 반환합니다. 직원 코드와 기술·담당 정보를 보여 주는 /api/workforce?detail=1은 로컬 서버를 PUBLIC_BID_WORKFORCE_DETAILS=1 환경변수로 명시 실행한 경우에만 유효하며, 세션 내 CSRF 토큰도 확인합니다. CSRF는 별도 로그인/권한 확인의 대체 수단이 아니므로 이 방식은 개인 PC 단일 사용자 개발 환경에 한정합니다. 업무망 공유/외부 호스팅/다중 사용자 접근에서는 상세 조회를 비활성화합니다. 새 직무 가용 MM 입력은 null(미정)으로 시작합니다.

## 2026-10-11 RFP 인력요건 예비 추출과 부서 인력 집계 비교 (개발 브랜치)

공고 상세의 **참가자격·과업 확인** 탭에서 `인력 요건 후보 확인`을 누르면 `GET /api/dashboard/staffing?id=G2B-...`가 이미 추출된 RFP 본문을 읽고, 명시적 개발자/분석가·초중고급·인원 패턴만 찾아 출처 발췌·문서 SHA-256과 함께 표시합니다. 로컬 비공개 인력 프로필의 **역할별 내부 등급 인원수 집계만** 대조하며 개인 코드·급여·담당 기술은 이 API에서 반환하지 않습니다. 추정 인원과 발주기관의 법정 인력 요건을 일치한다고 판단하거나 미등록/미탐지 사례를 부적격으로 표시하지 않습니다. RFP 미추출·명시 후보 미탐지·구형 출처의 불확실성을 분리하며, 사업별 실제 가용 공수·보유 자격·수익성은 미검증입니다. 읽기 전용·모델 외부 전송 없음. 설계: [RFP 인력 예비 추출](../docs/design/STAFFING_RFP_SLICE_2026-10-11.md). 사용자 화면 승인·독립 최종 검수·운영 적용 전까지 Draft 상태입니다.

### RFP 후보 탐지 정확성·출처 한계 보완 (2026-10-11)

- `/api/dashboard/staffing`에서는 **직무·등급별 인원수만** 비교한다. 개인 코드·급여·기술정보와 내부 가용 MM은 응답에서 제외한다.
- 우대사항/예시/제안 인력 구성 구간을 필수 인력 조건으로 승격하지 않는다. 명시적 `필수 인력` 또는 `요구 인력` 항목이 재등장할 때만 탐색 구간을 복구한다.
- 문서에 기록된 SHA-256 필드의 형식은 원문 파일 결속을 증명하지 않는다. `HASH_FORMAT_PRESENT_UNVERIFIED` 상태로 낮추고 발췌 내용 자체의 SHA-256을 별도 제공한다. 원본 재다운로드 및 정확한 위치 대조는 후속 작업이다.
- 문서 증거 총수·실제 분석 수·생략 수와 **각 발췌 첫 6,000자** 제한 및 절단 여부를 API/화면에 명시한다. 후보 0건은 요건 없음이 아니다.

### 인력요건 의미 검수 추가 보완

- `2명 이상`은 `count_kind=AT_LEAST`와 함께 최소 인원으로 표시하고, 단순 `2명`은 `STATED`로 구분한다.
- 단순 `참여 인력`, `인력 구성`, `사업 수행 조직`처럼 비필수일 수 있는 제목만으로 필수 인력 후보를 만들지 않는다. `필수 인력`, `요구 인력`, `투입인력 자격요건` 등 근거가 명시된 문맥에 한한다.
- `document_evidence` 전체에서 상태·본문·해시 형식이 유효한 항목을 먼저 찾은 후 최대 2개를 선택한다. 앞의 첨부가 실패해도 뒤의 추출 성공 문서를 놓치지 않으며, 생략 원인을 비추출/형식 오류와 개수 상한으로 나누어 표시한다.
- 6,000자 범위 내에서는 줄 수 제한 없이 추출된 전체 발췌를 확인한다. 문서 evidence 배열이 `null`/객체/문자열이면 읽기 전용 API는 503을 반환하고 원본을 보존한다.
- 문서 전체·정정·표/각주·요건 없는지 확인 및 회사 자격/가용성 판정은 여전히 사람의 공식 원문 검증이 필요하다.

### 문맥·인원 및 출처 추가 검증 (2026-10-11)

- `필수 인력은 별도 요구하지 않음`, `자율 구성`, `없음` 등의 부정 문맥은 인력요건 후보 추출 구간을 종료한다. 명시적 필수/요구 헤더가 다시 나타나기 전까지 후보를 만들지 않는다.
- `100명`, `120명 이상`, `1,000명 이상`(숫자 1000 등, 구분기호 없는 표기)을 인식한다. 500명 초과는 `OUT_OF_RANGE_FOR_REVIEW` 상태로 별도 검토한다.
- 본문 추출 성공과 원본 SHA-256 기록 유효성은 별개다. 해시 미기록·형식 오류에도 본문 후보는 탐지하고 `HASH_MISSING_UNVERIFIED` 또는 `HASH_INVALID_UNVERIFIED`로 표시한다. `NO_RFP_EXTRACTED`는 실제 추출 본문 부재에만 사용한다.
- 후보마다 저장된 발췌 내 행 번호와 기록된 경우 문서 식별 해시를 반환한다. 원문 PDF/HWP의 실제 페이지·표 위치는 아직 확인되지 않았으므로, 화면에서는 **저장된 문서 발췌**로만 표기한다.
- 읽기 전용 HTTP 테스트에서 `dashboard.json`과 `cases.json`의 바이트 불변을 모두 검사한다.

### 2026-10-11 인력 필수/면제 문맥 회귀 검수

- 독립 Codex 재검수는 실제로 수행했으며 마지막 세부 문맥 검수에서 `필수 인력 자격요건: 별도 자격증 필요 없음` 다음 줄의 인원 요건이 누락되는 반례를 발견했다.
- 실제 필수 인력의 수량 부정(`2명 이상 요구하지 않음`, `2명은 필요하지 않음`)과 부수 자격증·면허 면제를 분리하고, 쉼표로 구분한 다른 역할의 부정이 첫 역할을 지우지 않도록 항목 단위에서 처리한다.
- `QUALIFICATION_EXEMPTION`은 자격증·면허·기술자격·인증서에 대한 명시적 면제만 식별한다. 문장 변형과 원본 PDF/HWP 표 구조 해석은 완전성이 보장되지 않는다. 추출 후보는 계속 `UNVERIFIED`, 실제 RFP 전체 대조와 담당자 검증은 필수이다.
- 독립 재검수 **무결점 최종 승인(REVIEWED)** 은 아직 부여하지 않는다. 발견한 반례는 재현·수정·회귀 테스트로 처리하고 원본 사용자 JSON/개인 구성은 공개하거나 변경하지 않는다.

### 2026-10-12 독립 검수에서 발견한 정형 인력요건 결함 보완

- `최대 2명` / `2명 이내` / `2명 이하` / `2명 내외`는 정확한 필수 인원으로 환산하지 않고 사람 확인 대상으로 남긴다. 인력 적격 자동 확정은 하지 않는다.
- `개발자·분석가 고급 2명`처럼 복수 직무가 인원을 공유하는 구문은 한 직무에 잘못 배정하지 않도록 정형 후보에서 제외한다.
- `필수 인력은 자격증 소지자를 요구하지 않음`은 부수 자격 증명 면제로 처리하고, 뒤에 기술된 필수 개발 인력 후보는 유지한다.
- 별도 인력요건 GET API 응답에서는 원문 자유서술 발췌와 원문 첨부파일명을 반환하지 않는다. 대신 **허용된 역할·등급·인원·기술 토큰만으로 만든 탐지 표현**, 저장 문서 번호, 발췌 행 번호, 출처 해시/문서 식별 해시를 표시한다. 이는 원문 인용이 아니므로 UI에서 그 차이를 명시한다.
- 합성 문자열과 HTTP 응답 회귀 테스트에 성명·전화번호·전자우편이 응답되지 않는지 추가했다. 다른 API의 별도 프라이버시 검증은 후속 범위다.
- 전체 RFP 의미 분석, 표/각주/정정공고, 법적 자격과 인력 가용성 판단은 기존과 같이 검증 전이다.

## 2026-10-12 RFP 배치와 대시보드의 JSON 프로세스 간 경합 보호

- 기존 `os.replace` 원자 쓰기를 유지하고, 서로 다른 로컬 Python 프로세스의 **최신 JSON 읽기 → 검증/병합 → revision 증가 → 저장** 전체를 동일 `.dashboard-rfp.lock` 파일에 대한 운영체제 잠금으로 직렬화한다. Windows는 `msvcrt.locking`, Linux는 `fcntl.flock`을 사용하며 추가 외부 패키지는 없다. 서버 내부 `threading.RLock`은 그대로 유지한다.
- 대상 경로: 공식 공고 수집 성공/실패, 상세 면허·첨부, 재분류, RFP enrichment, 담당자 최종 판단, RFP 배치 결과 및 `rfp_batch.json` 진행 원장. 외부 공공 API/첨부 다운로드 및 OCR 중에는 JSON 트랜잭션 잠금을 보유하지 않는다.
- `.rfp-batch-worker.lock`의 수명 잠금으로 다른 프로세스의 같은 배치 중복 실행을 차단하고, 별도 프로세스에서 실행한 pause의 원장 상태를 다음 문서 처리 전에 확인한다. 비정상 프로세스 종료 시 운영체제가 잠금을 해제한다.
- 공고 재수집은 이미 확보한 공식 상세 RFP 첨부 링크를 덮어쓰지 않고 URL 기준 중복 제거해 유지한다. 이전 RFP 증거·사람 결정·판단 이력은 읽기-병합 경로에서 보존한다.
- 잠금 획득 제한시간 10초 초과 시 저장 전 실패 처리(HTTP 503). 잠금 파일에는 비밀·공고·인력 데이터가 없으며 활성/비활성 잠금 파일을 임의 삭제하지 않는다. **프로그램 이외의 직접 파일 수정, 여러 컴퓨터 간 네트워크 공유 파일 시스템의 잠금 보장, 두 JSON 파일을 통째로 하나의 DB 트랜잭션처럼 커밋하는 기능은 이 변경의 범위 밖**이다.
- 검증: `local_app/test_json_transaction.py`에서 별도 Python 프로세스 2개 실제 동시 갱신의 revision/이력/원문 보존, 제한시간, 강제 종료 후 잠금 회수, 배치 중복 실행 차단·원격 pause, 재수집 후 RFP 첨부 보존을 합성 임시 디렉터리로 테스트한다. 실제 사용자 `dashboard.json`/`cases.json`/`workforce.json`은 수정하지 않는다.

## 2026-10-12 RFP 배치·대시보드 JSON 충돌 방지

- 나라장터 공고 재수집·상세조회·RFP 추출·담당자 판단이 동일 `dashboard.json`을 쓰는 경우 **프로세스 내부 잠금 + OS 프로세스 간 파일 잠금**으로 읽기·검증·갱신·원자 저장을 직렬화합니다.
- RFP 배치는 별도 작업자 수명 잠금을 이용해 다른 프로세스 또는 같은 프로세스의 중복 배치를 차단합니다. 파일 잠금은 시간 제한 안에 확보할 수 없으면 오류로 처리하고 사용자 JSON은 덮어쓰지 않습니다.
- 기존 `final` 의사결정/이력, RFP 발췌 및 공식 상세 첨부를 우선 보존하고, 네트워크 작업 뒤 최신 파일을 다시 읽어 충돌을 확인합니다. 일시중지 요청은 기존 계약대로 **현재 문서 완료 후 다음 작업 전에 정지**합니다.
- 관련 설계/검증: `docs/design/RFP_JSON_PROCESS_LOCK_2026-10-12.md`, `docs/reviews/RFP_JSON_LOCK_REVIEW_2026-10-12.md`. 개인 PC의 원본 운영 JSON·API 키를 Git에 넣지 않으며 이번 변경에서 실제 자료를 자동 수정하지 않았습니다.

### 2026-10-12 첨부 보존 경계 보완

- 기존 공식 RFP/상세 첨부를 먼저 보존하고 새 공식 목록은 남은 40개 슬롯에만 추가한다. 신규 목록 40건 때문에 기존 검증 첨부가 유실되지 않게 한다.
- 동일 URL이면 기존 파일명·출처·식별자·추가 메타데이터를 유지하고, 기존에 없거나 비어 있는 필드만 최신 공식 목록에서 보충한다.
- 40건 제한으로 신규 첨부 일부를 저장하지 못할 수 있으며, 전체 RFP 수집 완전성은 사람 검증 대상이다.
- 합성 테스트 test_rfp_attachment_preservation.py: 신규 40개에 의한 기존 RFP 누락 방지, 동일 URL 메타데이터·기존 결정/원본 불변 PASS.

- 저장된 기존 첨부는 URL이 같아도 서로 다른 문서·정정·근거 식별자가 있을 수 있으므로 두 레코드를 모두 유지한다. 신규 첨부에 한해 동일 URL 기존 첫 항목의 누락 필드를 보충한다. 합성 test_two_existing_evidence_records_sharing_url_remain_distinct PASS.

- 새로 수집한 공고도 첨부 40개 상한을 적용한다. 신규 목록에서 URL이 같아도 이름·근거 식별자가 다른 두 별첨은 서로 병합하지 않고 별도로 보존한다. 합성 회귀 테스트 2건 PASS.

- 2026-10-12 CI 문서 동기화: `dashboard_backend.py` 첨부 병합의 기존 근거 우선·동일 URL 별첨별 독립 증거·최대 40개 제한을 코드와 테스트의 불변조건으로 유지합니다.

### 2026-10-12 첨부 및 공고 메타데이터 보존 최종 정책

- 공고별 저장된 첨부는 최대 120건이며, 한도 초과 시 기존 증거를 삭제하거나 잘라 저장하는 대신 변경을 거부한다.
- 동일 URL이라도 출처/파일명이나 문서 identity가 다른 기록은 각각 보존하고, 명확히 일치하는 근거에 대해서만 누락 필드를 보충한다.
- 빈값/누락값을 반환한 부분 재수집으로 기존 공식 공고 제목·기관·마감일과 같은 유효한 메타데이터를 지우지 않는다.
- 공고 RFP 수집·재분류·관련 첨부·담당자 결정의 read-modify-write는 동일 로컬 데이터 폴더에서 프로세스 간 잠금으로 보호한다. 데이터베이스 수준의 복수 파일 트랜잭션과 NAS 파일 잠금은 별도 검증 대상이다.

### 2026-10-12 최종 첨부/evidence 보존 보완

- 첨부 저장 상한은 120개로 상향하였다. 기존 공식 상세 첨부 40개와 추가 RFP 1개가 총 41개로 저장되고 재수집 후에도 유지된다. 121번째 신규 독립 첨부는 저장 실패로 처리해 기존 첨부를 자르지 않는다.
- 동일 URL의 독립된 `identity=A/B` 근거는 둘 다 유지한다. 같은 URL에서 B를 새로 수집한 경우 B에만 누락된 정보를 보충하며 A를 변경하지 않는다.
- RFP 배치 재추출로 상위 2개 파일이 달라져도 이전 `document_evidence`의 독립 문서 식별자를 보존한다. 합성 원문이 같은 경우도 포함한다.
- 독립 Codex 최종 수정 재검수: 위 3가지 **PASS**, 심각한 신규 회귀 미발견. 입력 SHA-256 `328a2d103cc60a04bbd228bf11419bd69a1865cab6f7c50267dd838dd1dbadcc`; 출력 원문은 개인 PC `user-json/rfp_evidence_review_retest.json`에 비공개 보관.
- 최종 Windows 합성 Python 전체 **177 PASS**, JavaScript 문법/Git diff 검사 PASS, 실제 2,223건 `dashboard.json` 원본 SHA 보존 PASS. 8765 원본 서버 변경 없음. 본 변경의 범위는 협조 프로세스/로컬 파일 시스템이며 정전 내구성·임의 잠금파일 교체·대량 실 RFP 추출은 별도 검증이다.

## 2026-10-12 공식 공고 읽기 전용 우선검토 순위
- GET /api/dashboard/recommendations: 전체 공식 공고와 현재 부서 관심분야를 읽고, 현재 기한 조건에 맞는 상세검토 후보 상위 30건을 추천 순위로 표시. 분석 모드는 RULE_BASED_READ_ONLY. 실제 AI/법적 참가자격/기술 수행능력/가용인력/수익성 검증 상태는 UNVERIFIED.
- /decision-preview 기존 수집관리 화면에 순위, 공식 분류/RFP 발췌 근거유형, 원문 미확인사항, 공고 상세 확인 버튼 연결. 비공개 인력·급여·RFP 본문·API 키는 추천 응답에 포함되지 않음.
- 설계·다음 단계: docs/design/RFP_RECOMMENDATION_SLICE_2026-10-12.md. 이 기능은 자동 Bid/No-Bid 결정이 아니라 상세검토 우선순위이다.

### 공식 RFP 확보 상태 진단 API

- `GET /api/dashboard/rfp-coverage`: dashboard.json + department_profile.json의 선택된 후보를 읽기 전용 집계하며, OPEN/REGISTRATION_REVIEW를 분리합니다.
- `EXTRACTED_TEXT / FAILED_ATTEMPT / READY_TO_FETCH / UNSUPPORTED_FORMAT / MISSING_OFFICIAL_LINK / INVALID_ATTACHMENTS` 상태별 건수, 현재 마감 전 추출 대기(`ready_active`)와 공식 상세조회 필요(`needs_related_lookup_active`) 건수를 반환합니다.
- 개인정보, 부서 인력·원가, 인증키, 원문 텍스트, 첨부 URL 및 개별 공고명은 응답에 포함하지 않습니다. 실제 운영 8765 서버 적용은 별도 백업·재시작 검증 대상입니다.

## 2026-10-12 긴 RFP 본문 청크 보존

공식 RFP를 **새로** 추출하는 `rfp_batch.Manager`는 최대 44,000자의 파서 텍스트를 `<PUBLIC_BID_LOCAL_DATA>/rfp_fulltext/<ref>.json`에 SHA-256 기반 원자적 파일로 기록합니다. 청크는 최대 4,000자, 시작·끝은 파서가 반환한 문자열 기준 0-based 문자 offset입니다. `document_evidence`에는 `fulltext_ref`, `fulltext_chars`, `fulltext_reported_chars`, `fulltext_chunks`, `fulltext_truncated`, `fulltext_position_basis`만 추가되고 청크 전체 본문은 일반 대시보드 API에 반환하지 않습니다.

`local_app/rfp_fulltext.py::load`는 로컬 내부 전용 함수로 청크 해시와 전체 텍스트 해시를 검증합니다. 공개 HTTP GET/모델 자동 연동 API를 새로 만들지 않습니다. 추출기 자체의 44,000자 한도·OCR/표/각주 누락·이전 70건의 소급 재처리·캐시 복구/청소/권한 분리는 후속 과제입니다. 로컬 사이드카는 평문이므로 개인 PC 데이터 보관 정책을 따릅니다. 테스트 `test_rfp_fulltext.py`; [설계](../docs/design/RFP_FULLTEXT_CHUNKS_2026-10-12.md).

## 기존 6,000자 RFP 발췌의 검증 후 소급 이관
- `rfp_backfill.Backfill(root, target_ids, persist, extractor)`는 이전에 성공한 공식 문서의 해시·identity·글자수·발췌가 **재수집 결과와 동일할 때** `fulltext_ref` 등을 기존 `document_evidence`에 추가한다.
- `run(1|3|10|25)`는 `rfp_backfill.json`을 이용해 안전 재개한다. SOURCE_CHANGED / PARSER_CHANGED / UNMATCHED / FETCH_FAILED는 자동 추천/수정 대상이 아니다. 기존 `rfp_text`, excerpt, 입찰 관련 사람 결정·이력은 보존한다.
- 이관 CLI는 현재 개인 PC의 별도 비공개 stage에서만 수동 실행한다. 일반 HTTP API와 원본 운영 데이터를 자동 이관하지 않는다. 테스트 `test_rfp_backfill.py`; [상세 설계](../docs/design/RFP_BACKFILL_VERIFIED_2026-10-12.md).

## 로컬 공식 RFP 이관 운영·복구 절차

scripts/promote_verified_rfp_stage.py를 사용하여 70개 공식 RFP 공고 및 127개 추출 근거를 비공개 청크 파일과 함께 이관할 수 있다. 이관은 2,223개 공고의 사람 최종 결정/사유/이력 및 기존 143개 RFP 작업 목록을 보존하고, 70건 문서 상태만 완료로 갱신한다. 파일 단위 원자쓰기의 교차 파일 중단 위험은 배포 저널과 --recover 처리로 보호한다. local_app/server.py는 PREPARED 저널이 있을 때 서버 기동을 거부한다. 테스트: local_app/test_release_rfp_stage.py 및 별도 Windows 비공개 운영 사본 HTTP/Chrome 검증.


## 2026-10-13 로컬 RFP 배포 안전성 보강 (개발 브랜치)

Codex NO_GO 지적의 4개 범위에 대해 서버 수명 독점 잠금, SQLite 동기식 PREPARED/COMPLETED 복구 의도, Windows 파일교체 MoveFileExW WRITE_THROUGH 및 POSIX 디렉터리 fsync, Windows CreateFileW 디렉터리/상위경로 핸들(GENERIC_READ, FILE_SHARE_DELETE 비허용, OPEN_REPARSE_POINT)을 유지해 경로 이름 변경을 차단하고 reparse 검사·파일 동일성도 재확인, 중단된 부분 백업의 원본 SHA 확인 후 재개 절차를 추가했습니다. 복구 의도 SQLite는 `PRAGMA synchronous=FULL`과 DELETE 저널을 사용합니다. 원래 `.rfp-release-transaction.json`도 유지합니다. SQLite가 PREPARED인 동안 서버 시작과 요청을 차단합니다. 로컬 서버가 실행 중이면 오프라인 배포/롤백/복구 도구는 별도 OS 프로세스 잠금 충돌로 거부됩니다.

배포 작업은 로컬 Windows 사용자 데이터와 별도 백업 경로가 있어야 하며 서버 종료 뒤 실행합니다. 부분 백업 재개는 `.backup-intent.json`의 기존 운영 JSON 해시가 동일하고 알 수 없는 파일이 없는 경우만 허용합니다. `recover`는 텍스트 저널이 사라졌어도 SQLite PREPARED 의도로부터 두 파일을 검증된 세대로 복구합니다. 버전이 다른 JSON은 제공하지 않고 서버가 실패하도록 설정했습니다.

**제한:** Windows 파일시스템·장치의 물리적 전원 장애를 여기서 직접 시험하거나 완전한 영속성을 보장하지는 않습니다. Microsoft MoveFileExW의 WRITE_THROUGH는 파일 이동을 플러시하지만, 모든 같은 볼륨 메타데이터 영속성의 증명은 아닙니다. SQLite FULL의 내구성도 OS/디스크의 fsync/FlushFileBuffers 계약에 의존합니다. 실제 종료 및 완전한 검수 전까지 공개 운영 배포와 main 통합은 별도 승인 대상입니다.

실행: `python -m unittest discover -s local_app -p 'test_*.py'` 및 독립 Codex 읽기 전용 재검수. 실제 사용 데이터의 손상·이력 보존은 테스트 폴더와 별도 원본 해시 점검으로 확인합니다.


## 2026-10-13 Windows 로컬 공식 공고 예약 갱신 (개발 기능)

- `local_app/scheduled_collection.py`: 사용자 DPAPI 조달청 인증키를 이용하여 공식 전체 용역 공고를 **7개 연속 24시간 구간**으로 조회. 오래된 순서에서 최신 순서로 동일 공고 식별자를 병합하고, 기존 담당자 판단·판단이력·저장 RFP 추출 본문은 변경하지 않음. 제목 키워드로 원천 공고를 제외하지 않음.
- `--data-dir "<사용자 비공개 데이터 폴더>" --days 7`은 원천 API 조회만 하는 **dry-run**이며, `--apply`를 붙일 때만 로컬 `dashboard.json`을 공통 다중 프로세스 잠금 후 병합 저장. `collection.mode=SCHEDULED_INCREMENTAL`, `lookback_days`, `window_end`를 기록함.
- 공식 API 한 일자라도 실패하거나 페이지 총건수 불일치 시 전체 적용을 중단. 조회 과정의 실패는 `collection.status=ERROR`로 기록할 수 있지만 기존 공고·사람 판단은 보존. 외부 API 키·원본/비밀 데이터는 로그에 출력하지 않음. **일시적인 공식 API 연결 실패는 동일 구간을 한 번 재시도하며, 상세 RFP 원문 자동 갱신은 아직 미구현**.
- Windows Task Scheduler: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install_local_collection_schedule.ps1 -Action Install`을 실행하면 **매일 오전 09:00 (PC 로컬 시각)**, 로그인된 현재 Windows 사용자로 7일 중첩 갱신을 수행하도록 등록. 기본 설정은 노트북 배터리 허용, 일정이 누락되면 가능할 때 실행, 중복 인스턴스 방지, 최대 60분. PC 로그인 세션이 없는 경우에는 실행되지 않음.
- 작업 확인/해제: 같은 스크립트에 `-Action Status` 또는 `-Action Remove` 지정. 키는 해당 사용자 Windows DPAPI 보관소에 있으며 스케줄러 인수/파일에 포함되지 않음. 실제 정정/취소의 자동 판별과 RFP 근거 무효화·AI 추천은 후속 구현 및 검증 대상.
- 로컬 웹서버는 기존 `127.0.0.1:8765` 실행 상태와 공통 JSON 잠금을 공유하며 서버를 강제로 종료하지 않음. 배포 `PREPARED` 저널 상태일 때 갱신 요청을 거부함.


### 2026-10-13 예약 수집 등록·실검증 상태
Windows SID 동등성으로 예약 작업 소유자를 확인하도록 등록 스크립트를 보완했습니다. 개인 PC `TD-kiseok`에 **매일 09:00** 현재 사용자 로그인 세션으로 예약 작업을 등록했으며 다음 실행은 **2026-10-14 09:00**입니다. 실제 API 7일 DRY_RUN 3,053건 성공, 첫 7일 APPLY는 ProviderError로 안전 중단 후 1일 APPLY 826건 신규 저장 성공, 기존 공고는 2,223건에서 총 3,049건으로 증가했습니다. 기존 사람 판단 이력과 RFP 보호 필드 13종 불변, 나머지 비공개 JSON 4개 해시 동일, Chrome 목록·상세·수집관리 PASS. 실제 Task Scheduler 예약 실행은 아직 이루어지지 않았으며, 7일 예약 배치의 운영 안정성은 추가 확인 대상입니다. 상세 근거: [자동 수집 검증](docs/reviews/AUTO_G2B_COLLECTION_2026-10-13.md).


## 2026-10-13 공식 정정·취소 공고 반영
- 조달청 공식 목록 API의 `bidNtceNo`(공고번호), `bidNtceOrd`(차수), `ntceKindNm`(공고종류)만으로 취소 및 후속 차수의 존재를 판별합니다. 제목에 취소·변경 표현이 있다는 이유만으로 확정하지 않습니다. 같은 공고번호의 숫자 차수가 더 높으면 과거 차수는 `notice_lifecycle=SUPERSEDED`, 공식 공고종류에 취소가 명시되면 해당 최신 차수를 `CANCELLED`로 보관합니다. 추가 원문 정정 이력 API의 전수 조회는 이번 범위 밖입니다.
- 공고 JSON과 기존 사람 최종 결정, `history`, 저장된 RFP 원문·SHA·첨부 증거를 삭제하지 않습니다. 저장 문서가 있는 공고의 공식 중요 메타데이터·신규 첨부 또는 후속 차수 변경은 `rfp_review_status=STALE`로 표시하고 수동 최신성 검증이 필요함을 UI에 안내합니다. 기존 추출 증거로 자동 입찰 적격 확정이나 재검증을 하지 않습니다.
- 규칙 기반 추천은 `CANCELLED`, `SUPERSEDED`, 차수 중복 검토 상태 `REVIEW`, RFP 최신성 `STALE`을 제외합니다. 보관된 공고 목록과 과거 판단 이력은 유지하고 공식 링크·후속 차수와 근거를 화면에서 확인할 수 있습니다.
- 기존 로컬 데이터 확인(미변경): `python local_app/notice_lifecycle_cli.py --data-dir <개인 JSON 폴더>`. 결과를 적용하려면 `--apply`를 추가합니다. 현재 저장된 공고를 공식 메타데이터로 재분류하며 API나 AI를 호출하지 않습니다. 이후 일상적인 API 수집 결과에도 동일 규칙을 적용합니다. 모든 저장은 기존 잠금·배포 가드를 사용합니다.
- 한계: 동일 공고번호의 정정 정보가 최근 7일 API 목록에 보이지 않으면 새로운 변경을 탐지하지 못하며, 원공고가 다른 공고번호로 재공고되는 경우 자동 동일성 판정을 하지 않습니다. 다음 작업의 RFP 의미 분석·AI 추천과 별도입니다.


### 2026-10-13 Codex 1차 NO_GO 후 보완
- 같은 공고번호와 **숫자 차수**가 같으면 공식 차수 표기 `0`, `00`, `000`을 기존 보존 ID에 합쳐, 사람 결정·기추출 문서가 다른 레코드로 갈라지는 문제를 방지합니다. 기존에 표기 변형이 별도 저장되어 있으면 임의 삭제·자동 병합하지 않고, 그중 공식 취소가 확인된 경우 해당 숫자 차수 전체를 취소 상태로 차단합니다.
- 한 번 확인한 동일 차수 `CANCELLED`은 이후 일반공고 응답으로 자동 해제되지 않습니다. 새로운 **더 높은 차수**가 발행되면 그 새로운 차수를 따로 검토하며 이전 취소 이력은 보존됩니다. 기본 공고 목록에서 취소·과거 차수·중복 차수 검토 항목은 제외하되 전체 보기에서 확인할 수 있습니다.
- 저장된 RFP가 `STALE`이면 기존 원문을 계속 보존하고 추천을 보류합니다. **현재는 최신 공식 증거로 재추출·재검증을 완료한 뒤 STALE을 해제하는 자동 전이가 없으므로**, 명시적 후속 검증 전에는 안전을 위해 추천에 다시 진입시키지 않습니다. 원문 재추출과 재검증 UX는 사용자 다음 개발방향 결정 이후 별도 구현입니다.


## 2026-10-13 RFP 요건 구조화 1단계: 추출 문구와 원문 근거 조회

- 기존 RFP 추출·SHA-256 검증 청크를 **읽기 전용**으로 재사용하는 `local_app/rfp_requirements.py`와 `GET /api/dashboard/rfp-requirements?id=...`를 추가했습니다. 취소·구차수·STALE 공고에서는 분석을 보류하며, 실제 참가 가능성/법적 자격/원가를 확정하지 않습니다. 모델 API 호출이나 외부 전송, 사용자 JSON·사람 판단 갱신 없음.
- **2026-10-13 당시 8유형:** 참가자격/면허/실적/과업/기술/인력·공수/기간/예산을 원문 관련 표현 후보로 구조화했습니다. **2026-10-15 D-16 이후에는 평가기준을 포함한 9유형/schema v2가 최신 계약**입니다. 문서 이름·원본 SHA-256·발췌 최대 220자·추출 텍스트 offset·불완전성 경고를 반환합니다. 원본 페이지 번호·필수 요건 여부는 추정하지 않습니다. 캐시 위변조/출처 불일치면 분석 실패로 명시합니다.
- `/decision-preview` → 공식 공고 전체 상세 → `참가자격·과업 확인` → `RFP 요구사항·출처 근거 확인` 버튼에서 분류·근거를 직접 검토할 수 있습니다.
- 실제 비공개 RFP 대표 20건에서 규칙 기반 표현 후보 561건 탐지, 원문 참조 가능한 현행 후보 66건(당일 저장상태 기준), 일부 절단/부분 텍스트 4건. 이 결과는 원문 의미 적격 판정이 아닙니다. 자세한 계약은 `docs/design/RFP_REQUIREMENTS_SLICE_2026-10-13.md` 참조.


### Codex 독립 검수 지적에 따른 출처 결속·증거 순회 보완
- 공식 첨부 identity로 확인된 **실제 첨부 파일명만** 응답에 표시. 저장된 `document_evidence.name`이 공식 첨부명과 다르면 불일치 경고를 남기고 증거를 제외합니다.
- 증거 이력 최대 120개 항목을 살펴보고 **정상 SHA/파일명/본문 검증에 성공한 문서 2개**까지 선택합니다. 앞의 기록이 실패해도 이후 정상 기록을 탐지하고, 처리 상한·중복·충돌을 경고합니다. 같은 첨부 identity의 다른 원본 SHA가 있으면 둘 다 제외합니다.
- 요건 표현 후보는 필수 조건 여부와 원본 페이지가 미확인입니다. 캐시나 문서 이름의 불일치가 있으면 자동 분석 결과를 확정하지 않습니다. 이는 실제 문서 의미를 판단하는 AI 기능과 구분합니다.


### Codex 2차 지적: 공식 첨부 목록의 조용한 절단 보완
- 공식 첨부 목록은 **400건 이내에서 identity를 대조**합니다. 121번째의 정상 공식 첨부는 분석 대상에 포함됩니다. 400건을 초과하면 공식 첨부 탐색 상한을 `PARTIAL`과 명시적 경고로 표시하고 누락 원인을 감추지 않습니다.
- 합성 회귀 2건(121번째 정상 첨부 인식, 401번째 이후 탐색 상한 경고)을 추가했습니다. 앞의 Codex 개선 사항(출처 파일명 결속 및 최대 120개의 증거 이력에서 성공 2개 선정)은 유지합니다.
