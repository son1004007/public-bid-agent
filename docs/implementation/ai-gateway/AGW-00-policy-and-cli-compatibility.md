> **최신 개발 목적/우선순위 (2026-11-20):** 사용자에게 유료 모델 비용 허용을 받았으므로 **회사·공급자별 이용 적격성이 확인되는 최초 provider 실제 유료 E2E를 가능한 한 먼저 수행한다.** '비용 절감을 위한 수동 JSON만 허용'으로 불필요하게 지연시키지 않는다. 승인 조건을 만족하지 못하면 그 provider 실호출만 BLOCKED로 명시하고 다른 안전한 코드 개발을 병행한다. 공개 RFP+합성 데이터 1차 테스트, user-confirmed account, 제한된 실행 횟수/금액/timeout, 결과 JSON 및 이어쓰기 resume가 수용 기준이다. 사용자 비용 허용은 회사 기밀 반출·무한 과금·구독 중계 면책이 아니다.

**2026-11-20 공식 재검증:** OpenAI 공식 [Codex as a platform](https://developers.openai.com/blog/codex-as-a-platform)은 `codex exec`(단발 구조화), SDK(시작/resume/stream), app-server(제품 내 제어)를 지원한다. Anthropic [Claude Code legal](https://code.claude.com/docs/en/legal-and-compliance)은 제품에서 변조 없는 Claude Code 호스팅 시 Commercial Terms 준수 및 각 사용자 본인 계정/개별 과금을 요구하고, 소비자 계정으로 다른 사용자 요청을 중계하는 것은 불허한다. [Claude CLI reference](https://code.claude.com/docs/en/cli-reference)에서 `claude -p`, `claude auth status`, `-r` 재개 확인. 최종 선택 전 해당 설치 버전 `--help`와 회사 계약/권한·서버 실측 확인 필수.

# 계약·공식 CLI 호환성·실행 승인

- 작업 ID: AGW-00
- 상태: DESIGN_READY / IMPLEMENTATION_NOT_STARTED (GitHub 문서만 작성)
- 범위: public-bid-agent AI Gateway 실행기 설계. 참조 [작업 목차](README.md), [상위 세션 설계](../../server-migration/16-user-cli-session-and-blind-cross-check.md).
- 실행 정책: 중앙 CONTROL 및 대상 AGENTS 우선, 실제 회사 자료·외부 호출·data1 운영 배포는 승인 이전 차단, 별도 AI 코드 리뷰는 선택·기능/보안/회귀 검사는 필수.

## 목적 및 결정 게이트
- 서버에 Codex/Claude Code를 설치해 사용자별로 직접 로그인, 분석 및 resume하려는 요구를 공급자 공식 정책과 분리해 점검합니다.
- 정책/회사 승인 미확인은 POLICY_BLOCKED이며, 등록/CLI 설치/로그인 성공을 READY로 판정하지 않습니다. 소비자 계정 로그인 토큰을 애플리케이션이 읽거나 다른 사용자 대신 중계하지 않습니다.
- 기본 실행 경로는 승인된 본인 공식 CLI 호스팅 또는 적합한 기업·API 계약이며, 수동 JSON 가져오기는 별도의 비용 절감 대안입니다. Google AGY/Gemini 자동 위임은 중지 상태를 유지합니다.

## 상세 작업 순서
1. Codex와 Claude 각각 인증 방법(공식 CLI 사용자 직접 로그인), 회사 제품 내 제공 가능 여부, 개인/기업 구독의 재사용 조건, API 대체 경로, 허용 데이터 유형, 청구/쿼터, 출력 구조, 세션 resume, 라이선스·감사 보관 정책을 행렬로 기록합니다.
2. 설치 대상 OS·CLI 버전·명령을 읽기 전용으로 확인한 뒤 로그인·비대화형 호출·resume 옵션을 공식 문서 및 실제 --help에서 대조합니다. 확인하지 못한 명령은 IMPLEMENTATION_UNKNOWN입니다.
3. 사내 승인 담당자, 승인 문서 식별자, 적용 사용자 범위, 공급자별 외부 데이터 분류, 계약 만료·취소 조건을 비밀 없는 정책 레코드로 관리합니다.
4. 빌드 시 allowlist(PROVIDER_EXECUTION_ALLOWED)가 없거나 회사 실자료 전송 승인이 없으면 CLI 모델 요청 0건. 정책 취소는 대기 작업을 중단하고 세션 ID/기존 결과를 보존합니다.
5. company data = false로 분류된 공개 공고·합성 RFP만 독립 실험 허용할지 명시적으로 결정합니다. 공급자 로그·훈련·보관 옵션과 GDPR/기밀 조항은 계약 검토 대상으로 남깁니다.

## 기술 계약
- policy manifest 필드: provider, plan_class, access_mode(SELF_LOGIN_CLI / ENTERPRISE_API / DISABLED), data_class_allowlist, policy_state(UNKNOWN/ALLOWED/DENIED), approval_ref, verified_cli_version, checked_at.
- 원장에 토큰/비밀번호/쿠키/OAuth 코드 및 회사 원문을 기록하지 않습니다.
- 사전 조건: 조직 지침과 합치지 않는 provider mode는 자동으로 차단합니다.

## 실패·보안 선제 대응
- 로그인만 성공했으나 계약 범위가 불명확: POLICY_BLOCKED.
- CLI 버전마다 인수/출력 필드 상이: pin 또는 adapter 분기, 근거 없는 fallback 금지.
- 사용량 한도와 신규 과금 발생: 사용자 승인 없는 API 키 변경·타 계정 전환 없음.
- 공급자 도구가 임의 코드를 실행할 위험: AGW-02 sandbox 승인 전 모델 실행 금지.

## 검증/완료 기준
- 0/1/2 profile 정책 행렬 단위 테스트, 거부 시 egress 0, 정책 취소 후 대기 작업 차단.
- 공식 출처/최종 확인일/CLI --help 실제 증거/회사 승인을 별도로 기록합니다. 공급자 허용이 확인되지 않으면 본 카드 완료는 POLICY_RESEARCH_DONE으로만 표기하고 실제 로그인 게이트는 BLOCKED로 유지합니다.
- 공식 문서: https://code.claude.com/docs/en/legal-and-compliance , https://code.claude.com/docs/en/cli-reference , https://developers.openai.com/blog/codex-as-a-platform .

## 구현 의존성/다음 작업
- 이 문서는 모듈 단위 설계이며 실제 엔드포인트·DB schema·CLI 명령이 구현된 상태를 주장하지 않습니다. 바뀐 계약/버전은 구현 시 증거와 함께 이 문서를 갱신합니다.
- 다음 작업은 [AGW 작업 인덱스](README.md)의 선행 의존 관계와 기존 [HBR 작업 원장](../../../TASKS.md)을 따릅니다.
