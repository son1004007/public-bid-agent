> **2026-11-20 최신 구현 상태: CODE_PARTIAL / SYNTHETIC_DB_PASS.** [AGW-05/09 실제 코드·합성 DB·테스트 기록](AGW-05-09-IMPLEMENTATION-2026-11-20.md). `server/ai_gateway_core/result_contract.py`의 strict JSON/중복키/결과 연결/허위 근거/요건 coverage 검증, `ai_gateway.models.AnalysisRun/AnalysisRevision` 및 `migrations/0002_analysis_results.py`, `analysis_service.py` 멱등/결과 수정 거부/승인 신규 revision 구현. RFP 자료만으로 MET·NOT_MET 확정 금지. **PostgreSQL DB-level trigger/grants/WORM·실제 Job/outbox·회사 데이터는 미구현**. ORM 막음만으로 특권 SQL 변경까지 방지하는 것은 아님. [core 77 PASS](https://github.com/son1004007/public-bid-agent/actions/runs/44676123480), [Django 378×3 PASS](https://github.com/son1004007/public-bid-agent/actions/runs/44676123557).

# JSON 구조 검증·증빙 식별자 대조·불변 결과 저장

- 작업 ID: AGW-09
- 상태: CODE_PARTIAL / SYNTHETIC_DB_TESTED; PUBLIC_PRODUCTION_NOT_CONNECTED
- 우선순위: P0; 선행 작업과 승인 조건은 [AGW 목차](README.md) 참조.
- 기존 연계: [HBR 원장](../../../TASKS.md), [사용자별 세션/교차 검증](../../server-migration/16-user-cli-session-and-blind-cross-check.md), [전역 보안·계약](../../server-migration/15-mcp-provider-executor-subscription-policy.md).
- 범위: 합성·공개 RFP와 격리 환경에서 코드/테스트 가능; 실제 CLI 로그인·회사 데이터 외부 전송·유료 모델·data1 배포는 별도 적격성·승인 전 OFF.

## 목표
Codex/Claude가 생성한 임의 문자열을 업무 판단으로 신뢰하지 않고, 서버가 JSON을 검증하고 불변 이력으로 저장합니다.

## 입력·출력 계약
- 입력은 AGW-05 AnalysisResultV1 및 CLI wrapper(AGW-06/07)의 최종 결과 객체.
- Python Pydantic 또는 JSON Schema validator의 strict 모드로 필수 필드·enum·데이터 타입·길이·중첩 수·unknown fields 정책을 통제. schema v1은 스냅샷·프롬프트·run에 고정.
- 서버가 run_id / provider / snapshot_sha / source_document_version / model_identity를 실행 문맥과 비교. **AI가 provider/evidence_id를 새로 만들었다는 주장으로 DB fact 생성 금지**.
- 요건 개별 verdict의 evidence_ids가 서버에 알려진 해당 run의 ACL/스냅샷 내부인지 검증. NOT_MET, UNKNOWN, PARTIAL의 누락 이유 표시. 사용자가 나중에 확인한 정정은 별도 revision/승인 이벤트로 추가.
- 회사 원가·MM·예상 수익은 기존 SQL/Decimal 계산에서만 읽어 보고. 모델 JSON은 위험요인/가정 후보일 뿐 금액 원장과 같지 않습니다.
- 대용량 JSON/깊은 중첩/중복 객체/데이터 URL/프롬프트 유출 방지를 위해 byte/depth/items 상한과 문자열 필드 길이 검사.

## 저장 트랜잭션
1. AnalysisRun/attempt/session/snapshot의 provider·사용자·정책/권한을 다시 확인.
2. validated_json canonicalize→digest SHA-256→AnalysisRevision에 append-only INSERT, 원본 CLI stdout은 일반 DB에 미보관.
3. 동일 (run_id,provider,result_digest) 재도착 시 기존 revision 참조(멱등)하고 다른 결과는 explicit new revision이 필요. 이전 성공 결과 덮어쓰기 금지.
4. 정해진 outbox 이벤트 RESULT_VALIDATED 생성. 두 provider revision이 준비되면 AGW-10 deterministic compare로 전달.
5. 인증·계약·정정 문제 발생 시 저장된 과거 이력을 지우는 대신 STALE/REVOKED 정책 표기 및 조회 권한 재검증.

## 오류 처리
- 잘못된 JSON/schema: INVALID_RESULT (원문/토큰 비노출, 재실행 자동 없음)
- 허위/범위 밖 evidence: UNSUPPORTED_CITATION
- stale run/version: STALE_RESULT
- 다른 사용자/부서 자료: 403/정보 비노출
- DB commit 후 worker ack 유실: outbox replay 시 중복 INSERT 없음.

## 인수
- 합성 valid·invalid JSON, 가짜 ID, 허용되지 않은 company fact, 10MB 초과 payload(크기는 구현 결정), JSON depth, duplicate ids, rollback, idempotent replay, provider 이름 위조, ACL change.
- canonical output digest·revision status·source SHA 조회 E2E, 모델 원문 출력/비밀이 공개 Git/CI/artifact/log에 없는지 확인.

## 구현 시 변경 금지·증거
- 기존 실행기/임베딩/입찰 원본·회사 계정/사업부 집계 원가 정책/보안 차단은 보존합니다. 기능 개발 후 테스트 로그, 해당 commit SHA, 정책 승인/실제 실행 범위를 CURRENT_STATE.md에 기록합니다.
- 세부 코드 위치는 신규 server/ai_gateway 후보이며, 코드 구현 시 기존 app/serializer·작업 원장과 중복되지 않도록 실제 저장소를 재검토합니다.
