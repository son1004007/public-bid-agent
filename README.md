# Public Bid Agent | 공공 입찰 참여 의사결정 지원

> 구현 단계: **사용자 PC에서 실행하는 로컬 Python MVP** + 별도로 보존 중인 React/FastAPI 화면 시안. 실제 AI 계정 로그인·외부 문서의 의미 검증·보안 독립 검수·운영 배포는 완료되지 않았습니다.
>
> Python 기준: **CPython 3.12.x** (CI: Python 3.12). 자세한 의존성·고지 의무는 [라이선스 검토](docs/DEPENDENCIES_AND_LICENSES.md)에 기록합니다.

## 1. 이 프로젝트가 해결하는 문제

공고/RFP/회사 정보에서 *참여 자격, 기술 요구, 투입 자원, 원가, 경쟁 및 계약 리스크*의 근거를 구조화한 후 Codex와 Claude의 의견을 비교하고, 최종 사용자가 참여·보류·미참여를 결정합니다. AI 의견과 실제 법적 적격 여부, 최종 사용자 결정, 수주 결과는 분리해 기록합니다. **입찰서 자동 제출이나 실제 낙찰확률 제공을 구현하지 않았습니다.**

## 2. 현재 로컬 실행 아키텍처

```mermaid
flowchart TD
    USER[사용자 브라우저] -->|127.0.0.1:8765, Host/Origin/CSRF| APP[Python 표준 HTTP 서버]
    APP -->|업로드 원본을 일시 전달| PARSER[별도 Python 문서 추출 프로세스]
    PARSER -->|텍스트, 추출 방식, 경고| APP
    APP <-->|원자적 저장 및 조회| STORE[내 PC ~/.public-bid-agent-local/cases.json]
    APP -->|명시적 외부전송 동의가 있을 때만| GRAPH[LangGraph StateGraph]
    GRAPH --> N1[독립 분석: Codex CLI]
    GRAPH --> N2[독립 분석: Claude Code CLI]
    N1 --> PEER[상대 의견 재검토 1회]
    N2 --> PEER
    PEER --> COMP[조건/점수/권고 이견 비교]
    COMP -->|미검증 의견·근거| STORE
    USER -->|검증값 수정 및 최종 선택| APP
    N1 -.->|모델 사용 시 원문이 AI 제공자에게 전송됨| OPENAI[OpenAI AI 서비스]
    N2 -.->|모델 사용 시 원문이 AI 제공자에게 전송됨| ANTHROPIC[Anthropic AI 서비스]
```

- 브라우저: `local_app/index.html`, `local_app/app.js`. 프롬프트 입력·파일 선택·동의·AI 의견 및 이견 표시·영향인자 검증·최종 선택.
- HTTP 및 로컬 저장: `local_app/server.py`. loopback 전용, `cases.json` 원자적 갱신, 8개 필수조건과 12개 비교인자, 사용자 최종결정 별도 저장.
- 문서 파서: `local_app/extractors.py`. PDF/한국어 OCR, Excel, HWP/HWPX, DOCX 및 일반 텍스트. 추출 제한/경고 표시. 별도 subprocess이지만 OS 수준의 완전한 악성파일 샌드박스는 아닙니다.
- AI 워크플로: `local_app/cross_review.py`. **실제 LangGraph** 노드 `independent_analysis → peer_critique → evidence_comparison`. 상대 모델을 1회씩 재검토하고 근거/값의 이견을 정리합니다. LangChain Core `ChatPromptTemplate`를 사용합니다. 한 모델만 성공하면 가짜 합의를 만들지 않습니다.
- 외부 실행: 설치·로그인된 `codex`/`claude` CLI만 명시적 동의 후 사용. 인스턴스/토큰을 직접 수집하지 않습니다. **실제 두 모델 인증·요금제 실행 성공은 사용자 PC에서 확인해야 합니다.** 한 공급자의 CLI 실패는 명시적 실패로 표시합니다.
- 저장: 앱 업무 데이터는 사용자 홈의 JSON에만 저장합니다. 모델 사용 시 자료가 선택한 업체로 전송되고, 각 CLI 자체의 세션·캐시 저장은 앱의 통제 밖입니다.

## 3. Python 설치 및 실행

### Windows PowerShell

Python 3.12.x를 설치하고 저장소 루트에서 실행합니다. `py -3.12 --version`으로 설치 버전을 확인합니다. **2026년의 Python 3.12 보안 릴리스는 소스 배포만 제공하므로 Windows 3.12 설치 프로그램 제공 여부를 공식 다운로드 페이지에서 확인**하고, 운영 PC의 보안 업데이트 정책을 따르세요.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r local_app/requirements.txt
.\.venv\Scripts\python.exe local_app/server.py
```

### macOS/Linux

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r local_app/requirements.txt
.venv/bin/python local_app/server.py
```

실행 후 `http://127.0.0.1:8765/` 방문. 종료는 터미널 `Ctrl+C`. 파일은 **`~/.public-bid-agent-local/cases.json`** 에 로컬 저장됩니다. 필요 시 `PUBLIC_BID_LOCAL_DATA` 및 `PUBLIC_BID_LOCAL_PORT` 환경변수를 설정합니다. `.venv`와 JSON은 Git에 넣지 않습니다.

### 스캔 PDF OCR 준비

별도 실행 파일 **Tesseract OCR**과 `kor`, `eng` 언어팩이 필요합니다. `tesseract --list-langs`로 확인합니다.

- Windows: Tesseract 배포판 설치 시 `kor` 선택, PATH 설정.
- Ubuntu/Debian: `sudo apt-get install tesseract-ocr tesseract-ocr-kor tesseract-ocr-eng`.
- macOS: `brew install tesseract tesseract-lang`.

## 4. 사용 순서

1. **공고 만들기**로 가상·실제 공고에 대한 로컬 검토 건을 생성합니다.
2. 설명 프롬프트를 작성하거나 **Excel(XLSX/XLS/XLSM), 일반·스캔 PDF, HWP/HWPX, DOCX, TXT/MD/CSV/JSON**을 선택해 텍스트를 추출합니다. PDF·표·OCR의 추출 한도와 누락 경고를 읽습니다.
3. 자신의 컴퓨터에 설치된 Codex/Claude Code CLI를 공식 절차로 인증하고, AI 사용 제공자를 선택합니다. **AI에 보낼 자료를 확인하고 외부 전송에 동의한 뒤** 실행합니다.
4. 모델별 독립 의견, 상대 의견 검토 및 이견 목록을 확인합니다. **2개 모델 선택 시 최대 4회 모델 요청**이 발생할 수 있습니다. API 비용·구독 이용 자격은 CLI 제공자의 계약·사용 정책에 따릅니다.
5. `AI 초안 적용` 버튼으로 미검증 영향인자를 채운 뒤 원문을 확인하여 오입력을 수정하고, 확인 항목에만 체크합니다. 자동 점수는 **실제 수주확률이 아닙니다**.
6. 최종 **참여/보류/미참여**를 직접 선택하면 사람이 선택한 결정과 이유가 JSON에 저장됩니다. AI는 최종 결정을 수정하지 않습니다.

설치·사용 방법 상세는 [local_app/README.md](local_app/README.md)와 동일 기준으로 유지합니다.

## 5. 데이터 흐름 및 저장 경계

- 원본 업로드 파일 바이너리는 업무 JSON에 넣지 않고 추출 텍스트·출처 파일명·추출 방식·경고를 기록합니다.
- JSON은 암호화되지 않습니다. PC/계정 권한, 디스크 암호화, 백업 범위는 사용자가 관리해야 합니다.
- 문서 내부에 있는 악성 프롬프트는 **비신뢰 데이터**입니다. 공식 입찰요건·금액·계약조건 등 중요한 사실은 사람이 원문과 증빙을 직접 확인해야 합니다.
- 선택한 AI 분석 요청 때에는 해당 원문 텍스트가 외부 서비스로 이동합니다. 기업 내부 문서는 회사 허가·기밀 유지 및 AI 서비스 계약을 먼저 확인하세요.
- 파일당 10MiB, 공고당 6개. 추출 텍스트 파일당 최대 44,000자, 모델 입력 90,000자, PDF 최대 40페이지/OCR 12페이지 등 현재 제한이 있습니다.

## 6. 기존 웹 UI 시안과의 관계

별도 `frontend/`(React/Vite)과 `backend/`(FastAPI)는 합성 공고 검색/입찰관리 화면 설계 시안입니다. **현재 로컬 앱과 동일한 프로덕션 서비스가 아니며**, 실제 나라장터 API·Google 로그인·PostgreSQL/RAG·공개 운영 배포는 완료되지 않았습니다.

- [웹 입찰관리 UI 시안](frontend/public/bid-management-preview.html)
- [계정 선택 UI 시안](frontend/public/ai-account-preview.html): 진짜 OAuth 연결 아님
- [미래 확장 아키텍처](docs/02-architecture.md): 로컬 우선 결정에 맞춰 별도 목표 구조로 유지

## 7. 테스트 및 변경 시 문서 갱신

```bash
python -m unittest discover -s local_app -p 'test_*.py' -v
node --check local_app/app.js
python scripts/check_documentation_sync.py
```

**코드·의존성·UI/API 계약이 변경되는 커밋에는 `README.md`와 `local_app/README.md`를 같은 커밋에서 갱신**해야 하며, GitHub CI가 이를 검사합니다. 아키텍처·데이터 흐름·새 모델/패키지·사용법이 바뀌면 `docs/02-architecture.md` 및 [의존성 라이선스 검토](docs/DEPENDENCIES_AND_LICENSES.md), `AGENTS.md`, `CURRENT_STATE.md`와 `TASKS.md`의 관련 부분도 같이 수정합니다. 이 검사는 문서 **수정 여부**를 강제하는 것이며 사실 관계까지 자동 보증하지 않으므로 PR 리뷰에서 일치 여부를 확인합니다.

## 8. 라이선스 및 미완료 게이트

코드·문서: [Apache License 2.0](LICENSE). 주요 패키지의 허용적 라이선스 사용은 가능하지만, **의존 패키지 전체와 PDFium/OCR 바이너리를 재배포할 때 고지·라이선스 파일 동봉 의무**가 존재합니다. [라이선스 검토표](docs/DEPENDENCIES_AND_LICENSES.md)와 [NOTICE](NOTICE) 참고. 인증·상용 모델 호출 계약은 오픈소스 코드 라이선스와 구분됩니다.

- CI: 실행형 로컬 코드와 문서 형식 테스트. **모의 AI CLI 응답으로 LangGraph 테스트**하며 실제 개인 계정으로 모델을 호출하지 않습니다.
- 미완료: 기관별 실제 HWP/RFP OCR 정확도, 완전한 파일 파서 샌드박스, LangGraph 영속 체크포인트/재개, 정식 RAG, 실제 두 모델 CLI 인증/출력 E2E, 독립 최종 보안 검수와 사용자 UI 승인.
- 검수 전 개발 브랜치 `feat/sprint1-search-demo` 및 [Draft PR #1](https://github.com/son1004007/public-bid-agent/pull/1) 유지. 사용자 승인 없는 운영 배포/`main` 병합은 진행하지 않습니다.
> CI 의존성 계약: 각 Python 패키지는 `local_app/requirements.txt`에 한 줄씩 기록합니다. 2026-10-09 LangGraph 추가 시 줄바꿈 오류를 검사하고 수정했습니다.

## 2026-10-10 Codex 단독 실행 모드

Claude Code 구독이 없더라도 Codex CLI 로그인만으로 독립 영향인자 분석 1회 → 미검증 초안 → 사용자 수정/원문 대조 → 최종 Bid/No-Bid를 수행합니다. 단일 AI는 교차검토가 아니므로 합의한 것처럼 표시하지 않습니다. Windows npm 설치는 확장자 없는 `codex`가 아닌 `codex.cmd`를 실행합니다. 계정 기본 모델이 Codex에서 지원되지 않을 수 있으므로 이 로컬 앱은 `gpt-5.6-terra`를 명시하고, `--ephemeral --ignore-user-config --ignore-rules --sandbox read-only`로 실행합니다. 모델 접근 권한은 계정/버전마다 다르므로 실패 시 UI에서 오류를 확인합니다.


### Windows 실환경 Codex 단독 테스트 (2026-10-10)

회사 노트북의 **합성 공고만** 사용한 기능 확인: Windows + Python 3.12 + Codex CLI 0.154.0, ChatGPT 인증. `-m gpt-5.6-terra`와 `--ephemeral --ignore-user-config --ignore-rules --sandbox read-only`로 한 차례 모델 요청, `/api/analyze` 성공. JSON에 필수 Gate **8개**, 비교 인자 **12개**, 권고 `hold`, `ai_draft`, `cross_review.status=single_or_failed` 기록 확인. 사람의 `decision=undecided` 유지 확인, 모델 응답 **21.2초**. 실제 Claude 연동/교차반론은 수행하지 않음.

해당 Windows 사용자에게 로컬 전용 시작 바로가기 `Public Bid Agent (Local)`를 만들었으며 `http://127.0.0.1:8765/` 접근 성공. 바탕화면 바로가기는 배포 소스가 아니라 **해당 노트북의 편의 실행 설정**입니다. 앱 업무 JSON과 테스트 JSON의 위치를 분리했고 바인딩은 `127.0.0.1`로 한정합니다. 개인 Codex 설정은 변경하지 않았습니다.

## 공개된 실제 입찰공고 3건을 이용한 MVP 검증 (2026-10-10)

`local_app/fixtures/public_tenders_2026_10_10.json`에는 공개 입찰공고 **3건의 수기 전사 정보**와 **실제 회사가 아닌 가상 부서 4개 시나리오**를 저장합니다. [공고/업체 개인정보 및 재현성 검증](local_app/test_public_tenders.py)은 소스 URL과 공고번호/마감/가정 자료의 구분을 확인합니다. 공식 나라장터 원본 첨부 다운로드는 403 오류여서 직접 검증하지 못했으므로, 전재문·메타데이터 출처를 명시하고 실제 입찰 전 정정/마감 확인이 필수입니다. **실제 어니컴 부서의 인력·등록 자격·실적은 입력하거나 추정하지 않았습니다.** 이 자료는 실제 낙찰 확률의 정답 데이터가 아닙니다.

### 2026-10-10 실제 공고 검증 결과에서 나온 변경

실제 공고 3개 / 가상 부서 4개로 Codex를 실행했을 때 모델은 모두 보류 권고를 냈고 `reason`을 비워 반환했습니다. 단순 보류만 표시하면 **명시적 참가요건 불일치와 자료 부족을 구별하지 못하므로**, `local_app/decision_support.py`를 추가했습니다. `REVIEW_NO_BID_PROVISIONAL`(AI 제시 미충족), `HOLD_UNVERIFIED`, `HOLD_CONFLICT`, `READY_FOR_HUMAN` 등은 AI의 판단/사용자 결정과 별도로 저장됩니다. AI가 작성하지 않은 권고 사유는 임의로 생성하지 않고 **모델 사유 미제공** 경고로 보여줍니다. 공고 사실은 재게시 공개자료, 업체·부서 조건은 가정값임을 표시합니다.

## 2026-10-10 실공고 수기 MVP 검증 상태

**공개 입찰공고 3건 + 가상 부서 조건 4개**를 실제 Codex 구독으로 분석하고, AI 원문/하드게이트/원문 미확인/사람 결정을 로컬 JSON에 구분해 저장했습니다. 실제 AI 4건 분석과 개정 HTTP 위험 재분류에 성공했습니다. 자세한 수치와 원문 출처 제한은 [MVP 검증 보고서](docs/reviews/MVP_PUBLIC_BID_E2E_2026-10-10.md)를 참고하세요. 회사 노트북 `Public Bid Agent (Local)` 바로가기로 확인할 수 있으며 검증 사례의 회사 능력은 전부 **가상**입니다. **AGY/Codex 독립 최종 검수는 원격 권한 정책으로 막혀 `main` 병합을 보류**합니다. 권한을 우회하지 않습니다.
