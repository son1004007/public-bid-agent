> **구현 업데이트 2026-11-20:** [NAS Docker 실제 provider thread 재개 증거](AGW-NAS-SESSION-E2E-2026-11-20.md). `session_service.py` Django transaction/row lock + unique active binding + fencing token/expiry, 사용자 READY·현재 공고 버전, unknown side effect/timeout 시 RECOVERABLE 및 UUID 보존, mismatch 시 RESET_REQUIRED, 수동 안전확인 후 동일 UUID 재개 기능 구현. [Django 334 tests 포함 (Windows/Linux/PostgreSQL, Windows CDP 재실행 통과)](https://github.com/son1004007/public-bid-agent/actions/runs/44663410740). **DB 연계 모델 호출 worker, run revision, 운영 세션 볼륨 및 자동화 배포는 미구현.** 설계서 상태: CODE_PARTIAL, TESTED_IN_SYNTHETIC_DB, PRODUCT_WORKER_NOT_DONE.

# 장기 SessionBinding·Resume·신규 세션 전환

- 작업 ID: AGW-04
- 상태: DESIGN_READY / IMPLEMENTATION_NOT_STARTED (GitHub 문서만 작성)
- 범위: public-bid-agent AI Gateway 실행기 설계. 참조 [작업 목차](README.md), [상위 세션 설계](../../server-migration/16-user-cli-session-and-blind-cross-check.md).
- 실행 정책: 중앙 CONTROL 및 대상 AGENTS 우선, 실제 회사 자료·외부 호출·data1 운영 배포는 승인 이전 차단, 별도 AI 코드 리뷰는 선택·기능/보안/회귀 검사는 필수.

## 영속 세션 설계
- session owner key = (web_user_id, provider, notice_id, purpose=ANALYSIS|ISSUE_REVIEW). 기본 전략은 동일 사용자/공고/provider/purpose 기존 세션을 사용; 공급자별 서로 다른 session ID와 home을 사용합니다.
- 신규 공고/최초 분석은 첫 세션 1개를 생성. 이후 동일 공고의 질문/수정은 프로세스를 종료·재기동하더라도 저장 session_id로 Resume. 기존 RFP 정정은 session을 유지할 수 있으나 새 버전·바뀐 근거를 명시하고 이전 판정 stale 처리.
- 정상 상태 흐름 NEW → ACTIVE → PAUSED → RESUMING → ACTIVE → PAUSED, 문제 발생 시 RECOVERABLE 또는 RESET_REQUIRED. RESET_REQUIRED만 신규 session과 기존 session의 archive reason을 남깁니다.
- 인증 만료, 토큰 소진, 429, 5xx 또는 일시 네트워크 장애는 새 세션 트리거가 아니라 기존 session을 보존하고 복구 후 resume. session not found, 근거 오염, 잘못된 사용자/공고 결속, 보안 사고만 RESET_REQUIRED.
- 개인/기관 계약 만료는 SessionBinding 보존, 실행만 OFF.

## 동시성·데이터
- DB transaction에서 key unique와 lease owner/fencing token을 획득. 동일 세션에 동시 resume 요청 시 기존 Job 반환 또는 409; concurrent CLI 실행 금지.
- provider_session_id는 민감 메타데이터로 취급하여 일반 UI/API로 반환하지 않고 session owner·OS home·provider 일치를 매번 확인.
- 위임 워커가 종료되면 provider session transcript 보존하고 db JobAttempt에 종료 코드/작업 시각·해시만 기록. 출력·인증정보는 일반 로그에 저장하지 않습니다.
- 장기 대화 문맥 비용/오염을 제어: summary/delta 재입력 시 입력 토큰/한도 기록, context-too-long 처리 우선 사용자 경고, 정책 승인된 이슈라면 RESET_REQUIRED. 주기적 자동 reset으로 신뢰성 임의 저하 금지.

## 상태 전이 알고리즘
1. request/notice_version/policy/identity 검증.
2. session row 잠금 → existing active ID 있으면 RESUMING; 없으면 NEW.
3. worker는 제안된 provider CLI 옵션으로 단 한번 실행; 정상 결과를 정해진 스키마로 검사하여 run revision 저장.
4. 성공 시 동일 session id와 last_success 저장, lease 해제; 실패면 에러코드 분류 후 보존/RESET_REQUIRED. timeout 이후 중복 재실행 시 임의 유료 재호출 금지.

## 검증·완료
- 생성 1회/재개 3회에서 공급자 session ID 동일함, worker 재시작 후 Resume, 로그인 만료 후 재로그인/Resume, 다른 사용자 session ID 거부, race 중 하나만 실행, RFP 정정 후 기존 근거 stale.
- 계정·세션 저장소 손실 시 이전 결과 보존과 복구 플랜; CLI 도움말에 맞는 실제 resume E2E는 정책·환경 승인 후 별도로 기록.
- 기술 실행 참조: https://developers.openai.com/blog/codex-as-a-platform , https://code.claude.com/docs/en/cli-reference .

## 구현 의존성/다음 작업
- 이 문서는 모듈 단위 설계이며 실제 엔드포인트·DB schema·CLI 명령이 구현된 상태를 주장하지 않습니다. 바뀐 계약/버전은 구현 시 증거와 함께 이 문서를 갱신합니다.
- 다음 작업은 [AGW 작업 인덱스](README.md)의 선행 의존 관계와 기존 [HBR 작업 원장](../../../TASKS.md)을 따릅니다.
