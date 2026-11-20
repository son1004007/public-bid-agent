> **실제 연결 우선 (2026-11-20):** 코드/합성 테스트 뒤 무기한 HOLD가 아니라, 허용된 사용자 인증·격리 환경/회사 반출 조건이 확인되면 가장 먼저 **공개 RFP 1건을 실제 유료 Codex 모델로 실행하여 JSON + 동일 세션 resume**까지 E2E한다. 제품 통합에는 `codex exec`만 고집하지 않고 공식 SDK/app-server가 세션 관리에 더 유리할 수 있으므로 검증된 통합 방식을 선택한다. 최소 품질 gate는 run_id·공고 버전·evidence ID 검증. 승인 없는 company data1 설치는 여전히 보류.

> **2026-11-20 실제 실행 증거:** [AGW 실행 기록](AGW-RUN-2026-11-20.md). Windows 개인 CLI `codex-cli 0.166.0`, 사용자 인증 확인 후 합성 공고를 유료 모델로 분석해 `NOT_MET` JSON 생성 및 **동일 thread UUID로 resume 성공**. 실제 사용된 안전 호출 계약: 시작 `codex exec --skip-git-repo-check --sandbox read-only --json -C <isolated-dir> -`, 재개 `codex --sandbox read-only exec resume --skip-git-repo-check --json <verified-session-uuid> -`. **Windows PowerShell/npm은 공백 포함 prompt를 직접 argv로 넘길 때 인수 분할 위험** → stdin(`-`) 사용. `--sandbox`는 resume 서브명령 옵션이 아니라 최상위 위치에 배치. [실제 구현](../../../server/ai_gateway_core/codex_cli.py), [mock 회귀](../../../server/tests/test_codex_adapter.py), [CI](https://github.com/son1004007/public-bid-agent/actions/runs/44659013489). 단, 코드는 승인된 격리 OS runner와 user-to-session DB binding을 요구하며 **서버 자체 E2E는 미완료**.

# Codex CLI 전용 실행·JSON·Resume Adapter

- 작업 ID: AGW-06
- 상태: DESIGN_READY / IMPLEMENTATION_NOT_STARTED
- 우선순위: P0; 선행 작업과 승인 조건은 [AGW 목차](README.md) 참조.
- 기존 연계: [HBR 원장](../../../TASKS.md), [사용자별 세션/교차 검증](../../server-migration/16-user-cli-session-and-blind-cross-check.md), [전역 보안·계약](../../server-migration/15-mcp-provider-executor-subscription-policy.md).
- 범위: 합성·공개 RFP와 격리 환경에서 코드/테스트 가능; 실제 CLI 로그인·회사 데이터 외부 전송·유료 모델·data1 배포는 별도 적격성·승인 전 OFF.

## 목표
Codex 프로필이 READY인 경우 사용자 전용 공식 Codex runtime에서 승인된 AnalysisRequestV1을 실행하고, 기존 SessionBinding을 우선 Resume합니다. Claude와 어댑터/홈/세션 ID를 공유하지 않습니다.

## 제안 모듈(아직 미구현)
- server/ai_gateway/adapters/base.py: ProviderAdapter(protocol)에서 check_capabilities, verify_ready, start, resume, cancel, parse_result.
- server/ai_gateway/adapters/codex.py: CodexAdapter; 버전별 capability manifest/로그 이벤트 파서.
- server/ai_gateway/runner/subprocess.py: sandbox worker에서 명령 allowlist 및 stdout size/time 제한, terminal/event 분리.

## 구현 순서/실행 계약
1. 사용자 OS sandbox에서 codex --version, codex exec --help, codex exec resume --help, codex login status를 확인하고 설치 버전에 맞는 명령 벡터를 고정(사용자 입력으로 옵션 조합 불허).
2. 초기 세션 start: 공식 codex exec의 구조화 출력 옵션(예: --json, --output-schema)을 해당 버전에서 확인하고, 정상 종료 이벤트로 provider session ID를 추출해 SessionBinding에 저장합니다. stdout JSONL 이벤트를 최종 결과 단일 객체와 혼동하지 않습니다.
3. 후속 실행 resume: SessionBinding의 ID가 해당 사용자/공고/목적/OS sandbox와 일치하는지 확인 후 codex exec resume <verified_session_id> 형태로 실행. **resume 시 출력 schema 옵션 지원 여부는 해당 설치 버전 --help로 확인**; 미지원이면 출력 사후 strict schema validator 사용.
4. 결과 event stream에서 마지막 완료 assistant result와 실제 turn terminal status, usage, token estimate, model identity, elapsed, exit code를 분리. 중간 tool text/log는 결과 JSON이 아닙니다.
5. 모든 workspace는 읽기 전용 evidence packet, 도구 사용 금지/제한, sandbox 정책을 적용. 개발 repo를 부여하지 않고 코드 실행/쓰기 권한 최소화.
6. 성공 결과 JSON→AGW-09; CLI 401/auth 오류→AUTH_REQUIRED, 429→QUOTA_LIMITED, session unavailable→AGW-04 RESET_REQUIRED, network/timeout→RECOVERABLE 보존; 이미 전송한 요청은 재시도 전 결과 존재를 검증합니다.

## 위험 대응
- Codex 프로세스가 성공 exit=0이지만 최종 JSON 부재: INVALID_RESULT로 보존·담당자 검토, 다음 공급자로 자동 fallback 하지 않음.
- 출력에 토큰/숨김 파일 경로/프롬프트 전체: scrub before logging; 원본 stdout을 공용 로그에 보존하지 않음.
- 세션 간 공고 혼입: 보존 키와 snapshot ID 검증, 다른 공고 접근 거부.
- 설치 CLI가 undocumented flags를 거부: 공식 문서/실측 기준 범위 축소; sandbox 무력화 옵션으로 우회하지 않음.
- 유료 요청 중 timeout/중복 retry: original attempt fence+provider execution reference를 찾고 중복 호출 전에 명시 승인.

## 인수
- mocked CLI 두 번 실행 후 동일 세션 ID resume, 최초 실행 ID 캡처, JSONL 파서의 intermediate event 무시, 잘못된 출력/인증 오류/429/timeout 분기, user A/B 격리.
- 승인된 테스트 계정으로 실제 공개 RFP+합성 역량 데이터 E2E 검증 전에는 REAL_CONNECTED 표기 금지.
- 공식 기술 자료: https://developers.openai.com/blog/codex-as-a-platform .

## 구현 시 변경 금지·증거
- 기존 실행기/임베딩/입찰 원본·회사 계정/사업부 집계 원가 정책/보안 차단은 보존합니다. 기능 개발 후 테스트 로그, 해당 commit SHA, 정책 승인/실제 실행 범위를 CURRENT_STATE.md에 기록합니다.
- 세부 코드 위치는 신규 server/ai_gateway 후보이며, 코드 구현 시 기존 app/serializer·작업 원장과 중복되지 않도록 실제 저장소를 재검토합니다.
