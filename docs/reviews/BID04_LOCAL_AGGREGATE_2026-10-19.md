# BID-04 로컬 실제 공고 집계 검증

> 이 문서는 기존 CLI 세션 종료 시점의 NO_GO 기록이다. 이후 직접 사용자 승인과 정상 환경의 화면/API 포함 재검증·독립 GO는 [최신 재개 기록](BID04_UI_DEPLOY_2026-10-19.md)을 따른다. 이전 실패/증거는 보존한다.

- 상태: **VERIFIED (로컬 코드/전수 회귀) / 독립 최종 VERDICT: NO_GO / 완료 게이트 BLOCKED**. DONE 아님, commit/push 없음.
- 시작: `feat/sprint1-search-demo`, `648ca0a`. 추적 파일 깨끗함, 사용자 작업 파일만 있었고 요청한 BID04_TASK_LOCAL.txt는 제거했다. 작업 중 새로 나타난 별도 승인 메모는 사용자 대화의 main/배포 금지 지시를 대체하지 않으며 변경/커밋하지 않는다.
- 정책: CONTROL 및 handbook 8개는 이전 GitHub main 검증 로컬 사본을 읽었다. 현재 GitHub 원격 원본 최신성 재확인은 OS 소켓 접근 거부로 BLOCKED. 원본을 새로 확인했다고 주장하지 않는다. AGENTS/D-20/현재 상태·백로그/관련 로컬 요구·설계·테스트 기준 적용.
- 변경: [설계 계약](../design/BID04_LOCAL_AGGREGATE_2026-10-19.md), `bid_now_audit.py` 순수 집계, `bid_now_audit_cli.py` 읽기 전용 실행, 합성 21 tests, Windows workflow 연결. 기존 HTTP/UI/수집/저장 기능과 의존성은 유지했다.

## 실제 자료의 안전한 집계

2026-10-19 **14:36 KST** 로컬 실행. 실제 원문·공고 ID·회사/개인·기술 분포/인원/원가·개별 해시는 출력/검수/문서에 포함하지 않았다. 외부 API·LLM 호출 없음. 과거 5,691건을 현재 수치로 재사용하지 않았다.

| 집계 | 건수 |
| --- | ---: |
| 전체 저장 공고 | 5,718 |
| 활성 검토 / 보류 / identity 무효 | 2,369 / 3,349 / 0 |
| 활성 분야 비교 불명 | 2,369 |
| 활성 등록기한 검토 위험 | 45 |
| 활성 마감 <=24h / 24~72h / 72h~7d / 이후 | 457 / 601 / 424 / 887 |
| 전체 객체의 마감 경과 / 불명 | 2,347 / 682 |
| 취소 / 구차수 / STALE 신호 | 314 / 514 / 11 |
| 등록기한이 제출마감보다 뒤인 일관성 위험 | 6 |
| 저장 window와 현재 재계산 불일치 | 1,129 |
| 중복 ID / 숫자 차수 모호 / lifecycle 불일치 | 0 / 0 / 0 |
| 실제 법적 적격 미검증 | 5,718 |

위험은 중첩될 수 있다. 저장 window는 시간이 지나면 재계산과 달라질 수 있으므로 불일치를 데이터 손상으로 단정하지 않는다. 기한 역전 6건은 보수적으로 보류했으며 원본을 고치지 않았다. 활성은 저장 상태상 검토 대상이고 공식 최신성/등록/자격/보완 허용/수익은 **UNVERIFIED**다.

결과 **BLOCKED_EVIDENCE**: 부서 분야 설정 누락/형식 미확인, 기술 증빙, MM/원가·운영 근거, 공고별 대조 부족. 실제 설정 원문은 반환하지 않았다. 분야 비교 불명은 미일치/역량 부적합으로 확정하지 않으며 기회는 보존한다. workforce v1은 ASSUMED/UNKNOWN만 허용하므로 기술 증빙을 자동 VERIFIED로 승격하지 않는다.

- 전후 고정 입력 읽기 `STABLE_OBSERVED_READS`, 쓰기 없음. 별도 전후 SHA 검사는 잠금 파일을 제외한 로컬 보호 파일 **393/393 동일**, 변경/삭제/추가 **0**, 읽기 오류 **0**. 해시/파일 목록은 메모리에서만 비교하고 공개하지 않았다. 잠금 파일을 포함한 최초 전체 검사는 고정 BLOCKED_INPUT만 반환하여 정확한 원인은 UNKNOWN이며 전체 보존 PASS로 주장하지 않았다.
- release 상태 **LEGACY_COMPLETED_UNVERIFIED**. 최초 실행은 JSON-only 완료 저널의 과거 SHA 차이로 집계를 차단했다. 기존 정상 수집이 dashboard만 갱신하고 완료 JSON 해시를 갱신하지 않는 공개 코드 근거를 별도 Codex가 검토하여 오차단 설계를 수정했다. 이는 실제 차이 원인 규명이 아니며 현재 세대 무결성·복구 완료를 증명하지 않는다. SQLite COMPLETED 두 파일 검증/PREPARED·손상·sidecar 차단은 그대로 유지했다. 운영 복구·원본 쓰기 없음.

## 실행 검증

환경: 별도 테스트 venv **CPython 3.12.0**, `pip check` PASS, Node **22.14.0**. 운영 Python·패키지·서버를 변경하지 않았다.

| 확인 | 결과 | 명령/한계 |
| --- | --- | --- |
| BID-04 합성 | PASS 21 | 별도 unittest 실행 및 최종 전수 440개 내 같은 21개 모두 PASS |
| 전체 local_app | **PASS 440 / SKIPPED 0** | 최종 5파일 결속, 309.928초, exit0. import/discover 전에 테스트 소유 TemporaryDirectory를 PUBLIC_BID_LOCAL_DATA에 지정. 원시 로그 `bid04-isolated-final-unittest-20261019.log`; 이전 두 중단 실행은 PASS 아님 |
| 감사 / backend | PASS 14 / 11 | `unittest discover -s scripts -p 'test_audit_*.py' -v`, `PYTHONPATH=backend pytest backend/tests -q` |
| Node 계약 | PASS 22 | BID UI/RFP/recommendation/legacy 네 test 파일을 `node --test`로 실행 |
| 프런트엔드 빌드 | PASS | `npm.cmd run build` (PowerShell npm.ps1 실행 정책 거부 후 설치된 npm.cmd 진입점 사용, 정책 변경 없음) |
| 정적/문법/공백 | PASS | check_ui_preview, Node syntax, 새 Python3개 AST 및 최종 git diff --check. 소스 manifest 일치 확인 |
| Chrome 합성 E2E | BLOCKED | Chrome155/Node22.14 기본 sandbox, 시작 시 `Chrome exited (2147483651)`, exit1. 브라우저/기존 UI 소스·보안 설정 변경 없음. PASS 아님 |
| README 동기화 | 동반 수정 확인 / 신규 커밋 검사 NOT RUN | 두 README pending diff 동반 변경 확인. checker 실행은 기존 HEAD648ca0a에 대해 `no application source change in this commit`; 미커밋 소스의 통과로 오인하지 않음 |
| GitHub 원격·새 SHA 두 CI | BLOCKED / NOT RUN | api.github.com:443 OS 소켓 권한 거부. 최종 GO 없는 commit/push 없음 |

첫 합성 실행의 Windows lstat/fstat ctime 불일치가 실제 재현되어 Windows에서는 명시 birthtime을 사용하도록 수정했다. dev/ino/size/mtime 및 전후 바이트 비교는 유지하며 POSIX는 ctime을 사용한다. [Python 3.12 stat 계약](https://docs.python.org/3.12/library/os.html#os.stat_result). 21개 합성 재실행 PASS, 해당 실행은 최종 전체 회귀와 구분한다.

최초 두 전체 회귀는 최종 코드 변경 전/기본 데이터 경로의 격리 누락으로 중단(exit1)했으며 완료 PASS가 아니다. 두 번째 실행의 120초 진단 스택은 기존 `test_rfp_race_safety.py`의 `server.persist` → `tempfile.mkstemp(dir=server.ROOT)`를 확인했다. 그 테스트는 대상 JSON만 임시 경로로 주고 기본 ROOT를 일부 호출에서 복구한다. **INFERRED:** 현재 sandbox의 기본 폴더 쓰기 거부와 Windows tempfile 재시도가 충돌. 제품·권한·timeout/시험 항목을 바꾸지 않고 지원 env를 테스트 전용 임시 폴더로 지정한 최종 전수 실행은 **440 PASS/0 skip/309.928초**로 완료했다. 양쪽 CI에도 runner.temp 기본 경로를 명시했다. 운영 데이터 경로로 지정하지 않으며 원인 확인은 합성 회귀에 한정(D-10/API 조사 아님). Python 전체는 감사14/backend11 포함 **465 PASS**.

## 독립 검수 provenance

- 사전 설계: fresh-context Codex `/root/bid04_design_review`, read-only, 공개 코드·정책·설계만 직접 읽음. 초기 요청은 원요구·제약·정확한 설계 경로 및 기존 소스 근거를 제공했고 예상 finding/결론을 주입하지 않았다. 실제 자료 접근·수정/설치/Git 기록 없음.
- **VERDICT: GO**(설계). 중단 세대 확인 누락 MAJOR를 수용·해결했고, 이후 JSON-only 완료 저널과 SQLite COMPLETED의 구분 오류를 기존 수집 코드 근거로 재검토하여 별도 설계 수정 **GO**. 이전 판정을 구현/릴리스 GO로 대체하지 않는다.
- 최종 구현 독립 검수: fresh-context Codex `/root/bid04_final_readonly`, **VERDICT: NO_GO**. 원요구/고정 소스·정책/실행 로그 위치를 제공했고 원하는 finding/verdict를 주입하지 않았다. 실제 자료·로컬 승인 메모 접근/수정/설치/서버/Git 기록 없음. 순수 AggregateTests **10/10 독립 PASS**, raw log **440 tests /309.928s/OK** 직접 확인, 이전 중단 실행 제외. 검수자가 시작/종료 5개 소스 결속 일치와 diff --check PASS를 확인했다.
- 확인된 **소스 BLOCKER/MAJOR 없음**. 현재 Chrome 시작 실패로 인수 미완료, GitHub 소켓 거부로 원격 정책/브랜치·신규 두 CI 검증 불가를 각각 **인수/외부 검증 BLOCKER**로 판정했다. 부서 증빙은 BLOCKED_EVIDENCE이며 실제 적격/수익 판단 승인 아님. 지적 수용, 미해소 상태를 그대로 유지하고 commit/push/DONE 보류. source-only GO나 이전 BID-03 성공으로 최종 NO_GO를 대체하지 않는다.
- 최종 검수용 고정 소스: audit 함수/CLI/합성 테스트/양쪽 workflow **5개** 파일 bundle SHA256 `a821128f18c2067b5e84d820974f4ed9839516238030efaadf7910c5ec5d853f`. 초기 4파일 결속 뒤 CI의 기본 테스트 경로 격리만 추가하여 재동결, 제품3파일 SHA는 같다. 이는 공개 소스의 결속이며 실제 자료/개별 공고 SHA가 아니다. 원시 로그·소스 manifest는 로컬 임시 공간에만 둔다.

## BLOCKERS 및 재개 조건

1. **EVIDENCE**: 승인된 부서 설정·기술/MM/총원가·출처/확인일/공고별 대조 부족 → 실제 부서 적합·법적 자격/수익 확정 불가. 책임자가 로컬 증빙을 검증해야 하며 Git/AI로 보내지 않는다.
2. **GITHUB_SOCKET_DENIED**: 원격 최신 정책/원격 브랜치·commit/push/두 CI 확인 불가. 정상 권한의 GitHub 연결 복구 후 다시 읽기 전용 확인하고, 최종 GO 및 사용자 게이트 충족 시에만 Git 기록 재개. 현재 네트워크/권한 우회 없음.
3. 최종 회귀 PASS, 독립 최종 **NO_GO**. 사용자 최신 요청대로 **문서 포함 미커밋 유지**, DONE/푸시 금지. 인수/원격 검증이 정상화된 후 같은 변경본·정책/회귀 근거로 별도 Codex 최종 재검수 필요. BID-05 이후 단계·D-10·main·배포·실제 입찰은 진행하지 않는다.
4. **CHROME_STARTUP**: 기본 sandbox Chrome 합성 runner가 시작 중 exit2147483651. 현재 환경 원인 UNKNOWN, 기존 BID-03 성공을 이번 검증의 성공으로 재사용하지 않는다. 동일 보안 설정에서 정상 실행 가능해진 뒤 전체 합성 E2E 재확인, 현재 미완료 게이트 유지.
