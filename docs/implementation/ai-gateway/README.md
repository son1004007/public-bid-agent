> **2026-11-20 NAS P0 실제 Docker 재개/코드:** [AGW NAS Docker 2회 실모델·동일 session Resume 및 SessionLease 구현 기록](AGW-NAS-SESSION-E2E-2026-11-20.md). 개인 `son1004007` CLI 인증으로 각기 다른 Docker 컨테이너에서 **같은 session** 성공. [`session_service.py`](../../../server/bid_server/ai_gateway/session_service.py)의 DB session fence/timeout/복구, [`nas_docker_codex.py`](../../../server/ai_gateway_core/nas_docker_codex.py)의 UID/전용 홈+RO Docker 고정 argv 구현. 기본 3개 런타임 안전 게이트 미승인 시 실제 제품 호출 OFF. [AGW core 50 tests PASS](https://github.com/son1004007/public-bid-agent/actions/runs/44663410679); Server foundation Windows/Linux/PostgreSQL 334건씩 PASS (Windows CDP 1차 실패 후 재실행 성공). 차기 AGW-05/09 evidence/revision + Job dispatcher.

> **2026-11-20 사용자 최신 우선순위 (기존 mock-first 대체):** 유료 Codex/Claude 실호출을 허용하고 **빠른 실제 E2E·정확도 검증을 우선**한다. P0은 AGW-00 공식 이용·호환 확인/AGW-02 안전 격리와 병행하여 **첫 번째 허용 provider 실제 유료 요청→JSON→resume**을 조기 검증하는 것. 그다음 두 번째 provider 실제 요청 및 독립 교차 검증. 기존 '모든 합성 기능 완성 후 실호출'은 과거 백업 경로다. 회사 자료 외부 전송, CLI 구독 중계, data1 운영 배포는 기존 계약/보안 승인 필수. 테스트 코어: [server/ai_gateway_core](../../../server/ai_gateway_core), [코어 회귀 15건](../../../server/tests/test_ai_gateway_core.py), [CI](../../../.github/workflows/ai-gateway-core.yml). 이 문장은 이전 계획 기준입니다. **최신 실호출·Resume PASS는 최상단 NAS 2컨테이너 실측 기록을 우선**합니다.

> **2026-11-20 P0 실제 개발/실측 최신:** [AGW 첫 실행 결과와 검증 로그](AGW-RUN-2026-11-20.md) 참조. 사용자 개인 Windows Codex 0.166.0에서 **실제 모델 JSON 요청 + 동일 세션 Resume 성공**. `server/ai_gateway_core/codex_cli.py`의 코드/테스트 및 `server/bid_server/ai_gateway`의 Django ProviderProfile/SessionBinding/GET /api/v1/ai/providers 코드·migration 추가. [AGW core CI 35건](https://github.com/son1004007/public-bid-agent/actions/runs/44659013489), [Server foundation Linux/Windows/PostgreSQL 303건씩](https://github.com/son1004007/public-bid-agent/actions/runs/44659013442) PASS. **서비스 사용자별 CLI 로그인/OS 격리 실행기/실제 자동 분석 요청·회사 data1 배포는 여전히 미완료.** 기존 '전체 구현 미착수/모의 테스트만' 문구는 최신 NAS/Django 코드와 실측에 의해 대체되며, 아래 계획표는 선행조건 순서 참고용이다. 상태 정본은 [TASKS](../../../TASKS.md)/[CURRENT_STATE](../../../CURRENT_STATE.md).

# AI Gateway / Codex·Claude Code 구현 작업 단위 인덱스

- 기준일: 2026-11-20 KST
- 상태: **16개 카드 설계 작성 / Codex Adapter·Django 사용자별 SessionBinding·NAS Docker 실모델 재개 CODE_PARTIAL / 사용자별 정식 로그인 UX·자동 분석 API·data1 배포 NOT_DONE**
- 소유 저장소: son1004007/public-bid-agent
- 최상위 작업 원장: [TASKS.md](../../../TASKS.md), 실제 코드·CI·런타임 상태: [CURRENT_STATE.md](../../../CURRENT_STATE.md)
- 작업 브랜치: [Draft PR #5](https://github.com/son1004007/public-bid-agent/pull/5), fix/bid-security-20261116
- 전역 진입점: [Global CONTROL](https://github.com/son1004007/ai-agent-workflow-playbook/blob/main/CONTROL.md) → [registry](https://github.com/son1004007/ai-agent-workflow-playbook/blob/main/config/repositories.yml) → [local AGENTS](../../../AGENTS.md) → [DECISIONS](../../../DECISIONS.md) → CURRENT_STATE / TASKS → 이 문서 → 대상 작업 카드.
- 배경 기술: [공급자 구독/MCP 정책](../../server-migration/15-mcp-provider-executor-subscription-policy.md), [사용자별 CLI 세션·교차 검증 최신 정본](../../server-migration/16-user-cli-session-and-blind-cross-check.md), [서버 데이터/작업 모델](../../server-migration/05-data-api-jobs.md), [HBR RAG 설계](../../server-migration/10-hybrid-rag-bid-decision.md).

## 확정 요구 및 설계 원칙

- 서버의 각 업무 사용자가 **자기 Codex·Claude Code 공급자 계정에 공식 CLI에서 직접 로그인**한 뒤에만 가용성 판정. 웹 앱이 해당 공급자의 password/OAuth token/cookie를 수집·중계하거나 계정을 공유하지 않습니다.
- 사용 가능 0개=NO_AI(RAG/SQL), 1개=SINGLE, 2개=두 AI **각자의 기존 ANALYSIS 세션을 resume한 독립 분석** 후 구조적 근거 비교. 1개 실패 시 DEGRADED_SINGLE을 교차 검증 PASS로 표기하지 않습니다.
- **정확도 우선 설계:** 1차에는 상대의 대화·답변을 보지 않음. 서버가 requirement/evidence/참가자격/가용 MM/집계 원가를 검산. 불일치 이슈에만 별도 ISSUE_REVIEW 세션에서 필요한 주장·근거를 최소 공유하며 기존 ANALYSIS 세션은 수정하지 않음.
- 세션 보존이 기본이며 CLI 프로세스는 작업마다 bounded 실행. 사용자×provider×공고×목적별 SessionBinding에 기록. **새 세션은 최초 작업·기존 세션 분실/오염 등 정당한 상황에서만** 생성. 인증 만료·429·네트워크 오류는 기존 ID 보관 후 복구.
- **실제 회사 자료/개인 구독으로 회사 공용 요청을 중계하는 구현은 금지**. 공급자/사내 계약 허용 및 data1 workspace/보안/외부 반출 승인 전까지 자동 모델 호출·로그인·운영 설치는 OFF. 합성 데이터/isolated runner/mock 기능 설계와 테스트는 진행 가능.
- Google AGY/Gemini 신규 자동 위임은 전역 Control의 중지 정책 유지. 개발 과정 독립 AI 리뷰는 선택이지만 보안·기능·회귀 및 조직 승인·사람 입찰 결정은 필수.

## 작업 카드 / 개발 순서 / 선행 조건

각 카드에는 **설계·기술·데이터 계약·정상/실패 흐름·보안·테스트·종료 기준**을 기록합니다. 실제 상태 변경은 항상 TASKS와 CURRENT_STATE를 먼저 갱신합니다.

| ID | 우선 | 카드 | 주요 선행/의존 | 연계 업무 |
| --- | --- | --- | --- | --- |
| AGW-00 | P0 / 실사용 HOLD | [계약·CLI 옵션·인증 사용 적격성](AGW-00-policy-and-cli-compatibility.md) | CONTROL/공식 문서/회사 승인 범위 | HBR-04/08 |
| AGW-15 | P0 | [모델·API·JSON·상태 전이 공통 구현 계약](AGW-15-implementation-contracts.md) | 기존 Django models/SM03/SM05 확인 | HBR-04/06 |
| AGW-01 | P0 | [관계형 데이터 모델 / RBAC / DRF API](AGW-01-data-model-and-apis.md) | AGW-15, 기존 세션/업무 ACL | HBR-04/06 |
| AGW-02 | P0 설계 / IDC HOLD | [웹 사용자별 CLI OS·권한·네트워크 격리](AGW-02-user-cli-sandbox.md) | AGW-00, AGW-01, IDC workspace 승인 | HBR-04/08 |
| AGW-03 | P0 모의 / 실로그인 HOLD | [Codex·Claude 별도 로그인/가용성 판정](AGW-03-login-and-readiness.md) | AGW-00/01/02; 모의 상태는 선행 개발 가능 | HBR-04/06 |
| AGW-04 | P0 | [SessionBinding / resume / lock·lease](AGW-04-session-binding-and-resume.md) | AGW-01/02, AGW-03 mock | HBR-04 |
| AGW-05 | P0 | [공개 RFP·회사 정책 범위의 evidence packet/JSON schema](AGW-05-evidence-packet-and-json-schema.md) | HBR-01/02/03 데이터 계약, AGW-15 | HBR-04 |
| AGW-06 | P0 mock / 실제 HOLD | [Codex CLI 실행·출력·resume Adapter](AGW-06-codex-executor-adapter.md) | AGW-02~05, 공급자 허용 | HBR-04 |
| AGW-07 | P0 mock / 실제 HOLD | [Claude Code CLI 실행·출력·resume Adapter](AGW-07-claude-executor-adapter.md) | AGW-02~05, 공급자 허용 | HBR-04 |
| AGW-08 | P0 | [0/1/2 READY 라우팅·Celery/outbox·실행 분기](AGW-08-condition-router-and-jobs.md) | AGW-01/03~07/09 | HBR-04/06 |
| AGW-09 | P0 | [JSON 스키마·근거 검증·불변 결과 저장](AGW-09-result-json-and-immutability.md) | AGW-01/05/15 | HBR-04 |
| AGW-10 | P0 | [독립 분석 간 결정론적 교차 검증](AGW-10-evidence-first-cross-validation.md) | AGW-05/08/09, HBR-03 정형 facts | HBR-04 |
| AGW-11 | P1 | [불일치 이슈·별도 세션 1회 재검증](AGW-11-disagreement-issue-session.md) | AGW-04/09/10, 정보 제공 동의 | HBR-04/06 |
| AGW-12 | P1 | [React 공급자 로그인 상태·분석·근거 비교 화면](AGW-12-web-ui-and-user-flow.md) | AGW-01/03/08~11, 사용자 검토 | HBR-06 |
| AGW-13 | P1 설계 / data1 HOLD | [CI/격리 staging/운영 승인·배포·복구](AGW-13-ci-security-deploy-and-rollback.md) | 보안/정책/기능 검증/별도 회사 승인 | HBR-08 |
| AGW-14 | P1 | [법적 참가자격·근거 정확도/지연/비용 성능평가](AGW-14-accuracy-and-latency-evaluation.md) | AGW-09/10/11, 독립 RFP gold | HBR-04/08 |

### 구현 가능한 세로 슬라이스 순서

1. **첫 합성 MVP:** AGW-15 → 01 → 05 → 09 → AGW-03(등록/READY mock) → AGW-04(mock resume) → 08(mock 0/1/2) → 10(mock 근거 diff). 모델 API/구독 없이 DB + JSON + 조건부 교차 검증 검증 가능.
2. **각 CLI 독립 연결:** AGW-00 실제 이용 조건 확인 + AGW-02 격리 → AGW-03 공식 로그인 → AGW-06 Codex E2E → AGW-07 Claude E2E. **공급자 계약 불허면 해당 실제 연결은 HOLD**, 합성 mock 경로는 진행.
3. **사용자 가치:** AGW-12 UI + AGW-11 중요 이슈 검증(기존 ANALYSIS session 보존).
4. **운영 품질:** AGW-13 CI/격리 staging/복구 검증 + AGW-14 독립 gold 평가 후 승인된 data1 제한 시범.

기존 HBR-01/02(로컬 임베딩/공개 RFP 검색) 및 HBR-03(법인·부서 근거 SQL/RAG)은 AGW-05/10의 업스트림입니다. 모델 executor 계획 때문에 해당 작업을 완료한 것으로 표시하지 않습니다.

## 공통 검증·문제 예방 체크리스트

- [ ] 계약·CLI 버전·회사 반출 미승인 → 차단/모의 경로로만 테스트
- [ ] 사용자 OS/CLI 홈·세션·로그 간 교차 격리
- [ ] 공급자 계정 인증 상태와 실제 quota/연결/권한/기기 상태 분리
- [ ] 프로세스가 종료되어도 기존 SessionBinding resume, 잘못된 사용자/공고/목적은 거부
- [ ] 0/1/2 READY 모든 조합 + 변경·권한 철회·한쪽 실패 시 상태 정확성
- [ ] 똑같은 RFP/근거 snapshot에서 1차 양쪽 답변 비공유 보장
- [ ] 임의 JSON·evidence ID·원문 차수·LLM 제안 금액을 무신뢰 입력으로 검사
- [ ] 두 모델 의견 일치라도 법적 자격/회사 MM/Decimal 집계 사실과 별도 검증
- [ ] 불일치 이슈만 최소 근거 공유, 최대 1회 추가 라운드·사람 최종 결정
- [ ] Idempotency/Outbox/DB lease 및 worker 중복·timeout/partial-save 복구
- [ ] 실제 모델 호출/인증정보/회사 자료를 GitHub·CI·로그로 누출하지 않음
- [ ] 변경 SHA·필수 CI·권한·실제 승인된 사용자 경로/복구 근거 확인

## 다른 AI·새 채팅에서의 재개 지시

아래 순서로 진행하면 과거 대화 내용을 다시 전달할 필요가 없습니다.

```text
1. son1004007/ai-agent-workflow-playbook/CONTROL.md
2. config/repositories.yml -> public-bid-agent
3. public-bid-agent/AGENTS.md -> DECISIONS.md -> AI_CONTEXT.md
4. CURRENT_STATE.md -> TASKS.md -> 최근 PR #5/commit/CI evidence
5. docs/implementation/ai-gateway/README.md (이 목차)
6. ID가 가장 낮다는 이유가 아니라 P0/선행 의존/실제 허용된 작업 중 첫 미완료 AGW 카드 선택
7. 해당 카드와 기존 code/tests 읽기 → 최소 구현 → 필수 보안·기능·회귀 검증
8. 승인된 범위의 실제 운영/격리 staging 경로 E2E(없으면 NOT_RUN) → 상태·실패·다음 카드 갱신
```

- 작업을 수행해도 새로운 프롬프트로 자동으로 또 다른 AI/AGY를 개발자로 위임하지 않습니다.
- 구현 완료를 문서 작성/모의 CI나 등록 성공만으로 선언하지 않습니다.
- 외부 서비스 연결/회사 자료 반출/공급자 로그인/서버 배포가 필요하면 기존 보안·승인 정책과 실제 허용 workspace를 먼저 확인합니다.
- 변경 이력과 현재 상태는 **TASKS.md/CURRENT_STATE.md**가 정본입니다. 이 문서와 전역 TASK_INDEX는 탐색용 목차이며 상태 대시보드가 아닙니다.
