# AGW-05 실제 구현 증거·인계 — RFP 출처 스냅샷 및 변경 감지 강화

- 기준: 2026-11-20 KST
- 대상: `son1004007/public-bid-agent` Draft PR #5, `fix/bid-security-20261116`
- 소유: [AGW-05 설계 카드](AGW-05-evidence-packet-and-json-schema.md), [AGW 전체 목차](README.md)
- **구현 범위:** 합성 RFP + 검토자가 원본 바이트 해시를 직접 확인한 PUBLIC 문서의 **로컬 스냅샷 생성**. 공개 실공고 자동 수집/실제 승인/모델 반출/운영 NAS 배포는 미실시.
- **보안:** AGY/Gemini 자동위임 OFF, 기존 device-control Docker/egress 기본 차단·data1 회사 반출 승인·공급자 개인계정 격리 유지.

## 1. 발견한 문제 / 실제 수정

| 항목 | 이전 위험 | 수정 및 의미 |
| --- | --- | --- |
| Chunk 본문 절단 | `_chunk_text`가 1800byte로 잘라 이후 추가된 필수 자격요건/본문 변조를 못 볼 가능성 | **1800byte 초과 시 `SOURCE_CHUNK_TOO_LARGE`**로 중단. 적법한 분할은 추출기에서 source locator 보존하며 별도 수행해야 함 |
| 문서 원본 식별 | excerpt만 해시; 첨부 PDF/HWP 원본 SHA·추출 실행과 약하게 연결 | packet 모든 `requirement` / `evidence` 항목에 `document_sha256`, `extraction_run_id`, `source_span_id`, `source_hash`를 결속 |
| 공고 정정 원본 | 공고 UUID는 같으나 원문 payload digest가 바뀔 위험 | 상위 `notice_source_digest`를 SHA-256으로 결속; snapshot replay/결과 append 전 원본 공고 digest 재검증 |
| 패킷 내부 위조 | 요구사항의 `source_hash`가 excerpt와 실제 불일치해도 만들 수 있었음 | build 시 **UTF-8 excerpt 자체의 SHA-256**과 `source_hash`를 독립 대조; canonical JSON과 전체 packet SHA 검산 |
| 출처 상태 변경 | 문서 SHA, 추출 실행, Chunk category, 공고 원문 수정에도 기존 이력 붙는 상황 | 저장 결과 재검증/dispatch preflight에서 **현재 DB 원문·문서·추출·ACL·승인**을 재조회. 맞지 않으면 fail-closed. |
| PUBLIC 판정 | 공식처럼 보이는 URL/공유읽기 플래그만으로 PUBLIC 판단 우려 | `PublicRfpAttestation` / `0003_public_rfp_attestation.py` 추가; 기본 `packet_approved=False` / `provider_export_approved=False` / `revoked=False`. 별도 staff-only 원본 바이트 확인 없이는 PUBLIC 생성 불가 |
| RFP 프롬프트 | 문서 본문의 악의적인 지시가 모델 명령으로 취급될 위험 | `render_analysis_prompt`로 **검증된 canonical packet**을 untrusted JSON 데이터로만 삽입. 도구·파일 접근은 실행기가 별도로 제어. 프롬프트만으로 공격 불가능을 보장하지 않음 |

## 2. PUBLIC Source Attestation — 기술 계약

- 원본 공식 정보 근거: [조달청 나라장터 입찰공고정보서비스](https://www.data.go.kr/data/15129394/openapi.do). 2026-11-10 기준 제공 API에는 목록/상세/원본 첨부파일 URL/변경 이력 등이 있다. 본 작업은 **공식 API 호출을 수행한 것이 아니라 출처 검증 로직을 구현**한 것이다.
- 기본 요건: `Notice.source == G2B_OFFICIAL_API`; 최신 `NoticeVersion`, 취소 아님, 공식 HTTPS URL 정확한 hostname(`www.g2b.go.kr`, `g2b.go.kr`, `data.g2b.go.kr`, `apis.data.go.kr`, `www.data.go.kr`), 서비스키가 포함된 URL/의심스러운 authority 거부.
- [`public_source.py`](../../../server/bid_server/ai_gateway/public_source.py) `approve_official_public_document`: 신뢰된 staff가 **실제 raw notice payload bytes와 raw attachment bytes를 전달**, DB에 보관된 `NoticeVersion.source_payload_digest`, `DocumentVersion.sha256` 및 `size_bytes`와 직접 해시·크기 대조; 현재 공고, 사용 가능한 문서, 공유 읽기 허가 확인 후 승인. 기존 동일 DocumentVersion 승인 덮어쓰기 거부. 이 서비스는 UI·외부 호출·네트워크·CLI 기능을 갖지 않음.
- [`analysis_service.py`](../../../server/bid_server/ai_gateway/analysis_service.py) `create_attested_public_analysis_run`: 승인 이후에만 trusted backend가 `ExtractionRun.PARSED`, `coverage.complete=True`, warnings 없음, `DocumentVersion.CURRENT`, staff 계정 유효·not revoked·packet/provider 승인 유지 상태를 체크하고 PUBLIC-only packet을 저장. 회사 증빙은 빈 배열. 모델 호출은 없음.
- `verify_run_snapshot_for_dispatch`: 실제 모델 실행을 허가하는 함수가 아닌 **조회·검사 전용**. 요청한 사용자, 최신 공고, SHA canonical, stored source 현재 원문·추출 상태·권한·승인 철회를 매번 확인. 반환된 `EvidenceSnapshot`을 호출자 스스로 적합한 제품 정책/계약/개인 인증/egress 네트워크/세션 lease와 연결해야 실제 호출 가능.
- `render_analysis_prompt`: 검증된 snapshot에서만 provider별 고정 지시 + untrusted JSON 데이터 생성. 두 provider는 동일 packet/hash를 공유하되 provider 문자열·1차 실행 세션은 별개. RFP만으로 `MET`/`NOT_MET` 확정 금지, 회사 사실은 미포함.
- 원본 바이트는 **공개 GitHub에 커밋하지 않으며**, 접근 승인된 별도 스토리지로 이동·보존해야 한다. 테스트의 G2B-looking URL과 raw bytes는 전부 **합성 fixture**이며 실제 정부 공고를 가져왔다고 주장하지 않는다.

## 3. 구현·테스트 위치

- 코드: [`snapshot.py`](../../../server/ai_gateway_core/snapshot.py), [`analysis_service.py`](../../../server/bid_server/ai_gateway/analysis_service.py), [`public_source.py`](../../../server/bid_server/ai_gateway/public_source.py), [`models.py`](../../../server/bid_server/ai_gateway/models.py), [`0003_public_rfp_attestation.py`](../../../server/bid_server/ai_gateway/migrations/0003_public_rfp_attestation.py)
- 테스트: [`test_ai_gateway_snapshot.py`](../../../server/tests/test_ai_gateway_snapshot.py), [`test_ai_gateway_analysis.py`](../../../server/tests/test_ai_gateway_analysis.py), [`test_ai_gateway_public_source.py`](../../../server/tests/test_ai_gateway_public_source.py)
- 인수 항목: 1800byte 이후 RFP 텍스트 거부, 조작된 source hash/원본 PDF SHA/notice payload SHA/extraction ID/category 거부, source approval 없거나 revoked·권한 제거·불완전 추출 실패, spoofed G2B URL/서비스키 차단, 승인된 같은 PUBLIC packet을 CODEX/CLAUDE에 독립 전달 가능한 identity, read-only preflight 변경 감지, 전체 schema/migration 검증.
- **정확한 CI 성공/실패 결과는 GitHub Actions의 실제 workflow 상태를 확인한 후 CURRENT_STATE/TASKS에 기록한다.**

## 4. 남은 P0 / 운영 차단

1. **실제 공식 공고 첨부 원문 확보 검증:** 조달청 API/문서 다운로드를 승인된 수집기에서 수행하고 원본 응답 바이트·공고 차수·첨부파일 SHA-256·크기·URL을 안전하게 저장, 정정/취소 이력과 reconcile. 해당 데이터가 없으므로 실공고 1건에 대한 공식 원본 E2E는 아직 아님.
2. 문서/PDF/HWPX 추출 결과 자체가 원본 바이트에서 만들어졌다는 **extractor 입출력 provenance & locator/표/각주 coverage** 검증, 누락 시 PARTIAL/UNKNOWN. 지금은 DB ExtractionRun FK·coverage metadata에 의존한다.
3. 승인된 조직·사업부 실제 회사 fact 권한/집계 projection을 source-specific으로 설계 및 원가 SQL 검산. 현재 company_facts=[] 외 반출 금지.
4. **특권 SQL 불변성·승인 감사 추적**: `AnalysisRun` ORM 차단만으로 DB superuser나 migration job 변경을 막을 수 없다. `PublicRfpAttestation`의 승인·철회에 대한 감사 이력/역할 제약과 WORM/DB trigger는 향후 별도.
5. **AGW-08 연결**: 명시 사용자 run 요청 + Job/Outbox + 최신 근거 preflight + 실제 자기 계정 Codex/Claude 세션/계약/회사 egress 검사 + Docker 격리 + 결과 strict parse/append. 현행 공급자 실행기 기본 false 유지.
6. **운영:** 개인 NAS 앱 서버 배포, 회사 data1 설치, 회사 자료·API serviceKey 전송, 공개 ingress 변경, AGY 재위임은 현재 작업 범위 아님.

## 5. 재개 안내

다른 AI/채팅은 [Global Control](https://github.com/son1004007/ai-agent-workflow-playbook/blob/main/CONTROL.md) → 대상 [AGENTS](../../../AGENTS.md) → [CURRENT_STATE](../../../CURRENT_STATE.md) → [TASKS](../../../TASKS.md) → [AGW 목차](README.md) → 이 문서 → 최신 CI/코드를 순서대로 확인하고, **실제 데이터가 없다는 이유로 테스트용 공고를 실제 검증 완료로 표시하지 않는다**.
