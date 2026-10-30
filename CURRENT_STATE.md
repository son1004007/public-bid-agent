## 2026-10-31 H01 실행 코드 추가 — 검증 진행 중

작업 정의 `harness/tasks/A01.json`, 명령 registry, `scripts/task_harness.py`의 validate/run/verify/status,
구조화 unittest adapter와 제한 실행기를 구현했습니다. [반복 사용 안내](docs/implementation/HARNESS_USAGE.md)를 따릅니다.
A01 날짜 테스트는 변경하지 않았고 H02가 다음 단계입니다. 외부 GO/CI/실자료 완료 및 운영 배포로 승격하지 않습니다.
Linux 합성 인수 15개 실행 결과와 Windows/독립 검수/CI 결과는 별도 검증 기록으로 확정합니다.

# 현재 개발 상태

## 2026-10-31 하네스 설계·Gateway 실행 안내

- [하네스 계약](docs/design/EXECUTION_HARNESS_SPEC_2026-10-31.md): task/명령 allowlist·고정 소스·구조화 테스트·독립 검수/CI 결속·실행 기록·재개/무효화·인수 시나리오. 코드 구현/제품 테스트/배포는 NOT RUN.
- [Gateway 런북](docs/implementation/GATEWAY_CODEX_HARNESS_RUNBOOK_2026-10-31.md): Windows 비승격 버전 probe 성공(Codex0.163.0/Python3.12.0). 별도 인증 상태 probe는 TIMEOUT_TERMINATION_UNCONFIRMED; 실제 모델 호출 가능 여부 미확인. 상세 증거·재개 절차는 런북 참조.
- 기준 main `0892b35`의 [CI41066016072](https://github.com/son1004007/public-bid-agent/actions/runs/41066016072)는 failure 확인. 이번 문서 게시로 CI/제품 검증을 통과시켰다고 주장하지 않음.
- 다음 개발: [H01 프롬프트](docs/implementation/CODEX_HARNESS_H01_PROMPT_2026-10-31.md)로 최소 하네스가 실제 합성 테스트와 A01 결과를 기록하도록 구현. H02에서 A01 날짜 수정·전체 검증. 아래 A01 첫 작업은 첫 제품 수정 순서를 뜻함.

## 2026-10-30 설계·구현 검토 및 재개 문서

- [제품 검토/근거/재개 계획](docs/reviews/PRODUCT_REVIEW_AND_RESTART_PLAN_2026-10-30.md), [AI 시작점](docs/implementation/AI_START_HERE.md), [작업 카드 A01~A08](docs/implementation/AI_EXECUTION_TASKS_2026-10-30.md).
- 확인 main `a4440a2`, 개발 `09068bf`, 마지막 기능 `a4b7cd4`. BID-06 도구 구현 완료/실자료 검증 보류, BID-07 미착수.
- 최신 [CI 40881574416](https://github.com/son1004007/public-bid-agent/actions/runs/40881574416) backend FAIL/frontend PASS. 고정 10월20일 마감 테스트의 OPEN 기대가 현재 CLOSED와 충돌하며 이번에 동일 실패 재현. 현재 전체 CI green 아님.
- 이번 부분 검증: Python3.12.14 관련38 PASS, Node24.22.1 검수 UI 계약6 PASS. 전체 회귀/Windows/Chrome/현재 운영/실자료 평가 NOT RUN. 소스 수정·배포 없음. 과거 PASS/운영수치와 구분.
- 다음: 개발 재개 범위에서 A01 날짜 테스트 정비, 이후 A02/A03 실제 원본·정답 검증. 상세 조건은 카드 참조.

## 2026-10-19 17:28 KST BID-06 IMPLEMENTATION_DONE / 실자료 NOT_EVALUATED

- 독립 정답 구절·원본 페이지/표/각주 위치·분류·추출 비교, 명시 승인/수정/보류/누락 등록·이력·SHA/차수 변경 재검수, 범위 한정 TP/FP/FN/Precision/Recall/F1/누락률 도구를 기존 목록/상세/API에 연결했다. 후보는 독립 정답으로 승격하지 않는다. 공식 원본 SHA 티켓과 사람의 최신성/전체 선택 페이지·표/각주/이미지/OCR 확인 전 승인 불가. 기존 원본/설정/이력 불변, 새 검수 파일은 사람 명시 저장만 생성한다.
- Python504(local_app479+감사14+backend11)·Node42·Chrome155 390/1440 전체 E2E/build/정적 PASS. 독립Codex 최초 NO_GO MAJOR1(배포 성공 소스/프로세스 오판) 수정 후 최종 GO, 순수모형7+독립경계4 PASS. [설계](docs/design/BID06_GROUND_TRUTH_2026-10-19.md), [전체 검증](docs/reviews/BID06_GROUND_TRUTH_2026-10-19.md).
- 실행 구현 `a4b7cd402c634807092d72a3fd1f25188819112c`: [개발 Sprint 1 CI](https://github.com/son1004007/public-bid-agent/actions/runs/39222149967)·[Windows acceptance](https://github.com/son1004007/public-bid-agent/actions/runs/39222149888)·[main CI](https://github.com/son1004007/public-bid-agent/actions/runs/39222548603) 모두 SUCCESS. 기존 main b20f515 조상 확인 후 fast-forward. Ubuntu479+14+11 및 Windows128/전체 Chrome PASS.
- 17:28:26 KST 기존127.0.0.1:8765 배포·API200·GET 전용 운영Chrome390/1440 인수 PASS. Windows venv launch/직계 child listener의 정확 소스/생성 시각/계보 검증, 첨부·설정·이력 포함393파일 전체 백업·SHA 대조/배포 전후 동일. 이전 검증 소스de8c294/백업·복구 경로 보존, 성공하여 실제 rollback 불필요.
- 실제5718, 보관 문서 공고70·차수 미검증127문서, 승인 정답0·실자료 정확도 NOT_EVALUATED/BLOCKED_EVIDENCE. 운영 검수 목록113건(저장 증거 메타데이터 포함, 유효 문서 수와 다름), 새 실자료 검수 파일 생성 없음. 전체 정확도/대표성·회사 적격/수익/인력/MM 미확인. **VALIDATION_DONE 및 BID06 전체 DONE 아님.** 최신 공식 원본·독립 사람 정답·실측 결과 독립검증 필요. BID07 미착수.
- 문서 마감 commit은 실행/테스트/CI 코드가 위 배포 SHA와 동일하다. 최종 개발/main 문서 HEAD CI는 별도 최종 확인·보고하며 문서 때문에 서비스를 재시작하지 않는다. 사용자 승인 메모 미추적 보존, 외부 공개/실제 입찰·자동 투찰/외부 참여 확정 없음.

## 2026-10-19 16:10 KST BID-05 DONE / main·기존 localhost 운영 인수 PASS

- 공식 문서 보완 작업/보류 큐와 기존 후보 화면/API를 구현했다. 미확보/다운로드 대기·실패/추출 실패·부분 추출·잘림·경고/정정·취소·마감·SHA·버전 결속을 구분하고 마감/확인 소요별 우선순위, 근거·다음 작업·재평가 제한을 제공한다. 기존 성공/사용자 검토 이력 보존, 역량/분야 불일치 자동 제외 없음. 실제 적격·수익·인력/MM은 UNVERIFIED/BLOCKED_EVIDENCE, 원본 전체 분석 완료 아님.
- 최종 Python482(local_app457+감사14+backend11)·Node36·Chrome155 390/1440 전체 E2E·build PASS. 독립 read-only Codex 최종 GO, MAJOR1·MINOR1 해결(캡처 revision/상세 전 GET·차수/ID·요청/화면 경합 방어), 독립Node28 PASS. [전체 검증/이력](docs/reviews/BID05_DOCUMENT_FOLLOWUP_2026-10-19.md).
- 실행 구현 `de8c294d8afc5ddbc3f2ff5ba70eb9d52885c708` 개발 push 후 [개발 Sprint 1 CI](https://github.com/son1004007/public-bid-agent/actions/runs/39213540830)·[Windows acceptance](https://github.com/son1004007/public-bid-agent/actions/runs/39213540829)·[main CI](https://github.com/son1004007/public-bid-agent/actions/runs/39213881253) 모두 SUCCESS. Ubuntu457+14+11 PASS, Windows106 PASS 및 새 큐/기존 전체 Chrome PASS. 기존 main bd1c072가 조상·원격 변경 없음 확인 후 fast-forward했다.
- 기존 소유자 전용 `127.0.0.1:8765`에 16:10:32 KST 고정 소스를 적용했다. 이전 검증 소스4f1743d/백업·정확 PID 확인, 첨부·설정 포함393파일 백업 및 SHA 검증, 배포 후393파일 전체 동일. API200·운영390/1440px 읽기 전용 큐/작업·보류·legacy 경고 및 기존 흐름 PASS. 복귀 조건/이전 소스 확인, 배포 성공으로 실제 복귀는 불필요했다. 인터넷 공개/방화벽/이전·초기화·실제 입찰/자동 투찰/외부 참여 확정 없음.
- 16:11 KST 운영 API: 전체5,718 / 확인작업2,870 / 보류2,848. 시간 경과로 최초15:37의2,872/2,846과 달라졌지만393파일 bytes는 그대로다. 공식 최신성·원본 binary 재확인 및 회사 증빙 미검증은 공고별 보류로 유지한다. 문서 마감 커밋은 실행 코드가 위 배포 SHA와 같아 재시작하지 않는다. 로컬 승인 메모 미추적 보존, BID-06 미착수(승인된 최신 원본/사람 정답 표본 선행).

## 2026-10-19 15:10 KST BID-04 DONE / main·기존 localhost 운영 인수 PASS

- 구현: 실제 로컬 공고의 전체/활성/보류·기한·취소/정정/STALE·일관성·분야 비교/역량/MM/원가 증빙 부족을 CLI와 기존 후보 화면/API로 읽기 전용 표시. 증빙 없음은 BLOCKED_EVIDENCE, 적격/수익/보완 허용은 UNVERIFIED, 역량 부족 자동 배제 없음. 실제 입찰/자동 투찰·인터넷 공개 없음.
- 검증: Python468(local_app443+감사14+backend11), Node27, build PASS. 기본 sandbox Chrome155 합성390/1440px PASS. 별도 읽기 전용 Codex 최초 MAJOR1 수정/재확인 후 GO, 인계 CI 격리·첨부 포함 백업·명시 refspec 보완도 GO 유지. 실제 자료5,718/활성2,369·부서 비교불명2,369; 회사 증빙은 미검증.
- 개발 및 main 실행 소스 `4f1743d78f2c909bc60b63ad341e8a643b6a32ce`. [개발 Sprint 1 CI](https://github.com/son1004007/public-bid-agent/actions/runs/39207655216), [Windows synthetic acceptance](https://github.com/son1004007/public-bid-agent/actions/runs/39207655224), [main CI](https://github.com/son1004007/public-bid-agent/actions/runs/39208016065) 모두 SUCCESS. 기존 main `10b4dcb`가 조상임을 확인한 fast-forward이며 main의 기존 작업·Lab 작업 트리/설정은 보존했다.
- 기존 소유자 전용 `127.0.0.1:8765`에 검증된 고정 소스를 적용했다. 첨부 포함393파일 백업·SHA 확인 및 배포 후393파일 전부 동일, API200·390/1440px GET 전용 Chrome/legacy 무결성 경고·기존 화면 인수 PASS. 이전 고정 소스와 백업의 존재·실패 시 소스 복귀 절차 확인, 실제 복귀는 불필요했다. 데이터 복원/덮어쓰기 없음.
- 문서 마감 커밋은 실행 코드가 위 배포 SHA와 같으며 재배포/재시작을 유발하지 않는다. BID-05 미착수. 비공개 로컬 승인 메모는 미추적 상태로 보존했다. [전체 검증/제약](docs/reviews/BID04_UI_DEPLOY_2026-10-19.md). 아래 대기/NO_GO는 이전 실행 이력이다.

## 2026-10-19 BID-04 화면·API VERIFIED / 독립 GO / CI·배포 대기

- 기존 작성자 종료(task_complete)와 미커밋 18개 파일 외부 백업 후 인계. CLI 원본 3개는 바이트 동일하게 보존하고 GET `/api/dashboard/bid-now-audit`와 후보 화면의 전체 공고 위험·증빙 집계를 연결했다. 고정 오류/권한·10초 제한·최신 요청 우선·legacy 무결성 미검증 경고를 표시한다.
- 14:59 KST 실제 읽기 전용 재검증: 전체 5,718 / 활성 2,369 / 보류 3,349 / 무효 0, 부서 비교 불명 2,369. BLOCKED_EVIDENCE 및 적격·수익 UNVERIFIED. 원문/ID·회사·인력·원가 미출력, 원본 쓰기 없음. 기존 CLI 검증 보호 파일393개 불변과 이번 legacy 배포 helper 한정318개 불변은 범위가 다르다. 새 운영 백업/보존 검사는 원문 첨부를 포함한 모든 파일(.lock 제외)로 확대한다.
- local_app443 PASS(건너뜀0) + 감사14 + backend11 = Python468 PASS, Node27 PASS, build PASS. Chrome155 기본 sandbox 합성390/1440px PASS. 독립 Codex 경고 계약 MAJOR1 수정·관련5개 재검증 후 최종 GO. 기존 세션 NO_GO/차단은 아래 이력으로 보존한다.
- 사용자 최신 승인에 따라 개발/main CI·기존 localhost 백업/배포/운영 화면·API·데이터 보존 인수를 진행한다. 현재 DONE 아님. [최신 검증](docs/reviews/BID04_UI_DEPLOY_2026-10-19.md).

## 2026-10-19 BID-04 로컬 회귀 VERIFIED / 최종 Codex NO_GO / 완료 게이트 BLOCKED

- `648ca0a`의 개발 브랜치에서 별도 읽기 전용 CLI/집계·합성 회귀를 구현했다. 실제 저장 공고 5,718건 중 활성 검토 2,369·보류 3,349, 부서 비교 불명 2,369. 증빙 부족 **BLOCKED_EVIDENCE**, 법적 적격·수익 UNVERIFIED. 스킬 부족/분야 불명만으로 기회 폐기 없음. 실제 ID/원문·회사/인력/원가·개별 SHA 미노출.
- 고정 입력 전후 안정성 확인, 보호 파일 393/393 내용 동일(잠금 제외, 변경/추가/삭제/읽기 오류 0). 새 의존성·기존 서버/UI/원본 저장 변경 없음. 최종 전체 local_app **440 PASS/0 skip/309.928초**(신규21 포함), 감사14/backend11 포함 Python465 PASS, Node22·build·정적/문법/공백 PASS. 기본 테스트 ROOT를 임시 폴더로 격리한 전수 실행이며 이전 두 중단 실행은 PASS 아님.
- 별도 fresh-context 읽기 전용 Codex 최종 **NO_GO**: 소스 중대 결함 없음/독립10 PASS이나 Chrome 기본 sandbox 시작 실패(exit2147483651) 및 GitHub OS 소켓 거부로 인수/원격 검증 **BLOCKED**. source bundle5개 종료시 동일. 사용자 지시에 따라 문서 포함 commit/push/DONE 없음, main·운영 배포·실제 입찰·D-10 조사 없음. 최신 상세는 [검증 보고](docs/reviews/BID04_LOCAL_AGGREGATE_2026-10-19.md), [실행 백로그 BLOCKERS](docs/implementation/DEPARTMENT_BID_NOW_EXECUTION_2026-10-18.md). 아래 BID-03/BID-04 미착수 표기는 당시 이력이다.

## 2026-10-19 BID-03 DONE / 독립 GO·두 GitHub CI 성공

- 기존 미커밋 15개 파일을 보존하고 전역 정책 9개를 GitHub 원본에서 재확인. 후보 세 큐·보류/문서 위험·UNVERIFIED·기존 상세 연결 유지.
- CPython 3.12.0 별도 테스트 venv에 선언 의존성 설치, `pip check` PASS. `langchain-core 1.6.12`, `pytesseract 0.3.13`. 전체 local_app **419 PASS / 213.041초 / SKIPPED 0**, 감사 도구 14 PASS, backend 11 PASS(합계 444). Node 22 PASS, TypeScript/Vite build·npm audit(0건)·정적/문법/공백 PASS.
- Chrome 155.0.8059.40 동일 runner·기본 sandbox로 **1440px/390px 실제 합성 E2E PASS**: 세 큐/보류/미검증/기존 상세/파일 선택/수기 이력 저장·재조회/가로 넘침·외부 페이지 요청 없음. 스크린샷 육안 확인. 이전 시작 실패·회귀 정체는 이번 환경에서 재현되지 않았고 과거 원인의 확정과 구분한다.
- 독립 Codex 재검수 **GO** 후 구현 커밋 `f642796bbe2634fe3b6ef405f3332e848027f756`을 개발 브랜치에 푸시. 동일 SHA [Sprint 1 CI 39198868801](https://github.com/son1004007/public-bid-agent/actions/runs/39198868801) 및 [Windows synthetic acceptance 39198868837](https://github.com/son1004007/public-bid-agent/actions/runs/39198868837) **모두 SUCCESS**, BID-03 **DONE**. Ubuntu 419+14+11 PASS, Windows 68 PASS 및 390px/1440px Chrome E2E PASS 로그 확인. 운영 데이터/서버·main·배포·실제 제출 변경 없음. 다음 BID-04는 이번 요청에서 미착수. [검증 기록](docs/reviews/BID03_SHORTLIST_UI_2026-10-19.md).

## 2026-10-18 BID-02 구현 완료 및 BID-03 차례

- BID-02 커밋 `9f3ab29` 전체 418 PASS, Codex GO, GitHub Sprint 1/Windows CI 모두 SUCCESS. 현재 자동 입찰은 없고 회사 자격·보완 후 수익성은 UNVERIFIED. **다음 BID-03: 화면에서 분야 일치·보완/수익 검토·사전등록 대상 구분.**

## 2026-10-18 BID-02 읽기 전용 실데이터 교차검사

- 신규 GET `/api/dashboard/bid-now-shortlist`: 공고·부서 선택·운영자료를 동일 락으로 읽고 공개 공고 ID·상태 코드·증빙 부족 고정 코드만 반환. 법적 자격/부서 MM/예상이익 UNVERIFIED. 관련 합성 21 PASS, 전체 Python 418 PASS, Codex 독립 GO. 실제 Windows 로컬 보호 데이터 5,691개 비식별 집계에서 일치 검토 178, 역량 보완/수익 검토 2,158, 사전등록 검토 393; 중복되지 않는 상태별 분류이며 수익성 적합 판정은 아님. [단계 추적](docs/implementation/DEPARTMENT_BID_NOW_EXECUTION_2026-10-18.md).


## 2026-10-18 D-20 부서 현행 입찰 선별 우선 개발

- 최신 사용자 목표: **현재 부서 자체 역량이 부족해도 실제 보완 가능하고 비용 차감 후 이익이 큰 공고까지 검토**. 필수 법적 자격·공식 기한은 보수적으로 확인. 금액·원가 근거가 없으면 마진 미확인으로 유지. 기존 전체 공고 수집·보존, 취소·정정·구차수 이력 유지.
- BID-01 최초 안전 분류는 **DONE**: 전체 Python 412 PASS, Codex read-only GO, [Sprint1 CI](https://github.com/son1004007/public-bid-agent/actions/runs/39128145994)·[Windows CI](https://github.com/son1004007/public-bid-agent/actions/runs/39128145903) 모두 성공(개발 브랜치 c759c53). 다음 BID-02 API 연결 및 운영 데이터 불변 검증 대상. 현재 로컬 P09 운영 서버에 BID-01 새 소스를 적용했다고 주장하지 않음.
- 최신 승인 실행 계획 [BID-01~BID-09 및 BLOCKERS](docs/implementation/DEPARTMENT_BID_NOW_EXECUTION_2026-10-18.md)를 최우선으로 실행. BID-01은 보수적 검토 작업 큐부터 시작하고, 회사 증빙 없는 자동 `READY_TO_BID_VERIFIED` 판정 금지.
- 사용자 지시에 따른 새 작업 실행 일정은 별도로 관리하며 이전 '매시간 상태 모니터링'은 중지 유지. 사용자의 실제 Bid/No-Bid, main, 공개 배포는 자동 실행하지 않음.


## 2026-10-18 20:46 이후 감사 전용 누락 패키지 설치 확인

- Windows P09 운영 Python과 분리된 `AgentRunner/audit-venv` 생성. 개발 검증 도구 `jsonschema 4.26.0`, `packageurl-python 0.17.6`, `pip-audit 2.10.1`, `license-expression 30.4.4`, `cyclonedx-python-lib 11.12.0` 설치. 양쪽 환경 `pip check` 확인, 운영 P09 서비스에는 별도 설치하지 않음.
- 실제 Python CycloneDX 1.5 SBOM 48개: 공식 스키마 0 오류, PURL 0 오류, dependency ref 0 오류. `pip-audit`가 보고한 47개 0건 및 누락된 `packaging 26.3`의 OSV 단독 질의 0건을 구분하여 기록함.
- LICENSE 후보가 배포 wheel에 없던 패키지 3개 가운데 `et-xmlfile 2.0.0`, `openpyxl 3.1.5`는 PyPI의 SHA 검증된 sdist에서 LICENCE 파일 발견. `langsmith 0.14.6`은 sdist에 발견되지 않아 공식 LangSmith 저장소 MIT LICENSE 확보. 패키지 버전별 정확한 NOTICE 원문 및 전체 외부 바이너리 법적 승인은 계속 별도. [근거](docs/reviews/LOCAL_AUDIT_TOOLS_2026-10-18.md).


## 2026-10-18 Python SBOM / 운영 백업 읽기 전용 후속

- P09 검증된 source 및 원본 보호 정책 유지. 실제 요청 1~6단계의 비식별 로컬 실측·남은 승인 경계는 [종합 검증](docs/reviews/FOLLOWUP_SIX_STAGE_2026-10-18.md)에 기록. 별도 읽기 전용 백업 검사에서 릴리스 백업 318개와 현행 318개 내용 해시 일치, 누락·오류 0. 복원 실험/운영 파일 수정은 수행하지 않음.
- Python 연결 패키지 48개의 CycloneDX 1.5 SBOM 및 관찰 pin 48개 생성, dependency 관계 49개, 공식 JSON schema 오류 0. 감사·SBOM 합성 테스트 14 PASS. Python hash lock, LICENSE/NOTICE·외부 바이너리 통합은 계속 미완료. [검증](docs/reviews/PYTHON_SBOM_AND_BACKUP_CHECK_2026-10-18.md).


## 2026-10-18 공급망 보완의 최종 구현·CI 결과

- `feat/sprint1-search-demo`의 `d63adbbf4c6f8bcbbf7d7a2141f51c7a2fc95d0d` 공급망 점검/Vite High 수정/React 잠금 파일/CI 보안 게이트·RFP 인수 절차 문서 반영.
- Codex 독립 검수 최초 NO_GO 2건(의존성 marker/extras 순회) 수정 후 **GO**, 감사 회귀 7건 PASS. [Ubuntu Sprint 1 CI](https://github.com/son1004007/public-bid-agent/actions/runs/39113379131) **SUCCESS**, [Windows 합성 E2E CI](https://github.com/son1004007/public-bid-agent/actions/runs/39113379117) **SUCCESS**.
- 실제 Python 로컬 서버 배포 소스는 검증된 P09 `f06a3fa` 유지, 서비스 HTTP 200, 이전 P07 자동 적용 스케줄 비활성. 운영 데이터 변경/공개 배포/사용자 UI 승인 없음.
- 정확한 LICENSE/NOTICE 고지, 실제 RFP 독립 FN 라벨과 회사 승인 증빙, 사용자의 UI 인수는 남은 게이트. [보안 감사](docs/reviews/DEPENDENCY_SECURITY_AUDIT_2026-10-18.md) · [실제 원문 인수](docs/reviews/RFP_REAL_EVIDENCE_GATE_2026-10-18.md).

## 2026-10-18 잔여 의존성·공급망 점검 진행

- P09 완료와 Windows P07 자동 롤백 방지 상태를 유지한 채 공개 의존성만 조사. Python 직접 10/10 충족, 설치 51개·연결 48개·`pip check` 통과, OSV 공개 패키지 48개 버전 조회 취약점 반환 0.
- 독립 Codex 최초 NO_GO 2건을 플랫폼 marker 및 중첩 extras 순회 보완으로 해결, 최신 검수 **GO**. Python 감사 7개 합성 회귀 PASS.
- React 시안 `Vite 7.1.12` npm High 발견 후 `7.3.7`로 보완하고 `frontend/package-lock.json`을 생성. `npm audit` 0건, npm lock 설치/TypeScript/빌드 PASS, CycloneDX npm 21개 구성요소 생성.
- Python 메타데이터 SPDX 표기 26, 구형 라이선스 표기 25로 자동 법적 판단 미완료. 로컬 비식별 집계 API 기준 활성 RFP 검토 후보 220, 텍스트 확보 87, 공식 첨부 확보 대기 130(기타 3), 절단 신호 12·경고 21로 독립 원문 정답 검토가 필요. [실제 인수 게이트](docs/reviews/RFP_REAL_EVIDENCE_GATE_2026-10-18.md). 실제 RFP 필수요건 정답 라벨·회사 증빙·사용자 화면 인수는 계속 미검증. `main`·외부 공개 미진행. [감사 근거](docs/reviews/DEPENDENCY_SECURITY_AUDIT_2026-10-18.md).


## 최신 상태: 2026-10-18 P09 전체 합성 개발·CI·Windows 로컬 적용 검증 완료

- 개발 브랜치 `feat/sprint1-search-demo`. P04~P08 완료 후 P09 초기 커밋 `bf3dca4`의 Windows CI에서 기본 로캘 `cp1252`와 한국어 UTF-8 출력/읽기의 불일치로 1 FAIL/1 ERROR가 발생했다. 두 오류를 재현한 후 `f06a3faebbcf3995f6d1ac2fd3fe5c1f9b978c86`에서 수정했다.
- P09 현재 소스: Windows 기본 인코딩과 무관한 파서 ASCII-safe JSON 출력, UTF-8 테스트 파일 읽기, `PYTHONIOENCODING=cp1252` 교차 회귀. Windows 6개 모듈 **52 PASS**, 전체 Python **403 PASS**, 합성 Chrome 단독 E2E **PASS**, 별도 read-only Codex **VERDICT: GO**.
- 동일 SHA의 GitHub **Sprint 1 CI** [39110626764](https://github.com/son1004007/public-bid-agent/actions/runs/39110626764)와 **Windows synthetic local acceptance** [39110626835](https://github.com/son1004007/public-bid-agent/actions/runs/39110626835) **모두 SUCCESS**.
- Windows TD-kiseok `127.0.0.1:8765`에 검증된 Git SHA의 immutable source만 적용: HTTP/API 확인, 적용 후 read-only Chrome 8개 단계 **PASS**, 원본 보호 파일 **318개 SHA 불변**, 기존 원본 직접 갱신 없음. 실제 문서 법적 적격/전체 요건 Recall/회사 증빙과 사용자 UI 최종 승인은 여전히 **NOT VERIFIED**.
- `main` 미병합, 인터넷 공개/실제 입찰 미실행, 외부 비공개 LLM 전송 없음. 이전 P09 NO_GO/BLOCKED 섹션은 수정 이전의 시점별 기록이며 현행 판정이 아니다. [종합 검증 보고](docs/reviews/P09_WINDOWS_CI_FINAL_2026-10-18.md).


## 2026-10-18 P09 NO_GO/P1 배치 fixture 격리 수정 (독립 재검수 대기)

- 기존 `RFP_BATCH`가 운영 root를 유지하는 결함을 임시 root manager 교체·네 외부 어댑터 차단으로 수정. 운영 앱 코드 변경 없음. 메모리 차단자 아래 수정 전 GET 회귀 실패 재현, 수정 후 API **11 PASS**(IDLE·RUNNING 장부 및 실제 임시 worker lease 포함).
- 관련 6개 모듈 API·보안·복구 회귀 **51 PASS**(CPython 3.12.0); 어댑터 mock 선확인 보강 후 집중 재실행 **1 PASS**. 전체 저장소 회귀/CI는 NOT RUN.
- Chrome 재실행은 sandbox 진단/exit `2147483651`로 **BLOCKED**, 보안 완화 없음. 아래 최초 48 PASS는 배치 격리 증거가 아니다. [재현·결과·한계](docs/reviews/P09_SYNTHETIC_ACCEPTANCE_2026-10-18.md). 독립 재검수/Git 기록은 orchestrator 인계, 사용자 자료 접근·배포·main·add/commit/push 없음. D-10/P11 보류.

## 2026-10-18 P09 Windows 합성 API·복구 게이트

- 신규 HTTP 인수 테스트 8개와 Chrome E2E runner, 배포 없는 Windows CI 경로 추가. 실행 앱 코드·저장 형식 변경 없음. 관련 Windows CPython 3.12.0 회귀 **48 PASS**, Python/Node 문법 검사 PASS.
- Chrome 155.0.8059.40은 새 페이지 생성 단계에서 sandbox 진단 후 exit `2147483651`; 브라우저 시나리오는 **BLOCKED**, UI 승인 아님. 보안 완화 없이 종료했고 운영 서버/사용자 자료는 접근하지 않음.
- 설치 의존성 일부 누락 및 선언 범위 불일치 확인; 전체 의존성/라이선스/SBOM·CI·독립 검수·실 운영 복구/배포는 별도 미완료. [명령·게이트·인계](docs/reviews/P09_SYNTHETIC_ACCEPTANCE_2026-10-18.md). add/commit/push·main·배포 없음, D-10/P11 보류.

## 2026-10-18 P08 수기 이력 복구 합성 회귀 (독립 검수 대기)

- 실행 코드 변경 없이 신규 11개 테스트와 기존 백업 fixture/assertions 보강. 제출·평가·선정/미선정/철회 재조회, 실패 후 재시도·중복 거부, 실제 두 프로세스 revision 경합, 백업/복원 이력 보존·최신 편집/변조 거부 확인.
- Windows CPython 3.12.0 관련 5개 모듈 **53 PASS**, 공백 검사 PASS. README 2종 동기화. [검증·한계·인계](docs/reviews/P08_SYNTHETIC_HISTORY_RECOVERY_2026-10-18.md).
- 독립 Codex 검수/CI/실 운영 복구·Chrome 인수는 NOT RUN이며 orchestrator 인계. 실제 자료 접근·외부 전송·자동 입찰·main·배포·add/commit/push 없음. D-10/P11 보류 유지. P08 전체 완료나 이력 자동 백업 구현으로 표시하지 않음.

## 2026-10-18 P07 구형 검증 NO_GO/P2 보완 (독립 재검수 대기)

- 조언·API 요약·UI 계산/체크박스에 동일한 유효 검증 조건 적용. 구형 공백 근거 8 Gate/12 factor는 미검증·지표 미산출, 원본 플래그·최종 결정·이력 보존.
- 신규 Python 6개/Node 3개 회귀에서 수정 전 결함 재현 후 관련 Python **88 PASS**, Node **11 PASS**, JS/공백 검사 PASS. 합성 GET 파일 바이트 불변과 부분 저장 응답 검증. [인계](docs/reviews/P07_LEGACY_VERIFICATION_FIX_2026-10-18.md).
- 이번 작업은 GitHub 연결로 CONTROL 및 지정 handbook 원본 확인. 이전 네트워크 BLOCKED 기록은 당시 이력이다. 실자료·외부 LLM·운영 적용·전체 회귀·독립 재검수 NOT RUN. add/commit/push·main·배포 없음, D-10/P11 보류 유지.

## 2026-10-18 P07 입력 절단 NO_GO/P2 보완 (독립 재검수 대기)

- 90,000자 자료 상한의 실제 전달 범위·누락 문서 기록/표시, 범위 밖 인용 거부 및 입력 절단 시 AI 조건·점수 제외/판단 보류를 추가했다. 사용자 결정·이력 보존, 확인된 사용자 미충족 우선 유지.
- 수정 전 신규 회귀 3개에서 2 FAIL/1 ERROR로 재현. 신규 7개 포함 관련 Python **82 PASS**, Node **8 PASS**, JS 문법·diff 공백 검사 PASS. 합성 HTTP에서 저장 범위와 전달 문자열 일치 및 조회 파일 불변 확인.
- 독립 재검수는 orchestrator 인계. 외부 CONTROL/handbook 원본 접근 BLOCKED(네트워크); 저장소 규칙/결정/로드맵 기준. 전체 회귀·실자료·외부 LLM·운영 적용 NOT RUN. 아래 75/6은 수정 전 이력이다. [근거](docs/reviews/P07_SYNTHETIC_RECOMMENDATION_DRAFT_2026-10-18.md).

## 2026-10-18 P07 추천 DRAFT·출처·fallback (독립 검수 대기)

- 수동 AI 화면(`/`)에서 인용의 출처 ID·추출 텍스트 SHA·문자 위치·문구를 대조하고 의미/최신성/회사 적격 미검증을 표시한다. 서버의 분석 입력 버전 결속, 구형/변경 입력 및 모델·의존성 누락 fallback, 사용자 unknown/공백 확인값 방어를 추가했다.
- 합성 Python 관련 7개 모듈 **75 PASS**, Node **6 PASS**, JS 문법 PASS. HEAD 기존 결함 2개 재현·수정 확인. 외부 모델 호출 없이 임시 JSON HTTP로 조회 불변·사용자 결정/이력 보존·늦은 결과 409 확인.
- 실제 LangGraph 실행은 `langchain_core` 미설치로 BLOCKED(그래프 경계는 mock). 독립 검수·전체 회귀·CI·실자료 검증·브라우저 인수·운영 반영은 NOT RUN. orchestrator 검수/Git 기록 인계이며 P07 전체 완료가 아니다. D-10 보류, main·배포·git add/commit/push 없음. [실행/제약](docs/reviews/P07_SYNTHETIC_RECOMMENDATION_DRAFT_2026-10-18.md).

## 2026-10-18 P01/P06 문서 위험·부서 준비도 합성 보완 (독립 검수 대기)

- PDF 페이지별 OCR 육안 대조 신호/이미지 조사 실패 미확인, HWPX 섹션별 표·각주·병합 표식/원본 페이지 미확인 및 수동 검토 안내를 API/화면에 연결했다. 셀 간격/1×1 span은 병합 위험으로 세지 않는다.
- 부서 6개 확인표에 요약·출처·확인일 누락/오류/미래 날짜, 직무·가용 MM·0원 단가/총원가 기준 준비도 사유와 등록·면허·실적별 대조 항목을 추가했다. 모든 법적 적격·수익성과 자료 유효성은 UNVERIFIED, 공고별 비교는 NOT_PERFORMED다.
- CPython 3.12.0 관련 9개 모듈 **82 PASS**, 기존 Node 요약 계약 **3 PASS**, JS 문법 PASS. 실제 사용자 데이터 미접근·미전송, 합성 HTTP/임시 파일 불변 검사만 수행. 전체 회귀/브라우저 인수/실문서 평가/운영 적용/CI/독립 검수는 NOT RUN. add/commit/push·main·배포 없음; D-10 보류. [명령·계약·인계](docs/reviews/P01_P06_SYNTHETIC_READINESS_2026-10-18.md).

> **이 문서는 날짜별 실증 로그입니다.** 사용자 확정 결정은 [DECISIONS.md](DECISIONS.md)가 원본이며, [AI_CONTEXT.md](AI_CONTEXT.md)가 최신 상태를 짧게 요약합니다. 과거의 '최신 기준' 표기는 해당 시점의 기록입니다. 2026-10-15 로컬 운영 공고는 3,777건(CURRENT 3,263/CANCELLED 201/SUPERSEDED 313, STALE 10), RFP 구조화 Stage 1 실제 8765 서버·Chrome 기능 검증 및 원본 SHA 164/164 일치, 전체 274 PASS·Codex GO를 확인했습니다. **사용자의 최종 UI 승인, main 병합, 공개 릴리스는 별도**입니다.

## 2026-10-18 P05 공식 출처·차수·STALE 합성 검증 (NO_GO 보완, 독립 재검수 대기)

- 공고번호/차수를 자른 뒤 검증하여 서로 다른 입력이 같은 ID로 수용되는 실패 4개 subtest를 재현했다. `normalize`에서 전체 식별자를 검증하도록 수정하고 기존 허용 형식·오류 계약을 유지했다.
- 신규 합성 회귀 14개: 숫자/별칭 차수 도착 순서, 취소·구차수·STALE 유지, 출처/공고 버전 결속, 캐시/파서 진입 차단, 원문·사람 판단·이력 보존. 관련 7개 모듈 Windows CPython 3.12.0 **76 PASS**. [실행 명령·검증 범위](docs/reviews/P05_SYNTHETIC_SOURCE_SAFETY_2026-10-18.md).
- 독립 검수 **NO_GO/P1**에서 같은 배치의 취소→일반 응답 손실이 확인됐다. 신규 4개 테스트의 수정 전 29개 subtest FAIL을 재현한 뒤, 페이지·수동/예약 조회기간 중복 제거와 저장 병합에서 관측한 취소 공고종류를 보존하도록 수정했다. 동일/별칭 차수 48개 배치 순열·페이지 경계·조회기간 각 위치·추천 제외·원문/사람 판단/이력/입력 불변·반복 이벤트 보존을 포함하여 관련 8개 모듈 **91 PASS**.
- **IMPLEMENTED / TESTED**, 수정분 독립 Codex 재검수 대기. 전체 회귀/CI/실원본 검증/운영 반영은 NOT RUN. 실제 사용자 JSON/RFP/회사 증빙 미접근·미전송. STALE 자동 해제 없음, D-10 조사 제외, main·add/commit/push·배포 없음. orchestrator에 재검수/Git 기록 인계.

## 2026-10-18 P04 NO_GO 지적 2건 수정 (독립 재검수 대기)

- PDF fingerprint에 기존 OCR 이미지 의존성 Pillow의 버전을 포함. 저장·현재 provenance에 같은 strict schema 검사를 적용하여 현재 schema `True`/`1.0`의 거짓 일치 판정을 차단. OCR 실행 파일·언어팩 버전은 `NOT_CAPTURED`, 구형 증거는 `NOT_VERIFIED` 유지. 캐시 마이그레이션 없음.
- Windows CPython 3.12.0, 합성 fixture만 사용. 새 회귀 테스트로 수정 전 Pillow 변경/boolean·float schema의 3개 실패를 재현했고 수정 후 `python -B -m unittest test_rfp_original_compare test_rfp_batch -v` **20 PASS** (`local_app`에서 실행).
- 추가 `python -B -m unittest test_extractors -v`: **7 PASS / 1 ERROR / 2 SKIPPED**. OCR 시험은 `pytesseract` 미설치로 ERROR(환경 BLOCKED), HWP 및 XLS 시험은 의존성 미설치로 SKIPPED. 환경/의존성 변경 없이 제한을 기록. 전체 회귀·실제 원본 검증·운영 롤백·배포는 **NOT RUN**, 독립 Codex 재검수는 대기.
- 이번 작업에서 비공개 사용자 JSON/RFP/회사 증빙 접근·전송, main 수정, add/commit/push, 운영 반영 없음. D-10 조사는 계속 보류.

## 2026-10-16 P04 신규 RFP 파서 설정 fingerprint (실원본 미검증)

- `local_app/extractors.py`에서 공개 파서 코드 SHA·Python 버전·관련 패키지/상한/실행 방법의 정규화 fingerprint를 합성 문서에 기록. 신규 `rfp_batch.py` 추출 proof에만 엄격한 schema로 추가, 원본 재추출에서는 해당 fingerprint의 일치 여부를 별도 표시. **구형 증거는 `NOT_VERIFIED`, OCR 실행 바이너리·언어팩 버전은 `NOT_CAPTURED`; 원문 페이지/표/각주·전체 Recall은 미확인**. 이미 저장된 사용자 RFP 캐시/사람 판단을 소급 수정하지 않음. [실행표](docs/design/REMAINING_EXECUTION_ROADMAP_2026-10-16.md).

## 2026-10-16 P00~P03·P06 개발 추가 (합성 검증 / 실원본 미검증)

- 2026-10-16 Windows 전체 **319 PASS**, Codex 1차 NO_GO 2건 수정→2차 **GO**, 8765 재기동 후 라벨/검토 큐 GET smoke, Chrome headless 위험 패널 렌더링 확인. 사용자 JSON+RFP 캐시 164개 SHA-256 불변. 실 PDF/HWP 원본 대조·수동 라벨 GUI 클릭·실 Recall, 사용자 최종 승인·main/외부 배포는 NOT RUN.
- 문서화: [P00~P11 전수 실행표](docs/design/REMAINING_EXECUTION_ROADMAP_2026-10-16.md). 새 `document_quality.py`는 재현이 확인된 로컬 선택 원본에서 PDF 페이지별 문자 수/이미지 객체 및 HWPX 표·각주 메타만 별도 프로세스로 추출. `rfp_audit_labels.py`는 실제 RFP 추출 문자 후보에 대한 사람의 분류 검토를 **비공개 독립 로컬 JSON**에 기록하고, 현재 추출 텍스트 SHA/offset과 달라지면 과거 라벨 STALE로 표시. 수정 이벤트는 보존하고 현재 집계는 최신 라벨만 계산. `rfp_review_queue.py`는 공식 공고 ID/고정 위험만 반환. 원본 페이지 전체 정답·실제 Recall·법적 적격·AI 자동 적격 추천은 **미검증**. 테스트/독립 검수/CI/로컬 반영 결과는 별도 검증 보고에 명시.

## 2026-10-16 후속 단계 2~9 로컬 수직 연결 (D-18, 일부 기능과 경계)

- 실제 로컬 원본 PDF/HWP 선택→공식 증거 SHA·캐시·현재 파서 재추출 비교, 동일 캐시 동시 생성/길이 충돌 원자적 안전 실패, 비식별 부서 증빙 준비도, 담당자 수동 제출/평가/선정·미선정 이력 API/UI 구현. 신규 RFP 증거만 공고 번호·차수 결속하고 **기존 구형 근거는 `PROVENANCE_VERSION_UNVERIFIED`로 보류**. Windows 전체 **308 PASS**, Codex 1차 NO_GO 2건 해결 후 **2차 GO**, localhost 8765 재기동 뒤 페이지/JS/API HTTP 200·원본 대조 불량 요청 400, 비공개 파일 164개 SHA 동일. 실제 원본 PDF/HWP 파일 대조 및 사용자 Chrome GUI 클릭은 **NOT RUN**. 법적 적격·회사 실증·전체 문서 Recall·AI 종합 자동추천·사용자 UI 승인/main/공개 배포 미완료. [검증 보고](docs/reviews/RFP_FOLLOWUP_STAGE2_4_2026-10-16.md), [10단계 계획](docs/design/STAGE2_4_EXECUTION_PROGRESS_2026-10-16.md).

## 2026-10-16 공식 원본·캐시 오프라인 비교 준비 (D-17 후속 5단위)

- [설계 및 전체 후속 작업](docs/design/RFP_ORIGINAL_AUDIT_PLAN_2026-10-16.md): 기존 보관 청크에서 PDF/HWP 원본 바이너리를 복원할 수 없음을 명시. `rfp_original_compare.py`는 원본을 별도 제공받으면 공식 첨부 identity/SHA, 증거 측 5개 fulltext 필드·캐시와 현재 로컬 파서의 추출 텍스트·길이 재현 여부만 검사(방법·버전·OCR `NOT_VERIFIED`). 합성 PDF·HWPX·TXT 집중 **7 PASS**, Windows 전체 **299 PASS**, Codex NO_GO 2회 보완 뒤 **3차 GO**. 비공개 JSON/RFP 캐시 **164개 SHA-256 집계 동일**. 실제 원본 파일 대조/Chrome 새 UI/운영 서버 신규 API 배포는 **NOT RUN**(이번 변경은 오프라인 순수 함수). [검증 기록](docs/reviews/RFP_ORIGINAL_COMPARISON_2026-10-16.md).

## 2026-10-16 RFP 추출 문자 손실 정량 진단 (D-17 후속 4단위)

- 기존 `/api/dashboard/rfp-coverage`에 `extraction_loss_all/active` 추가: 저장 메타데이터 신고 문자 수 차이만 비식별 집계, 불확실/경고 별도 표시. **Windows Python 전체 292 PASS, Codex GO**, 로컬 8765 재기동 후 페이지/API HTTP 200. 마감 전 180후보, 절단 증거 13/공고 12, 기록된 미보관 합계 657453자; 비공개 JSON/캐시 **164개 SHA-256 집계 동일**. 실제 PDF/HWP 원문 누락·요건 Recall 및 Chrome GUI 동작은 **미검증**. [검증 기록](docs/reviews/RFP_EXTRACTION_LOSS_LENGTH_2026-10-16.md).

## 2026-10-16 RFP 확보 품질 메타데이터 진단 (D-17 후속 3단위)

- 기존 `/api/dashboard/rfp-coverage`에 `by_quality_all/active` 비식별 상태 집계를 추가하고 수집 화면에 표시. 취소·구차수·REVIEW는 활성 후보에서 제외. Windows Python 전체 **287 PASS**, 집중 6 PASS, Codex 최초 NO_GO 지적 수정 후 최종 **GO**. 검증된 코드로 8765 서버 안전 재기동, 화면/품질 API HTTP 200, 실제 메타데이터 기반 부서 후보 287·마감 전 180 중 캐시 참조 57·발췌 31·파서 절단 12·경고 21 확인. 사용자 파일 SHA-256 집계 164/164 불변. 실제 Chrome 클릭·사용자 UI 승인 및 원본 PDF/HWP 전체 Recall은 **미검증**. [검증 보고](docs/reviews/RFP_QUALITY_METADATA_2026-10-16.md).

## 2026-10-16 RFP 정량 평가 도구 (D-17 후속)

- `rfp_taxonomy_benchmark.py`는 사람이 사전 지정한 추출 문장 라벨만으로 3분류 혼동 집계/Precision·Recall·F1을 산출하며, 실제 원문 전수 누락률이나 법적 참가자격을 판정하지 않는다. 합성·오류 경계 **5개 테스트 PASS**, Windows 전체 **284 PASS**, Codex 지적(F1 null/0 및 문서 건수) 수정 후 최종 GO. [평가 프로토콜 및 검수 근거](docs/reviews/RFP_TAXONOMY_BENCHMARK_PROTOCOL_2026-10-16.md). 실 RFP 독립 라벨링과 원본 전체 추출 손실 평가는 별도 미완료.

## 2026-10-16 RFP 표시 상한 가시화 (D-17)

- 9개 분류 후보는 카테고리별 5건 표시 상한을 그대로 유지하되, 검증된 청크에서 같은 SHA+표현 중복을 제거해 **상한으로 생략된 추가 표현 후보** 수를 응답과 UI에 포함한다. 생략이 있으면 `source_coverage=PARTIAL`; 원본 요구사항 전체 누락률과는 다르다.
- 2026-10-16 실제 Windows Python 전체 279/279 PASS, Node UI 3/3 PASS, Codex NO_GO 지적 보완 후 2차·정적 경로 보완 3차 GO. 로컬 서버 재기동 후 HTTP 200 및 실제 비공개 RFP 집계 9유형/19개 표시/14개 상한 생략/2문서 확인. 원본 JSON 40개+RFP 캐시 124개 총 164개 전후 SHA-256 집계 일치. Chrome GUI·사용자 UI 승인과 법적 적격 판단은 미완료. [검증 보고](docs/reviews/RFP_CAP_VISIBILITY_2026-10-16.md).

## 2026-10-15 RFP 유형 분류 개선 (D-16)

- 기존 단순 `공동수급` 참가기준 오탐을 수정하고 평가기준·선정방식을 독립 유형으로 추가. 9개(schema v2), 제목/계약변경/학습 점수 등 주요 오탐 억제. 기존 SHA 검증·원본 보존·취소/구차수/STALE 차단 유지.
- **실제 검토:** 당시 현행·비STALE fulltext 보유 공고 65건 중 균등 표본 20건을 로컬에서 읽기 전용 분석. 상한 내 참가자격 93·평가기준 95·과업 표현 20개 분류 후보를 확인. 이 수치는 완전성/Recall/Precision의 통계적 추정치가 아님. [점검 보고](docs/reviews/RFP_TAXONOMY_3WAY_2026-10-15.md).
- 실제 Windows 로컬 서버 schema v2 재기동 및 Chrome 9개 분류·32개 원문/출처 접힘·모바일 PASS, Codex 1~3차 NO_GO 지적 수정 후 4차 GO, 전체 Python 276 PASS, 개인 비공개 파일 SHA 164/164 일치. 사용자 최종 UI 승인 및 Stage 2 진행 결정은 별개.

## 2026-10-15 RFP 원문 우선 화면 개선 (D-15)

- RFP 구조화 API·원본 JSON·캐시·수집 로직은 변경 없이 `dashboard-live.js`와 `bid-decision-dashboard-preview.html`만 UI 변경. 원문 표현 1열 카드, 파일명·SHA-256·문자 위치는 항목별 기본 접힌 `details/summary` 메타정보에 표시. [UI 검증 보고](docs/reviews/RFP_ORIGINAL_FIRST_UI_2026-10-15.md).
- 실제 Chrome 원문 표현 31개/접힘 31개, 펼치기·닫기, 모바일 390px 가로 넘침 없음, Windows 전체 **274/274 PASS**, 사용자 비공개 파일 **164/164 SHA-256 일치**. Codex 1차 NO_GO(CSS 글로벌 범위) 지적 수정 후 **2차 독립 GO**. 사용자 최종 화면 승인은 별도.

## 2026-10-15 최신 RFP 구조화 1단계 로컬 적용 결과

- `TD-kiseok`에서 검수된 소스 `e02dfbc` 및 최신 문서 `3a7fb51`을 확인하고 기존 127.0.0.1:8765 서버를 기동했습니다. 3,777건의 실제 공고와 비STALE RFP fulltext 참조 후보 65건이 확인됐습니다.
- 실제 GET: RFP 8개 유형, 근거 표현 31개/문서 1개, SHA·추출 문자 위치·원본 페이지 미추정·법적 적격 UNVERIFIED; 취소·구차수·STALE 차단, 잘못된 ID 400/없는 ID 404 확인.
- 실제 Chrome: 공식 목록 3,777 → 상세 → 참가자격·과업 → RFP 요구사항 버튼 클릭 및 근거 출력, 기존 홈/수집관리와 모바일 390px PASS.
- 사용자 JSON 40개 및 RFP 캐시 124개 **164/164 SHA 동일**, 파일 추가/삭제/변경 0건. Windows 전체 Python 274 PASS, JS·문서 동기화 PASS, Codex 독립 GO와 GitHub CI 성공.
- 상태 `LOCAL_APPLIED`, `CHROME_E2E_VERIFIED`. 사용자 최종 UI 승인, main 통합, 인터넷 공개, 다음 Stage 2, 7일 API 실패 원인 진단은 미실행. [현장 검증 보고](docs/reviews/RFP_STAGE1_LOCAL_ACCEPTANCE_2026-10-15.md).

## 2026-10-13 실제 구현·검증 상태 (당시 기록)

**현재 기준 화면은 `http://127.0.0.1:8765/decision-preview`입니다.** 개인 Windows PC의 `local_app/server.py`가 Python 표준 HTTP 서버로 제공하며, `frontend/public/bid-decision-dashboard-preview.html`과 `frontend/public/dashboard-live.js`가 실제 API에 연결됩니다. `bid-management-preview.html`은 초기 정적 퍼블리싱 시안이며 `frontend/` React + `backend/` FastAPI는 현재 운영 서버와 별도인 합성 개발 자산/공개 서비스 장기 계획입니다.

- **2026-10-13 읽기 전용 실측:** **2026-10-11 마지막 수집된 로컬 공고 메타데이터 스냅샷 2,223건**입니다. 최신성·전수성·정정/취소·법적 유효상태는 보장하지 않습니다. 관심 부서 후보 143건, 이날 평가시 마감 전 후보 109건 중 로컬 RFP 본문 추출 상태 후보 107건/메타데이터만 2건. 107건은 원문 전체 요건·최신성·자격 검증 완료를 뜻하지 않습니다. `RULE_BASED_READ_ONLY`의 상위 30건 표시는 **상세검토 우선순위**이며 실제 AI 적격 추천·법적 자격 확정/낙찰확률이 아닙니다.
- **RFP 전체 작업과 지정 범위 이관:** 전체 원장은 `PAUSED / DONE 109 / PENDING 34 / FAILED 0`로 남아 있습니다. 별도로 10월 12일 **70개 공고/127개 문서**의 격리 검증 범위를 로컬 운영에 반영한 **이관 저널만** `COMPLETED`입니다. 비공개 본문 저장 파일 124개와 문서 근거 기록 127개는 서로 다른 집계 단위로 일대일 대응·중복 여부는 추가 검증 대상입니다. 백업 1개 확인. 로컬 적용과 **인터넷 공개 출시**, CI 성공과 **전체 앱 독립 보안 승인**, 개별 API 확인과 **브라우저 전체 인수 테스트**는 서로 다릅니다.
- **기능 경계:** 공식 공고 메타데이터 수집/분류·일부 RFP 추출과 원문 보존·규칙 기반 순위/수기 결정은 구현되어 있습니다. 8개 필수조건과 12개 비교인자는 검토 가정이고 법적 적격성 `UNVERIFIED`입니다. 14개 문서는 44,000자 추출 한도로 완전성 미검증이며 위 RFP 후보 107건과의 대응도 추가 확인 대상입니다. 표·각주·정정/취소·업종·지역/첨부 누락과 실제 부서 기술·실적·가용 MM·원가 기반 과업 적합성은 추가 검증해야 합니다.
- **미완료:** 평일 오전 9시 정기 수집(현재는 화면 시안), 전체 공고 자동 AI 의미 분석/실질적 입찰 참여 추천, Google 다중 사용자 로그인·원격 계정 연결, 공식 제출/점수/낙찰 자동확인, 공개 인터넷 서비스. 개인 Codex CLI의 제한적 수동 AI 분석 실증은 별개입니다.
- **Source of Truth:** 본 문서의 최신 절과 [TASKS.md](TASKS.md)를 기준으로 하고, 아래 10월 9일 단계·각 날짜별 '이번 변경 범위' 설명은 **당시 이력**으로 해석합니다. 프로젝트 독립 최종 검수는 최신 사용자 지시대로 Codex만 사용합니다.

## 2026-10-09 이후 개발 이력 (아래 최초 '현재 단계'는 당시 상태)

- 기준일: 2026-10-09
- 대상: son1004007/public-bid-agent
- 개발 브랜치: feat/sprint1-search-demo / Draft PR #1
- 사용자 우선순위: **설계 → UI 퍼블리싱 → 사용자 화면 검증 → 프런트엔드 수정 → 백엔드 세부 구현**
- 현재 단계: **독립 실행 공고→참여→제출→결과→회고 통합 UI 퍼블리싱 작성 / 사용자 피드백 대기 (UI_PROPOSED)**
- backend: 초기 합성 공고 API와 테스트 11개 기존 구현을 유지. 더 이상 백엔드 확장하지 않음.
- frontend: 기존 React/FastAPI 코드 보존. `frontend/public/bid-management-preview.html`을 **현재 검토 대상**으로 추가했고 `ui-review.html` 목록에서 연결. 과거 `bid-detail-review.html`은 구버전 시안으로 보존.
- 신규 시안은 브라우저 메모리 수기 상태만 다루며 서버 저장·공식 조회·개별 업체 입찰내역 조회가 아니다.
- 실공고 연동, Google 로그인, RAG/LLM, 실제 행정자격 판정, 외부 서비스 배포: 미구현/비활성.
- 공통 UI 퍼블리싱 우선 정책: personal-engineering-handbook의 Draft PR #1, **아직 검수/승인 전**.

## 사용자가 확인할 퍼블리싱 범위

- 공고 탐색 / 상세 검토 / 임시 검토 보관함 / 화면 검증 메뉴
- **공고별 상세 화면**: 기본정보, 행정 참가자격, 제안서·평가배점, 제출 수기 기록, 낙찰·기술/가격 점수, 수주 이력 표
- 제출/점수 수기 입력의 값 검증, 모든 자료의 합성·미확인 표기
- 합성 공고 8건, 검색어 및 AI/SW/DATA 필터
- 선택한 공고의 기술·사업 요건 예시
- 0건/오류 화면 시뮬레이션
- 데스크톱·모바일 반응형 레이아웃, 키보드 동작 기본 확인
- 화면 검증 체크리스트

설계 자료는 **합성 fixture**이며 실제 공공 입찰 정보가 아니다. 브라우저 밖으로 데이터를 전송하거나 서버·DB에 보존하지 않는다.

## 실행 및 검증 상태

- 최초 Sprint 1 백엔드: 로컬 pytest 11 PASS (2026-10-09).
- 최초 Sprint 1 PR CI: Python 및 TypeScript/Vite 빌드 PASS (GitHub Actions 37885735328).
- GitHub Actions push [37894035152](https://github.com/son1004007/public-bid-agent/actions/runs/37894035152) 및 PR [37894040200](https://github.com/son1004007/public-bid-agent/actions/runs/37894040200): **PASS**. Python 백엔드 테스트, TypeScript/Vite 빌드, 독립 UI 정적 HTML JavaScript 구문·안내문·외부 자원 참조 검사, 번들 내 퍼블리싱 파일 포함 여부를 확인했다. 사용자 화면 적합성 승인/브라우저 E2E를 대체하지 않는다.
- 사용자 검증용 시안과 일치하는 별도 정적 데모는 로컬 브라우저에서 화면/상호작용을 사전 점검했으나, GitHub 파일의 정식 시각 검수 및 사용자 승인은 여전히 미완료.
- 별도 AGY/Gemini 의미 검수: **NOT RUN (REVIEW_DEBT)**. Draft PR 유지 및 main 병합/릴리스 금지.
- 기존 R1~R4 설계 검수 및 정정 ADR은 삭제하지 않음.

## 다음 작업

1. 사용자가 [UI 화면 검증 가이드](docs/ui/SCREEN_REVIEW_GUIDE.md)와 공고별 [상세·제출·결과 시안](frontend/public/bid-detail-review.html)을 직접 확인하도록 안내.
2. 페이지/탐색/상세/보관함/모바일/빈 결과·오류에 대한 사용성 피드백 수집.
3. 사용자 결정에 따라 화면과 API 응답 데이터 계약 수정.
4. UI 검증 뒤 해당 화면의 필요 기능부터 백엔드 구현을 이어감.
5. 변경 단위 독립 검수·실제 테스트 및 필요 시 별도 사용자 승인 후 main 통합을 판단.

## 근거 문서

- [화면 검증 가이드](docs/ui/SCREEN_REVIEW_GUIDE.md)
- [독립 HTML 퍼블리싱 시안](frontend/public/ui-review.html)
- [애자일 개발 절차](docs/07-agile-development-workflow.md)
- [기존 Sprint 1 실행 기록](docs/implementation/SPRINT1_RUNBOOK.md)
- [다른 채팅/AI용 인수인계](docs/implementation/CONTINUE_IMPLEMENTATION_PROMPT_2026-10-09.md)
- [보안·독립 검수 정책](https://github.com/son1004007/personal-engineering-handbook/blob/main/REVIEW_POLICY.md)

## 2026-10-09 상세 퍼블리싱 추가

- 목록에서 `전체 상세·제출·낙찰 관리` 링크로 이동.
- 상세 페이지 6개 화면: 기본정보/참가자격/제안서·평가/제출 관리/낙찰·평가점수/진행 이력.
- 제출 기록은 `미확인/미제출/제출했다고 기록/접수증을 사람이 확인했다고 기록`로 구분하며 공식 접수 확인을 주장하지 않음.
- 평가점수는 입력값과 만점의 유효성을 검사하며 미공개·미입력 점수를 0으로 환산하지 않음.
- 공식 조사: `docs/research/2026-10-09-bid-lifecycle-management.md`. 공식 공공 API는 개찰·낙찰·계약을 제공하지만, 내 기업이 제출했다는 사실과 개별 기술점수는 별도의 증빙/공개 조건이 필요.
- 새 HTML 상세 퍼블리싱의 GitHub Actions push run [37900354978](https://github.com/son1004007/public-bid-agent/actions/runs/37900354978) 및 PR run [37900360576](https://github.com/son1004007/public-bid-agent/actions/runs/37900360576): PASS. 백엔드 tests, frontend Vite typecheck/build, 정적 JS 및 독립 HTML 파일 포함 검증을 통과. 독립 최종 검수 및 실제 GitHub 버전의 브라우저 E2E는 NOT RUN.

## 2026-10-09 사용자 방향 동의: 입찰 전체 과정 관리

- 사용자 피드백: 공고 탐색뿐 아니라 **발굴 → 참여/미참여 판단 → 제안서·가격입찰서 각각 제출 확인 → 개찰·낙찰/계약 → 기술·가격 점수와 수주/미선정 회고**로 확장하는 방향에 동의했다.
- **승인된 것은 기능 방향과 진행 방식이다.** 현재 6개 탭의 UI 구성/문구/상호작용 전체 승인이나 실제 외부 API/개인정보·보안 설계 승인으로 해석하지 않는다. UI 상태는 `UI_PROPOSED / USER_FEEDBACK_PENDING` 유지.
- 추가 화면 설계 시 가격입찰서와 기술제안서 각각의 제출/접수 확인 상태·근거를 분리한다. 공고별 제출 요건이 다르므로 필수 여부 자체도 공식 공고를 기준으로 판정한다.
- 참여하지 않기로 한 이유, 담당자 및 준비 단계, 제출 확인 결과, 개찰·낙찰·계약의 별도 상태, 기술/가격별 공개 또는 통보 점수, 점수 미확인 상태, 실패 원인과 개선사항을 **최종 UI 시안 검토 대상**으로 둔다.
- 서버 데이터 저장 및 공식 정보 자동 확인/수주 확정은 여전히 미구현이며, 개인·업체 비공개 기록은 공개 저장소의 합성 시안에 넣지 않는다.

## 2026-10-09 P0 통합 입찰관리 UI 퍼블리싱

- 현재 주요 검토 화면: `frontend/public/bid-management-preview.html`. HTML/CSS/바닐라 JS 단일 파일로 외부 서버·React/npm 없이 브라우저에서 작동한다.
- 대시보드: 8건 가상 입찰기회, 검색/분야/참여결정 필터, 결정·제출·수주 집계, 공고별 상세 이동.
- 참여 결정: Bid/No-Bid + 사유(미참여 필수), 담당자, 단계, 내부 준비일, 판단 근거.
- **제출 확인 분리:** 기술제안서와 가격입찰서마다 해당 공고 요구 여부/제출수기/접수증 확인수기/근거/확인일 구분. 실제 계정/공식 API 조회는 없음.
- 결과: 공고 전체 개찰/낙찰 상태와 우리 회사 선정, 계약 상태, 근거 유형을 서로 분리.
- 점수: 기술/가격 값·만점과 근거 유형, 입력 검증. 미확인은 0점으로 처리하지 않음.
- 회고: 미참여·미선정 원인, 개선·후속 조치. 결과/회고 대시보드에서 요약.
- 시안 조작: `가상 진행 사례 채우기`, `시안 초기화`; 브라우저 새로고침 시 자료가 사라진다. 회사 비공개 정보·실제 입찰 서류 입력 불가.
- **검증 상태:** UI 소스 작성, GitHub PR CI/실제 브라우저 동작 및 모바일 QA 결과는 최신 실행 증거로 별도 판단. 사용자 화면 승인 및 AGY 독립 최종 검수는 여전히 `NOT RUN` / `UI_PROPOSED`.
- 다음 작업: 화면의 검색, 참여 결정, 서류별 제출/접수, 점수 검증, 결과/회고, 모바일 동선에 대한 사용자 검증 → UI 수정 → 필요 데이터/API 계약 설계.

## 2026-10-09 통합 입찰관리 UI CI 및 브라우저 검증 결과

- GitHub Actions PR run [37904121398](https://github.com/son1004007/public-bid-agent/actions/runs/37904121398): frontend 타입 검사·Vite 빌드·3개 정적 HTML 검사 및 기존 backend pytest 모두 **PASS**.
- GitHub Actions 아티팩트: `bid-management-ui-preview` (ID `11603641894`) / 외부 운영 배포가 아닌 다운로드 가능한 HTML 묶음.
- HTML 3개를 CI 아티팩트에서 확보해 로컬 Chromium Playwright로 직접 시나리오 검증 **17/17 PASS**. 검사 항목: 8건 목록/집계, 가상 사례, 미참여 사유 필수, 제안서 접수 증빙 필수, 제안서/가격서 상태 독립, 점수 범위 및 출처, 회고 반영, 초기화, 콘솔 페이지 오류 0, 390px 모바일 가로 넘침 없음, 기존 목록의 새 화면 연결.
- Chromium은 HTML 문서를 `page.set_content`로 로딩해 가상 사용자 조작을 확인했으며 로컬 HTTP 서버/공개 배포를 수행하지 않았다. 브라우저 E2E 전체 경로/Google OIDC/실제 나라장터/인증·권한은 테스트하지 않았다.
- **UI 사용자 직접 검수: PENDING, 독립 최종 의미 검수: NOT RUN (REVIEW_DEBT)**. Draft PR #1 유지, `main` 병합 및 공개 운영 배포 미실행.

## 2026-10-09 사용자 개인 Codex 계정 선택 시안

- 최신 명시 요구: Public Bid Agent 사용자마다 **자신의 ChatGPT/Codex 계정을 선택해서 AI 분석에 사용할 수 있도록** UI 추가.
- `frontend/public/ai-account-preview.html`: 화면 내 AI 사용 안 함 / 내 ChatGPT-Codex 계정 선택 방식, 가상 A/B 계정 전환·가상 계정 추가·초기화, AI 요금제 사용 권한 요청 의향·공개 데이터만 전송 옵션, 실제 인증 미연결 상태를 구분.
- `frontend/public/bid-management-preview.html` 대시보드/메뉴, `ui-review.html` 목록, React 초기 앱에서 해당 화면으로 링크 추가.
- UI 시안 계정 정보: **합성 이름과 임시 메모리만 사용**. OAuth, 실제 계정 목록 조회/연결, 사용자 이메일·API 토큰 수집/보관, AI 요청·실제 비용/요금제 차감 없음.
- 공식 조사: `docs/research/2026-10-09-chatgpt-account-integration.md`. OpenAI의 Sign in with ChatGPT는 로컬 OSS용 사용자별 계정 등록·전환 및 사용자 승인 사용량 공유를 지원하지만, 공개 원격 웹서비스 적용은 별도 승인 대상.
- 후속 백엔드/인증 개발은 공식 원격 연동 승인/허용 여부 확인, OAuth/OIDC PKCE/state/nonce, ID token 검증, 계정/워크스페이스/권한 분리, 안전한 token 보관·폐기, 사용량 한도/예산과 데이터 격리 검증 뒤 진행.
- 화면 사용성 승인 `UI_PROPOSED`, 이번 변경의 독립 최종 검수 `NOT RUN/REVIEW_DEBT`로 유지.

## 2026-10-09 개인 Codex 계정 시안 검증 증거

- GitHub Actions push [37917254772](https://github.com/son1004007/public-bid-agent/actions/runs/37917254772) 및 PR [37917259804](https://github.com/son1004007/public-bid-agent/actions/runs/37917259804): **success**, Python backend pytest, React/Vite 빌드 및 오프라인 HTML JavaScript 정적 검사 통과.
- CI 산출물 `bid-management-ui-preview` artifact ID `11610855568` (신규 `ai-account-preview.html` 포함 HTML 4개). 외부 배포가 아니라 검토용 다운로드 파일이다.
- CI 아티팩트의 신규 계정 시안을 Chromium Playwright로 메모리 페이지 로드/인터랙션 테스트: **16/16 PASS**, 브라우저 pageerror **0**, 390px 모바일 가로 넘침 없음. 로그인 비활성·가상 A 선택·사용권한 의향 미승인·가상 계정 추가/전환·초기화·새 문서 로딩 상태 폐기·입찰관리 사이드바 링크를 포함.
- 전체 인증 E2E/실제 OpenAI OAuth·모델 사용 및 사용자 UI 승인, 독립 최종 검수: **NOT RUN**. 기존 REVIEW_DEBT 및 Draft PR 게이트 유지.

## 2026-10-09 Bid/No-Bid 영향인자 입력 화면 퍼블리싱

- 사용자 요구: 독립변수(영향인자)를 입력해서 Codex/Claude의 상호 검토와 **사용자 참여 결정**에 적용해야 한다.
- 공고별 관리의 **영향인자 평가** 탭 추가: 6개 공고별 필수조건 충족/미충족/미확인/해당없음, 8개 비교 인자의 1~5 수기 평가+근거·출처, 예상매출/수행원가/제안비용, 공고 기술·가격 배점.
- 추천 지표는 모든 Gate 확인·8개 인자 입력 때만 가중합 예시로 산출하고, 법적 적격·낙찰 확률/모델 분석으로 표시하지 않는다. 사용자 최종 결정은 별도 Bid/No-Bid 화면.
- 아직 실제 Codex/Claude/모델 API·RAG 연동 없음. 가상 두 AI의 **미실행 자리표시자**만 제공하며 자동 AI 의견을 꾸며내지 않음.
- 상세 변수 정의/근거/후속 LangGraph 계약: `docs/design/BID_NO_BID_FACTORS.md`. 실제 회사 자료 입력 금지.
- 필수 Gate·평가인자·지표의 수치는 공개 제품 시연용 가설로, 사용자/실제 사례 검토 전 정책·통계적 추천 정확도는 미확인.
- 본 UI 작업은 기존 공개 배포 불가, 사용자 UI 검토/독립 최종 검수 대기 상태 유지.

## 2026-10-09 Bid/No-Bid 영향인자 UI 검증 결과

- GitHub Actions push [37921415790](https://github.com/son1004007/public-bid-agent/actions/runs/37921415790) / PR [37921419837](https://github.com/son1004007/public-bid-agent/actions/runs/37921419837): **SUCCESS**. 최신 합성 HTML 4개 퍼블리싱 정적 검사, JS `node --check`, Vite 빌드, 기존 FastAPI pytest 정상.
- PR head `f1ffbbe1e981237e7615e803422998dad907f6a5`의 CI 산출물 ZIP `bid-management-ui-preview` (artifact `11611952655`)을 별도 확보, Chromium 브라우저에서 `page.set_content` 로드해 18개 조작 점검 **PASS**. 포함 항목: 빈 상태/메뉴/필수조건 근거 오류/6개 Gate+8개 인자/가중점수 80·100/가상 이익률 25%/사용자 결정 미변경/두 AI 미실행/기술·가격 배점 합계 거부/필수요건 실패 시 점수 미산출/공고별 입력 격리/브라우저 JS 오류 0/모바일 390px 가로넘침 없음.
- Chrome `file://` 접근은 컨테이너 정책상 차단돼 로컬 브라우저 자동시험은 `page.set_content` 방식이다. GitHub Pages 또는 사용자 실제 인터넷 브라우저/데이터 연동/인증 E2E 테스트를 의미하지 않는다.
- 영향인자 가중치 20/15/15/15/10/10/10/5 및 참여 검토 75·55 임계치는 *임의 퍼블리싱 시연 정책*이며 통계적 정확도나 실제 경쟁력·수익성 증빙이 없다.
- 여전히 `UI_PROPOSED / USER_FEEDBACK_PENDING`, AGY 독립 최종 의미 검수 `NOT RUN/REVIEW_DEBT`, `main` 병합/운영 배포 미실행.

## 2026-10-09 로컬 우선 JSON/AI 추출 전환 (최신 지시)

- 사용자: 영향인자를 직접 채우는 것이 아니라 **프롬프트·업로드 문서를 AI가 읽고 가정/근거/미확인 값을 초안으로 채운 후, 사람은 오류를 수정**하게 한다.
- 앱의 모든 상태·문서 추출 텍스트·AI 초안·수기 보정·사용자 최종 결정은 개인 PC JSON 파일에 저장한다. **로컬 저장이 AI 공급자 전송을 의미하지는 않으며**, 명시적 분석 시 선택한 공급자로 전송한다.
- 로컬 실행: Python 표준 라이브러리 localhost 앱 `local_app/server.py`, 접속 `http://127.0.0.1:8765/`, 저장 `~/.public-bid-agent-local/cases.json` (경로 환경 변수로 변경 가능). HTML/JS는 로컬 서버만 제공.
- 지원: text/markdown/csv/json 파일, pypdf PDF, python-docx DOCX (업로드 바이너리 미보관·추출 텍스트만 보관). HWP/HWPX/OCR 미지원. PDF/DOCX 파서는 현재 외부 비신뢰 파일 완전 격리 미구현.
- AI 실행: 실제 설치/로그인되어 있는 Codex CLI / Claude Code CLI 중 하나/둘을 선택하고 외부전송에 동의하면 제한된 서브프로세스로 요청 시도. AI 성공/실패/미설치를 구분하고 결과가 없는데 더미 결론을 만들지 않음.
- 로컬 단일 PC의 JSON에만 앱이 저장하지만 **Codex/Claude 도구 자체의 캐시·세션·원격 모델 제공자의 보존 정책은 별도**임. 절대 '전체 데이터를 오프라인에서만 처리'했다고 주장하지 않는다.
- AI가 만든 원문 근거/점수는 수기 확인 전 `verified=false`이며 사람이 기존 검증한 값은 자동 덮어쓰기 불가. 권고와 결정 별도.
- APMP 자료의 Go/No-Go·경쟁 우위·공고준비 비용·발주 목적·수익 및 조달청 계약 방식 검토를 반영한 8 Gate/12 비교 인자. 기준은 `docs/research/2026-10-09-local-first-ai-extraction.md`.
- 현재 단계: 신규 로컬 실행 MVP 코드 작성; CI/직접 브라우저 검증 및 사용자 승인/독립 리뷰는 별도 증거 전까지 **PENDING**. 이전 공개 웹 UI는 보존되고 본 변경으로 출시/공개 배포가 허용된 것이 아님.

## 2026-10-09 로컬 앱 구현 검증

- 최신 구현 커밋 `d097edc0652671d389d104bb32d5346ab65a37ef` — Python localhost Handler HTTP 속성 충돌 수정.
- GitHub Actions PR [37927086638](https://github.com/son1004007/public-bid-agent/actions/runs/37927086638): `success`, backend 기존 pytest, 로컬 JSON/HTTP unittest **8개 PASS**, frontend TypeScript/Vite 빌드 및 JS `node --check`, 기존 퍼블리싱 검사 PASS.
- 로컬 실행 ZIP: Actions run 37927086638 artifact `local-python-bid-agent` (ID 11613449792), source 6개 파일. 해당 ZIP을 내려받아 Python 3.13에서 unittest 8개 및 Node 문법 검사를 다시 통과.
- 로컬 Python 서버를 `127.0.0.1:8766`으로 실제 실행하고 직접 HTTP/JSON/CSRF 테스트는 성공. Chromium 환경에서는 localhost 직접 탐색이 플랫폼에서 차단됨(`ERR_BLOCKED_BY_ADMINISTRATOR`). 브라우저 화면 검사는 `set_content`와 모의 프런트엔드 fetch 결과로 분리 수행; 공고 생성/설명 저장/영향인자 입력 UI 등 핵심 UI 조작 성공, 모바일 390px 스크롤 가로 넘침 없음, page JS 오류 0. **실제 browser-to-localhost E2E 미검증**.
- 실제 Codex·Claude CLI 인증으로 수행하는 모델 분석은 **NOT RUN**. 이번 테스트는 실제 AI로 원문을 전송하지 않았으며 CLI 실행에서 계약/인증/JSON 생성 여부는 사용자 PC 검증 필요.
- 업로드 PDF/DOCX는 아직 완전한 별도 샌드박스가 없으므로 신뢰 불가능한 문서 처리는 개발 단계. 실제 기밀 회사 자료 운영 사용은 승인·보안 검수 전 HOLD.
- LangChain/RAG 및 LangGraph의 두 AI 상호 반론·상태 보존·중단/재개: **NOT IMPLEMENTED**. 현재는 독립 Codex/Claude 의견 요청과 사람 결정 분리용 MVP.
- 사용자 직접 UI 승인 `UI_PROPOSED`, AGY/Gemini 독립 최종 검수 `NOT RUN / REVIEW_DEBT`, `main` 병합/운영 배포 금지.

## 2026-10-09 실제 문서 형식 확장 구현

- 사용자 요구: 기존 UI는 유지하고 구현 단계로 진입. Excel(.xlsx/.xlsm/.xls), 일반 및 스캔 PDF 한국어 OCR, HWP 5.x, HWPX 지원.
- 코드: `local_app/extractors.py` (파일 형식 식별, ZIP 폭탄/크기/페이지 제한, PDF 텍스트+로컬 Tesseract OCR 자동 분기, Excel 시트별 셀 값, HWPX XML 본문, Apache-2.0 `python-hwpx`의 HWP 5.x 텍스트, DOCX 표 포함), `server.py` (별도 추출 subprocess + JSON 추출방식/경고 저장), `app.js`/`index.html` (UI 업로드 형식 및 경고 표시).
- 지원 범위: 파일당 10 MiB, PDF 40페이지/OCR 12페이지, Excel 최대 24시트·2500행·90열, ZIP 총 해제 35MiB/최대 750개 엔트리, 파일당 추출 텍스트 44,000자. 문서 전체를 무제한 분석했다고 주장하지 않음.
- OCR: Python 패키지 외에 Tesseract 실행 파일+한국어 `kor` 언어팩 사용자 PC 설치 필수. 모델 API를 통한 OCR이 아니라 **로컬 OCR**.
- 구형 HWP: `python-hwpx>=6.6,<7`의 HWP 5.x 파서 사용. 암호화/배포용/DRM HWP, HWPX 이미지/수식 등 한계. AGPL `pyhwp`는 직접 의존성으로 포함하지 않음.
- 코드/자동화: `local_app/test_extractors.py` 형식별 테스트, `local_app/test-requirements.txt` CI 테스트 의존성, 다운로드 아티팩트 업데이트.
- 이 변경은 업로드 바이너리를 업무 JSON에 저장하지 않고 추출된 텍스트·방식·오류경고·잘림 여부만 기록한다. Codex/Claude AI 전송은 사용자 명시 동의 이후 별개 경로.
- **검증 게이트:** GH CI 성공 여부/실 HWP·XLS 테스트는 실제 run evidence로 확인. 외부 악성 파일에 대한 완전한 OS 격리나 실제 사용자의 CLI 교차 검토/인증/정확도는 별도 미완료.

## 형식별 검증 및 파서 수정 (2026-10-09)

- 초기 CI HWP 테스트에서 python-hwpx의 TextExtractor가 ZIP HWPX 전용이라 실패. `HwpxDocument.open(path)`로 변경 후 HWP5 실바이너리 생성/재추출 테스트 통과 (커밋 `b5c1e176a5020717181620dcabf3b7a17688d6fb`).
- [GitHub CI 37932735254](https://github.com/son1004007/public-bid-agent/actions/runs/37932735254) push: frontend/backend SUCCESS, 로컬 문서 unittest 19개 중 18개 PASS + 1개 OCR Tesseract 미설치 skip. 실 HWP5·XLS 읽기 PASS.
- 로컬에서는 Tesseract+kor로 이미지 PDF OCR 시험 통과. CI에도 Korean Tesseract 설치 단계 추가하여 후속 run에서 19개 전부 검증하도록 함.
- 실제 다양한 기관 문서의 HWP 특수기능, 이미지 표/수식, OCR 숫자·표 재현율은 미검증. 중요한 사업 조건은 원문 직접 확인 필요.

## 최종 문서 파서 테스트 (2026-10-09)

- [GitHub PR CI run 37933016608](https://github.com/son1004007/public-bid-agent/actions/runs/37933016608): **frontend/backend SUCCESS**.
- `python -m unittest discover -s local_app -p 'test_*.py' -v`: **19 PASS / 0 SKIP**. 한국어 Tesseract 설치 후 스캔 PDF OCR, HWP 5.x 바이너리 생성/재추출, XLS 및 XLSX, HWPX, PDF, HTTP 파일 저장, ZIP 압축 제약 포함.
- CI의 `local-python-bid-agent` 산출물에 실행 코드, 의존성, README, 테스트 파일 모두 포함.
- 실제 기관별 대용량 RFP의 일부 이미지/복잡한 표, OCR 숫자 인식 정확도, 사용자 로컬 Codex/Claude CLI 계정 인증은 미검증. OS sandbox·AGY 독립 보안검수, 사용자 화면 승인, main 병합 및 인터넷 운영 배포도 별도 게이트.

## 2026-10-09 Python/라이선스 점검 및 로컬 2-AI 그래프

- 기준 인터프리터: CPython 3.12.x. GitHub Actions 3.12, `.python-version` 3.12, 루트/로컬 README 가상환경 명령 통일. 3.12.15 보안 릴리스는 source-only로 Windows 바이너리 설치 가이드는 공식 가용성 주의.
- 직접 의존성 Apache-2.0 호환성 점검: BSD/MIT/Apache-2.0/PIL MIT-CMU. PDFium 포함 패키지/전이 의존성 재배포 NOTICE는 별도 게이트. 공식 링크 `docs/DEPENDENCIES_AND_LICENSES.md`.
- `local_app/cross_review.py`에 실제 LangGraph StateGraph 독립 분석 → 상대 의견 재검토 최대 1회씩 → 기계적 이견/공통점 비교 로직 추가. LangChain Core ChatPromptTemplate 활용.
- `/api/analyze`는 사용자 동의 검증 후 그래프 실행. 분석 중 JSON 파일 lock을 놓고, 원문이 변경된 경우 오래된 결과를 거부. AI 결과는 미검증 초안이며 사용자 최종 결정 자동 변경 금지.
- UI에는 모델별 의견과 교차검토 이견/근거를 표시. 실제 모델 계정 연동/외부 요청 성공은 사용자 PC에서 검증 필요.
- 전체 구조/실행방법 루트 README에 기록, 코드 변경 커밋 시 루트·로컬 README 동시 갱신 CI 차단 규칙 적용 (`scripts/check_documentation_sync.py`).
- 새 테스트 결과/CI 상태는 해당 SHA의 실제 run 확인 후 표기, 독립 보안·사용자 최종 승인 미완료.

## 2026-10-10 Codex 전용 검증 개발

- Claude Code 유료 계정이 없는 환경을 지원하도록 Codex 단독 분석 모드 명확화. 기존 LangGraph의 단일 공급자 경로를 사용, 교차검토 상태는 만들어내지 않음.
- 회사 노트북 실제 테스트에서 Windows `shutil.which('codex')`가 npm extensionless shim을 선택해 WinError 193 확인. `codex.cmd` 사용으로 수정.
- 이어진 실제 CLI에서는 개인 기본 모델 `gpt-6.1-sol`이 ChatGPT 구독 인증 Codex에서 지원되지 않음을 확인. 사용자 설정을 변경하지 않고 프로젝트 호출에 `-m gpt-5.6-terra` 명시 및 임시 세션 `--ephemeral` 적용.
- 실제 Codex 호출·AI JSON 생성/저장 E2E는 별도 시험 결과 확인 필요. 회사 정보 없이 합성 입찰만 사용.

## 2026-10-10 회사 노트북 Codex 단독 실제 E2E 통과

- 사용자 계정에 Claude Code 유료 사용권이 없어 Codex 단독 모드를 실제 시험. 합성 가상 입찰공고만 사용, 회사 업무 자료 전송 없음.
- Windows Python 3.12 + Codex CLI 0.154.0 + ChatGPT 인증: 기존 npm `codex` 실행은 WinError 193, 기존 모델 `gpt-6.1-sol`은 Codex 인증에서 HTTP 400. 앱에서 `codex.cmd` + `gpt-5.6-terra` + read-only/ephemeral/user config 무시로 해결. 최소 JSON 원격 요청 직접 성공.
- 개발 브랜치 `778e2b047c09b7d3a488c7a8aa452d4809039c78` 회사 노트북 `PublicBidAgent\\Lab`에 fast-forward, Python 로컬 unittest **27 PASS**, Node 구문 검사 PASS, GitHub Actions PR run `37987914612` SUCCESS.
- 실제 HTTP `/api/new` → `/api/save` → `/api/analyze` (`providers=[codex],consent=true`) 성공, 약 21.2초. Codex 결과 `status=success`, `recommendation=hold`, Gate 8개 / Factor 12개, `ai_draft` 생성과 로컬 JSON 저장 확인. LangGraph `cross_review.status=single_or_failed`; 사용자 결정 `undecided` 보존.
- 테스트 서버 8769 중지. 실사용 로컬 서버 8765 실행, 바탕화면 `Public Bid Agent (Local)` 런처 별도 설치, HTTP 200 및 loopback 127.0.0.1 확인. 실사용 데이터 `%LOCALAPPDATA%\\PublicBidAgent\\Lab\\user-json\\cases.json`, 테스트 데이터는 별도 `codex-synthetic-test-data`.
- 실제 Claude 및 2-AI 교차검토 E2E 미수행, 보안 독립 최종 검수/회사 실무 문서 OCR 정확도 미완료. 대외 운영 또는 main 병합하지 않음.

## 2026-10-10 실제 공고 수기 표본과 평가 입력

- 나라장터 공고 3건 메타데이터/전재문을 공개 재게시 서비스에서 수기 확인: `R26BK01745574-000`, `R26BK01747372-000`, `R26BK01759604-001`.
- 공식 나라장터 공고 첨부 직접 다운로드 시 회사 노트북/컨테이너 환경에서 403 또는 접속 오류로 원본 검증 불가. 해당 자료는 `source_quality=third_party_republication`이며, 공고/원문 사실과 가상 업체 내부 상태를 별도로 기록.
- 가상의 부서 능력/법적 등록/인력/원가가 다른 시나리오 4개 작성. 모든 '가상 기업'은 사용자 실제 재직 부서에 관한 사실 진술이 아니다.
- 검증 fixture: `local_app/fixtures/public_tenders_2026_10_10.json`. 공고 원문 전재의 LLM 사업은 AI 코어 RAG 구현이 **과업 제외**, 운영·서비스 연동이 주로 요구됨. 하나의 재게시 출처에서 입찰마감 14:00 vs 공고 메타데이터 10:00 충돌하여 더 빠른 10:00으로 일단 가정하고 확인 필요.
- 현시점에는 아직 실제 공고의 Codex 판단 검증 결과를 작성하지 않음. 정상 호출 및 결과 비교를 수행한 뒤 채운다.

## 실제 공고 3건·가상 부서 4개 Codex 실분석 완료 (2026-10-10)

- PC 별도 합성 데이터 `public-notice-mvp-synthetic-data`에서 네 번의 실제 Codex 구독 모델 실행(사용자 계정, 합성 부서 조건만). 각각 18.7초/31.6초/27.0초/21.4초, CLI SUCCESS 4/4, Gate 8개·Factor 12개 출력 4/4, 미검증 ai_draft JSON 저장, 실제 사용자 decision=undecided 유지.
- R26BK01745574-000 가상 대기업: 참가 유형 불일치 등 AI가 필수 Gate 2개 실패를 추출했지만 `recommendation=hold`이고 `reason` 빈값.
- R26BK01747372-000 가상 약한 팀: 과학 시뮬레이션 인력 부족 Gate 1개 실패·보류. 동일 공고 가상 전문팀: 실패 Gate 0, 미확인 7, 보류.
- R26BK01759604-001 가상 클라우드팀: RFP 미확인으로 필수 Gate 모두 unknown, 평가인자 점수 0/12, 보류.
- 따라서 단순 model.recommendation으로는 참가 결격 위험과 증빙 부족을 차별화하지 못하는 결함 확인, `local_app/decision_support.py` 보수적 위험표시와 모델 사유 누락 감지/사용자 보정 후 재산정 도입.
- 미해결: 공식 G2B 원문 403(전재 자료 근거 한계), 모델 사유 빈값, 과거 낙찰 데이터 부재로 실제 '수주 확률' 예측 불가. 정식 독립 검수와 main 병합은 별도 판단.

## 2026-10-10 최신: 수기 공고 분석 완주 / MERGE HOLD

- 실제 공고 3건(수기 전사), 가상 회사·부서 조건 4개, 사용자 PC Codex AI 실행 4/4 SUCCESS. 결과 Y1 raw hold 4, 참고 Gate 위험: provisional no-bid 2 / 추가 증빙 hold 2, 사용자 Y2 undecided 4. 모델별 사유 문자열 전부 공란으로 안전 경고 노출.
- `decision_support.py` UI 및 백엔드 GET/POST 로컬 HTTP 재검증 4/4 PASS, 36개 Python 회귀 테스트, GitHub CI run 37997843667 SUCCESS.
- 사용자용 Windows 로컬앱 8765 `[검증 사례·실제공고/가상 업체]` 4개 데이터 이관, JSON 백업 수행 후 HTTP 200/4건/127.0.0.1 확인. 실제 사용자 회사 데이터는 사용하지 않음.
- 공공 공고의 공식 원본 첨부 403, 재게시 마감 충돌, Codex 판단 근거 부족 및 AI 원시 reason 누락 한계 남음.
- AGY/Gemini 및 Codex의 독립 최종 코드 검수가 원격 read-only command 권한 차단으로 미완료. 별도 유효 review 결과 없음. 글로벌 정책상 `REVIEW_DEBT / MERGE HOLD`로 남기며 위험 권한 우회 금지.
- 상세 재현 기록: `docs/reviews/MVP_PUBLIC_BID_E2E_2026-10-10.md`. 다음 작업: 안전한 독립 검수 해결→필요시 수정/재검수→main 병합→자동 수집 Sprint.

## 2026-10-10 독립변수 확인 UX 개선

- 4건의 로컬 가상부서 분석 데이터 재확인: AI `ai_draft`에는 모든 8 Gate와 12 Factors의 제안 및 근거가 존재하나 수기 `factors`에는 아직 score가 저장되지 않아 기존 UI는 'AI 초안 적용' 전까지 공백을 보여주었음.
- 기존 데이터에서 **위험 통제 risk 점수의 방향 역전**을 발견: 수행위험이 매우 높다는 근거인데 5점으로 반환된 사례가 있었음. 과거 결과는 변경하지 않고 미검증 상태로 둠. 신규 AI 프롬프트에 risk/bid_cost 등 모든 Factor 5점=유리한 상태 및 reason 필수 안내 추가.
- 화면에 `AI 독립변수 20개 및 추출 근거 (읽기 전용, 미검증)`를 추가해 공고 선택만으로 원본 Gate/Factor/근거 표시, 사용자 편집/결정에 부작용 없음.
- 변경의 CI/PC 실제 응답 검증 및 독립 최종 검수는 해당 변경 SHA별 실행 증거 확인 필요.

## 2026-10-10 팀장용 독립변수 입력문서 가이드 추가

- 기존 8 Hard Gates/12 Soft Factors를 외부발주 자료(입찰공고/RFP)와 실제 회사 보유 자료(입찰자격/실적·인력/원가·제안계획)의 **5개 문서 묶음**에 연결. 문서별 보유 담당자, 예시, 누락 시 요약 방안, 정보 등급, 20변수별 확인 질문 포함.
- 단일 데이터 사전 `local_app/document_guide.json`, 앱 첫 화면(공고 선택 전에도 접근)에서 독립변수→필요 문서/미확인 질문 가이드. 서버 GET `/document-guide.json`, 사용자별 상태 변경/모델 호출 없음.
- 안내 목적만 구현: 자동 문서 종류 식별·출처 인용 정합성·자동 문서 체크리스트 작성은 미구현. 실제 내부자료를 개인 ChatGPT/Codex에 전송하지 않고 허가/비식별 수기요약을 안내.
- CI artifact에 문서 매핑 및 현재 실제 실행에 필요한 decision_support.py 등 파일 포함하도록 패키징 경로 수정.
- 새 변경의 Windows 로컬/CI 증거 및 독립 코드 검수 결과는 확인 후 별도 기록. 기존 Draft PR main 병합 HOLD 유지.

## 2026-10-10 회사 운영정보/원가계산 단위 구현

- 회사 운영정보를 재사용 가능한 별도 로컬 `operations.json`으로 설계. role/MM 단가·가용, 간접비율·위험충당률 입력. 초기값은 **빈 직무 목록(실회사 정보 없음)**; 가상 fixture로 검증.
- 공고별 투입 MM·외주비·경비·제안준비비·공급가(VAT 제외), 수익/이익률 계산 엔진 추가. revision 동시 수정 충돌(409), 이전 견적 기준 버전 표시, 용량/입력값 엄격 검증, 원가 데이터 LLM 자동 전송 금지.
- 이번 수직 슬라이스의 실행·검수 결과는 실제 검증 후 확인할 것. 기존 수기 실공고 검증·입찰 최종 결정 기록은 변경하지 않음.
- 회사 원가/직원 개인 급여를 실데이터로 저장하거나 외부 전송하지 않았음. 보안 정책 승인 이전에는 가상 프로필만 사용.
- 기존 독립 리뷰 미완료로 main Draft PR HOLD 유지.

## 2026-10-10 운영 장부 범위 확장

- 원가 기준 외에 회사 영업·수행·재무·인력/협력사 운영자료 8종 수집/확인 메타데이터 관리(`registers`) UI와 JSON 모델 구현. 원본 파일/개인급여는 수집하지 않고, 담당 부서·비식별 요약·출처 문서명·검증일만 보관. 수집/요약 완료를 구분.
- 실제 회사정보는 입력하지 않으며 자동 Codex 전송하지 않음. 사용자 판단과 원가계산은 운영자료 요약에 따라 자동으로 변화하지 않는다.

## 2026-10-10 개발 브랜치 CI 회귀 관리

- 운영자료 날짜 검증 정규식의 잘못된 이스케이프를 로컬 실패 테스트로 발견·수정. 이어진 코드 한 줄짜리 fix 커밋이 루트/로컬 README 동시 변경 의무를 지키지 않아 push CI의 README gate 실패 확인(동일 SHA PR CI는 SUCCESS).
- 이 의미 있는 날짜 보정/추가 테스트 변경에서 두 README를 함께 갱신해 push CI 재검증. 과거 workflow failure 기록은 삭제/숨기지 않음.

## 2026-10-10 운영정보 원가/8종 운영자료 실제 검증 결과

- `ops-cost-synthetic-e2e` 합성 데이터에서 기준정보 revision 0→1→2, 인건비 27,000,000원, 예상 총원가 37,805,000원, 이익 12,195,000원(24.4%), 원가 재산정 구버전 상태 및 CSRF 필수 보호 검증. 인가되지 않은 실제 회사/고객 데이터 입력 없음.
- 추가 8종 자료 메타데이터(재무 reviewed, 파이프라인 needs_refresh, 나머지 미확인 6개) 로컬 저장 성공. 초기 사용자용 운영정보는 여전히 비어 있음.
- Windows 50개 unittest PASS, JS syntax PASS, GitHub push CI 38040046052 및 PR CI 38040049212 SUCCESS. CSRF 경계 테스트 1회 WinError 10053 간헐 실패 기록, targeted/full 재실행 PASS (관찰 필요).
- 실제 사용자 로컬 앱 8765 재시작, 기존 4개 합성 공고·최종결정 보존, UI HTML·JS·8종 운영자료 제공 200·loopback 확인. 브라우저 실제 인터랙션/레이아웃 검수는 NOT RUN.
- 상세 [운영정보 E2E 보고서](docs/reviews/OPERATIONS_COST_E2E_2026-10-10.md). AGY/독립 Codex 의미 검수 미완료로 Draft PR #1 및 main merge HOLD.

## 2026-10-10 새 화면 요구 반영: 공고 목록 중심 UX

- 사용자 요구: AI·데이터분석 공고를 정기 수집 → 목록에 표시 → 사용자가 버튼으로 참여여부 판별 → 판단기준과 8+12 영향인자를 별도 버전형 프로필로 저장 → 불참 항목의 이유/근거·사용 프로필·판단 이력 확인.
- 퍼블리싱 단계 구현: `frontend/public/bid-decision-dashboard-preview.html` (HTML/CSS/JS 정적, 백엔드 의존 없음), 기존 로컬앱 `/decision-preview` 경로와 첫 화면 안내 링크. 리스트·단건/일괄 판단·가상 수집·두 프로필 편집 및 가중치 검증·이력 필터·불참 근거 상세·반응형. 모든 데이터 합성/메모리 임시이며 수집·판별·영구저장·AI 연동은 실제 구현하지 않음.
- 사용자에게 먼저 화면 확인 요청. UI_APPROVED 아님. 실제 나라장터 수집 스케줄러, 실제 프로필 DB/JSON 모델, 검증 가능한 법적 Gate, 실제 입찰 참여 최종결정 이력은 차기 스프린트로 보류.

- 시안 코드 자동검증 1차에서 새로고침 안내 문구와 테스트 불일치 발견. 수정하면서 12개 Factor 가중치 프로필이 화면의 재판별에 실제로 반영되도록 가상 weightedFit() 시뮬레이터를 추가하고, 불참 최종결정에 별도 담당자 사유 입력을 요구하여 기록을 분리함. 사용자 검증 전까지 MOCK_ONLY.

- 독립 시안 Chrome headless DOM에서 공고 목록/프로필이 초기 렌더링되지 않는 결함 발견: 기존 로컬 서버의 CSP `script-src 'self'`가 HTML 인라인 코드를 차단. 보안 헤더를 완화하는 대신 별도 JS로 분리하고 로컬 동일출처 GET 라우트를 추가. 브라우저 실행 검증 진행 상태는 별도 기록.

## 2026-10-10 공고 의사결정 UI 퍼블리싱 최종 동작 상태

- 사용자 요청대로 목록 중심·정기 수집 계획·단건/일괄 판단(가상)·참여 판단 기준 Profile·8 Gate/12 Factor Profile·불참 사유 및 판단 이력 5개 영역을 정적 HTML+외부 JS로 구현.
- Windows Node JS 구문 검사 PASS, 정적 시안 Python 검사 3개 PASS, 실제 Chrome headless DOM 8개 공고행/5개 KPI/12개 가중치 컨트롤 생성 PASS, localhost /decision-preview HTTP 200, CSP 유지. GitHub push/PR CI 38049729286/38049733578 SUCCESS.
- 전체 Windows Python 53테스트 수행 중 기존에 반복된 CSRF negative-case URLopen WinError 10053 2개가 간헐 발생. 시안 범위 별도 테스트는 PASS; 기존 Windows 로컬 HTTP test 간헐 실패 추적 지속.
- Chrome headless에서 기본 렌더링을 확인했으나 실제 사용자 클릭 기반 브라우저 자동 E2E와 UI_APPROVED는 NOT RUN. 기존 로컬 JSON 사례는 시안 GET 동작으로 수정되지 않음. merge HOLD, 백엔드 기능은 UI 확인 후 구현.

## 2026-10-10 공고 전체 상세 화면 시안

- 사용자 요청: 공고 목록에서 상세보기 눌렀을 때 실제 어떤 내용이 표시되는지 구현. 별도 `view-full-detail` 화면, 4개 탭(기본/참가자격·과업/영향인자·사업성/결정·불참·이력), 원문·첨부 미수집 표시, 공고·프로필 동일 합성 상태로 목록/상세/이력 흐름 연결.
- 상세보기 자체는 단순 렌더링이며 AI/수집/서버 저장·판단 상태변경 없음. 실제 자동수집과 모델 분석·원문 증빙·프로필 서버 저장은 여전히 미구현. 화면 시연 데이터는 브라우저 탭 메모리만.
- 새 상세 화면의 테스트/브라우저 클릭 검증은 변경 후 확인하여 기록. main 병합 미실시, 독립 의미·보안 검수 필요.

- 상세뷰 회귀 검사의 첫 실행에서 동적 불참사유 입력 노드에 대한 정적 HTML 단언이 실패해, 노드 생성 코드 확인으로 테스트를 수정. 화면 자체의 실패로 분류하지 않음.

## 2026-10-10 전체 상세 화면 브라우저 검증

- Windows Chrome 19개 실제 클릭 체크 PASS: 공고 상세보기 부작용 없음, 자격조건 8/평가인자 12, 별도 판단 버튼·사유 입력·최종 불참기록, 목록 복귀/이력 유지.
- Python 상세 시안 회귀 4 PASS, Node syntax PASS, 로컬 HTTP 200, GitHub push/PR run 38050935732/38050937747 SUCCESS. 기존 사용자 합성 사례 5건 유지.
- [상세 보고서](docs/ui/DECISION_DETAIL_PREVIEW_E2E_2026-10-10.md) 참고. 사용자 UX 승인 및 독립 코드 리뷰는 여전히 미완료, main merge HOLD.

## 2026-10-10 프로필 로컬 백엔드 연결 (구현 중)

- 사용자 최신 지시: 퍼블리싱을 검토한 뒤 백엔드 구현으로 진행. 과거 `UI_APPROVED` 전 백엔드 확장 보류 규칙은 합성 로컬 프로필 수직 슬라이스에 한해 해제한다.
- 대상 브랜치: `feat/sprint1-search-demo`, Draft PR #1. `main`은 미병합된 기존 설계 단계이며 여기에 구현 코드가 없다.
- `local_app/decision_profiles.py`: 참여 판단 기준/12 가중치 2종의 입력 검증, 버전별 스냅샷, revision 경합 검사, 별도 `decision_profiles.json` 계약.
- `local_app/server.py`: GET `/api/decision-profiles`, POST `/api/decision-profiles/save`(Host/Origin/CSRF, 400/409/503 구분, 원자 파일 저장).
- `frontend/public/bid-decision-dashboard-preview.js`: 로컬앱 `/decision-preview`에서 저장/새로고침 복원, 독립 HTML 파일에서 메모리 시안 유지. 저장 충돌 시 이전 내용을 덮어쓰지 않고 재조회.
- **범위 제한**: 공고 8개/판별/불참 이력은 계속 합성·메모리 시연, 실시간 자동수집/AI 호출 없음. 기존 회사 운영정보·공고 분석 JSON 변경 없음.
- **검증된 실행 증거 (2026-10-10):** 커밋 `10a0dfb`의 [push CI](https://github.com/son1004007/public-bid-agent/actions/runs/38059273249)와 [PR CI](https://github.com/son1004007/public-bid-agent/actions/runs/38059276328)는 모두 SUCCESS. 로컬 Python unittest **60 PASS**, FastAPI pytest **11 PASS**, React/Vite 빌드/Node JS 문법/퍼블리싱 정적 검사/README 동기화 **PASS**.
- 위 결과는 GitHub Linux CI의 `VERIFIED (automated)` 범위에 한정된다. 사용자 PC의 로컬 브라우저 클릭/프로필 복원/동시 탭 E2E `NOT RUN`; AGY/Gemini 및 독립 Codex 최종 리뷰 `BLOCKED/REVIEW_DEBT`; 사용자 UX 승인 `NOT RUN`, main 병합·공개 배포 `HOLD`.
- [프로필 API 테스트 근거](docs/reviews/DECISION_PROFILES_API_2026-10-10.md).

## 2026-10-11 Windows 실행 및 Chrome E2E

- `TD-kiseok`에서 `feat/sprint1-search-demo`를 `bb06ff1`까지 Fast-forward, 작업 트리 clean 상태 확인.
- Windows CPython 3.12 로컬 unittest **60 PASS**.
- 기존 사용자 데이터를 변경하지 않는 임시 `127.0.0.1:8766` 환경에서 Chrome 실제 DOM·클릭 기반 프로필 저장/새로고침/가중치 변경/409 충돌 **6항목 PASS**.
- 기존 `127.0.0.1:8765` 개발 앱을 동일 저장 경로로 재시작. GET `/`, `/decision-preview`, `/bid-decision-dashboard-preview.js`, `/api/decision-profiles` 모두 HTTP 200.
- 기존 실제 사용자 `cases.json`의 SHA-256 재시작 전후 동일, 기존 공고 5건 유지. 테스트용 임시 Chrome·서버·데이터/스크립트 정리.
- 이 결과는 **Windows 합성 브라우저 E2E 및 기존 데이터 비파괴 재시작의 VERIFIED** 근거다. 새 사용자 프로필 실사용 데이터 저장·사용자 UX 승인·독립 AGY/Gemini/Codex 리뷰는 아직 미완료. Draft PR 및 main merge HOLD 유지.
- 상세: [Windows E2E 보고서](docs/reviews/DECISION_PROFILES_WINDOWS_E2E_2026-10-11.md).


## 2026-10-11 공고 중심 백엔드 수직 슬라이스 진행

- 최신 사용자 지시: 새 퍼블리싱 대시보드를 **구현의 기준 UI**로 삼고, 공고·상세·수집상태·판단 이력 API를 연결한다.
- 로컬 `local_app/dashboard_backend.py`: 조달청 공식 용역 입찰공고 조회 HTTPS 읽기 전용 어댑터, 최근 1일·최대 3페이지·키워드 임시 필터, 독립 dashboard.json, 수집 오류/0건 분리, 공고번호·차수 기준 upsert, 사람의 결정/이력 불변.
- `local_app/server.py`: `/api/dashboard` GET과 `/api/dashboard/collect`, `/api/dashboard/action` POST; 로컬 Host/Origin/CSRF, 409 충돌, 인증키 미설정 424, 외부 조회 실패 503. 기존 cases/operations 프로세스는 보존.
- `frontend/public/dashboard-live.js`: 로컬 /decision-preview에만 서버 응답으로 기존 8개 합성 자료를 교체하고, 공식 메타데이터/미확인 자격/사람 결정·이력을 별도로 렌더링. 독립 파일 시안은 시연 상태 유지.
- 정기 스케줄러, 전체 공고 커버리지, 공식 정정/취소, 실제 문서·RFP/모델 분석 및 점수, 실제 사용자별 로그인/공개 배포는 미구현.
- 인증키는 별도 환경변수 `DATA_GO_KR_SERVICE_KEY`로만 처리. 실키 기반 실제 API HTTP 성공과 사용자 데이터 운영은 별도 검증 전.
- 검증 상태: **구현 중 / 최신 커밋 CI·PC 실행 결과 확인 전**. 독립 최종 검수·사용자 UX 승인·main 병합은 계속 HOLD.

- Windows 전체 unittest 66개 실행에서 기존에 보고된 WinError 10053이 신규 CSRF 거절 테스트 1건에서 재발. 인증 거절 전 남은 요청 본문 처리 개선 코드를 추가했으며 최신 런타임/CI 재검증 전까지 해결 완료로 간주하지 않는다.


## 2026-10-11 새 공고 대시보드 Windows 실행 검증

- 개발 브랜치 `514183b` 기준 Windows unittest **66 PASS**, Node JavaScript 검사 PASS, Chrome fake-provider UI E2E 5항목 PASS.
- 기존 로컬 앱 8765를 최신 소스로 재시작. 메인/대시보드/JS/API 5개 HTTP 200, 기존 공고 5건과 cases.json SHA-256 유지, 공식 공고 대시보드 초기 0건.
- 공식 공공데이터포털 API 키 미설정 → 수집 POST는 HTTP 424, dashboard.json 자동 생성 없음. 실제 공식 공고 HTTP 수집은 **BLOCKED**. 중앙 [USER ACTION #20](https://github.com/son1004007/ai-agent-workflow-playbook/issues/20).
- 최종 코드/보안 독립 검수 및 UX 사용자 승인은 미완료. Draft PR/main merge HOLD.
- [Windows 브라우저·HTTP 검증 보고서](docs/reviews/DASHBOARD_BACKEND_WINDOWS_E2E_2026-10-11.md).


## 2026-10-11 나라장터 API 인증키 웹 등록 기능

- 사용자: 키를 이미 발급받음. 화면에서 공공데이터포털 활용신청 링크·인증키 입력·PC 저장·연결 확인까지 직접 사용하도록 변경 요청.
- 새 모듈 `local_app/procurement_credentials.py`: Windows 현재 사용자 DPAPI 암복호화, `LOCALAPPDATA/PublicBidAgent/secrets/g2b_servicekey.dpapi` 파일에 암호문 원자 저장. 입력키 평문/일부 글자/API query를 API 응답·파일 JSON에 반환하지 않음. 환경변수 기존 경로 보존.
- 기존 로컬 앱 `/api/procurement-key` GET (상태만), `/save`·`/verify`·`/delete` POST, 브라우저 `수집 관리` 패널 연동. 공식 사이트 링크는 신청 페이지에 이동하되 로그인/신청 대행 안 함.
- 첨부한 조달청 API v1.2 참조 문서에서 용역 검색 오퍼레이션 `getBidPblancListInfoServcPPSSrch`와 요청키 명 `ServiceKey` 확인해 어댑터 수정.
- 현재 단계: 로컬 합성/격리 검증, 사용자 발급 키 **실제 입력·연결 확인 아직 수행 전**. Windows 브라우저 및 GitHub CI/최종 보안 검수 결과 별도 추적. Draft PR 및 main HOLD.

## 2026-10-11 인증키 웹 등록 실행 검증

- GitHub 개발 브랜치 `acd8653`: Windows 전체 unittest **74 PASS**, 실 Windows CryptProtectData/UnprotectData 사용자 범위 왕복 PASS.
- Chrome Headless 실제 UI 클릭 5항목(미등록 상태/가상 키 암호화 저장/연결 확인 mock/공고 수집 mock/삭제) **PASS**. 가상 키는 별도 임시 폴더/임시 서버에서만 사용.
- 기존 PC 로컬 앱 8765 최신 코드 재시작, 메인/대시보드/JS/API 6경로 HTTP 200, 사용자 `cases.json` 해시 동일/기존 공고 5건 유지, 실제 키 아직 미입력/미등록.
- 구현 CI Push [38113357140](https://github.com/son1004007/public-bid-agent/actions/runs/38113357140) 및 PR [38113360004](https://github.com/son1004007/public-bid-agent/actions/runs/38113360004) **SUCCESS**.
- 사용자가 키 발급을 완료했다고 보고함. 다음은 실제 키를 자신의 로컬 수집 관리 화면에 붙여넣고 **별도의 API 연결 확인** 실행. 키는 공유하지 않는다.
- [웹 인증키 검증 보고서](docs/reviews/PROCUREMENT_KEY_WEB_E2E_2026-10-11.md). 독립 최종 보안 검수/사용자 UX 승인 전 Draft PR/main merge HOLD.

## 2026-10-11 실 API 수집 및 최근 7일 조회 보완

- TD-kiseok Windows DPAPI에 실제 사용자가 등록한 키 존재 확인(값 출력 없음). `POST /api/procurement-key/verify` 실제 API 응답 `ok=true`, `verified=true` 확인.
- 기존 24시간 실 API 수집은 `status=SUCCESS`, 원본 1건·제목필터 해당 0건·저장 0건. 이는 정상적인 주말 조회이며, 실 관심공고 수집 실패라는 의미는 아님.
- 실제 API 과거 일자 별도 진단: 2026-10-08 KST 원본 700건/관심 제목 90건, 10-09 KST 원본 10건/관심 제목 2건. 개발 시안이 아닌 실제 조달청 API 반환 공고 기준이며, 참가자격/적합도는 검증 전.
- 데이터가 0건인 주말에도 유효한 목업/실데이터 UI 검증을 위해 `POST /api/dashboard/collect`에 1일/7일 옵션, UI 조회 기간 선택을 추가. 7일 수집은 모든 일자를 조회할 때만 성공으로 기록하며 공고 중복 제거 및 이전 의사결정 보존.
- 이 변경의 Windows/Chrome 재테스트 및 실제 7일 저장 검증은 커밋 이후 별도 증거를 기록. 독립 보안 검수·UX 최종 승인 전 Draft/main HOLD.

## 2026-10-11 실제 나라장터 공고 수집 및 Chrome 목업 테스트 결과

- 사용자 등록 Windows DPAPI 키 구성 확인, 실제 `/api/procurement-key/verify` 응답 **SUCCESS**.
- 실제 `/api/dashboard/collect`: 24시간 원본 1/관심 0, 범위 보완 후 **최근 7일 원본 2,227/제목 필터 275건**, 로컬 dashboard.json 공고 275건 저장. API 수집 SUCCESS, revision 2.
- 공개 공고 링크 275건, 제목 기반 AI 104/SW 97/DATA 74. 마감 미래 209, 마감 미확인 37. 제목 필터는 입찰 가능/실제 자격/AI 적합성 평가가 아님.
- Windows unittest 76 PASS, 실제 공고 Chrome 목록·상세·8개 미확인 필수조건/12개 미확인 영향인자·수집 상태·새로고침 PASS.
- 실제 공고를 **별도 임시 서버/JSON 사본에 복제**해 담당자 보류/사유/프로필 이력 저장 및 새로고침 검증. 실제 dashboard.json/cases.json E2E 전후 바이트 동일.
- KPI '합성 공고 목록' 안내를 실데이터에서 공식 API 출처 표시로 변경. 수정 후 Chrome 7개 시나리오 모두 PASS.
- GitHub Actions 최신 Push [38114456978](https://github.com/son1004007/public-bid-agent/actions/runs/38114456978) / PR [38114459846](https://github.com/son1004007/public-bid-agent/actions/runs/38114459846) SUCCESS.
- [실 API/Chrome 검증 상세보고](docs/reviews/G2B_LIVE_COLLECTION_UI_E2E_2026-10-11.md).
- 공개배포·main 병합 HOLD: 독립 AGY/Gemini/Codex 최종 보안/의미 검수 및 사용자 최종 UI 승인 미완료.

## 2026-10-11 전체 용역·과업 원문 기반 관심 분야 분류 구현

사용자 요청: 제목 필터 누락 방지, 조달청 전체 용역 원본 저장 후 공고 상세·과업내용·기한·부서 카테고리 필터 적용.

구현: procurement_filter.py 로 AI/SW/DATA/SECURITY 분류와 REVIEW/OUT_OF_SCOPE 및 취소/마감/등록기한 분리. department_profile.json 버전 저장. 공공조달 분류/정보화사업/업종 제한/규격서1~10 URL/파일명/입찰공고 상태 보존. procurement_documents.py 공식 g2b HTTPS 첨부 안전 다운로드+로컬 subprocess 텍스트 추출/재분류, 최대 5건 요청 배치. 전체 원본 DB에서 삭제하지 않음.

참가자격 실제 충족, RFP 파서가 처리하지 못하는 파일, 별도 면허·지역 상세 API, AI 모델 근거 분석과 독립 최종 검수는 미완료. 실제 Windows/CI/브라우저 검증 전까지 구현 결과를 VERIFED로 간주하지 않음. Draft/main merge HOLD.

## 2026-10-11 공고별 나라장터 추가 제한·첨부 조회

- 새로운 procurement_related.py 가 공식 입찰공고정보서비스 면허제한/참가가능지역/e발주 첨부 목록 오퍼레이션을 고정 HTTPS로 조회한다.
- local_app/server.py POST /api/dashboard/related 를 UI 상세 탭 버튼에 연결한다. 선택 공고번호+차수만 추가 조회하고, 기존 사용자 판단/문서/공고 목록은 보존한다.
- 실제 회사의 등록/면허/실적/수주 참여자격은 미확인 상태를 유지한다. 실 서비스 API E2E 및 독립 보안 리뷰 전까지 검증 완료로 표기하지 않는다.

## 2026-10-11 전체 용역·RFP·면허/지역 상세 구현 검증

- 사용자 제목 필터 누락 문제 개선 완료: 공식 API 최근 7일 원본 2,225행 → 공고번호+차수 2,223건 전수 저장. 구 275건/사용자 사례 5건 및 최종 판단 이력 0건 보존.
- 공식 공공조달분류·정보화사업/제안첨부/본문/마감/취소/등록마감 분리, 부서 관심 분야 AI/SW/DATA/SECURITY 로컬 프로필. 범용 개발·구축 오탐 수정 후 전체 2,223건 로컬 재분류: CANDIDATE 143, REVIEW 2080. 화면 기본 현재 후보 125, 필터 변경하면 전체 2,223건 확인.
- 실제 NMS 소프트웨어 개발 PDF RFP 6,284자 안전 추출, 본문 근거로 AI/SW/DATA 분류. 5건 일괄 시험 중 4건 성공/1건 실패를 확인하고, 이후 자동 5건을 부서 CANDIDATE 우선으로 제한. 현재 총 추출 성공 문서 5개, 나머지 미확인.
- `/api/dashboard/related`: 공식 면허/참가지역/e발주 첨부 3 오퍼레이션. 실제 NMS 공고 상세 API 성공, 면허/지역 목록 0건, 첨부 2건 보존, 회사 법적 참가자격 UNVERIFIED 유지.
- Windows unittest **93 PASS**, JS 검사 PASS, GitHub Push [38117518610](https://github.com/son1004007/public-bid-agent/actions/runs/38117518610)/PR [38117521593](https://github.com/son1004007/public-bid-agent/actions/runs/38117521593) 모두 **SUCCESS**. 실제 Chrome 2,223행 전체 필터/125 기본 후보/공식 RFP/면허·지역 상세 UI **7 PASS**.
- [상세 검증 보고서](docs/reviews/G2B_ALL_TENDER_CATEGORY_RFP_2026-10-11.md). 독립 코드/보안 검수 및 사용자 UI 최종 승인 전 Draft/main merge HOLD.

## 2026-10-11 재개형 RFP 배치·REVIEW 2차 메타 우선순위 (개발 진행)

- 사용자 최신 지시에 따라 기존 별도 퍼블리싱 화면을 만들지 않고 `/decision-preview` 수집 관리 화면을 확장. 직렬 RFP 처리/중단·재개·실패 재시도, 작업 상태 별도 `rfp_batch.json`, 문서 2개까지 출처·SHA256·본문 발췌 기록.
- 재시작 후 처리 상태 복원, 기존 공고 성공/담당자 참여 결정/원본 2,223건 보존. RFP 다운로드는 원래 승인된 공식 HTTPS 도메인, 8MiB, 90초 추출 subprocess/파일 제한에 의존.
- 공고 전체 REVIEW 2,080건을 공식 정보화사업·조달분류·과업첨부/제목 재검토: 상세 문서 우선 확인 신호 227건. 규칙 순위이지 수행 가능/법적 적격 판정 아님. `G2B-R26BK01763641-000` 학습경험플랫폼(LXP) 구축 용역이 기존 REVIEW에서 발견됨.
- Windows 전용 venv Python unittest **102 PASS**, Node JS syntax **PASS**. 실제 2,223개 공고의 **별도 JSON 사본**과 포트 8766으로 배치 1+3건, Chrome UI로 1건 추가 E2E: 총 batch 성공 7/실패 0/대기 136 (기존 후보 성공 1건 포함). 사본 이력 건수/공고 건수 보존.
- 본문/키/회사 운영자료 외부 전송 없음. 기존 8765 사용 데이터는 배치 처리하지 않았으며, 실제 전체 추출 완료를 주장하지 않는다. 독립 최종 검수·사용자 UI 승인·main 병합은 여전히 게이트.
- 구현 설계: `docs/design/RFP_RESUMABLE_BATCH_2026-10-11.md`; 테스트: `local_app/test_rfp_batch.py`, `test_procurement_discovery.py`.

## 2026-10-11 부서 비식별 인력·급여가정 원가 연계

- 사용자 요청에 따라 실명 없이 코드로 관리하는 로컬 비공개 workforce.json을 새로 도입. 실제 소속/등급/기술 배정과 가정 단가는 개인 PC에만 저장하며 공개 저장소에는 스키마·구현·합성 테스트만 기록한다.
- 직무별 등급 단가를 기존 operations.json의 직무별 1MM 원가 형태와 연결할 수 있게 했고, 가용 MM=null을 0과 구분하도록 원가 계산기를 개선했다. 인력 코드 자체로 입찰 참가자격/개별 기술 적합성을 확정하지 않는다.
- /api/workforce 읽기 경계와 수집관리 화면 로컬 프로필 목록 연결. 기존 공고 JSON/참여 결정/실제 자료는 조회·로컬 인력 등록 중 변경하지 않는다.
- 검증 근거, CI/PR, 독립 검수·UX 승인 상태는 이후 확인해 기록한다. RFP 배치의 크로스프로세스 경합 미해결 및 main 병합 HOLD 유지.

### 2026-10-11 비식별 인력 최종 의미 검증 보완

- 독립 Codex 첫/두번째 검토에서 인력 필드의 자유서술·기술 검증근거·전체 급여 원가 오인·급여 미정 이익 노출 위험 확인, 허용 담당분야·집계 기본 API+CSRF 상세 조회·명시적 원가 basis·가용 미정/급여만 반영한 경우 이익 null로 조치.
- 실제 소속 및 개인 명단은 비공개 로컬 workforce.json과 operations.json에만 존재, 공개 repo에는 코드·범용 분류·합성 테스트만 위치. 원본 dashboard/cases 체크섬 보존.
- Windows Python unittest 115 PASS, JS 구문 PASS, 실제 로컬 읽기 전용 HTTP smoke PASS(격리 포트). 후속 CI/최종 독립 리뷰 상태는 별도 확인 필요.
- 기존 8765 실행 인스턴스 재시작/적용은 하지 않았으며, 재시작·인력 입력 승인 및 기존 RFP 크로스프로세스 원자성 문제와 사용자 UI 검수 전에 Draft/main 병합 금지.

- 3차 독립 코드 검토 후 로컬 공통 운영정보의 새 직무 MM=0 오류를 미정(null)으로 수정하고, 개인별 인력 상세 조회는 기본 비활성+명시적 단일 사용자 개발 모드에서만 허용. 마지막 Windows unittest 116 PASS, JavaScript 구문 PASS, 실제 로컬 사용자 데이터 smoke 및 dashboard/cases 체크섬 보존 확인. Draft/main HOLD 유지.

## 2026-10-11 RFP 인력요건 후보 추출 개발

- 공식 문서 excerpt/구형 rfp_text에서 역할·내부 초중고급·숫자+명 패턴의 보수적 후보만 검출. 문서 SHA-256/원문 발췌/상태/불확실성 포함, 여러 자격·직무 복합 표현은 확인대기.
- GET /api/dashboard/staffing?id=... 조회 전용으로 실제 로컬 workforce.json 역할·등급 *집계*와만 비교. 개인 식별자/개별 급여/실제 기술 반환 금지, 법정 기술자 등급과 내부 초중고급 동일시 금지, 적격·부족·수익 결과는 UNVERIFIED.
- 실제 원본 공식 공고 수집/판단·RFP 배치 저장은 수정하지 않는다. 8765 서버 적용 및 Draft/main 병합 보류.
- 검증/CI/독립 리뷰 상태는 테스트 후 증거를 갱신할 것.

### RFP 인력 2차 독립 검토 finding 및 보완

- 2차 검토 입력 SHA-256 `79a53aaad218762512d95833785c52998270649dc2325b9304e15d1289cc9199`, 동일 격리 Codex CLI / 비공개 JSON 미전송.
- 수용: `2명 이상`을 최소 인원 상태로 분리, 명시적 필수/요구/자격 문맥만 사용, 전체 evidence 중 유효 추출 자료 2개를 선택, 6,000자 내 450줄 컷 제거, 손상된 evidence 배열에 503.
- 문서 증거 생략은 비추출·형식 불일치와 2개 처리 상한을 분리했고, 개인 가용 MM 정보는 계속 외부 API에 미포함.
- 실제 저장 공고에서 본문 추출 성공 5건 중 엄격한 정형 인력요건은 0건. 이 수치는 인력요건 부재를 확정하지 않으며 RFP 원문 확보·표 복원이 후속 병목.
- 최종 코드·브라우저/CI/독립 재검수 상태는 증거 확보 후 갱신. Draft PR 유지 및 main 병합 보류.

- 인력요건 재검수 보완 이후 Windows 전체 unittest 134 PASS, Node 구문 검사 PASS; 실제 공식 공고 2,223건 read-only 스캔(본문 성공 5건, 정형 인력요건 자동 후보 0건)·dashboard 원본 체크섬 보존 PASS. 추출 누락 가능성으로 인원 적격/부적격은 여전히 UNVERIFIED. 최종 CI/독립 코드 재검수/사용자 UX 승인 및 원본 RFP 작업 병목은 지속 추적.

- 별도 합성 폴더/포트 8768에서 headless Chrome CDP 검증: 공식 목록 연결 → 공고 상세 요구사항 탭 → '인력 요건 후보 확인' 클릭 → 개발자/분석가 2건·문서 해시/원문 증거 표시 PASS, 해당 합성 dashboard 체크섬 불변 PASS. 원래 사용자 8765 인스턴스는 미수정. 최종 사용자 UI 승인과 실제 RFP 요건 정확도 검증은 미완료.

### 인력 요구 RFP 3차 독립 리뷰 지적 처리

- 3차 독립 Codex 검토 입력 SHA256: `83af92e39b9154ad7c0d099d541f13338a268d82656086e4c4bddbb6365c286b` (공개 diff, 비공개 JSON 미전송).
- HIGH 부정/자율 구성 문구를 필수 인력으로 오인 위험 → 부정 문장 발견 시 필수 문맥 중단.
- MEDIUM 100명 이상 정규식 누락 → 최대 네 자리까지 인식, 대규모 표기는 별도 검토.
- MEDIUM 해시 미기록/오류 시 정상 본문 누락 → 본문·해시 상태 분리.
- LOW PDF 페이지/표 근거가 없는 문서명 표시 → 저장 발췌 행 번호와 문서 식별 해시 제공, 원본 페이지 미확인으로 표기.
- TEST 원본 사례 보호 근거 부족 → dashboard/cases 모두 바이트 불변 테스트 추가.
- 3차 보완 이후 독립 코드 재검수/CI는 별도 확인 필요, main 병합 HOLD 유지.

### 2026-10-11 인력요건 검수 경계 보완

- 독립 Codex 검수에서 필수 인원 누락/비필수 인원 오탐 반례 발견 및 수정: 역할별 부정, `N명 이상`, 자격증·면허 면제 문맥 분리. 코드/테스트는 공개 대상, 실제 회사 인력/원본 공고는 개인 PC에만 유지.
- 규칙 기반 RFP 후보 추출의 문장 의미 정확도는 미확정. 법적 참가자격·실제 투입가능성·이익 추정 결과는 계속 UNVERIFIED. 최종 독립 코드 보안 검수 및 UI 승인/main 병합 보류.
- 전체 unittest/브라우저/공고 체크섬 검증의 마지막 결과는 확인 후 기록.

- 인력요건 1단계 독립 반복 검수에서는 부정·면제 문맥 관련 반례가 연속 발견됐다. 마지막 `자율 구성(자격증 필요 없음)` 사례도 재현·수정 후 해당 단위 테스트 PASS. 독립 무결점 승인 여부는 미확정, GitHub 최신 수정본 푸시/8765 적용/main 병합 모두 미수행.

### 2026-10-12 인력요건 기능 독립 검수 완료(한정)

- 독립 Codex API/UI/개인정보 경계 PASS, 파서 결함 검출·수정·회귀 후 7개 유형 재검수 PASS. 세부 근거 `docs/reviews/STAFFING_RFP_REVIEW_2026-10-11.md`.
- 인력요건 예비 추출 기능 범위는 `REVIEWED`로 판정하되 법적 적격·실제 가용 MM·원본 RFP 전체 의미·정정 등은 `UNVERIFIED`. 전체 저장소 `RELEASED` 아님.
- PC Python unittest **150 PASS**, JS 문법 PASS, Git diff whitespace PASS, 합성 Chrome 사용자 흐름 및 사본 불변 PASS(재실행). 최초 Chrome 새 프로필의 화면 로딩 실패는 UI cold-start 위험으로 별도 기록.
- 로컬 원본 공식 공고 2,223건 중 추출 성공 5건의 정형 인력요건 자동 후보 0건, dashboard checksum 보존. 본문 미확보가 후속 사업 적합도 분석의 가장 큰 병목.
- 최신 로컬 수정분의 GitHub 푸시, 운영 포트 8765 적용, main 병합 **미수행**. Draft PR #1 개발 브랜치에서 다음 단계 진행.

- **인력요건 기능 최신 로컬본 독립 검수 최종 결론:** API/UI/비공개 집계 경계 PASS, 파서 수정 10유형 독립 Codex PASS (입력 SHA-256 `87ff93415c4e3bb5b67367c72f5c09229e2234efdce83d17719009334ff433ed`). Python 전체 150 PASS, 합성 Chrome 버튼 흐름 및 데이터 불변 PASS(재실행), 개인 PC 실제 공고 2,223건 원본 체크섬 불변. 이 기능만 `REVIEWED`; 사용자의 실제 인력 법적 자격, 전체 RFP 정확도, 전체 앱 운영 검증은 아직 `UNVERIFIED`. GitHub 최신 푸시/운영 8765 변경/main 병합 미수행.

## 2026-10-12 RFP JSON 다중 프로세스 경합 수정

- 진단: 기존 `server.py`의 `LOCK`은 프로세스 내부만 보호해 2개 독립 Python 프로세스의 `dashboard.json` read-modify-write 경합에서 늦게 저장한 프로세스가 다른 변경을 덮어쓸 수 있었다. `persist()`의 `os.replace`는 파일 손상 방지이지 유실 갱신 보호가 아니었다.
- 수정: `json_transaction.py`에서 OS 파일 잠금을 도입하여 server/dashboard API와 RFP Manager가 공통 JSON 트랜잭션을 수행한다. 별도 RFP worker lease는 다중 프로세스 중복 배치를 차단하고 다른 인스턴스의 pause를 확인한다. 공식 재수집 시 상세 RFP 첨부 보존도 추가.
- 증거: Windows 합성 별도 프로세스 동시 업데이트, lock timeout·프로세스 강제 종료, 중복 worker·pause, URL 합치기 테스트 PASS. 전체 Python/Node/독립 검수/CI는 각 최신 결과 확인 후 기록하며, 실제 공고 원본 및 인력자료 변경 금지.
- 개발 브랜치 Draft PR 유지, main 병합 및 기존 사용자 포트 8765 서버 적용 금지. 파일 잠금은 동일 로컬 파일시스템의 협력 프로세스에 한정. 불변조건 검증 후 본문 확보 작업 확대.

### 2026-10-12 RFP 배치 JSON 다중 프로세스 충돌 수정

- `json_transaction.py`: Windows `msvcrt` / POSIX `flock` 파일 잠금과 동일 프로세스의 `threading.Lock`을 중첩해 `dashboard.json` read-modify-write 충돌 차단. OS가 종료된 배치의 수명 잠금은 자동 해제되며 잠금 표식 파일은 보존한다.
- `rfp_batch.py`: 배치 중복 시작 방지 `.rfp-batch-worker.lock`, Thread.start 실패 시 PAUSED 복구, 다른 관리자 일시중지 반영(현재 처리 1건 완료 후 중단), 최신 문서 서명 비교 후 저장.
- `server.py`: 대시보드 변경 POST 경로에서 동일 트랜잭션을 사용하고 잠금 시간 초과를 로컬 HTTP 503으로 안전 처리.
- `dashboard_backend.py`: 새 공고 재수집이 과거 공식 상세 첨부/RFP/의사결정 이력을 덮어쓰지 않도록 기존 첨부 병합.
- 대상 검증: 임시 합성 JSON에서 Windows의 두 실제 Python 프로세스 동시 저장, 같은 프로세스의 서로 다른 Manager 중복 시작, 배치 수명 잠금, 비정상 종료·일시중지·재개, 파일 보존. 실제 2,223건 운영 대시보드 직접 쓰기 미수행.
- 독립 AGY print 120초 제한으로 출력 미확인(검수 부채), Codex 독립 검수 지적 중 실제 Thread.start 결함 수정, 일시중지 1건 완료는 설계 계약에 부합. 새 최종 검수와 CI 결과는 별도 확인 필요. Draft PR 유지, main 병합·운영 적용 금지.

- **RFP 배치 JSON 충돌 수정 로컬 검증 결과:** Windows Python 전체 161 PASS, 실제 두 Python 프로세스·배치 작업자 수명 잠금·중복 Manager·스레드 실패·일시중지·기존 결정/첨부 보존 합성 검증. JS/Git diff 체크 PASS. 사용자 공고 원본 2,223건 SHA 체크 보존.
- Codex 독립 재검수는 협조 프로세스 조건에서 핵심 lost-update/worker-singleton 통과로 보되, 악성 잠금파일 교체·정전 내구성은 범위 밖/미보장. AGY 최종 출력은 timeout으로 미확보. `REVIEWED`/main 병합/운영 8765 적용 금지. 근거 `docs/reviews/RFP_JSON_LOCK_REVIEW_2026-10-12.md`.

### 2026-10-12 RFP JSON 동시성 수정 최신 검증 확정

- **실제 Windows Python 전체 회귀 166 PASS**, JS 문법 및 Git diff 검사 PASS. 이는 합성 데이터와 임시 로컬 HTTP 테스트의 결과이며 실제 사용자 원본 JSON의 쓰기 테스트가 아니다.
- RFP batch/legacy enrich의 동일 JSON 충돌을 공통 프로세스 파일 잠금과 최신 근거 서명 비교로 보호하고, 다른 서버 작업자 수명 잠금·부모 프로세스 종료 후 IN_PROGRESS 복구·실패만 명시적 재시도·기존 PENDING의 정상 재개·최신 인력/원문/판단 보존을 테스트했다.
- 독립 Codex 첫/후속 검수 중 근거가 있는 stale enrich·FAILED ledger·완료 상태·일시중지 worker 경합 지적을 수정했다. 최종 지적 중 FAILED 혼재 시 미처리 PENDING까지 전면 재개 금지는 기존 명세와 충돌하여 명시적 재개 테스트로 기각했다. AGY/Gemini 결과는 미확보이므로 전체 독립 최종 승인 완료로 과장하지 않는다.
- 향후 실제 운영 적용 전에는 현행 8765 로컬 서버를 안전하게 재시작하여 모든 writer가 공통 파일 잠금을 사용하는지 확인하고, 복구용 버전 백업·강제 종료/전원 장애 검증을 별도 수행해야 한다.

## 2026-10-12 공식 공고 읽기 전용 우선검토 순위
- GET /api/dashboard/recommendations: 전체 공식 공고와 현재 부서 관심분야를 읽고, 현재 기한 조건에 맞는 상세검토 후보 상위 30건을 추천 순위로 표시. 분석 모드는 RULE_BASED_READ_ONLY. 실제 AI/법적 참가자격/기술 수행능력/가용인력/수익성 검증 상태는 UNVERIFIED.
- /decision-preview 기존 수집관리 화면에 순위, 공식 분류/RFP 발췌 근거유형, 원문 미확인사항, 공고 상세 확인 버튼 연결. 비공개 인력·급여·RFP 본문·API 키는 추천 응답에 포함되지 않음.
- 설계·다음 단계: docs/design/RFP_RECOMMENDATION_SLICE_2026-10-12.md. 이 기능은 자동 Bid/No-Bid 결정이 아니라 상세검토 우선순위이다.

- [2026-10-12 추천 웹] 2회 독립 Codex 지적 이후 URL/파일명 identity 검증·취소 대소문자·선택 필드 안전성 보완, Chrome 합성 추천 목록/상세 이동 PASS. 개인 PC 실제 공고 2,223건을 read-only 평가해 현행 검토 순위 후보 111건, 상위 30건, 원문 SHA 불변; 운영 8765 새 코드 적용/실제 입찰 추천 여부는 별도 검증 필요.

## 2026-10-12 공식 RFP 원문 확보 병목 확인

- **읽기 전용** /api/dashboard/rfp-coverage 및 /decision-preview 원문 확보 현황 패널 구현. 개인 인력/원가/공고 내용·첨부 URL은 응답에 포함하지 않는다.
- 실제 로컬 저장 공고 2,223건 중 현재 선택 부서 CANDIDATE 143건(마감 전 110건). 전체 후보 저장 본문 39/공식 지원 링크 대기 87/미지원 4/링크 없음 13. 마감 전: 저장 본문 38/대기 70/미지원 1/링크 없음 1. 기록상 실패 0은 다운로드 장애가 없다는 뜻이 아니라 저장된 실패 상태가 0건이라는 뜻이다.
- 실제 dashboard.json, department_profile.json SHA 비교 동일. 새 RFP 다운로드와 운영 8765 서버 변경은 하지 않았다.
- Windows Python 전체 unittest 196건 PASS, 신규 진단 테스트 3건 PASS, Node JS 문법 및 git diff --check PASS. 사용자 실제 데이터 불변 확인. 원래 8765 운영 서버 미변경, GitHub CI는 푸시 후 확인.

## 2026-10-12 마감 전 공식 RFP 70건 격리 확보 검증

- Windows 개인 PC의 별도 비공개 stage에서 공식 원문 대기 70건을 25/25/20건으로 직렬 처리, **DONE 70 / FAILED 0 / PENDING 0**.
- stage의 마감 전 CANDIDATE 110건 중 추출본문 확보 **38 -> 108**, 지원 형식 미비 1건, 공식 링크 없음 1건. 기존 공고 2,223건과 사용자 결정·이력 보존.
- 신규 추출 evidence 기록 127건 중 발췌 6,000자 제한을 초과한 문서 **96건**, 파서 경고 **14건**. 문서 전체 표·각주·정정 정확성 및 AI 의미 분석은 미검증.
- 사용자 운영 dashboard/rfp_batch/cases/operations/workforce/(존재 시)department_profile 원본 SHA-256 전후 동일. 8765 운영 서버·원본 자료·main 미변경.
- 본 작업은 공개 실자료를 이용한 **격리 수집 검증**이며 운영 적용·서비스 RELEASED 또는 실제 입찰 가능 확정을 뜻하지 않는다.
- 상세 실증: [RFP 70건 격리 배치 보고](docs/reviews/RFP_ACTIVE_70_ISOLATED_E2E_2026-10-12.md).

## 2026-10-12 신규 공식 RFP 전체 텍스트 로컬 청크 보존 - 한정 검증

- 기존 문서당 excerpt 최대 6,000자는 UI 호환으로 유지, 새 배치가 추출한 텍스트 최대 44,000자는 비공개 `rfp_fulltext` 청크(JSON)로 보관. 메타데이터 ref만 기본 대시보드 반환.
- CPython 3.12 로컬 200 unittest PASS. 실제 공개 공식 RFP 1건의 19,779자/5청크 및 추가 문서 3,823자/1청크 격리 수집 성공, 기존 사용자 JSON/판단·이력 SHA-256 불변.
- 44,000자 초과 원문/표/각주/파서 OCR 완전성, 이미 추출된 70건 backfill, 파일 캐시 복구, 외부 AI 의미·법적 자격 분석, 운영 8765 적용/독립 최종 검수/main 병합은 미완료.
- [설계](docs/design/RFP_FULLTEXT_CHUNKS_2026-10-12.md), [실증](docs/reviews/RFP_FULLTEXT_SINGLE_E2E_2026-10-12.md).

## 2026-10-12 공식 RFP 70개 공고 / 127개 문서 청크 소급 이관

- Windows 개인 PC 별도 격리 stage에서 과거 공식 RFP 추출 evidence **127개 전부** 원본 바이너리 SHA-256과 기존 발췌·파서 문자 수 재검증 뒤 청크 참조 보강. 3/25/25/25/25/24개로 단계 실행, DONE 127 / 불일치·다운로드 오류 0 / pending 0.
- 문서 증거 127개, 보존 청크 578개, content-addressed sidecar 124파일, 미참조 0파일. 예전 6,000자 발췌를 넘은 문서 96개는 추가 추출 본문을 보관했고 14개는 파서 44,000자 상한으로 원문 전체 보존 미확인.
- 공고 2,223건 기존 업무필드/사람 판단·이력/RFP 발췌 불변. 사용자 원본 및 이전 별도 검증 사본 SHA 불변. 운영 8765 서버와 main 변경 없음.
- 합성 신규 회귀 10개 포함 개인 PC Python unittest **210 PASS**. Codex 1차 코드 지적의 metadata 임의 덮어쓰기·캐시 검증 부족·동시 worker 보호 보완. AGY 최종 검수 출력은 시간 제한으로 확보하지 못하여 승인/릴리스 아님.
- [설계](docs/design/RFP_BACKFILL_VERIFIED_2026-10-12.md), [실증·잔여 위험](docs/reviews/RFP_BACKFILL_VERIFIED_E2E_2026-10-12.md).


## 2026-10-13 로컬 RFP 배포 안전성 보강 (개발 브랜치)

Codex NO_GO 지적의 4개 범위에 대해 서버 수명 독점 잠금, SQLite 동기식 PREPARED/COMPLETED 복구 의도, Windows 파일교체 MoveFileExW WRITE_THROUGH 및 POSIX 디렉터리 fsync, Windows CreateFileW 디렉터리/상위경로 핸들(GENERIC_READ, FILE_SHARE_DELETE 비허용, OPEN_REPARSE_POINT)을 유지해 경로 이름 변경을 차단하고 reparse 검사·파일 동일성도 재확인, 중단된 부분 백업의 원본 SHA 확인 후 재개 절차를 추가했습니다. 복구 의도 SQLite는 `PRAGMA synchronous=FULL`과 DELETE 저널을 사용합니다. 원래 `.rfp-release-transaction.json`도 유지합니다. SQLite가 PREPARED인 동안 서버 시작과 요청을 차단합니다. 로컬 서버가 실행 중이면 오프라인 배포/롤백/복구 도구는 별도 OS 프로세스 잠금 충돌로 거부됩니다.

배포 작업은 로컬 Windows 사용자 데이터와 별도 백업 경로가 있어야 하며 서버 종료 뒤 실행합니다. 부분 백업 재개는 `.backup-intent.json`의 기존 운영 JSON 해시가 동일하고 알 수 없는 파일이 없는 경우만 허용합니다. `recover`는 텍스트 저널이 사라졌어도 SQLite PREPARED 의도로부터 두 파일을 검증된 세대로 복구합니다. 버전이 다른 JSON은 제공하지 않고 서버가 실패하도록 설정했습니다.

**제한:** Windows 파일시스템·장치의 물리적 전원 장애를 여기서 직접 시험하거나 완전한 영속성을 보장하지는 않습니다. Microsoft MoveFileExW의 WRITE_THROUGH는 파일 이동을 플러시하지만, 모든 같은 볼륨 메타데이터 영속성의 증명은 아닙니다. SQLite FULL의 내구성도 OS/디스크의 fsync/FlushFileBuffers 계약에 의존합니다. 실제 종료 및 완전한 검수 전까지 공개 운영 배포와 main 통합은 별도 승인 대상입니다.

실행: `python -m unittest discover -s local_app -p 'test_*.py'` 및 독립 Codex 읽기 전용 재검수. 실제 사용 데이터의 손상·이력 보존은 테스트 폴더와 별도 원본 해시 점검으로 확인합니다.


## 2026-10-13 로컬 RFP 배포 4건 수정·Codex 재재검수

- 수정 커밋 d8b7007, 4077ff5. Windows Python 전체 227 PASS, 디렉터리 이름 변경 실 OS 거부 PASS. 독립 Codex 1차 NO_GO(경로 교체 경쟁), Windows CreateFileW 디렉터리 핀 보완 후 2차 범위 한정 GO(단일 신뢰 사용자, localhost 오프라인 배포).
- 서버 수명 잠금, SQLite FULL/PREPARED 복구 의도, Windows WRITE_THROUGH 및 해시 세대 검증, junction/reparse 경로 검사·디렉터리 핸들 유지, 중단된 백업 준비 재개를 구현. 상세: docs/reviews/LOCAL_RFP_RELEASE_REVIEW_2026-10-13.md.
- 개인 PC의 기존 8765 실행 코드는 아직 교체하지 않았으며 실사용 JSON에 대한 신규 배포/롤백 없음. main 및 외부 배포 별도 보류. 물리 전원 장애 및 동일 계정 악성 프로세스 위협은 범위 밖.


## 2026-10-13 검수 승인 코드 로컬 8765 실배포·웹 검증
- 개인 PC 운영 코드를 c0a1115 -> fe499d8 Fast-forward 후 서버 재시작. 원본 데이터는 이미 70건 RFP가 반영된 상태라 중복 적용하지 않음.
- 원본의 JSON 6건, RFP sidecar 124건을 서버 중지 상태로 백업하여 SHA-256 130/130 동일 확인. 서버 기동·브라우저 테스트 후에도 130/130 원본 동일.
- localhost GET 9/9 HTTP 200, 실제 Chrome: 공식 2,223건 목록 바인딩·상세 클릭, 수집관리 RFP 표시, 추천·진단 API, 390px 레이아웃 PASS.
- 실제 운영 원본 복사본에서 SQLite PREPARED + 텍스트 저널 누락 + JSON 1개 세대 불일치를 재현, recover의 양쪽 원본 2/2 SHA 복구 PASS. 운영 자료에는 변경 없음.
- 현 RFP 원장 DONE 109 / PENDING 34 / FAILED 0 (PAUSED), 마감 전 후보 106 중 원문 EXTRACTED 104, 미지원 1, 링크 없음 1. 새로운 분석/추천 결과가 아니라 현재 저장 공고 상태임.
- 상세 검증: docs/reviews/LOCAL_RUNTIME_VERIFY_2026-10-13.md. 로컬 기능 확인 후 외부 공개 배포 및 main 병합은 여전히 미실행.


## 2026-10-13 다음 구현: 로컬 공식 공고 예약 수집 1단계
- 신규 `local_app/scheduled_collection.py`에서 사용자 DPAPI 키로 과거 7개 24시간 구간을 오래된 순으로 조회, 공고 ID 중복은 최신 데이터 우선, 기존 사람 판단·RFP 본문·이력 보존. API 전체 일자 성공 후에만 OS 잠금 하에 최신 JSON 병합.
- 기존 조달청 API 수집 로직의 페이지 totalCount 변동/누락 검증을 강화함. 원문 분류/입찰 가능 확정과 자동 RFP 새로 추출 기능은 없음.
- Windows 작업 스케줄러 등록 스크립트(`scripts/install_local_collection_schedule.ps1`) 및 합성 실패·동시 수정·보존·비밀키 출력 금지 테스트를 추가. 실제 설치/운영 수집 및 Codex 최종 검수는 검증 실행 결과가 확보된 뒤 별도로 기록해야 함.


## 2026-10-13 자동 공식 공고 수집 1단계 완료·잔여 위험
- Windows 전체 unittest 240 PASS, Codex 독립 재검수 GO (개인 PC 단일 사용자), GitHub 코드 CI 성공. 실제 공식 API 최근 1일 dry-run 820건, 최근 7일 dry-run 3,053건.
- 첫 실제 7일 저장 API 오류로 안전 중단, 이후 1일 실제 저장 826건 성공. 공고 2,223 -> 3,049건, 기존 사용자 판단/원문 필드 13종 및 이력 불변, 다른 JSON 4개 SHA 동일, Chrome UI PASS.
- Windows Task Scheduler `PublicBidAgent-OfficialCollection` 등록 Ready, 다음 실행 2026-10-14 09:00. 현재 Task LastRun은 미실행. 등록 사용자 SID 비교 보완.
- 자동 7일 예약 작업 실사용 성공과 API 안정성은 미확인. 기존 공고의 뒤늦은 정정/취소 상세 갱신과 RFP 근거 stale 전파는 미구현. 보고서: docs/reviews/AUTO_G2B_COLLECTION_2026-10-13.md.


## 2026-10-13 공식 공고 정정·취소 반영 단위
- `local_app/notice_lifecycle.py`: 공식 공고번호/숫자 차수로 같은 원공고의 후속 차수 연결, 최신 공식 종류가 취소면 취소 상태, 이전 차수 SUPERSEDED, 중요 메타 변경 시 기추출 RFP STALE 표시. 사람 결정·증거·이력은 보존.
- `local_app/dashboard_backend.py`의 실제/예약 수집 병합 이후 상태 재평가, `recommendations.py`의 부적합 최신성 추천 차단, `frontend/public/dashboard-live.js`의 상세 표시. `notice_lifecycle_cli.py`는 기존 데이터 preview/apply를 API 호출 없이 수행.
- 7일 API 오류 분석은 사용자 명시 제외. 다음 개발 방향은 이 기능의 검증 결과를 보고받은 뒤 사용자가 결정.


## 2026-10-13 정정·취소 Codex NO_GO 지적 보완
- 1차 Codex: P1 취소가 이후 일반공고 응답으로 해제될 위험, P1 차수 `00` vs `000` 별도 저장·취소 손실, P2 기존 STALE 재추출 후 자동 회복 부재, P2 기본 목록 구차수 노출 지적.
- P1 수정: 동일 숫자 차수는 기존 공식 저장 ID에 병합, 동일 차수 취소는 최신 일반공고 응답에도 유지, 기존의 동일 차수 중복 레코드에 취소가 있으면 모두 추천 제외. 기본 목록에서 SUPERSEDED/CANCELLED/REVIEW 제외(전체 보기는 유지).
- P2 STALE 복구 자동 전이는 설계 범위 밖으로 명시: 공식 새 RFP 검증 전까지 추천 보류, 향후 별도 판단 이후 구현. 정정·취소/기초 원문·판단 이력 보존 우선.


## 2026-10-13 공식 정정·취소 최종 로컬 운영 적용
- 코드 23ff078 CI success, Windows 전체 258 PASS, Codex 재재검수 GO(신뢰 단일 사용자 localhost). 이전 NO_GO 취소 sticky·차수 표기 통합 2건 보완.
- 기존 3,049건 원본에 정정/취소 수명주기만 직접 반영: CURRENT 2,653 / CANCELLED 167 / SUPERSEDED 229, RFP 재검증 STALE 8. 운영 반영 전 JSON 6개와 RFP sidecar 124개 백업, 변경 후 공고 ID 3,049/3,049, 과거 판단·RFP·이력 불변, 다른 JSON 5/5 및 캐시 124/124 SHA 일치.
- 8765 서버 재기동, 실제 Chrome 목록·상세·수집관리, API 추천 결과 검증 완료: 추천 내 CANCELLED/SUPERSEDED/STALE 0. 상세: docs/reviews/OFFICIAL_AMEND_CANCEL_LOCAL_VERIFY_2026-10-13.md.
- 7일 API 오류 분석은 사용자 요청에 따라 수행하지 않았으며 다음 기능 방향은 사용자가 결정. STALE 자동 재검증/공식 변경이력 별도 API 재조회/다른 공고번호 재공고 매핑은 미구현.


## 2026-10-13 RFP 요건 구조화 1단계 (진행 중, 검증 상태는 최신 보고로 확인)
- `rfp_requirements.py`는 공고·공식 첨부 identity·원본 SHA·기존 private fulltext 청크를 검증하고 8개 요건 분야의 제한된 표현 후보와 문자 위치를 JSON으로 제공. `server.py` 로컬 GET, `frontend/public/dashboard-live.js` 수동 조회 UI 연동. 원본 사용자 판단/공고 JSON 쓰기 없음.
- 실제 운영 데이터 read-only 샘플: 검증 가능 청크를 가진 현행 후보 66건, 그중 20건의 8개 분야 표현 후보 561건, 실패/0건 0건, 일부 텍스트 절단 표본 4건. 본문/개인자료는 repo에 기록하지 않음.
- 8개 STALE 공고는 분석 보류. 기존 7일 수집 API 오류 분석 제외. 원본 페이지 번호/필수·선택/입찰 적격/AI 의미 추출은 이 스프린트 미구현.


## 2026-10-14 사용자 결정 원본 문서화 / RFP Stage 1 소스 검증
- **[DECISIONS.md](DECISIONS.md)를 사용자 확정 결정의 정식 진입점으로 지정**. `AGENTS.md`, `AI_CONTEXT.md`, `README.md`, `local_app/README.md`, `TASKS.md`에서 참조. 이전에 남은 2,223건/자동수집 미구현 등의 날짜별 과거 문구와 실제 현재 상황을 구분하도록 현재 컨텍스트 정리.
- RFP 구조화 1단계 `rfp_requirements.py` 및 로컬 GET/UI 수동 조회 기능 소스 작성. Windows 3.12 전체 회귀 274 PASS, 읽기 전용 Codex NO_GO 2회 수정 후 **3차 GO** (신뢰 단일 사용자 localhost). 실제 RFP 20건 비식별 샘플의 텍스트 표현 후보 561건(일부 문서 절단 4건). `docs/reviews/RFP_REQUIREMENTS_CODEX_REVIEW_2026-10-14.md` 참고.
- **미완료:** 최신 소스를 실제 8765 로컬 서버에 재시작 반영, Chrome 새 버튼 검증 및 40개 기존 private JSON+124개 RFP sidecar SHA 재대조. 이 증거 확보 전에는 Stage 1을 `LOCAL_APPLIED`/사용자 UI 승인으로 표시하지 않음. 다음 구현 단계는 사용자 선택 후 진행. 기존 7일 API 실패 원인 분석은 D-10에 따라 제외.
