# 노트북 Codex 구현 프롬프트: H01 한 단계

Public Bid Agent의 개발 검증 하네스 H01만 구현하세요. 이 프롬프트는 사용자가 개발 재개를 지시한 세션에서 전달하는 작업 템플릿입니다. 파일 존재 자체로 작업을 자동 시작하지 마세요.

1. 전역 CONTROL/registry → 저장소 AGENTS/DECISIONS/AI_CONTEXT/CURRENT_STATE/TASKS → `docs/implementation/AI_START_HERE.md` → `docs/design/EXECUTION_HARNESS_SPEC_2026-10-31.md` → Gateway 런북을 읽으세요. 최신 branch/commit/CI와 실제 작업경로를 확인하고 기존 변경을 보존하세요.
2. 이번 범위는 H01: Python3.12로 task/command registry 검증, allowlisted subprocess 실행, 구조화 테스트 결과/소스 hash 결속, 비공개 실행 기록, validate/run/verify/status CLI입니다. Codex 자동 호출·자동 다음 단계·운영 배포는 만들지 마세요.
3. 먼저 작은 설계 계약/예시 task와 위험·인수기준을 정리해 프로젝트 규칙에 맞는 독립 설계 검수를 받으세요. 필요한 경우 사용자에게 전체 설계를 다시 요구하지 말고 이 명세의 결정된 경계를 적용하세요.
4. 테스트 한 건이 실제로 실행되는 수직 기능부터 구현하세요. 성공·exit nonzero·0 tests·보고서 누락/다른 run·timeout·소스 변경·허용범위 위반을 임시 폴더에서 검증하세요. resume/외부 GO·CI 승격을 아직 구현하지 않았다면 명시 미지원/WAITING 상태를 반환하세요.
5. 기존 A01 날짜 실패의 baseline을 별도 기록하고 단일 회귀를 하네스로 실행하세요. 초기 H01에서 A01 제품 실패가 남으면 그대로 FAIL로 기록하세요. A01 수정과 전체 CI 완료는 H02 단계이며 H01 성공으로 A01 DONE을 만들지 마세요.
6. 테스트 명령과 판정 규칙을 모델 자유 출력에서 가져오지 마세요. task/registry/검증기는 신뢰된 기준 ref에서 고정하고, 구현자가 검증 결과를 위조할 수 있는 한계를 명시하세요. 실제 회사/RFP/인증 파일은 읽지 말고 합성 데이터 전용 경로를 사용하세요.
7. 실행 증거에는 명령·환경·exit/timeout·실행/실패/skip 수·SHA·산출물 hash와 상태를 기록하세요. `PASS` 문자열·Codex exit0·GitHub 파일 생성만으로 완료 판정하지 마세요. Windows 자식 종료가 검증되지 않으면 해당 adapter를 BLOCKED로 남기세요.
8. 루트/local_app README와 관련 설계·상태·작업 카드를 동기화하세요. 테스트·정적/문서 검사와 새 fresh-context 독립 Codex 검수 후 개발 브랜치/PR에 게시하고 같은 SHA의 CI를 확인하세요. 기존 CI 실패와 하네스 실패를 분리하세요. 임의 main 병합·운영 재시작·자동 스케줄·입찰은 하지 마세요.
9. 종료 시 실제 변경 파일/명령/결과/검수·CI 링크, NOT RUN/BLOCKED와 다음 H02 작업 하나를 보고하세요. 구체적인 접근/인증/도구 차단이 있으면 증거와 재개 조건을 남기고 가짜 성공으로 넘기지 마세요.

최소 인수 결과: 하네스 자체 합성 성공·실패 판정이 실제 실행으로 확인되고, A01의 현재 결과를 왜곡 없이 기록하며, 외부 게이트가 없는 상태에서 전체 작업 완료를 주장하지 않아야 합니다.
