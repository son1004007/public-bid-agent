# H01 실행 하네스 검증 기록

## 범위와 구현

- 기준 main: `9f8597e531a0013f11f6654027998fee1ab2d8c1`
- 검증 코드: `3b7ff8b789bba2c44a48db487dba5d8f40e0bfe7`
- 게시: [Draft PR #2](https://github.com/son1004007/public-bid-agent/pull/2), `feat/harness-h01`.
- task JSON/명령 registry, validate/run/verify/status, 고정 SHA snapshot, 구조화 unittest 보고서, timeout/출력 제한/자식 종료, hash 결속 실행 기록 구현.
- H02 전체 검사·검수/CI 증거 자동 결속, H03 재개/작업별 잠금은 미구현. H01은 task_complete=false만 반환.

## 실제 검증

| 환경/검사 | 결과 |
|---|---|
| Linux Python 3.12.14 자체 인수 | 15 PASS, 3.684초 |
| 노트북 Windows Python 3.12.0 자체 인수 | 15 PASS, 30.891초 |
| [Development harness CI](https://github.com/son1004007/public-bid-agent/actions/runs/41119880356) | Ubuntu/Windows PASS |
| 노트북 validate | VALIDATED |
| 노트북 A01 run/verify/status | 모두 VERIFY_FAILED, task_complete=false, 미실행 필수 검사 4개 명시 |
| [Sprint 1 CI](https://github.com/son1004007/public-bid-agent/actions/runs/41119880075) | frontend PASS, backend 기존 A01 날짜 실패로 FAIL |
| 제품 local_app 회귀(CI) | 479 실행, 실패 1/skip 2. CLOSED != OPEN, test_procurement_filter.py:34 |
| 문서 동기화 | 위 Sprint 1 frontend gate PASS. 작성 환경 shallow HEAD 검사는 SKIP으로 구분 |

노트북 run ID: `5f8f9aa3-bd4a-47f4-bb71-cc8ad4482f60`. 실행 결과 종료코드1을 확인했으며 재검증/상태 조회에서도 동일 실패를 유지했습니다.
원본 로그/실행 폴더는 노트북에 보관하고 공개 Git에는 개인 경로·인증정보·운영 데이터 없이 요약만 남깁니다.
합성 인수는 성공/실패/skip/보고서 누락·identity·개수·exit/증거·snapshot 변조/허용 범위/기존 폴더/시간 초과 자식/출력 한도 등을 검사합니다.

## 독립 검수

- 별도 노트북 Codex 0.166.0 읽기 전용 세션 `01a18e69-47af-73e0-b748-1fcf801bbf5e`.
- 대상은 위 코드 SHA와 main 기준의 변경. 판정 **GO — H01 한정**, BLOCKER/MAJOR 없음.
- 확인: 부분 성공 DONE 승격 없음, START 전 Windows Job 결속/active process=0 확인, 증거와 snapshot 검증.
- MINOR 1: HARNESS_USAGE가 문서 검사까지 Development harness CI에서 실행한다고 쓴 문구. 후속 문서 수정으로 실제 unittest만 실행함을 명확화.
- 독립 테스트 **NOT RUN**: Codex 로컬 runner pipe-in 연결 실패로 고정 SHA GitHub 원문을 읽어 검수. 작성자 테스트를 독립 실행이라고 표기하지 않음.

## 진행 중 발견·대응

1. 노트북 Codex 로컬 실행·파일 수정 runner 연결 실패, 비대화형 GitHub 쓰기 승인 차단. 정책을 완화하지 않고 본 세션 GitHub 연결로 코드 게시, Gateway로 노트북 검증, Codex는 독립 읽기 검수에 사용.
2. Windows CRLF/LF 차이로 초기 무결성 인수 실패. `.gitattributes`와 합성 fixture Git 설정 수정 후 15 PASS. 기존 clone의 세 파일 잔존 CRLF는 해당 고정 Git blob과 동일 byte로 복원해 실제 A01 실행. 재사용자는 새 clone 권장, 무결성 검사는 유지.
3. A01 날짜 실패는 제품 변경 H02에 남겨두고 실패 그대로 기록. 전체 CI green/제품 완료/운영 배포 주장 없음.

## 다음 AI 작업

CONTROL → AGENTS → DECISIONS → CURRENT_STATE/TASKS → [사용법](../implementation/HARNESS_USAGE.md) → 최신 PR/CI → task/registry 순서로 읽습니다.
H01을 다시 설계하거나 새로 만들지 말고 기존 실행기로 baseline을 재현하십시오.
H02에서 A01 날짜 계약을 고정 clock 기반으로 수정하고 전체 required_checks adapter와 외부 검수/CI 결속을 구현·검증하십시오.
허용 task 범위 변경은 신뢰 정책 변경이므로 별도 검수된 commit으로 고정합니다. 실패 후에는 새 run 폴더를 사용합니다.
