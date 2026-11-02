## 2026-11-03 00:57 KST — 스케줄러 Git 소유권 원인 수정, 비동기 작업 실행 중

- 원인 CONFIRMED: 기존 H02 runtime의 .git 소유자가 Administrators여서 Interactive/Limited 사용자 Git이 dubious ownership으로 거부했다. SSH 성공/인증 오류가 아니라 스케줄러 실행 계정과 저장소 소유권 불일치다. 실제 Git stderr로 확인.
- 수정: 동일 일반 사용자 스케줄러에서 public GitHub 원본을 새 `D:\01_git\public-bid-agent-work-h02-user`에 clone하고 검수·CI 완료 SHA `a219b0fe05b3dd041ae2a2c6958e5ad163f8618f`로 detached checkout. clone task exit0, .git owner=TD-KISEOK\\User 확인. safe.directory 예외, ACL/권한/실행 정책 변경 없음.
- `PublicBidAgent-WorkQueue-H02` action/WorkingDirectory와 기존 launcher `D:\Temp\bid-work-h02-worker.ps1`를 새 runtime에 연결. launcher에 Git preflight 로그/실패 exit를 추가. 원래 launcher는 .before-preflight로 보존. 고정 runtime 소스 파일 수정 없음.
- 기존 queue `D:\Temp\bid-work-queue-h02`와 기존 요청 `h02-30-002`를 그대로 사용. 시작 전 기존 worker 없음, job은 request.json만 존재 확인. 새 ID 중복 제출·이전 결과 삭제 없음.
- SSH 시작 요청 종료 이후 별도 연결에서 RUNNING/heartbeat 확인: worker PID19580, 시작 2026-11-03 00:57:05 KST, heartbeat 00:57:25 KST. trusted/candidate 모두 위 a219 전체 SHA. 스케줄러 Git preflight도 같은 SHA 반환. **최종 result는 아직 없으므로 PASS/비동기 인수 완료로 표시하지 않는다.**
- 독립 Work 복구 설계 검수 GO(전달된 증거 기준, 별도 원격 재실행 아님). 동일 구현 SHA 기존 CI 3종 SUCCESS 재확인. 운영 clone/서버/사용자 데이터는 변경하지 않음.
- 다음 회차: **002 result.json부터 회수**하고 ID/SHA/exit/cleanup/필수 결과 확인. 실행 중이면 중복 기동 금지. 성공하면 새 runtime을 계속 사용하고 H02-2 local/backend/frontend 검사 연결로 이동. 실패하면 원인별 수정. 이전 Administrators 소유 runtime을 다시 스케줄러에 연결하지 않는다. 최초 Work 후속 구현·GitHub 기록 경로 확인과 전체 제품 DONE은 별개다.

## 2026-11-03 H02 검사 병합·노트북 예약 실행 인수

- PR #3 main 병합 완료: merge `cca76ffa8200cbb0e6eb7612828e8738cbf79062`, 구현 `a219b0fe05b3dd041ae2a2c6958e5ad163f8618f`. 날짜/분류16+감사14를 기존 adapter에 연결하고 packaging 개발 의존성 누락을 수정. 독립 Work 검수 GO.
- 동일 구현 SHA CI 3종 SUCCESS: Development harness 41466990325, Sprint1 41466990611, Windows synthetic local acceptance 41466990407. 과거 Chrome 시작 timeout 원인까지 해결됐다고 해석하지 않음.
- Windows 별도 개발 venv의 `h02-30-001` 실제 결과: SUCCEEDED, exit0, cleanup=true, report_present=true, LOCAL_VERIFIED 2개. run ID `9c7af909-8d52-42f2-a138-1e7652de7de9`, 완료 2026-11-03 00:03:27 KST. 이는 foreground 검증이며 새 스케줄러 비동기 인수 증거가 아님. missing_checks=backend_regression/frontend_contract/local_regression, task_complete=false.
- 이번 실행에서 registry 누락 검사 1 PASS/exit0 재확인. GitHub/Gateway 접근과 실제 후속 구현·push·CI·병합 연속성 확인. 이 반복의 Work 후속 개발 경로만 검증됐으며 전체 제품 무인 완성/새 H02 비동기 인수는 미완료.
- 새 고정 runtime `D:\\01_git\\public-bid-agent-work-h02`, queue `D:\\Temp\\bid-work-queue-h02`, trusted/candidate는 위 a219 전체 SHA. Python은 별도 `D:\\Temp\\bid-h02-test-venv\\Scripts\\python.exe` (packaging26.3).
- 실제 변경: 기존 일반 사용자 task `PublicBidAgent-WorkQueue-H02`의 action을 PowerShell launcher `D:\\Temp\\bid-work-h02-worker.ps1`와 명시적 WorkingDirectory로 수정. 실행 정책/권한 완화 없음. 반복 trigger는 아직 없고 Work가 Start-ScheduledTask로 시작.
- `h02-30-002` 최초 복합 제출 요청은 TIMEOUT_TERMINATION_UNCONFIRMED. 이후 job 폴더/해당 worker 프로세스 미관측·task Ready를 확인하고 짧게 분리하여 제출 QUEUED 및 start 요청 성공. 마지막 관측 LastTaskResult=1, running/result 파일 미관측. 로그 조회도 원격 timeout으로 원인 미확정. **새 ID 재제출/worker 반복 실행 금지**: 다음 회차 기존 002 request/running/result, 실제 프로세스, task, launcher 로그를 먼저 대조.
- 운영 clone은 변경하지 않음. 기존 localhost 운영 브라우저 인수와 데이터 불변성 검사는 잔여. 합성 CI 성공을 운영 인수로 대체하지 않음.
- 다음: 002 종료/실행 원인 확인 → 남은 H02-2 local/backend/frontend 연결 → H02-3 증거 결속 → H03 잔여 및 제품 카드. 실제 회사 증빙/사람 정답은 BLOCKED_EVIDENCE 유지. 전체 제품 DONE 아님.

> H02 감사 테스트는 기존 개발 의존성 `packaging>=26,<27`을 재사용합니다. 큐 실행기 자체는 표준 라이브러리이며 감사 검사는 분리된 개발 Python에서 실행합니다.

# Work 중심 비동기 개발 반복

2026-11-02 사용자 최신 지시: 구현과 판단은 Work에서 수행하고 노트북은 실행만 담당한다.
별도 검증 AI/노트북 Codex를 필수로 두지 않는다. 기존 H01 상세 검증을 재사용한다.
main 병합·기존 localhost 배포까지 승인됐으며 실제 입찰/회사 증빙/사람 정답을 생성하지 않는다.

## 역할과 완료

- Work: CONTROL/AGENTS/상태/작업 카드/실제 PR·CI를 읽고 작은 미완료 작업을 구현한다.
- 노트북: 고정 runtime의 `scripts/work_queue.py worker`가 한 요청을 실행하고 종료한다.
- 예약 Work: 매시간 결과를 확인하고 수정/다음 작업을 진행한다. 실행 중 작업이 있으면 중복 제출하지 않는다.
- 기존 H01: 단일 A01 검사 상세 결과를 검증한다. 큐는 ID/SHA/exit/report/cleanup만 연결한다.
- `SUCCEEDED`는 요청한 검사 성공이며 전체 제품 DONE이 아니다. H02 전체 검사와 후속 제품 카드는 별도로 남는다.

전체 완료는 A01~A08 카드의 요구 기능·회귀·필요한 검수·동일 SHA CI·Windows 설치/운영 브라우저 인수 및 실자료 증거 게이트가 충족된 경우다.
실자료/회사 근거가 없는 카드는 BLOCKED_EVIDENCE로 보존하며 자동으로 완료 처리하지 않는다.
하네스 개발만 반복하지 말고 실행 경로가 확보되면 H02-2/3 및 실제 제품 카드로 진행한다.

## CLI와 실행 환경

Python 3.12와 Git, 소유자가 검토한 public 코드만 사용한다. 큐는 저장소 밖 일반 사용자 전용 폴더다.
runtime clone은 고정 SHA로 유지하며 실행 중 fetch/checkout/수정하지 않는다. 후보 commit은 먼저 fetch한다.
요청마다 전체 40자리 SHA를 사용한다. 운영 서버가 사용하는 clone과 큐 runtime은 분리한다.

```powershell
py -3.12 scripts/work_queue.py --queue D:\Temp\bid-work-queue submit --id a01-001 --trusted <runtime-sha> --candidate <candidate-sha>
py -3.12 scripts/work_queue.py --queue D:\Temp\bid-work-queue worker --trusted <runtime-sha>
py -3.12 scripts/work_queue.py --queue D:\Temp\bid-work-queue status
```

작업 스케줄러의 일반 사용자 Interactive/Limited task는 고정 `worker` 명령을 실행한다.
노트북 로그인/전원 유지가 필요하며 로그아웃·절전 상태에서 실행된다고 주장하지 않는다.
주기 트리거를 사용할 때는 `MultipleInstances=IgnoreNew`; 실행기는 OS 잠금으로도 중복을 거부한다.
작업은 600초/stream별 2MB 한도이며 기존 Windows Job/POSIX process group으로 생성한 자식만 정리한다.
자유 shell 명령, 자동 모델 호출, 비공개 자료 전송, 자동 git 쓰기는 큐에 없다.

## 결과와 복구

각 job 폴더의 request.json, running.json(5초 heartbeat), result.json, stdout/stderr, harness-run을 확인한다.
같은 ID/내용 재제출은 EXISTING이며 같은 ID의 다른 SHA는 거절한다. 완료 결과는 덮어쓰지 않는다.
잠금 획득 후 잔존 RUNNING 발견 시 INTERRUPTED로 기록하고 전체 큐를 차단한다.
heartbeat만으로 살아 있음/죽음/완료를 확정하지 않는다. 프로세스 종료가 확인되기 전 재실행하지 않는다.
INTERRUPTED/BLOCKED_ENVIRONMENT는 자동 해제하지 않는다. Work가 실제 프로세스/결과를 확인한 후
이전 큐를 그대로 보관하고 별도 새 큐/새 ID로 재개한다. 비공개 원시 로그는 GitHub에 올리지 않는다.

Gateway 성공은 테스트 성공이 아니다. timeout 종료 미확인은 실제 파일/작업/프로세스로 대조한다.
긴 inline 명령 전달에서 무출력 timeout이 관측됐다. 짧은 명령+작은 파일 조각 전송을 우선한다.
stdin에 UTF-8 BOM이 붙는 경우 `TrimStart([char]0xFEFF)`로 제거한다. 실행 정책을 낮추지 않는다.

## 예약 Work의 매회 절차

1. 최신 CONTROL → registry → AGENTS → CURRENT_STATE/TASKS/이 문서 → 최신 PR/CI 확인.
2. 기존 큐/스케줄러 상태 읽기. 실행 중이면 상태만 기록하고 중복 구현/기동하지 않는다.
3. 종료 결과를 실제 SHA/기록과 대조. 실패하면 원인을 수정하며 테스트/판정 기준을 약화하지 않는다.
4. 첫 실행 가능한 미완료 카드 구현 → 기존 테스트 → 필요한 독립 Work 검수 → 개발 브랜치 push.
5. 동일 SHA CI 성공 후 승인된 main 병합/로컬 배포와 운영 화면 인수. 사용자 변경/운영 자료 보존.
6. 실행 증거·잔여 작업·다음 명령을 GitHub에 기록하고 다음 반복에서 이어간다.
7. 전체 완료이면 예약 중지. 도구/사용량/필수 근거 차단이면 중단 원인 기록, 무의미한 재시도 금지.

예약 등록과 무인 실행 성공은 다르다. 최초 예약 실행에서 GitHub/Gateway 접근과 실제 후속 작업 기록을
확인한 뒤 END_TO_END_AUTONOMOUS_VERIFIED로 표시한다. Work의 실제 후속 구현/push/동일 SHA CI/병합 경로는 2026-11-03 확인했다. 새 H02 스케줄러 인수와 전체 제품 완료는 최상단 최신 기록처럼 미완료다.

## 확인된 노트북 설치 (2026-11-02)

- runtime D:\01_git\public-bid-agent-work-v2, trusted SHA 87cfb4f9ca856dccbd39909b41a2c060aa44a7ef
- queue D:\Temp\bid-work-queue-v2, task PublicBidAgent-WorkQueue, launcher D:\Temp\bid-work-worker.ps1
- a01-async-002 SUCCEEDED, exit0/cleanup=true/LOCAL_VERIFIED. 원격 제출 후 별도 연결로 결과 회수.
- 이 runtime은 H01 한 검사 정책으로 고정되어 있다. 새 H02 정책은 검수된 새 runtime/큐에서 실행하고 기존 runtime을 실행 중 바꾸지 않는다.
- Work 후속 실행의 GitHub/Gateway 접근과 결과 회수를 확인했고 실제 H02-2 변경을 진행했다. 전체 제품 자동 완료와 구분한다.
