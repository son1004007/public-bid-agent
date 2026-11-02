> **구현 후 안내:** [HARNESS_USAGE](HARNESS_USAGE.md)가 실제 CLI 기준입니다. 아래는 최초 사전 점검 당시 이력입니다. Codex 0.166.0 모델·GitHub/Gmail read 호출은 이후 성공했으나 로컬 runner pipe 및 비대화형 MCP 쓰기 승인은 차단됐습니다. controller/Gateway 검증 경로를 사용하며 sandbox/승인 정책은 완화하지 않습니다.

# Gateway → 노트북 Codex 하네스 구현 안내

- 2026-10-31 KST / **구현용 런북**, 하네스는 아직 NOT IMPLEMENTED.
- 선행 문서: [AI_START_HERE](AI_START_HERE.md) → [하네스 명세](../design/EXECUTION_HARNESS_SPEC_2026-10-31.md) → [A01~A08](AI_EXECUTION_TASKS_2026-10-30.md).
- 전역 CONTROL·device-control의 최신 Gateway 정책을 우선한다. 공개 문서에는 장비 IP/사용자 홈 실제 경로·인증정보·비공개 자료를 기록하지 않는다.

## 1. 이번에 확인한 것과 확인하지 못한 것

| 점검 | 결과 |
| --- | --- |
| Gateway 등록 대상 `windows11-notebook` | ready 확인. 이후에도 매 실행마다 재확인 |
| 비승격 PowerShell 버전/도움말 조회 | job `job_01M6709X5X0003HJCJP1QVTFQD` succeeded, exit0 |
| Codex / Python | `codex-cli 0.163.0`, `Python 3.12.0` 확인 |
| 지원 옵션 | `exec`, `-C`, `--sandbox workspace-write/read-only`, `--json`, `--output-last-message`, stdin `-` 확인 |
| 인증 상태 후속 조회 | job `job_01M670BC5D000EN69CNH495FYT` failed / `TIMEOUT_TERMINATION_UNCONFIRMED`, 출력 없음. exitCode 필드0만으로 성공 처리하지 않음 |
| 종료 미확인 이후 프로세스 읽기 전용 점검 | job `job_01M670KKTH00TW3VM8EAR7TWQQ` succeeded. 관측된 codex/node는 기존 시작 시각의 프로세스였으며 종료/변경하지 않음. 해당 timeout job의 전체 자식/래퍼 종료를 입증한 것은 아님 |
| 실제 Codex 추론·구현/노트북 저장소 위치·sandbox 실행 | **NOT VERIFIED**. 버전 조회로 모델 권한/남은 한도/안전한 구현 성공을 보장하지 않음 |
| 하네스 구현/전체 테스트/운영 배포 | **NOT RUN** |

공식 OpenAI [Non-interactive mode](https://developers.openai.com/codex/noninteractive/)를 실제 조회하여 `codex exec`, JSONL 이벤트, `-o`, workspace-write 옵션을 확인했다. 검색 도구는 오류였으며 공식 페이지 직접 HTTP 조회와 설치 CLI 도움말을 대조했다. `--full-auto`는 최신 문서에서 지원 종료로 표시되므로 사용하지 않는다. `--dangerously-bypass-approvals-and-sandbox`, `--ignore-rules` 같은 우회 옵션을 이 런북에 적용하지 않는다.

## 2. Gateway 작업자가 먼저 할 일

1. Gateway 운영 스킬을 읽고 `list_servers`에서 사용자의 Gateway 계정에 등록된 정확한 Windows 대상 ID를 찾는다. 과거 ID/주소를 하드코딩하지 않는다.
2. `execute_command`는 `shell=powershell`, `privilege=none`으로 호출한다. 관리자권한·포트포워딩·전역 Git 자격증명·sandbox 설정은 변경하지 않는다.
3. 이전 timeout job의 상태와 프로세스 생존을 읽기 전용으로 확인한다. command line 전체/환경변수/인증 파일은 출력하지 않는다. 프로세스가 있으면 시작 시각·부모 관계·해당 job의 정확한 식별을 대조한다. **다른 작업인지 불명확하면 종료하지 않는다.** 종료 미확인 상태에서는 모델 작업 재시도를 보류한다.
4. 실제 작업 폴더를 확인한다. 기존 운영 checkout과 데이터 경로를 개발 대상으로 재사용하지 않는다. Git remote가 이 저장소인지, 현재 branch/SHA·dirty 상태·동시 Codex 작업을 확인한다. 발견하지 못하면 사용자가 정한 개발 경로에 새 clone을 준비한다; 임의 전체 디스크/비공개 파일 검색 금지.
5. 확인된 경로에서 Codex `--version`, `exec --help`, Python3.12, Git, Node 버전과 인증 가용성을 각각 작은 읽기 전용 작업으로 확인한다. `login status`가 멈추면 실패를 반복하지 않고 로컬 터미널에서 확인하도록 인계한다. 인증 파일 내용/토큰을 읽거나 복사하지 않는다.
6. 초기 시험은 **공개 소스의 작은 read-only 작업**이다. 이후 sandbox workspace-write에서 임시 개발 파일 하나 쓰기/검증이 되는지 확인한 뒤 구현한다. 연결/도움말 성공과 실제 모델 실행 성공을 구분한다. 기존 사용자 지시·프로젝트 규칙을 무시하는 옵션은 쓰지 않는다.

Gateway `wait_seconds`는 원격 작업 전체의 완료 약속이 아니다. 반환 job ID를 보관하고 `get_job(after_cursor=nextCursor)` 또는 제공되는 대기 도구로 terminal 상태까지 확인한다. timeout·취소·출력 truncation·error 필드도 함께 본다. queued/running만으로 구현 시작/완료를 주장하지 않는다.

## 3. 작업 폴더 준비 — 변수는 실제 확인한 경로로 지정

다음은 **개발 재개 시 수행할 예시**이며 이번에 실행하지 않았다. `$repoPath`, `$workPath`는 구현 담당자가 확인한 별도 개발 경로여야 한다. 운영 폴더를 대상으로 실행하지 않는다.

```powershell
# 사전: $repoPath는 검증된 clone, $workPath는 아직 없는 별도 개발 경로
$ErrorActionPreference = 'Stop'
git -C $repoPath status --short
if ($LASTEXITCODE -ne 0) { throw 'Git 상태 조회 실패' }
# 출력이 있으면 사용자의 기존 변경을 보존하고 별도 경로를 준비한다.
git -C $repoPath fetch origin main
if ($LASTEXITCODE -ne 0) { throw 'fetch 실패: 자격증명/연결 확인, 우회 금지' }
git -C $repoPath worktree add -b feat/harness-h01 $workPath origin/main
if ($LASTEXITCODE -ne 0) { throw 'worktree 생성 실패: 기존 branch/path 보존' }
```

동일 branch/path가 있으면 위 명령을 다시 실행하거나 강제 덮어쓰지 말고 실제 상태를 확인한다. 비대화형 Git Credential Manager 인증 실패는 과거에도 있었으므로 토큰을 URL에 넣거나 인증 정책을 바꾸지 않는다. 사용자가 노트북 로컬에서 Git 인증을 완료하는 경로 또는 승인된 GitHub 플러그인 게시 경로를 사용한다. 파일 upload typed API가 실패하면 실패를 기록하고 검증 가능한 공개 소스 전달 경로만 사용하며 성공했다고 간주하지 않는다.

## 4. Codex 실행 방법

H01 프롬프트는 [CODEX_HARNESS_H01_PROMPT](CODEX_HARNESS_H01_PROMPT_2026-10-31.md)를 사용한다. **아래는 실제 Codex CLI 구문으로 확인한 실행 예시이나, 원격 모델 실행 E2E는 아직 미검증**이다. `$runDir`는 해당 실행 전용 비공개 폴더이며 개발 소스와 사용자 원본 밖에 둔다. `$codexExe`는 Get-Command로 확인한 실행 파일로 지정한다. Windows에서 `.ps1`이 정책에 막히면 실행정책을 풀지 말고 설치된 `.cmd` 등 정식 진입점 지원을 먼저 확인한다.

```powershell
# $workPath, $runDir, $codexExe는 사전에 확인/생성한 경로
$promptPath = Join-Path $workPath 'docs\implementation\CODEX_HARNESS_H01_PROMPT_2026-10-31.md'
$prompt = Get-Content -LiteralPath $promptPath -Raw -Encoding UTF8
$eventsPath = Join-Path $runDir 'codex-events.jsonl'
$stderrPath = Join-Path $runDir 'codex-stderr.log'
$finalPath = Join-Path $runDir 'codex-final.txt'
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$prompt | & $codexExe exec -C $workPath --sandbox workspace-write --json `
  --output-last-message $finalPath - 1> $eventsPath 2> $stderrPath
$codexExit = $LASTEXITCODE
if ($codexExit -ne 0) { throw "Codex 실행 실패(exit=$codexExit). 로그는 로컬에서 확인하세요." }
# exit0이어도 별도로 diff/테스트/증거를 검증한다.
```

모델 이름은 기존 허용 설정/계정 가용성을 확인해 사용하고 임의 변경하지 않는다. stdin UTF-8과 JSONL 리다이렉션 encoding은 실제 PowerShell 버전에 따라 검증한다. JSONL을 소비하기 전에 모든 줄 파싱을 시험하고 BOM/UTF-16 출력이면 검수된 로컬 변환/출력 writer로 처리한다. secret/원문이 포함될 수 있는 로그를 Gateway 응답이나 공개 Git에 그대로 출력하지 않는다.

이 직접 실행 예시는 프로세스 트리 종료/재개를 구현한 supervisor가 아니다. 실제 자동 실행에는 job timeout과 Codex 자식 종료 확인이 필요하다. 최초에는 범위를 작게 하고 시간 상한을 설정한다. timeout은 한도를 늘려 무한 반복하거나 백그라운드로 방치하는 이유가 아니다. Windows 인증/승인 대화가 필요하면 **해당 작업을 보류하고 노트북 로컬 터미널에서 같은 프롬프트를 실행**한다. SSH 사용자 세션에서 AGY가 겪었던 인증 문제를 Codex에도 동일하다고 추정하거나 임의 스케줄러를 생성하지 않는다.

## 5. Codex 종료 후 확인 순서

1. Gateway job terminal 상태, error, 실제 Codex exit, 종료/자식 잔존을 확인한다. 상충하면 성공 판정 금지.
2. 구현 대상 diff와 untracked 파일을 확인한다. 허용 범위 이탈·검증기/테스트 약화·사용자 데이터 변경을 검사한다.
3. Codex가 썼다는 테스트 요약 대신 부모/controller가 명세의 합성 테스트를 직접 실행해 구조화 결과를 확인한다.
4. H01 CLI가 실제 존재하는지 `--help`, task validate, 성공/실패 fixture run으로 확인한다. 명세에 적힌 **미구현 명령을 실행 완료로 기록하지 않는다.**
5. 중요 설계·완료 diff는 별도 Codex read-only 검수를 적용한다. 동일 구현 세션의 자기평가를 독립 GO로 저장하지 않는다.
6. 개발 브랜치 게시/CI와 정확 SHA 결과를 확인하고 CURRENT_STATE/TASKS 및 H01 실행 기록에 인계한다. main 병합/운영 서비스 변경/전체 A 카드 자동 실행으로 확대하지 않는다.

## 6. 실제 하네스가 구현된 후의 목표 인터페이스

아래 명령은 **설계 목표**이며 2026-10-31 현재 파일/기능이 없다.

```text
python scripts/task_harness.py validate --task A01
python scripts/task_harness.py run --task A01 --run-dir <전용-절대경로>
python scripts/task_harness.py verify --run-dir <전용-절대경로>
python scripts/task_harness.py status --run-dir <전용-절대경로>
python scripts/task_harness.py resume --run-dir <전용-절대경로>
```

H01에서는 validate/run/verify/status와 작은 합성 테스트부터 제공하고, resume는 H03에서 구현하기 전 명시적으로 unsupported 처리한다. Gateway는 이 명령을 실행/관측하는 통로이고, 작업 정의·증거 판정 로직은 저장소의 하네스에 둔다.
