# 불변 RFP 근거 패킷·프롬프트·JSON 스키마

- 작업 ID: AGW-05
- 상태: DESIGN_READY / IMPLEMENTATION_NOT_STARTED
- 우선순위: P0; 선행 작업과 승인 조건은 [AGW 목차](README.md) 참조.
- 기존 연계: [HBR 원장](../../../TASKS.md), [사용자별 세션/교차 검증](../../server-migration/16-user-cli-session-and-blind-cross-check.md), [전역 보안·계약](../../server-migration/15-mcp-provider-executor-subscription-policy.md).
- 범위: 합성·공개 RFP와 격리 환경에서 코드/테스트 가능; 실제 CLI 로그인·회사 데이터 외부 전송·유료 모델·data1 배포는 별도 적격성·승인 전 OFF.

## 목표와 위협 모델
- 서버가 동일 공고에 대해 Codex와 Claude에 **동일한 승인 근거**를 전달하고, 최초 판단은 완전히 독립적으로 수행하도록 합니다.
- 모델 출력의 그럴듯한 사실, 타 회사 비밀 데이터, 근거 없는 자격 충족 판단, RFP 내부의 악성 지시를 허용하지 않습니다.
- 기존 RFP/Chunk/NoticeVersion과 HBR-01/02/03의 검색·SQL 결과를 재사용합니다.

## 데이터 계약
AnalysisRequestV1 (server-generated):
- schema_version = "analysis_request_v1"
- run_id UUID, notice_version_id UUID, corpus_snapshot_id UUID, snapshot_sha256, prompt_version
- requirements: [{requirement_id, source_document_id, source_version, source_span_id, required_kind, exact_quote_or_redacted_excerpt}]
- evidence: [{evidence_id, evidence_type, source_version, source_span_id, span_hash, classification, approved_for_provider}]
- company_facts: 승인된 최소 projection만(법적 자격·실적·가용성·총계 MM). 직원별 급여·비공개 원가·민감 원문·미승인 부서 실적 제외.
- policy: approved_provider_id, classification_allowlist, max_prompt_bytes, max_result_bytes. 고객/회사 data 전송 미승인은 서버에서 생성 단계 거부.

AnalysisResultV1 (model response):
- schema_version="bid_analysis_v1", run_id, provider, notice_version_id, corpus_snapshot_id, snapshot_sha256, prompt_version
- requirements: [{requirement_id, assessment:"MET"|"NOT_MET"|"UNKNOWN"|"PARTIAL", evidence_ids:[], missing_evidence_ids:[], rationale_short}]
- risks: [{risk_type, severity, requirement_ids, evidence_ids, summary}]
- scenarios: [{scenario_type, assumptions_refs, feasibility:"FEASIBLE"|"CONDITIONAL"|"UNKNOWN"}]
- unknowns: [{requirement_id, reason}], model_metadata(source binding verified by server).
- 모델 output의 금액/마진/지원 여부는 **최종 계산 결과로 저장하지 않고** 서버 Decimal SQL 검산으로 대체.

## 파이프라인 설계
1. 사용자가 접근 가능한 notice 최신 버전과 문서 extraction 성공 상태 확인.
2. 권한 필터 적용 → lexical/vector RAG + 정형 SQL facts → 허용된 evidence ID들로 **불변 snapshot** 구성; 누락/OCR/문서 신뢰상태 표시.
3. canonical JSON(sort keys, no transient fields) → sha256 → AnalysisRun에 snapshot hash 저장. 원문 파일은 승인된 개인 접근 경로에서만 저장.
4. prompt template v1: 시스템 지시(근거 밖 주장 금지/불명은 UNKNOWN), 제공자별 실행 지시(서로의 답변 및 토론 이력 미전달), 데이터 packet, JSON 출력 schema. 입력 길이 상한과 큰 문서 분할·coverage 경고 구현.
5. 모든 외부 model call 직전에 evidence classification / ownership / supplier allowance 재검증. RFP에는 모델을 조종하는 문장이 포함될 수 있으므로 문서 내용은 untrusted evidence로 delimiter+safe text 취급.
6. provider 출력 JSON은 파싱→서버측 strict schema→현재 snapshot/근거 membership→자격/집계 사실 재계산을 통과한 revision만 게시.

## 실패 설계
- 원문 변경/공고 정정/출처 해시 불일치: STALE_SNAPSHOT, 재분석 필요; 조용히 이전 근거 재사용 금지.
- 청크 누락/OCR 부분 추출: PARTIAL_EXTRACTION, 자동 MET 판정 금지.
- 인가 없는 source/evidence: POLICY_BLOCKED; 진단 응답에 비밀 원문 출력 금지.
- 프롬프트 인젝션 "ignore instructions": RFP를 명령으로 실행하지 않고 출력·도구 정책이 더 우선.
- LLM이 JSON 외 텍스트/허위 evidence ID 출력: INVALID_RESULT, 원문/근거를 AI가 새로 만들어 저장 금지.

## 인수 기준
- 동일 packet 두 provider에 같은 snapshot/hash, 정상/상충/누락 3종 fixture.
- snapshot/ACL/출처 무결성 실패에 모델 요청 0건, 위험한 지시 무시, large input과 version 변경 경고, schema/unknown 보장.
- 근거 원문은 비공개 볼륨에 보존하고 GitHub/CI 공개 artifact에는 합성 fixture만 사용합니다.

## 구현 시 변경 금지·증거
- 기존 실행기/임베딩/입찰 원본·회사 계정/사업부 집계 원가 정책/보안 차단은 보존합니다. 기능 개발 후 테스트 로그, 해당 commit SHA, 정책 승인/실제 실행 범위를 CURRENT_STATE.md에 기록합니다.
- 세부 코드 위치는 신규 server/ai_gateway 후보이며, 코드 구현 시 기존 app/serializer·작업 원장과 중복되지 않도록 실제 저장소를 재검토합니다.
