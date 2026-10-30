# 실행 가능한 H01 하네스 사용법

H01은 **작업 정의 → 허용 검사 실행 → 결과 검증 → 실행 기록**을 반복하는 개발 도구입니다.
앱 운영 서버나 자동 코딩 에이전트가 아닙니다. Python 3.12와 Git만 필요합니다.

## 새 AI의 시작 순서

1. CONTROL → AGENTS → DECISIONS → CURRENT_STATE/TASKS → 이 문서를 읽습니다.
2. 최신 원격 브랜치/PR/CI와 `harness/tasks/A01.json`, `harness/commands.json`을 확인합니다.
3. 사람이 검토한 하네스/정책이 포함된 **전체 40자리 commit SHA**를 trusted-ref로 고정합니다.
   SHA 지정 자체는 검수 승인 증명이 아닙니다. 초기 개발 커밋은 잠정 테스트 기준입니다.
4. 후보 코드를 별도 개발 브랜치에 커밋하고 candidate-ref로 고정합니다. 미커밋 파일은 실행하지 않습니다.
5. validate → run → verify/status. 실패는 수정 후 **새 실행 폴더**에서 재실행합니다.
6. 코드/기준 SHA·테스트·독립 검수·CI를 현재 상태 문서에 기록합니다. H01은 DONE을 반환하지 않습니다.

## 명령

```powershell
# 먼저 원격의 검토된 개발 브랜치를 체크아웃하세요.
$trusted = git rev-parse HEAD
py -3.12 scripts/task_harness.py validate --task A01 --trusted-ref $trusted
# 부모 폴더는 존재해야 하며 아래 run 폴더는 아직 없어야 합니다.
$run = Join-Path $env:TEMP ('bid-harness-' + [guid]::NewGuid())
py -3.12 scripts/task_harness.py run --task A01 --trusted-ref $trusted --run-dir $run
py -3.12 scripts/task_harness.py verify --run-dir $run
py -3.12 scripts/task_harness.py status --run-dir $run
```

Linux에서는 `py -3.12` 대신 Python 3.12의 `python`을 사용합니다.
다른 후보 커밋 검사는 `--candidate-ref <40자리SHA>`를 추가합니다. 후보의 변경 범위는 신뢰된 task가 제한합니다.
현재 실행기 소스가 trusted-ref와 다르면 실행을 거부합니다. 후보 실행에 후보의 하네스 코드를 import하지 않습니다.

## 결과와 기록

- `VALIDATED`: 실행 전 계약 검사 성공. 테스트 통과 아님.
- `LOCAL_VERIFIED`: 선택 검사만 성공. `missing_checks`, `external_gates`, `task_complete=false`를 함께 봅니다.
- `VERIFY_FAILED`: assertion/skip/exit/0 tests/출력 한도 실패.
- `EVIDENCE_INVALID`: 결과 누락·다른 run/검사·hash 변경·요약/이벤트 손상.
- `STALE`: 실제 실행 snapshot이 바뀜.
- `TIMED_OUT`: 검사 시간 초과. `cleanup=false`이면 `BLOCKED_ENVIRONMENT`가 우선합니다.
- `INVALID_TASK`: 계약/경로/기준 소스/허용 범위 오류. 의존 단계가 있으면 H01은 실행하지 않습니다.
- `resume`: 명시적으로 `UNSUPPORTED`, 새 작업 실행 없음. H03 예정.

run 폴더에 `run.json`, `manifest.json`, `events.jsonl`, `snapshot/`, `trusted/`, 검사별 JSON/stdout/stderr를 보관합니다.
로그와 로컬 경로는 공개 Git에 올리지 않습니다. 요약과 재현 명령만 공개 기록합니다.
한 run의 폴더 생성은 배타적입니다. 전체 작업별 동시 실행 잠금/중단 복구/다중 이벤트 체인은 H03 범위입니다.
검사 실패 시 종료코드 1입니다. 종료코드 0도 A01 전체 완료나 운영 배포 승인이 아닙니다.

## 범위·신뢰·제약

A01의 전체 필수검사 목록은 보존하되 H01은 날짜 회귀 **1개**만 baseline으로 실행합니다.
기존 마감 날짜 실패는 수정하지 않았습니다. H02에서 고정 clock/날짜 계약과 전체 회귀를 수정·검증합니다.
명령 registry는 shell 자유 명령을 받지 않으며 등록된 unittest selector만 실행합니다.
Python adapter는 stdin START 이후 후보를 import하고 Windows Job/POSIX process group으로 자식을 묶습니다.
시간·출력 상한과 자식 종료를 적용합니다. **소유자가 신뢰하는 공개 합성 코드 전용**이며 OS sandbox/네트워크 격리 도구가 아닙니다.
전체 동일 계정의 악의적 증거 재작성, 임의 untrusted PR/회사 코드 실행을 방어한다고 주장하지 않습니다.
Git 파일 mode는 입력 digest에 포함하지만 snapshot 검증은 경로/파일 byte 기준입니다.

## 자체 인수

```text
python -m unittest discover -s scripts -p test_task_harness.py -v
python scripts/check_documentation_sync.py
```

CI `Development harness`는 Ubuntu/Windows에서 위 unittest 자체 인수만 수행합니다.
문서 동기화 검사는 기존 Sprint 1 CI frontend의 README synchronization gate에서 실행합니다.
기존 Sprint 1 CI의 A01 실패와 하네스 인수 결과는 분리합니다.
노트북 Codex의 로컬 runner pipe 오류/비대화형 GitHub 승인 차단은 이 하네스의 오류가 아닙니다.
그 경우 Gateway controller의 승인된 실행으로 검사하고, Codex는 읽기 전용 독립 검수에 사용합니다.

## 확인된 기준과 기존 체크아웃

[검증 기록](../reviews/H01_HARNESS_ACCEPTANCE_2026-10-31.md)의 구현 SHA에서 독립 코드 검수와 인수가 완료되었습니다.
사용 전 PR #2의 최신 상태를 확인합니다. main에 병합되기 전에는 `feat/harness-h01` 브랜치를 사용합니다.
기존 Windows 체크아웃은 `.gitattributes` 도입 전 CRLF 파일을 유지할 수 있습니다.
`running harness differs from trusted ref` 발생 시 검사를 우회하지 말고, 미커밋 작업을 보존한 뒤 **새 폴더에 새 clone**을 받아 실행하세요.
새 checkout에는 LF 규칙이 적용됩니다. 최초 validate/run은 전체 Git snapshot 검증 때문에 노트북에서 수십 초 걸릴 수 있습니다.
