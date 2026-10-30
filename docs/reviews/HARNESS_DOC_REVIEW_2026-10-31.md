# 하네스 명세·실행 안내 검수 기록

- 기준: `0892b35e558f250474368f79db7ef77d4c295646`, 2026-10-31 KST.
- 사용자 요청: 하네스가 작업 정의/실행기/검증기/실행 기록을 확인하는 방법을 설명·문서화해 GitHub에 게시하고 Gateway→노트북 Codex 구현 방법을 안내.
- 범위: 새 명세/런북/프롬프트 3개, 기존 진입 안내/상태 문서 7개. 하네스 코드·제품 기능 구현 없음.
- 독립 검수: `/root/harness_design_review`, Codex fresh-context/read-only. 사용자 원문 범위·baseline·고정 diff/새 문서·기존 정책·실제 Gateway 관측/공식 문서 확인 범위를 제공하고 결론을 지정하지 않았다.
- 결과: **GO (설계·문서 게시)**, BLOCKER0/MAJOR0/MINOR1. 제품 테스트 통과/노트북 모델 실행 성공/운영 배포 승인 아님.

## 확인 근거

부모 작업자는 공식 OpenAI noninteractive 문서와 노트북 `codex exec --help`를 대조했다. Gateway 버전/도움말 조회 성공, 별도 인증 조회 timeout·종료 미확인, 후속 기존 프로세스 읽기 전용 점검 성공을 런북에 그대로 기록했다. 모델 요청/인증 파일 조회/프로세스 종료/운영 변경은 하지 않았다.

독립 검수자는 신뢰된 ref의 정책/registry, 소스/검사/독립 검수/CI 증거 결속, 단일 사용자 hash 위조 한계, timeout/재개 경계, H01/H02/H03 의존성, 목표 CLI와 실제 검증 범위 구분을 확인했다. Gateway 관측은 부모가 제공한 증거이며 독립 모델/Windows 실행을 재수행한 것은 아니다.

MINOR: 실행기 `FAILED`와 미승인 정답의 `BLOCKED_EVIDENCE`가 하네스 상태 enum과 혼동될 여지. 실행기 실패를 `VERIFY_FAILED`, 미승인 정답을 상태 `WAITING_HUMAN`/사유 `BLOCKED_EVIDENCE`로 구분해 수정했다.

동일 독립 검수자가 변경된 명세 hash를 재확인하여 MINOR 종료·GO 유지, 미해결 지적0을 확인했다.

최종 명세 SHA-256: `7ba0545359a53565e8c30fe11cb14de6ad63f804ab3e9ab737542053823bd4e5`.
런북: `018a99dfadf2f3315bbef2a82b7e4e612a45f88fb818f982e6adddba366ddee3`.
프롬프트: `6d1aafdebe65c364f7e3219a6a8e2e8126d38889d8e594e019933796d99dfa7d`.

문서 확인: diff 공백 검사, 상대 링크 대상 존재, JSON 예시 구문 검사 PASS. 이는 하네스 구현 테스트가 아니다. 이 검수 결과 기록 자체는 최초 10개 검수 대상 밖에서 결과를 기록한 문서다. 게시 SHA는 GitHub commit 이력으로 확인한다.
