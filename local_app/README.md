# Public Bid Agent — 로컬 실행 사용법

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
