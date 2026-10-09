# Public Bid Agent - 개인 컴퓨터 로컬 실행 MVP

이 폴더는 공개 웹사이트가 아니라 **내 컴퓨터에서만 실행하는** 프롬프트·문서 기반 입찰분석 앱입니다.

## 실행

Python 3.11 이상 설치 후 저장소 루트에서 다음 명령을 실행합니다.

Windows PowerShell:

    py -m pip install -r local_app/requirements.txt
    py local_app/server.py

macOS/Linux:

    python3 -m pip install -r local_app/requirements.txt
    python3 local_app/server.py

실행 중 표시되는 \`http://127.0.0.1:8765/\`을 브라우저에서 엽니다. 터미널에서 Ctrl+C로 종료합니다.
기본 데이터 경로는 사용자 홈 디렉터리의 \`~/.public-bid-agent-local/cases.json\`입니다.
\`PUBLIC_BID_LOCAL_DATA\` 환경변수로 로컬 저장 위치를 변경할 수 있습니다. 외부 서비스에 자동 업로드하지 않습니다.

## AI 추출 사용

1. 공고 만들기 -> 자유 프롬프트 또는 파일(txt, md, csv, json, pdf, docx, xlsx, xls, xlsm, hwp, hwpx)을 등록합니다.
2. 설치된 Codex CLI 또는 Claude Code CLI를 공식 절차로 로그인합니다. 로컬 계정 인증정보를 앱에 복사/붙여넣지 않습니다.
3. 화면에서 분석 제공자를 선택하고 외부 전송 여부에 **명시적으로 동의**한 뒤 분석합니다.
4. AI 결과가 실제 JSON 구조로 반환되면 항목별 제안 초안이 생성됩니다. 'AI 초안 적용'을 누르면 사람 검증값을 덮어쓰지 않는 미확인 값으로 반영됩니다.
5. 값/근거를 수정하고 '내가 확인함'을 체크한 후 로컬 저장합니다. 최종 참여/보류/미참여는 사람이 따로 결정합니다.

Codex CLI는 설치가 확인될 때 \`codex exec --sandbox read-only --skip-git-repo-check -\`를, Claude Code CLI는 \`claude -p --tools "" --max-turns 1 --output-format text\`를 호출합니다. 실패·로그인 누락·미설치 시 결과를 위조하지 않습니다.

**중요:** 로컬 프로그램의 JSON 보관과 외부 모델 분석은 다릅니다. AI 실행 시 요청 내용은 선택한 제공자의 서버로 전송되며, 설치된 CLI 자체도 별도 캐시·세션·로그 파일을 생성할 수 있습니다. 회사/개인정보는 관련자의 외부 전송 허가 없이는 보내지 마세요. Claude Code의 구독 기반 외부 프로그램 사용 자격은 해당 시점의 Anthropic 이용조건을 확인해야 합니다.

## 로컬 저장과 보안 경계

- 앱의 관리 데이터는 모두 로컬 JSON. 파일 원본 바이너리를 보관하지 않고 추출된 텍스트만 로컬 JSON에 추가합니다.
- 포트는 127.0.0.1 전용입니다. LAN/인터넷에 공개하지 않습니다. Host/Origin/CSRF 검사, Content-Security-Policy를 적용합니다.
- Linux/macOS에서는 데이터 폴더 0700, JSON 파일 0600 권한을 적용합니다. Windows 권한은 파일시스템/사용자 계정 ACL에 따릅니다.
- PDF/Excel/HWP/HWPX/DOCX 파싱은 별도의 제한된 로컬 Python subprocess에서 수행하지만 **완전한 샌드박스는 아닙니다**. 출처를 신뢰할 수 없는 문서는 운영 환경에서 별도 격리 파서가 필요합니다. 스캔 PDF OCR(한국어 Tesseract 언어팩 필요), HWP/HWPX, XLS/XLSX/XLSM 추출을 지원합니다. 암호화·배포용 HWP와 DRM, HWPX 내부 암호화 및 이미지 포함 표/차트 OCR은 지원하지 않습니다.
- 로컬 JSON은 **암호화되지 않습니다**. 개인 PC 디스크 암호화/백업 권한을 별도로 관리하세요.
- 프로그램은 실제 전자입찰, 계약, 로그인 공유, 낙찰률 예측을 하지 않습니다.
- 주 API는 \`/api/state\`, \`/api/new\`, \`/api/save\`, \`/api/file\`, \`/api/analyze\`, \`/api/decide\`. 문서/모델은 소스 데이터를 증빙 없이 확정하지 않습니다.

## 테스트

    python -m unittest discover -s local_app -p "test_*.py" -v
    node --check local_app/app.js

이 프로토타입은 별도의 UI/데이터 계약 검증용 구현입니다. 기존 React/FastAPI 웹앱, LangChain/LangGraph 에이전트 운영 스택을 대체하거나 공개 배포 승인까지 완료한 것이 아닙니다. LangGraph 워크플로와 provider별 공식 API/OAuth, 안전한 파일 파서는 사용자 UI/실제 사용조건 검증 후 단계적으로 연결합니다.

## 2026-10-09 문서 읽기 기능 확장

| 입력 확장자 | 추출 방식 | 한계 |
| --- | --- | --- |
| .xlsx/.xlsm | openpyxl 읽기 전용, 데이터 값만 | 수식은 마지막 저장된 계산값(없으면 빈 값). 매크로 실행 안 함; 24시트/시트당 2,500행 및 90열 제한 |
| .xls | xlrd 바이너리 표 데이터 읽기 | 구형 Excel 파일, 저장된 결과값만 |
| .pdf | pypdf 문자 추출 | PDF 40페이지까지, 부족한 페이지는 한국어 OCR 자동 보완 |
| 스캔 PDF | pypdfium2 렌더 + pytesseract + 로컬 Tesseract | OCR 12페이지까지, 이미지 인식 오류/누락은 직접 확인 필수 |
| .hwp | python-hwpx HWP 5.x 바이너리 텍스트 읽기 | 암호/배포용/DRM·비표준 HWP 미지원. 실제 일반 HWP 문서 추가 샘플 검증 필요 |
| .hwpx | ZIP/XML 본문·표에서 텍스트 추출 | 이미지로 삽입된 내용, 그림/수식, 일부 특수 구조 미지원 |
| .docx | python-docx 문단 + 표 | 텍스트/표 이외 그림·차트 등은 미추출 |

필요 라이브러리 설치: `python -m pip install -r local_app/requirements.txt`. **PDF OCR에는 Python 패키지 이외의 Tesseract OCR 실행 파일과 한국어 `kor.traineddata`가 반드시 필요합니다.**

- Windows: Tesseract(UB Mannheim 유지관리 배포판 등) 설치 시 한국어 언어팩 선택, 설치 경로를 PATH에 추가. `tesseract --list-langs`에서 `kor` 확인.
- Ubuntu/Debian: `sudo apt install tesseract-ocr tesseract-ocr-kor tesseract-ocr-eng`
- macOS: `brew install tesseract tesseract-lang` 후 `tesseract --list-langs` 확인.

오류/추출 한도:
- 입력은 파일당 10MiB, 공고당 6개. ZIP/OLE 파일 형식 확인, 압축 파일 총해제 크기 35MiB, 내부 파일 750개 제한.
- 추출 문자는 파일당 44,000자로 제한되고 **일부만 추출된 경우 UI에 경고**합니다. 현재 모델 호출 시 문서 6개를 합쳐 90,000자 한도로 전달하므로 문서 전체 해석이 보장되지 않습니다.
- 업로드 파일 원본은 업무 JSON에 저장하지 않지만 서버와 파서 실행 중 메모리/OS 임시영역을 사용합니다. 파서 실행 시 90초 제한, POSIX에서 CPU/주소공간 사용량 제한. 완전한 OS 격리/샌드박스는 아니므로 신뢰할 수 없는 외부 문서 실행환경 분리가 후속 보안 과제입니다.
- OCR은 **100% 정확하지 않습니다**. 중요한 참가자격·마감·금액·점수는 원문을 직접 확인한 뒤 확정합니다.
- 파일 내용은 앱 로컬에서 추출하고 JSON에 보관합니다. 사용자가 AI 분석에 동의하고 실행하면 **추출된 문서 내용이 선택한 AI 업체로 전송**됩니다.

테스트: `python -m unittest discover -s local_app -p "test_*.py" -v`. HWP 및 구형 XLS 테스트는 CI에 설치된 라이브러리로 실행합니다.