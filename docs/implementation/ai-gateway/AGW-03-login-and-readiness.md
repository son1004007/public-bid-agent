# 공식 CLI 사용자별 로그인·등록/가용성 상태

- 작업 ID: AGW-03
- 상태: DESIGN_READY / IMPLEMENTATION_NOT_STARTED (GitHub 문서만 작성)
- 범위: public-bid-agent AI Gateway 실행기 설계. 참조 [작업 목차](README.md), [상위 세션 설계](../../server-migration/16-user-cli-session-and-blind-cross-check.md).
- 실행 정책: 중앙 CONTROL 및 대상 AGENTS 우선, 실제 회사 자료·외부 호출·data1 운영 배포는 승인 이전 차단, 별도 AI 코드 리뷰는 선택·기능/보안/회귀 검사는 필수.

## 사용자 흐름
1. 기존 업무 계정으로 웹 로그인/최초 비밀번호 변경을 완료합니다.
2. AI 설정에 Codex·Claude Code가 별도 표기되고 서버 런타임/정책이 허용된 공급자만 '공식 CLI 로그인' 안내를 제공.
3. 사용자가 자신에게 매핑된 OS sandbox의 **미변조 공식 CLI**에서 직접 공급자 인증 절차를 수행합니다. 웹 앱은 공급자 비밀번호·OAuth code/token·쿠키를 수신/중계/저장하지 않습니다.
4. 공급자 CLI의 비민감 status 명령과 현재 계정 및 정책/모델 접근성·한도를 확인해 ProviderIdentity를 갱신. CLI 설치·로그인 성공만으로 READY 확정하지 않습니다.
5. 로그아웃/권한 철회/구독 만료는 READY에서 제외하지만 기존 세션 저장소를 임의 삭제하지 않습니다.

## 상태 머신
NOT_REGISTERED → REGISTERED_DISABLED → AUTH_REQUIRED → AUTHENTICATED_UNVERIFIED → READY.
예외: POLICY_BLOCKED, CLI_MISSING, QUOTA_LIMITED, UNAVAILABLE; 재인증/계약 복구 시 READINESS 재검증.
READY = enabled AND policy_allowed AND auth_verified AND runtime_isolated AND data_class_allowed AND recent_executable_probe. 미확인 항목 하나라도 FALSE/UNKNOWN이면 READY 불가.
- 가용성은 요청 직전 다시 확인하고, 실행 중 401/403/429/토큰 변경 이벤트 발생 시 즉시 상태 강등.
- 'readiness status' 응답은 provider, state, reason_code, checked_at, execution_mode, user_enabled만 반환합니다.

## 공식 CLI 인터페이스 검증 절차
- Codex: 설치 CLI의 codex --version, codex login --help, codex login status, codex exec --help, codex exec resume --help를 읽고 정확한 옵션/exit/로그 노출 정책 확정.
- Claude: claude --version, claude auth --help, claude auth status, claude --help에서 login/--resume/--output-format/--json-schema 옵션 확인. stdout 파서는 공급자별로 격리.
- 공급자마다 버전/OS가 다르면 확인된 바이너리 해시에 묶인 capability manifest를 사용하고 미확인 옵션은 쓰지 않습니다.

## 오류·보안·테스트
- 회원 A의 로그인 요청에서 회원 B의 OS identity 사용 불가. stdout에 token이 포함되면 저장/응답하지 않고 즉시 보안 이벤트로 처리.
- 인증 만료는 AUTH_REQUIRED, quota 오류 QUOTA_LIMITED, 계약/비공개 자료 전송 불허 POLICY_BLOCKED, 런타임 사망 UNAVAILABLE. 다른 공급자로 무단 fallback 금지.
- 합성 status fixture 각 상태/expiration/policy revoke, 올바른 0/1/2 READY 산출, 실제 binary별 호환 read-only probe.
- 진짜 로그인·외부 모델 invocation은 AGW-00 이용 계약·AGW-02 인프라 승인을 충족한 환경에서만 사용자 본인이 수행. 그 전 화면은 mock 또는 비활성 상태로만 검증합니다.

## 구현 의존성/다음 작업
- 이 문서는 모듈 단위 설계이며 실제 엔드포인트·DB schema·CLI 명령이 구현된 상태를 주장하지 않습니다. 바뀐 계약/버전은 구현 시 증거와 함께 이 문서를 갱신합니다.
- 다음 작업은 [AGW 작업 인덱스](README.md)의 선행 의존 관계와 기존 [HBR 작업 원장](../../../TASKS.md)을 따릅니다.
