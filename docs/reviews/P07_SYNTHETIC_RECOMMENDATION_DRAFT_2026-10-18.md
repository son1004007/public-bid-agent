# P07 수동 AI 추천 DRAFT·출처·규칙 fallback — 2026-10-18

상태: **IMPLEMENTED / SYNTHETIC_TESTED / NO_GO 보완 후 독립 재검수 대기**. P07 전체 완료·운영 적용·REVIEWED/RELEASED가 아니다.

## NO_GO/P2 모델 입력 절단 보완 (이번 수정)

- 사용자 제공 독립 검수는 **NO_GO**: 90,000자 자료 상한이 출처/불확실성/fallback에 드러나지 않았다. 수정 시작 시 기존 P07 미커밋 변경이 있었으며 해당 변경을 보존하고 이 finding만 수정했다. 아래 초기 75/6 PASS와 독립 검수 NOT RUN은 이전 작업의 이력이다.
- `model_input()`이 자료 본문과 coverage schema 1을 함께 생성한다. 기존 자료 상한 90,000자는 헤더/구분자 포함이며 지침 문자열은 이 한도 밖이다. 각 source의 ID·이름·전체 추출 텍스트 SHA/문자 수·추출 경고 여부와 실제 전달 `[transmitted_start, transmitted_end)`를 기록한다. `COMPLETE`/`TRUNCATED`/`OMITTED`, 누락 source ID 목록, 전달 본문 SHA/길이를 제공하며 헤더만 잘려 나가는 경우는 문서 전체 누락으로 기록한다. offset은 UTF-8 바이트나 JS UTF-16 단위가 아닌 Unicode 문자 위치다.
- `prompt_for()`와 `context_digest()`는 같은 생성기를 사용한다. digest는 전달 본문 hash/범위/상한과 선택 자료 버전에 결속하며, 누락 문서의 hash는 **선택 자료 변경 감지**용이지 전달 증거가 아니다. 이전 digest 형식의 초안은 CHANGED/fallback이며 자동 재분석이나 이력 변경은 하지 않는다.
- 성공한 `/api/analyze` 결과에 서버 생성 `ai_input_coverage`를 저장한다. 실패 시 이 필드는 null이며 성공·실제 전송 완료를 주장하지 않는다. `decision_support.input_coverage`는 현재 자료 기준 재계산으로 구분한다. HTTP 테스트는 mock 그래프에 전달된 문자열과 저장 범위가 정확히 일치함을 확인하며 외부 모델 수신을 검증한 것은 아니다.
- 인용은 실제 전달 범위 안에 있어야 하며 잘린 문서의 앞부분 일치는 `partial=true`, `input_truncated=true`다. 미전달 꼬리/경계 걸침/누락 문서의 인용은 MISMATCH. 입력 잘림·누락 시 `MODEL_INPUT_INCOMPLETE`, `RULE_BASED_FALLBACK`, `HOLD_INPUT_INCOMPLETE`로 처리하고 AI 조건/점수는 판단에서 제외한다. 사용자 확인 미충족은 우선 유지하며 사람의 결정·사유·이력은 바꾸지 않는다.
- UI는 현재 자료의 파일별 전달 범위·일부 잘림·전체 누락을 literal text로 표시하며 파서 경고와 모델 입력 잘림을 구분한다. 최종 사용자 결정은 별도 유지한다.

검증 환경: CPython 3.12.0, Node v22.14.0. `PUBLIC_BID_LOCAL_DATA`는 합성 테스트용 임시 경로로 지정하고 HTTP 저장소는 테스트별 TemporaryDirectory를 사용했다. 실제 사용자 JSON/RFP/회사 증빙 미접근·미전송, 외부 CLI 호출 없음.

| 확인 | 결과 |
| --- | --- |
| 수정 전 신규 경계 회귀 3개 | 재현: 2 FAIL/1 ERROR (범위 메타 없음, 미전달 인용 수용, 보류 미적용) |
| 수정 후 관련 Python 7개 모듈 | **82 PASS** — 기존 75 + 신규 7; 44,000자 설명/문서 2개와 후속 누락 문서, 정확한 상한/1자 초과, 헤더 경계, Unicode, 미전달/경계 걸침 인용, 누락 자료 변경 감지, 사용자 확인 우선/결정·이력 보존, HTTP 범위 저장 및 GET 파일 불변 |
| Node UI/요약 계약 | **8 PASS** — 기존 6 + 신규 2; 실제 render 경로의 잘림/누락 범위·XSS 문자·사용자 결정 보존 및 인용 경고 구분 |
| JS 문법 / `git diff --check HEAD` | **PASS** |
| 전체 회귀·CI·실제 모델·브라우저 인수·운영 적용 | **NOT RUN** |
| 독립 Codex 재검수 | **NOT RUN** — orchestrator 인계, 기존 NO_GO를 자체 GO로 바꾸지 않음 |

재현 명령은 아래 초기 검증 절과 동일하며 Python 실행 전에 `PUBLIC_BID_LOCAL_DATA`를 합성 임시 경로로 설정한다. Git은 현재 저장소만 명령 단위 safe.directory를 지정한 읽기 전용 diff를 사용했고 전역/시스템 보안 설정은 변경하지 않았다. git add/commit/push·main·배포 없음, D-10/P11 보류 유지.

이번 수정에서 외부 CONTROL/handbook 원본은 네트워크 접근 제한 및 web fetch 실패로 **BLOCKED**였다. 읽었다고 주장하지 않으며 저장소 AGENTS/결정/맥락/현황/백로그/P00–P11 로드맵과 사용자 명시 수정 범위를 기준으로 작업했다. 아래 원본 정책 참조 문구는 이전 작성자의 기록이다.

## 범위와 원칙

- 기준: 개발 브랜치 `feat/sprint1-search-demo`, 작업 시작 HEAD `afc657a`; 시작 작업 트리 clean.
- 사용자 이번 지시 및 D-03/D-07/D-08/P07: 공개 소스·합성 fixture만 사용. 사용자 JSON/실제 RFP/회사 증빙을 읽거나 전송하지 않음. D-10/P11 조사 보류.
- main·배포/공개·보안 설정 변경·자동 입찰·git add/commit/push 없음. 독립 검수와 Git 기록은 orchestrator 인계.
- 기존 로컬 **수동 AI 검토 화면(`/`)**의 초안/판단 경로를 보완했다. `/decision-preview`의 전체 공고 자동 AI 추천이나 회사 적격/수익성 검증을 구현한 것은 아니다.
- 전역 CONTROL/handbook과 저장소 결정·상태·P00–P11 로드맵을 참조했다. 기존 다른 작업의 코드/검수 상태를 수정하거나 통과로 바꾸지 않았다.

## 동작 계약

1. `server.normalize()`는 각 gate/factor 및 전체 권고의 `citations`를 최대 4개까지 보존한다. 인용은 `source_id` (`prompt` 또는 `document:0`~`document:5`), `text_sha256`, `offset_start`, `offset_end`, `quote`로 제한한다. 모델의 URL/page/verified 주장은 인용 권한으로 수용하지 않는다. malformed/초과 인용은 빈 목록으로 내려 검증 불가로 처리한다.
2. `decision_support.advise()`는 현재 로컬 메모리 텍스트의 SHA와 Unicode 문자 범위(끝 제외), 직접 인용 최대 400자를 대조한다. `source_checks`는 `MISSING`, `MISMATCH`, `EXTRACTED_TEXT_MATCH_ONLY`를 구분하며 의미 검증은 항상 `UNVERIFIED`다. hash는 **추출 텍스트**의 hash이며 원본 파일 hash가 아니다.
3. 새 분석의 `ai_draft_context_sha256`은 서버가 전체 선택 입력의 source ID·이름·텍스트 SHA·불완전 추출 표시에 결속한다. 구형 기록은 `MISSING`, 이후 설명/문서 변경은 `CHANGED`로 표시하고 과거 AI 주장을 규칙 판단에서 제외한다. 인용 하나가 여전히 일치하더라도 전체 입력 변경을 무시하지 않는다.
4. 모든 파생 판단은 `draft_state=DRAFT`. AI 결과/입력 버전/출처/사유가 없거나 잘못되면 `RULE_BASED_FALLBACK`; 현재 입력에 연결된 AI 초안을 사용해도 `RULE_BASED_WITH_AI_DRAFT`이며 의미·법적 적격·수익성·수주확률 검증이 아니다.
5. 결정 규칙 우선순위: 사용자 확인 미충족 → 현재 출처가 연결된 AI와 사용자 상충 → 출처가 연결된 AI 미충족 제안 → 미확인 조건 보류 → 사용자 판단 대기. AI pass만으로 조건을 충족시키지 않는다. AI fail도 사람 미확인 건수에 남긴다. 출처 없는 AI fail은 별도 경고로 표시하고 미참여 판단 근거로 사용하지 않는다.
6. 사용자 `verified`는 유효한 `pass/fail/na`와 공백이 아닌 근거가 있어야 인정한다. `unknown`/공백 근거/미정 점수는 저장 시 확인값이 해제된다. `READY_FOR_HUMAN`은 사용자 확인 기록의 상태일 뿐 독립 검증·최종 참여 확정이 아니다.
7. GET `/api/state`는 현재 파생 판단을 재계산하고 **파일을 저장하지 않는다**. 기존 명시적 저장 흐름과 `/api/analyze` 결과도 재계산한다. AI 분석 중 원문 변경은 기존 409 거부를 유지한다. `decision`/사용자 사유/이력은 AI나 fallback이 덮어쓰지 않는다.
8. 선택 AI 검토의 ImportError/TimeoutError는 고정된 실패 안내와 fallback으로 처리하며 자동 재시도/대체 외부 모델 호출을 하지 않는다. 기존 Host/Origin/CSRF와 매 요청 외부 전송 동의 경계는 유지한다.
9. UI는 DRAFT·불확실성·입력 변경과 별도의 사용자 최종 결정을 표시한다. 인용 원문은 textContent와 기본 접힌 details로 제공하며 source 링크는 로컬 앵커만 사용한다. 원본 페이지는 미확인, 추출 경고/잘림은 별도 경고다.

## 검증

환경: Windows CPython **3.12.0**, Node **v22.14.0**. 모든 문서/판단은 합성, HTTP는 임시 JSON과 임시 loopback 포트. 실제 외부 AI 호출 없음.

```powershell
$env:PYTHONPATH='local_app'
python -m unittest test_recommendation_draft test_decision_support test_local test_recommendations test_operations test_decision_profiles test_document_guide
node --test scripts/test_recommendation_draft.cjs scripts/test_rfp_evidence_summary.cjs
node --check local_app/app.js
```

| 확인 | 결과 | 범위 |
| --- | --- | --- |
| Python 관련 7개 모듈 | PASS — 75 tests | 신규 P07 18개 포함; 인용 SHA/offset/문구/ID 변조, UTF-8/Unicode, 구형/변경 입력, 불완전 추출, 잘못된 확인값, 모델 실패, 미동의, 조회 불변, 최종 결정/이력 보존, 늦은 결과 409 |
| Node DOM/요약 계약 | PASS — 6 tests | 신규 UI 3개와 기존 RFP 요약 3개; XSS 문구 textContent, 로컬 앵커, DRAFT/fallback/최종 결정 분리 |
| JS 문법 | PASS | `local_app/app.js` |
| 기존 결함 재현 | PASS — 2 canaries | HEAD 원본 `advise`를 메모리에 로드: verified+unknown이 READY가 되는 사례, AI 없음이 사용자 미충족을 무시하는 사례 재현 후 새 코드의 HOLD/사용자 미충족 확인 |
| 실제 LangGraph 의존성 | BLOCKED | `import cross_review`에서 `ModuleNotFoundError: langchain_core`. 서버 fallback 및 그래프 결과 경계는 합성 mock으로 검증. 실제 그래프 실행 통과를 주장하지 않음 |
| 전체 회귀·CI·실제 LLM·브라우저 인수·실자료·운영 반영 | NOT RUN | 이번 합성 소스 변경 범위 밖 또는 환경/승인 필요 |
| 독립 Codex 검수 | NOT RUN | orchestrator 인계. 자체 점검/테스트는 독립 GO가 아님 |

초기 기존 판단 테스트 4개가 출처 없는 AI 판정/NOT_ANALYZED 계약으로 실패했다. 연결된 출처를 쓰는 합성 fixture와 새 fallback 기대값으로 조정하고, **출처 없는 AI fail이 보류되는 별도 부정 테스트**를 추가했다. 신규 HTTP 테스트 첫 실행의 의존성 오류도 숨기지 않고 선택 기능 불가 fallback으로 보완했다.

README 동기화는 이번 미커밋 변경의 루트/로컬 README 동반 변경과 내용을 확인한다. `scripts/check_documentation_sync.py`는 HEAD 커밋 비교 전용이므로 이번 미커밋 diff의 CI 통과 증거로 사용하지 않는다. Git 조회 시 sandbox 계정 소유권 차이로 알려진 현재 저장소에만 명령 단위 `-c safe.directory=<current repository>`를 적용했으며 전역/시스템 설정 파일을 변경하지 않았다.

## 인계 및 남은 검증

- orchestrator: 위 공개 소스/합성 테스트 diff와 이 계약을 독립 Codex에 검수 후, 지적 보완·필요 회귀·README 동기화 CI 및 Git 기록 진행. 아직 독립 판정 없음.
- 합성 fixture의 인용 일치는 실제 모델이 올바른 의미/자격을 판단한다는 증거가 아니다. 인용 의미, 회사 증빙의 진위·가용성, 원본 전체 표/OCR/최신성은 별도 권한과 검증 필요.
- 모델이 정확한 Unicode offset/인용을 만들지 못하거나 예전 초안에 출처·입력 버전이 없으면 보수적으로 fallback한다. 자동 자료 복원·재분석·외부 전송은 하지 않는다.
- 모델별 반론/교차검토의 의미 품질과 실제 LangGraph 환경, 브라우저 인수 및 자동 공고 추천 연결은 미완료다. 최종 사용자 선택·실제 제출/계약/결제는 자동화하지 않는다.
