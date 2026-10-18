# P09 Windows API·Chrome 합성 인수 및 배포 게이트

## NO_GO/P1 후속 수정: 합성 배치 경로 격리

- 독립 검수에서 기존 fixture의 `ROOT` 변경이 import 시 생성된 `RFP_BATCH`에는 적용되지 않는 결함을 확인했다. 아래 최초 48 PASS는 `/api/rfp-batch`의 격리를 검증하지 않았으므로 합성 전용 경계의 충분한 증거가 아니다. 기존 판정은 **NO_GO**, 수정분 독립 재검수는 orchestrator 인계다.
- `synthetic_server()`가 임시 root의 실제 manager를 새로 생성하고 `ExitStack`으로 교체/복원한다. extractor·related·key_getter·기본 fetcher를 모두 명시적인 실패 mock으로 지정한다. 운영 앱/브라우저 runner/CI 정의는 이번 수정에서 변경하지 않았다.
- 회귀 실행 전 기존 manager의 status와 root 경로 연산을 메모리 차단자로 대체한다. 수정 전 신규 GET 2개 실행은 **FAIL(1 failure / 3 errors, RUNNING 하위 경우 포함)**: 기존 manager 호출을 잡아냈으며 운영 파일/디렉터리/잠금은 조회하지 않았다.
- 신규 3개 회귀는 `IDLE` GET, 합성 `RUNNING` 장부의 worker lease 유무에 따른 `PAUSED`/`RUNNING` GET, 네 외부 어댑터 차단을 검증한다. 실제 임시 worker lock을 사용하며 장부 revision/바이트·dashboard 불변 및 기존 manager 미호출을 확인한다. 어댑터는 mock 여부를 먼저 검사하여 잘못된 fixture에서도 실제 인증 함수를 호출하지 않는다.
- Windows CPython 3.12.0: 수정 후 API 인수 **11 PASS**, 관련 6개 모듈 **51 PASS**(130.605초). 이후 어댑터 시험의 mock 선확인 assertion 추가분도 집중 재실행 **1 PASS**. 저장소 전체 회귀/CI는 이번 후속에서 실행하지 않았다.
- Chrome 155.0.8059.40 / Node 22.14.0 재실행: `Browser.getVersion` 후 페이지 생성 중 sandbox 진단과 exit `2147483651`, **CHROME_E2E BLOCKED**. runner의 fixture 종료/보존 확인은 통과했으나 UI 시나리오는 실행되지 않았다. sandbox/TLS/CSP/권한을 완화하지 않았다.
- Python AST·Node 문법, 수정한 미추적 테스트/보고서 공백 및 README 두 곳의 후속 설명 일치 검사 PASS. 중간 tracked diff 공백 검사는 통과했지만 최종 Git 재확인은 sandbox 실행 계정의 `dubious ownership`으로 BLOCKED. Git 전역 설정/신뢰 예외를 변경하지 않았으며 최종 diff와 같은 커밋 README 동기화 검사는 orchestrator가 수행한다.
- 사용자 자료 접근·외부 비공개 전송·운영 적용·배포·main 변경·add/commit/push 없음. D-10/P11 보류. 아래 최초 실행 기록은 후속 격리 수정의 검수/실행 증거와 구분한다.

후속 명령(`local_app` 디렉터리):

```powershell
python -B -m unittest test_local_acceptance -v
python -B -m unittest test_local_acceptance test_bid_outcome_recovery test_bid_outcomes test_json_transaction test_release_rfp_stage test_process_limits -v
```

Chrome 명령은 저장소 루트에서 `node scripts/test_chrome_synthetic.cjs`이며 원래 runner를 그대로 사용했다.

## 최초 작업 기록 (격리 결함 수정 전)

- 날짜: 2026-10-18. 기준 브랜치 `feat/sprint1-search-demo`, 작업 시작 HEAD `c0dcfff`.
- 상태: API/복구 `VERIFIED`; Chrome 시나리오 `IMPLEMENTED_UNVERIFIED / BLOCKED`; 독립 Codex 검수·CI `NOT RUN`, orchestrator 인계. P09 전체 완료 아님.
- 사용자 최신 지시: 공개 소스와 합성 fixture만 사용. 사용자 JSON/비공개 RFP/회사 증빙·기존 운영 서버 접근 금지. main·배포/공개·보안 완화·자동 입찰·add/commit/push 금지. D-10/P11 과거 API 실패 조사는 보류.
- CONTROL, registry, 지정 handbook 원본은 GitHub 연결로 확인. 중앙 관련 열린 사용자 조치 검색은 0건. 시스템 보안 설정이나 Git 전역 설정 변경 없음.

## 변경과 검증 범위

`local_app/test_local_acceptance.py`는 임시 폴더·임의 루프백 포트와 합성 공고/TXT만 사용한다. 앱 `Handler`의 Host/Origin/CSRF·보안 헤더·JSON 검증·복구 가드를 그대로 실행한다. fixture 전용 POST 허용 목록은 수기 이력/원본 대조 두 경로뿐이며 실제 키 조회/저장·외부 API/AI 함수는 실패하도록 대체한다. fixture 종료 시 서버 종료 및 기존 cases/TXT/캐시 바이트 보존을 검증한다.

신규 8개 HTTP 시험:

1. HTML/JS/API 정상 응답의 no-store, CSP, nosniff, frame/referrer 정책과 CORS 비허용.
2. 잘못된 Host, 누락/다른/null Origin, 누락/잘못된 CSRF의 403 및 JSON 불변.
3. 손상 JSON, 배열/null, 잘못된 Content-Type의 400 및 경로/traceback 비노출.
4. PREPARED SQLite 복구 의도 시 GET/POST 503 및 복구 payload 비노출.
5. 손상된 SQLite 의도 시 GET/POST 안전 차단.
6. 수기 사건 저장·중복 revision 409·재조회, 사람 최종 결정/기존 판단이력 보존.
7. 선택 파일 SHA 불일치, 메모리 처리/원본 미보관 및 기존 자료 불변.
8. 일치하는 합성 TXT를 실제 제한된 parser subprocess로 재현, 원본 미보관/본문 비반환.

`scripts/test_chrome_synthetic.cjs`는 Node 내장 모듈만 사용해 fixture 서버와 새로운 headless Chrome 프로필을 시작한다. 기존 Chrome 계정/탭/프로필을 조회하지 않는다. CDP pipe, 실제 마우스 이벤트와 `DOM.setFileInputFiles`로 목록/상세·HTML 문자 안전 렌더링, 파일 누락/불일치/일치, 수기 필수입력/저장/새로고침, 390px 상세를 검사하도록 작성했다. 페이지 요청은 fixture origin만 허용하며 외부 요청/미처리 페이지 예외를 실패로 판정한다. CDP/조건/전체 시간 제한과 소유 프로세스·프로필 정리가 있다. **현재 환경에서는 UI 단계에 도달하지 못했으므로 이 시나리오를 통과했다고 주장하지 않는다.**

`.github/workflows/windows-synthetic-acceptance.yml`은 Windows/Python 3.12/Node 22에서 같은 API·복구/Chrome 경로를 실행하도록 추가했다. 읽기 권한만 사용하며 배포·릴리스·아티팩트 업로드를 하지 않는다. Chrome 부재/실패를 성공이나 skip으로 바꾸지 않는다. 기존 Ubuntu CI는 변경하지 않았다.

## 실제 실행 증거

| 검증 | 결과 | 근거/한계 |
| --- | --- | --- |
| Windows CPython 3.12.0, 관련 6개 모듈 | **48 PASS**, 126.904초 | 신규 API 8개 + 기존 수기 이력/프로세스 잠금/복구/메모리 제한. skip 없음 |
| Python 컴파일·Node 22.14.0 문법 | PASS | 새 테스트/runner 구문 검사. UI 실행을 대체하지 않음 |
| 문서·workflow 정적 검사 | PASS | 작업 트리 공백, 신규 파일 공백, README 2종 P09 링크, YAML 파싱/Windows runner/읽기 권한 확인. 기존 README 검사기는 이전 커밋을 검사하므로 이번 미커밋 변경의 증거로 재사용하지 않음 |
| Chrome 155.0.8059.40 | **BLOCKED** | 버전 조회 성공 후 새 페이지 생성 중 종료 `2147483651`, sandbox 관련 진단. 정확한 OS 원인은 미확정. 재시도에서도 동일 단계 실패; 보안 완화하지 않음 |
| Windows GitHub Actions | NOT RUN | 파일 추가만 수행. orchestrator 검수·Git 기록 후 실제 실행 필요 |
| 독립 Codex 최종 검수 | NOT RUN | 소스·테스트·이 문서 인계. 기존 작업의 GO를 재사용하지 않음 |
| 운영 데이터 SHA/실제 복구·서버 적용 | NOT RUN | 실제 자료를 읽지 않았으므로 이전 164개 등의 SHA 불변을 이번 결과로 주장하지 않음 |

재현 명령(저장소 루트 PowerShell):

```powershell
$env:PYTHONPATH = 'local_app'
python -m unittest test_local_acceptance test_bid_outcome_recovery test_bid_outcomes test_json_transaction test_release_rfp_stage test_process_limits -v
python -m py_compile local_app/test_local_acceptance.py
node --check scripts/test_chrome_synthetic.cjs
node scripts/test_chrome_synthetic.cjs
```

Python 선택이 필요하면 `P09_PYTHON`, Chrome 실행 파일 선택이 필요하면 `P09_CHROME`에 실행 파일 경로만 지정한다. 데이터/운영 서버 경로 인수는 없다. Chrome 실패를 피하기 위해 sandbox/TLS/CSP를 끄거나 관리자 권한·전역 정책을 변경하지 않는다. 검증된 일반 Windows 실행 환경 또는 추가한 CI에서 동일 명령을 실행한다. Python fixture의 `--serve-chrome`은 runner가 소유하는 stdin 종료/120초 제한을 위한 내부 모드이다.

## 보안·라이선스·복구의 분리된 게이트

| 게이트 | 통과에 필요한 증거 | 현재 판정 |
| --- | --- | --- |
| 합성 API 보안 | 실제 Handler의 거부·정보 비노출·불변 자료 | PASS, 로컬 단일 사용자 범위. 전체 보안 감사 아님 |
| 합성 복구/격리 | 기존 승인 도구의 임시 데이터 전용 plan/apply/recover/rollback·최신 편집 거부·OS 잠금/Windows 경로 고정·메모리 제한 | PASS. 실제 운영 배포/전원 장애 보장 아님 |
| Chrome 기능 | 새 runner의 파일 선택·저장/재조회·모바일·외부 요청 부재 | BLOCKED, 환경에서 재실행 필요 |
| 실행 의존성 | 선언 범위의 모든 사용 패키지/선택 OCR·AI 구성 검증 | BLOCKED. 아래 현재 설치 목록의 누락/버전 미달 |
| 라이선스/공급망 | 정확한 후보 버전 잠금·전이 SBOM·배포 파일별 LICENSE/NOTICE·취약점 검증 | NOT RUN. 기존 직접 의존성 조사/새 의존성 없음으로 대체 불가 |
| 독립 검수/CI | 정확한 변경분의 Codex GO, 해당 소스의 Windows/기존 CI | NOT RUN, orchestrator 인계 |
| 실제 로컬 적용 | 위 게이트 및 승인된 비파괴 경로, 별도 권한의 백업/해시·복구 증거 | NOT RUN. 사용자 최신 배포 금지 지시 유지 |
| 사용자 UI/main/인터넷 공개 | 별도 사용자 인수·명시 승인, 공개 서비스 보안/권한/운영 조건 | NOT RUN / 이번 범위 제외 |

패키지 메타데이터만 확인한 현재 환경: pypdf 6.14.2, python-docx **1.1.2**(선언 `>=1.2` 미달), openpyxl 3.1.2, pypdfium2 4.30.1, Pillow **10.3.0**(선언 `>=11` 미달). xlrd, pytesseract, python-hwpx, langgraph, langchain-core는 미설치. 자동 설치·업그레이드나 새 의존성 추가 없음. 새 tests/runner는 표준 라이브러리 기반이며 전체 앱/OCR/AI 지원을 증명하지 않는다.

기존 `promote_verified_rfp_stage.py` 경로의 테스트는 모두 테스트가 생성한 임시 live/stage/backup에 한정했다. 운영 경로를 대상으로 dry-run/apply/rollback/recover를 호출하지 않았다. 실 운영 검증은 사용자 자료 읽기 금지와 배포 금지 때문에 이번 인계의 잔여 항목이다.

## 다음 검수자가 확인할 사항

- 실제 Chrome 시나리오는 미검증이다. 정상 Windows 환경에서 재실행하고 selector/브라우저 동작 실패가 있으면 동일 합성 경계에서 수정한다.
- 검수 대상은 새 테스트/runner/Windows workflow와 관련 문서다. 앱 동작·스키마·다른 작업자의 구현은 변경하지 않았다.
- 실행 증거와 독립 검수는 분리한다. orchestrator는 검수 후 Git 기록/CI를 처리하며, 이 작업에서는 add/commit/push를 실행하지 않았다.
- P09 전체 완료·UI_APPROVED·LOCAL_APPLIED·MAIN_MERGED·PUBLIC_RELEASED로 승격하지 않는다. D-10/P11 보류 유지.

공식 API 확인: [Chrome Headless](https://developer.chrome.com/docs/automation-and-testing/headless), [CDP DOM.setFileInputFiles](https://chromedevtools.github.io/devtools-protocol/tot/DOM/#method-setFileInputFiles). 브라우저 테스트를 작성하는 근거이며 실제 통과 근거는 아니다.
