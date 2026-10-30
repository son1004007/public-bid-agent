# 단계별 개발 하네스 구현 명세

- 상태: **DESIGN / NOT IMPLEMENTED**, 2026-10-31 KST.
- 대상: 기존 Python 3.12 로컬 제품과 [A01~A08 작업 카드](../implementation/AI_EXECUTION_TASKS_2026-10-30.md).
- 요청 범위: 작업 정의·실행기·검증기·실행 기록의 확인 방법을 명세하고, Gateway→노트북 Codex 구현 안내를 게시한다. 이번 문서 게시 자체는 하네스 구현/모델 실행/제품 수정/운영 배포가 아니다.
- 읽기: AGENTS → DECISIONS → [AI 시작점](../implementation/AI_START_HERE.md) → 이 명세 → [노트북 실행 안내](../implementation/GATEWAY_CODEX_HARNESS_RUNBOOK_2026-10-31.md).

## 1. 하네스가 무엇을 확인하는가

하네스는 정해진 규칙을 실행하는 Python 프로그램이다. 문서를 이해했다고 주장하는 AI 대신 **검증 가능한 입력·관측값·산출물**로 상태를 계산한다. Codex는 구현 담당이고 최종 단계 승격의 권위는 아니다.

| 구성 | 읽을 입력 | 확인 방법 | 실패 시 |
| --- | --- | --- | --- |
| 작업 정의 검증기 | 버전된 task JSON + 신뢰된 command registry + 의존 단계 결과 | 필수 필드/자료형/허용 enum, 알 수 없는 필드, task ID 유일성·순환 의존, 실행 대상/필수 검사 집합, 선행 증거 버전 | INVALID_TASK / BLOCKED_DEPENDENCY; 실행 전 중지 |
| 실행기 | 검증된 task ID·기준 소스·환경 | 격리 작업경로/깨끗한 검증 snapshot, 허용 argv, cwd, 시간·출력 상한, 독점 실행 잠금, 실행 전후 파일 목록/hash | VERIFY_FAILED / TIMED_OUT / INTERRUPTED / BLOCKED_ENVIRONMENT |
| 검증기 | 실제 subprocess 결과·구조화 테스트 보고·diff·독립 검수·CI | 종료 코드 + 보고서 무결성/검사 ID/실행 건수/실패·skip 정책 + 동일 소스/정의 결속 | VERIFY_FAILED 또는 WAITING_REVIEW/WAITING_CI |
| 실행 기록 | 실행기가 직접 만든 이벤트와 산출물 hash | run ID·증거 출처·연속 이벤트·원자 저장·현재 내용 재해시, 상태 재계산 | EVIDENCE_INVALID / STALE; 이전 PASS 재사용 금지 |

**구분:** `python -m unittest` exit=0, Codex exit=0, Gateway job succeeded는 서로 다르다. Codex 성공 종료는 대화 종료일 뿐, 테스트·독립 검수·제품 완료의 증거가 아니다. JSON Schema 준수도 내용의 진실을 보장하지 않는다.

## 2. 최소 파일 배치 — 구현 예정 경로

| 경로 | 책임 |
| --- | --- |
| `harness/tasks/A01.json` | 기계가 읽는 선행조건·검사 ID·변경 허용 범위·증거 요구 |
| `harness/commands.json` | 검수된 command ID→실행 파일/argv·cwd·timeout·결과 adapter 매핑 |
| `harness/task.schema.json` | 버전별 계약 명세. 최초에는 표준 라이브러리 명시 검증으로 구현 가능 |
| `scripts/task_harness.py` | CLI 진입점; validate/run/verify/status/resume 서브명령 |
| `scripts/harness_core/` | 실제 책임 분리가 필요한 validator/runner/evidence 모듈만 추가 |
| `scripts/test_task_harness.py` | 임시 폴더의 성공/실패/오염/재개 합성 테스트 |
| 저장소 밖 전용 실행 폴더 | `<run_id>/events.jsonl`, `run.json`, 테스트 결과, private stdout/stderr, diff manifest |

새 외부 서비스/DB/daemon은 초기 요구사항이 아니다. 원본 RFP·cases/operations·운영 데이터 경로는 실행 폴더로 사용하지 않는다. 저장소 내부 fallback을 지원할 경우 명시 gitignore와 경로 탈출·symlink/junction 거부가 선행된다. 기존 process_limits/JSON 잠금 규칙은 검토 후 재사용하며 운영 lock을 개발 하네스 lock과 혼용하지 않는다.

## 3. 작업 정의 계약

다음은 **설명용 예시**다. 파일 생성/CLI 구현 전에는 실행할 수 없다. 실제 명령은 신뢰된 registry에만 두고 모델 출력/공고문/자유 텍스트를 shell 명령으로 실행하지 않는다.

```json
{
  "schema_version": 1,
  "task_id": "A01",
  "mode": "synthetic",
  "depends_on": [],
  "required_checks": ["a01_deadline", "local_regression", "audit_regression", "backend_regression", "frontend_contract"],
  "allowed_changes": ["local_app/test_procurement_filter.py", "local_app/dashboard_backend.py", "README.md", "local_app/README.md", "docs/reviews/", "CURRENT_STATE.md", "TASKS.md"],
  "forbidden_changes": [".github/workflows/", "harness/", "scripts/task_harness.py", "scripts/harness_core/"],
  "requires_independent_review": true,
  "requires_ci": true,
  "requires_human_evidence": false,
  "max_attempts": 2
}
```

- allowed_changes의 끝 `/`는 해당 하위 경로, 나머지는 완전 일치로 정의한다. Windows 대소문자·구분자·경로 정규화를 적용하고 `..`, 절대 경로, junction/symlink 경계 이탈을 거부한다.
- 위 예시 목록은 A01 구현 시 호출 경로에 맞춰 별도 검수하여 확정한다. 범위 밖 변경을 몰래 허용하거나 명령 실행 중 manifest를 변경하지 않는다.
- 작업 정의와 command registry는 **실행 시작의 검수된 기준 ref**에서 읽어 hash를 고정한다. Codex가 수정한 작업 트리의 정책/검증기를 같은 실행에서 신뢰하지 않는다.
- 필수 검사 삭제, 테스트 0개 수집, 추가 skip, 판정 기준 완화는 정의 변경으로 별도 검수한다. max_attempts는 예산이며 PASS를 얻기 위한 자동 테스트 약화 권한이 아니다.
- 사람이 읽는 A 카드와 task JSON의 ID/목표/필수검사 불일치는 INVALID_TASK다. 자동 문서 생성은 이후 선택사항이며 최초에는 표 비교로 검수한다.
- 전역/프로젝트 AGENTS 등 bootstrap 지시를 코드로 완전히 이해했다고 인증할 수 없다. 읽은 문서 ref/hash를 기록하고 Codex 프롬프트에 제공하되, 실행 경계는 allowlist/검사로 별도 구현한다.

## 4. A01 실제 실행 흐름

1. 개발자가 승인된 기준에서 독립 작업 브랜치를 준비하고 Codex에 A01 한 건만 맡긴다. **초기 H01에서는 Codex 자동 호출 자체를 구현하지 않는다.** 사람이/Gateway가 Codex를 실행하고 하네스는 결과 검증을 담당한다.
2. 하네스 `validate`가 task/registry, Python3.12, Git root, 변경범위, 선행 증거를 확인한다. 이미 dirty인 사용자 작업을 reset/clean/stash하지 않는다.
3. Codex의 작업을 commit 후보 또는 별도 고정 snapshot으로 만든다. snapshot은 tracked/untracked 중 실제 검사 입력 전체·추가/삭제·모드·경로의 canonical manifest hash로 식별한다. 승인되지 않은 untracked 파일은 실행하지 않는다.
4. 원래 A01 실패의 재현을 baseline evidence로 따로 기록한다. 구현 후 검증에서는 **그 실패가 더 이상 허용되는 실패가 아니다**. 전체 검사는 command registry의 정확한 argv로 호출한다.
5. 예: 대상 회귀 `python -m unittest test_procurement_filter -v`는 전용 synthetic 데이터 디렉터리와 `PYTHONPATH=local_app`에서 실행한다. 전체 local_app/audit/backend/Node 명령은 현재 CI와 대조하여 registry에 등록한다. 단순 로그의 `PASS` 문자열 검색은 금지한다.
6. subprocess를 동기적으로 종료까지 기다리고 종료 코드·시각·결과 파일·환경·stdout/stderr hash를 수집한다. unittest 결과는 runner adapter가 TestResult의 run/failure/error/skip 목록을 JSON으로 저장한다. Node/backend도 버전 지원되는 구조화 reporter 또는 검수된 adapter를 사용한다. reporter가 없으면 판정을 미완료로 남긴다.
7. 실행 전후 snapshot/정의/검증기 hash와 허용 파일 범위를 비교한다. 테스트 중 소스가 바뀌면 STALE. 실패/보고서 누락/0 tests/예상치 못한 skip/timeout이면 VERIFIED 금지다.
8. 로컬 검사 통과는 LOCAL_VERIFIED일 뿐이다. **독립 Codex read-only 검수**는 동일 diff/snapshot을 새 세션에서 확인한다. 작업자 스스로 작성한 review.json을 독립 검수 증거로 인정하지 않는다.
9. 개발 브랜치 commit 후 CI의 실제 API 결과를 읽어 SHA·workflow·attempt·필수 jobs·결론을 대조한다. queued/skipped/cancelled/일부 success는 전체 PASS가 아니다. CI 대기 동안 WAITING_CI.
10. 요구된 독립 검수/CI와 실자료 조건까지 일치할 때 카드 DONE. 하네스는 사람 최종 입찰 판단·배포를 대신하지 않는다.

## 5. 검증 증거의 최소 데이터

`run.json`은 모델 응답이 아니라 신뢰된 실행기가 쓴다. 검증 완료 시 다음 필드가 빠지면 완료를 거절한다.

| 필드 | 내용 |
| --- | --- |
| identity | schema_version, run_id(UUID), task_id, attempt, predecessor_run_id, 시작/종료 UTC와 표시 TZ |
| inputs | repo/ref, base_commit, candidate_commit 또는 snapshot_digest, task_digest, registry_digest, harness_digest, 평가 입력 digest |
| environment | OS, Python/Node/Codex 버전, 결과 adapter 버전. env 전체/secret 덤프 금지 |
| checks | check_id, argv 배열, cwd의 비식별 논리명, start/end, exit_code, timeout/cancel, tests_run/fail/errors/skip, report hash |
| review | 독립 session 참조·검토 대상 digest·verdict·지적 처리. 서술과 직접 관측 provenance 구분 |
| ci | repository, commit_sha, run_id, run_attempt, workflow ID/name, required job 결과와 조회시각 |
| result | 단계 상태, 실패 코드, blockers, 다음 허용 단계. 사용자 제공 status를 복사하지 않음 |

`events.jsonl`은 순번·이전 event digest·현재 digest와 상태 전이를 append한다. `run.json`은 같은 디렉터리 임시 파일→원자 replace로 갱신한다. 이벤트와 요약이 어긋나거나 마지막 JSONL이 잘리면 자동 완료 처리하지 않고 복구 가능성/손상을 표시한다. OS 파일 잠금으로 같은 실행 폴더/작업의 동시 기록을 막는다. 순수 hash chain은 실수·변조 탐지에 도움을 주지만 **같은 OS 권한의 악의적 작성자가 전부 재작성하는 공격을 막는 서명이 아니다**.

초기 신뢰 범위는 소유자 단일 사용자 개발이다. 외부/untrusted PR이나 강한 위조 방지가 필요하면 별도 계정/ACL·검증 서비스·서명된 증거 경계가 필요하며 초기 하네스의 보안 보장으로 주장하지 않는다. 신뢰된 controller/검증기와 실행 로그는 Codex 수정 대상 밖에 두고, scope 검사는 실행 후 탐지이지 OS sandbox 대체가 아님을 명시한다.

## 6. 상태와 재개

기본 흐름: `PLANNED → VALIDATED → RUNNING → LOCAL_VERIFIED → WAITING_REVIEW/WAITING_CI/WAITING_HUMAN → DONE`. 실패 상태는 `INVALID_TASK`, `BLOCKED_DEPENDENCY`, `BLOCKED_ENVIRONMENT`, `VERIFY_FAILED`, `TIMED_OUT`, `INTERRUPTED`, `EVIDENCE_INVALID`, `STALE`로 구분한다.

- 미구현 H01은 VALIDATED/RUNNING/LOCAL_VERIFIED 및 실패만 처리해도 된다. 요구된 외부 게이트를 수집하지 못하면 WAITING_*이며 DONE 금지다.
- resume는 이전 증거/소스/task/환경/입력 hash, 잠금 소유자와 생존 여부부터 확인한다. RUNNING 기록만 남아 있으면 성공으로 간주하지 않는다. PID 재사용을 고려해 PID만으로 프로세스를 종료하지 않는다.
- 초기 지원은 **읽기 전용/합성 검증 명령의 재실행**뿐이다. 새 run/attempt를 만들고 이전 기록 보존. 모델 실행·저장·외부 부작용을 자동 반복하지 않는다.
- timeout/cancel 시 Windows에서는 생성한 프로세스 트리만 종료하고 자식 잔존을 확인한다. 안전한 프로세스 트리 제어가 지원되지 않으면 해당 adapter BLOCKED; `taskkill /IM python.exe`처럼 전체 이름 종료 금지.
- Gateway의 대기 종료/연결 끊김은 원격 프로세스 종료 증거가 아니다. job ID를 poll하고 terminal 상태와 실제 산출물 확인 전 새 작업을 중복 시작하지 않는다.
- 코드/정의/fixture가 바뀌면 관련 성공 증거를 STALE로 만들고 해당 검사를 다시 수행한다. 실행 결과에 쓰지 않는 문서 변경은 영향 범위를 명시하되 CI/검토 ref 대응을 기록한다.
- 승인 없는 실제 정답은 하네스 상태 WAITING_HUMAN, 사유 코드 BLOCKED_EVIDENCE로 기록한다. 기존 제품 백로그의 BLOCKED_EVIDENCE 상태와 하네스 enum은 별개다. A02/A03 실자료 승인과 제품의 READY_TO_BID_VERIFIED는 하네스 DONE과 다른 도메인 상태다.

## 7. 하네스 자체의 필수 인수 시나리오

| 상황 | 기대 결과 |
| --- | --- |
| 작은 합성 성공 명령 + 유효 보고서 | LOCAL_VERIFIED, 필요한 외부 게이트 없으면 DONE 불가 |
| exit nonzero 또는 tests_run=0 | VERIFY_FAILED |
| exit0 + 결과 파일 없음/잘못된 run_id | EVIDENCE_INVALID |
| task/명령 ID 미등록·순환 의존·필수검사 삭제 | 실행 전 거절 |
| 경로 탈출·junction·허용 밖 변경 | 거절/범위 위반 기록; 사용자 파일 자동 삭제 없음 |
| 일부 실패/skip/CI queued를 모델이 PASS 주장 | 실제 결과 유지, 승격 거절 |
| 실행 중 timeout + 자식 실행 중 | TIMED_OUT, 생성한 자식만 정리·잔존 확인 |
| 강제 중단 후 resume | 이전 이력 보존, stale 검사, 새 attempt; 완료 위조 없음 |
| 소스/테스트/manifest 수정 후 옛 PASS 재사용 | STALE |
| 두 실행이 같은 작업/기록 경로 사용 | 두 번째 실행이 잠금 충돌로 중지 |
| 같은 작성자의 가짜 독립 GO 또는 다른 SHA의 CI | WAITING_REVIEW/WAITING_CI 유지 |
| 다른 단계의 완료/합성 결과로 실자료 조건 대체 | BLOCKED_DEPENDENCY/WAITING_HUMAN |
| 로그 파일 변조/부분 저장/출력 상한 초과 | EVIDENCE_INVALID 또는 명시적 truncation; 판정 필수 결과 유실 시 실패 |

각 검증은 임시 폴더/합성 자료로 실행한다. 기준 통과 조건은 단순히 테스트가 존재하는 것이 아니라 위 실패를 실제 유도하고 예상 상태·보존·종료 동작을 확인하는 것이다.

## 8. 구현 단계와 기존 A 카드 연결

| 하네스 작업 | 범위 | 종료 조건 |
| --- | --- | --- |
| H01 | task/명령 검증 + 합성 실행 + 구조화 결과 저장 + A01 단일 회귀 연결 | 성공/실패/0 tests/timeout/소스 변경 검증. 실제 명령 한 번 실행. 아직 자동 Codex/단계 DONE 없음 |
| H02 | A01 수정 검증·전체 필수 검사·독립 검수/CI 결속 | A01 날짜 실패 수정, 동일 SHA 검증. 하네스 정책 변경과 A01 구현 diff는 구분해 검수 |
| H03 | 잠금/중단·재개/증거 무효화·Windows 실제 인수 강화 | 위 인수 표 전체 해당 항목 PASS, 임시 저장소 손상/중복/자식 종료 시험 |
| H04 | 필요할 때만 Codex adapter·후속 A 카드 | allowlisted prompt/소스만 전달, 호출/시간 예산, 실패 시 중지. 실자료/사람 게이트 보존 |

H01은 테스트 한 건을 실제로 돌리는 작은 수직 기능이다. 하네스 전체 프레임워크를 완성할 때까지 A01을 미루지 않는다. H02에서 A01을 완료한 뒤 A02/A03 자료 가용성을 확인한다. H04는 초기 구현의 필수조건이 아니다. 제품 구현·패키지의 README 동기화와 독립 검수 규칙은 유지한다.
