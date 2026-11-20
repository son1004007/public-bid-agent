> **실제 연결 우선 (2026-11-20):** 사용자 유료 호출 허용을 반영하여 다른 provider의 전체 mock/DB/UI 작업이 끝날 때까지 미루지 않는다. **Anthropic Commercial Terms를 충족하고 각 최종 사용자가 미변조 CLI에 직접 인증한 호스팅 경로** 또는 회사가 허용한 개별 사용자 API key 경로가 확보되면 즉시 **공개 RFP 실제 Claude 결과 JSON + 동일 세션 resume** E2E를 추진한다. 공식 [Claude 법무 정책](https://code.claude.com/docs/en/legal-and-compliance)상 제3자 제품이 소비자 계정 인증정보를 받아 사용자를 대신 중계하는 방식은 불허. 회사 실자료 전송/IDC 배포는 별도 승인.

# Claude Code 공식 CLI 실행·JSON·Resume Adapter

- 작업 ID: AGW-07
- 상태: DESIGN_READY / IMPLEMENTATION_NOT_STARTED
- 우선순위: P0; 선행 작업과 승인 조건은 [AGW 목차](README.md) 참조.
- 기존 연계: [HBR 원장](../../../TASKS.md), [사용자별 세션/교차 검증](../../server-migration/16-user-cli-session-and-blind-cross-check.md), [전역 보안·계약](../../server-migration/15-mcp-provider-executor-subscription-policy.md).
- 범위: 합성·공개 RFP와 격리 환경에서 코드/테스트 가능; 실제 CLI 로그인·회사 데이터 외부 전송·유료 모델·data1 배포는 별도 적격성·승인 전 OFF.

## 목표
Claude 사용자 계정을 해당 사용자가 공식 미변조 Claude Code에서 직접 인증하고, 승인된 실행 경로에서 비대화형 출력 JSON/이전 session resume을 구현합니다. 개인 Pro/Max 인증으로 다른 사용자 요청을 중계하는 설계는 제외합니다.

## 제안 모듈
- server/ai_gateway/adapters/claude.py: ClaudeCodeAdapter; native_cli_enabled, capability version, output parser.
- 공통 provider interface(AGW-06)는 사용하되, 프롬프트/세션/명령·사용량·error token을 Codex와 혼용하지 않습니다.

## 구현 계약
1. 격리 sandbox의 실제 claude --version, claude --help, claude auth --help, claude auth status 확인. 사용자 본인의 공식 로그인 흐름이 완료됐음을 출력 status에서 확인하되 token/쿠키를 앱으로 전달하지 않습니다.
2. 비대화형 호출은 공식 claude -p, --output-format json/stream-json, --json-schema 지원을 설치 버전에서 확인. 구조화 결과의 래퍼(result/session_id/usage 등)와 model JSON(payload)을 분리하고, 출력 크기 상한을 적용.
3. 기존 session이 있으면 claude -p --resume <verified_session_id> 형식의 지원 옵션으로 후속 turn 실행. 최초 수행 때 생성 session_id와 출력 run reference를 별도 저장. 같은 공고/사용자/목적 범위만 재개.
4. Claude Code가 tool use 권한 승인을 요청하더라도 AI 분석용 환경에서는 shell/파일수정/network/MCP 임의 도구 권한을 부여하지 않음. --dangerously-skip-permissions 등 보안 완화 플래그는 사용 금지.
5. 실행 종료에 따른 상태: AUTH_REQUIRED/QUOTA_LIMITED/RATE_LIMITED/POLICY_BLOCKED/SESSION_MISSING/INVALID_OUTPUT/TIMEOUT/UNKNOWN. 각 상태에서 원래 session record를 보존하고 상태 전이를 AGW-04에 통보. UNKNOWN 오류에서 무조건 새 session 시작 금지.

## 사전 위험
- CI stdin 불일치나 interactive login prompt가 발생하면 사용자에게 공식 인증 단계로 안내하고 worker 스레드를 무기한 점유하지 않음.
- 사용자 session ID를 공급자가 지역 CLI 저장소에 연결하는 구현은 HOME/작업 경로 영향을 받을 수 있으므로 동일 sandbox/home에서 재개 테스트.
- 공급자 CLI가 JSON schema 지원하더라도 서버 검증(AGW-09)은 필수; invalid JSON을 응답 text로 승격하지 않음.
- Claude 앱 법적 허용: 공식 Anthropic 문서는 end user의 미변조 CLI 직접 로그인과 제3자 플랫폼의 개인 인증정보 중계 금지를 구분합니다. 이 서비스에 해당하는 허용 범위를 AGW-00에서 확인하기 전 실행 OFF.

## 인수
- mock 1st call/2nd call same session, JSON wrapper 및 schema 불일치, 401/429/timeout, 독립 workdir, 프로세스 재시작 후 --resume 성공.
- 개인 token 교환/공용 저장/다른 사용자 session 재사용 시 negative tests pass; 합성 데이터 전용.
- 공식 문서: https://code.claude.com/docs/en/legal-and-compliance , https://code.claude.com/docs/en/cli-reference , https://code.claude.com/docs/en/cli-usage .

## 구현 시 변경 금지·증거
- 기존 실행기/임베딩/입찰 원본·회사 계정/사업부 집계 원가 정책/보안 차단은 보존합니다. 기능 개발 후 테스트 로그, 해당 commit SHA, 정책 승인/실제 실행 범위를 CURRENT_STATE.md에 기록합니다.
- 세부 코드 위치는 신규 server/ai_gateway 후보이며, 코드 구현 시 기존 app/serializer·작업 원장과 중복되지 않도록 실제 저장소를 재검토합니다.
