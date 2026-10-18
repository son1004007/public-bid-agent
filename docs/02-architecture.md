# Public Bid Agent 아키텍처 및 구현 경계

> **2026-10-18 개발 의존성 구분:** localhost Python HTTP 서버는 React/Vite를 실행하거나 전면 종속하지 않습니다. `frontend/`는 별도 React/Vite 시안으로, `frontend/package-lock.json`과 고정 Vite 7.3.7을 사용합니다. `scripts/audit_python_environment.py`는 비공개 파일 접근·네트워크 전송 없이 Python 설치 패키지 메타데이터만 조회하는 개발용 감사 도구입니다. OSV 공개 패키지 버전 검사와 npm audit 결과/라이선스 잔여 게이트는 [보안 감사](reviews/DEPENDENCY_SECURITY_AUDIT_2026-10-18.md)를 참조하며, 앱 운영 코드의 저장 경로나 사용자 인증 경계를 변경하지 않았습니다.

> **2026-10-13 구분:** Windows 로컬 `/decision-preview`는 `frontend/public/bid-decision-dashboard-preview.html`+`dashboard-live.js`와 `local_app/server.py`의 Python HTTP API에 연결된 실제 구현입니다. 로컬 `/` 수동 AI 분석 화면, `bid-management-preview.html` 초기 정적 시안, React/FastAPI 합성 앱, 장기 공개 웹 아키텍처를 구별합니다. 실제 현황·검증 상태는 [CURRENT_STATE.md](../CURRENT_STATE.md)를 따릅니다.

## 1. 실제 구현: 개인 컴퓨터 로컬 우선 구조

- **UI**: `/`은 수동 AI 분석/검토, `/decision-preview`는 실제 공식 공고 목록·상세/수집/부서 기준/순위 UI입니다. 두 화면 모두 `127.0.0.1:8765`의 Python 로컬 서버에 연결되며 공개 웹서비스가 아닙니다.
- **서버**: `local_app/server.py` 표준 Python HTTP 서버. Host 검증/Origin/CSRF, JSON 파일 원자 저장.
- **파일**: 최대 10MiB 인입 → 로컬 `extractors.py` 별도 프로세스/포맷 검사/리소스 상한 → 텍스트·오류/한도 메타데이터 반환. OCR은 로컬 Tesseract+한국어 모델 사용.
- **분석**: 사용자가 동의한 provider 목록만 LangGraph StateGraph로 실행.
  1. `independent_analysis`: Codex/Claude CLI의 독립 JSON 분석. 한 모델도 실패했다면 가짜 결과 생성 금지.
  2. `peer_critique`: 모두 성공했을 때만 다른 AI의 JSON을 비신뢰 주장으로 취급해 모델별 최대 한 차례 재검토.
  3. `evidence_comparison`: 각 원문 관련 Gate/평점/참여 의견의 값 일치·불일치 목록 및 검증 필요 상태 기계적 추출. 일치해도 참이라는 확증 아님.
- **사람**: AI 결과는 기본 `verified=false`인 영향인자 초안. 사용자가 원문을 확인한 값만 수동 확정. 참여/보류/미참여는 사용자만 결정.
- **저장소**: `~/.public-bid-agent-local/cases.json` (앱의 업무 데이터만). 업로드 원본은 영구 보관하지 않으나 추출 텍스트는 저장됨. 선택된 모델 CLI 자체 로그/보관은 별도 영역.
- **정확성**: AI/규칙 결과 `Y1`과 실제 사용자 결정 `Y2`, 실제 입찰·낙찰 결과 `Y3`는 다른 종속변수로 취급. 현재 8개 Hard Gate, 12개 Soft Factor 가중치는 시험용이며 수주 확률이 아님.

## 1.1 현재 공고 대시보드의 실행 데이터 흐름

현재 공고 2,223건은 **마지막 공식 수집 성공일 2026-10-11의 로컬 메타데이터 스냅샷**이며 정정·취소/전체성/현재 참가자격의 최신 상태를 보장하지 않습니다. 로컬 RFP 상태가 기록된 후보 107건도 전체 문서 의미·법적 요건 확인 완료와 구분합니다. 44,000자 추출 한도 대상 문서 14개와 후보 107건의 대응 관계는 검증 전입니다.

```text
/decision-preview (bid-decision-dashboard-preview.html + dashboard-live.js)
  → local_app/server.py : HTTP JSON API (127.0.0.1:8765)
  → 조달청 공식 공고 수동 수집/정정 구분 → dashboard.json(공고·수집·사람 판단)
  → department_profile.json(부서 관심 분야) → 규칙 기반 상위 30건 상세검토 순위
  → 공식 RFP 조회/제한된 파싱 → rfp_batch.json + 비공개 rfp_fulltext/ 청크
  → 인력/원가/판단 프로필(로컬 비공개 JSON) → 검증 전 비교 및 사람 결정
```

로컬 데이터 기본 경로는 `~/.public-bid-agent-local`이지만 PC 시작 설정의 `PUBLIC_BID_LOCAL_DATA`가 이를 재정의합니다. `cases.json`은 `/`의 수기 AI 분석용이고 `dashboard.json`은 `/decision-preview`의 실제 공고용입니다. 서로 같은 파일이나 DB가 아닙니다. RFP 원문 청크의 저장·참조와 화면의 6,000자 발췌 표시도 다른 범위입니다.

현재 순위는 `RULE_BASED_READ_ONLY`이며 AI 의미 판단/법적 적격성/실제 회사 수익성이 아닙니다. 최근 저장된 공고의 정정·마감 최신성, 첨부 누락, 14개 44,000자 절단 문서, 페이지·표·각주·OCR의 완전성은 후속 검증이 필요합니다.

## 2. 서비스 경계 및 보안 고려

- **P09 합성 검증 경계(2026-10-18):** `test_local_acceptance.py`는 실제 Handler를 임시 디렉터리·임의 루프백 포트에 연결하고 실제 credential/외부 제공자 함수를 차단한다. Chrome runner는 별도 프로필·CDP pipe로 UI를 검증하며 외부 페이지 요청을 거부한다. 기존 운영 서버/데이터·인증/앱 코드는 변경하지 않는다. Windows CI의 합성 통과는 배포/회사 적격/라이선스 완료 판정이 아니다([게이트](reviews/P09_SYNTHETIC_ACCEPTANCE_2026-10-18.md)).

- 인증: 로컬 단일 사용자 실행에 한정. 외부 웹서비스 인증/OAuth, 사용자별 원격 구독 동의는 미구현.
- 모델 외부 전송: 사용자 동의 **후에만** CLI 실행. 프롬프트/파일 추출 내용은 업체 서비스로 송신됨. 기업 비공개 자료에는 별도 회사 정책·승인이 필요.
- 문서와 모델의 출력은 모두 비신뢰 데이터. 자동 원문 의미 검증·법적 적격 확정·계약 자동 체결 없음.
- 로컬 JSON 평문/AI CLI 캐시 저장은 PC 사용자의 백업·암호화 대상. OS sandbox 완전 격리나 모델 API 비용·계약 보호 미구현.
- LangGraph **이번 구현**은 상태 단계 조정이며 **영속 checkpointer/Human-in-the-loop 내장 interrupt, 공식 API를 이용한 RAG와 비동기 작업큐는 추후 구현**. 사용자 결정은 현재 별도 HTTP 입력으로 반영.

## 3. 기존 React/FastAPI 설계 자산 (별도)

- `frontend/` React/TypeScript/Vite: 합성 공고 목록·입찰관리·AI 계정 선택 퍼블리싱 시안. 실제 Codex/Claude OAuth 연결 아님.
- `backend/` FastAPI: 합성 공고 조회 API와 테스트. 로컬 앱의 저장소/JSON을 사용하는 통합 배포 서비스 아님.
- 향후 공개 서비스 후보: React → FastAPI BFF (실사용자 인증) → 공공 입찰 공식 API/문서 격리 파서 → RAG → LangGraph 검토 → PostgreSQL. 사용자 요구의 **로컬 전용 데이터**와 충돌하지 않도록 별도 합의 전 운영 전환하지 않음.

## 4. 갱신과 검수 게이트

코드·라이브러리·API 변경이 있는 커밋마다 루트 및 `local_app/README.md` 동반 갱신을 CI로 강제합니다. 이 문서의 실제 구조와 코드도 동기화해야 합니다. [라이선스 검토](DEPENDENCIES_AND_LICENSES.md)의 SPDX/재배포 고지 의무를 확인합니다.

필요한 다음 검증: 실제 사용자 PC CLI 인증/2모델 요청, LangGraph 오류/타임아웃/문서 변경경합, 파서 샌드박스, 원문 citation 의미검사, 영속 상태 재개/취소, 실제 RFP OCR 평가, GitHub 독립 최종 코드 검수.

---

## 이전 공공 웹서비스 목표 아키텍처 (참고·미구현)

다음 내용은 초기 React/FastAPI 중심의 장기 설계 기준선입니다. **현재 로컬 앱의 구현 현황을 설명하지 않으며**, 실제 공개 배포/Google 인증/PostgreSQL/RAG 전환에 관한 새로운 승인 없이는 적용하지 않습니다.

# 02 아키텍처 설계

## 현재 상태

**2026-10-09 당시 합성 Sprint 1 이력: 합성 공고 검색/상세 소스 작성 중 / 공개 서비스 활성화 HOLD.** 로컬 백엔드 pytest 일부 PASS, 프런트엔드 빌드·최종 검수·공개 배포는 미실행이다. 합성 fixture 기반 로컬 공고 검색 수직 슬라이스는 먼저 구현하고, 사용되는 경계에 대한 계약과 테스트를 반복적으로 확장한다. 장기 설계 요소는 현재 구현의 필수 선행조건이 아니다.

## 구현 순서와 설계의 성격

- [애자일 실행 기준](07-agile-development-workflow.md)에 따라 React 화면 → FastAPI API → 합성/공식 조회 어댑터로 최소 수직 슬라이스부터 연결한다.
- 아래 전체 구조는 **목표 아키텍처**다. Google OIDC·영속 worker·LLM·RAG·SSE·pgVector는 실제 개발 시점에 필요한 계약과 검증을 거쳐 순차 채택한다.
- 초기 Sprint 1에서 인증, 외부 LLM, 사용자 프로필과 장기 worker를 구현하거나 이미 구현한 것처럼 표시하지 않는다.
- 새로운 실제 데이터/API 관측으로 설계 가정이 틀리면 관련 ADR과 테스트를 같은 변경에서 조정한다.

## 전체 구조

```text
사용자 브라우저(React/TypeScript)
    |
    | 동일 출처 HTTPS, HttpOnly 세션 쿠키
    v
FastAPI 단일 백엔드(BFF + modular monolith)
    |-- Google OIDC callback 및 서버 세션 / CSRF 검증
    |-- API 권한: actor_id + resource_id ownership
    |-- 입찰공고 탐색/표준화/개정 관리
    |-- 기업/기술 프로필의 비민감 데이터 관리
    |-- 문서 다운로드 게이트 -> 격리 PDF 파서
    |-- 원문 근거 버전 -> passage -> 요건 -> claim
    |-- 적합성 규칙 엔진 / 정보 부족 처리
    |-- 분석 실행 상태/판정/원문 최신성의 분리
    |-- PostgreSQL lease 기반 worker claim/heartbeat/recovery/취소
    |-- 모델 호출 예산/질문/취소/재시작
    |-- AI provider 인터페이스(기본 disabled/fake)
    |-- (필요 시) LangGraph, SSE, pgVector, MCP
    |
    +-- PostgreSQL(내부 네트워크)
    +-- 나라장터 공식 API(출처/권한 확인)
    +-- 허용된 공식 첨부 출처(HTTPS)
    +-- 공인된 AI inference endpoint(승인된 경우에만)
```

## 분리 기준 및 구현 불변조건

- **Frontend**: 검색·로그인 UI·프로필 편집·문서 출처/미확인 상태·근거 표시. 권한과 최종 적합성 판단은 서버에서만 수행한다.
- **API/BFF**: HTTP transport, 쿠키/CSRF, Google callback, ownership 검사. 사용자 ID/역할/원문 링크를 검증 없이 신뢰하지 않는다.
- **Application**: 검색·수집·분석 사용 사례, DB transaction, 분석 실행 및 취소 lifecycle, 자원 budget 적용.
- **Domain**: 원천 공고 정체성/개정, 요건/판정 불변조건, UNKNOWN, 원문 근거와 출처 버전 규칙. FastAPI·LangChain 등 외부 프레임워크에 직접 의존하지 않는다.
- **Infrastructure**: Google OIDC, 공공 API, 파일 수집, 격리 파서, DB, 모델 연동. 실패는 명시된 typed error/status로 변환한다.
- 외부 RFP, API payload, LLM 출력은 전부 **비신뢰 데이터**다. 결정적 값(권한, 공고 식별, 날짜, 불변조건, 네트워크 보안)은 일반 코드에서 판정한다.

## 인증 및 리소스 권한

[ADR-001](adr/ADR-001-auth-session-ownership.md)을 따른다. 백엔드 OIDC code flow + PKCE + state + nonce + ID Token 검증 이후 서버 opaque session을 발급한다. `__Host-session`, HttpOnly, Secure, SameSite, CSRF/Origin, rotation/expiry를 필수 검증한다.

서버 actor는 Google `sub` 검증 뒤 부여된 내부 사용자 ID다. Profile, AnalysisRun, Question, EvidenceSet, SSE, cancel/resume 권한은 `(actor_id, resource_id)` 계약으로 검사한다. SSE는 세션 쿠키 방식으로 구성할 수 있고 URL의 bearer token은 사용하지 않는다. 초기 MVP에서는 polling이 가능하므로 SSE 구현을 기능 게이트와 분리한다.

## 공식 입찰 데이터 및 버전

[ADR-002](adr/ADR-002-procurement-data-lifecycle.md)에 따라 원천 스냅샷과 표준 공고를 분리한다.

```text
공공 API 응답
 -> RawNoticeSnapshot(바이트 해시, 출처, 수집 일시, parser version)
 -> NoticeIdentity/NoticeRevision(실제 API 필드 확인 후 key 결정)
 -> revision_kind(ORIGINAL/CORRECTION/UNKNOWN)
 -> availability_status(OPEN/CLOSED/CANCELLED/UNKNOWN)
 -> source_freshness(CURRENT/STALE_SOURCE/UNKNOWN)
 -> DocumentVersion -> Requirement -> AnalysisRun
```

정정·취소·원문 변경 시 기존 분석 이력의 실행 완료 상태를 바꾸지 않고 최신성 projection에서 stale을 표시한다. 실제 fetch URL에 비밀정보가 있을 수 있으므로 원천 링크는 서버 fetch 주소와 공개 canonical 주소를 분리한다. API 0건/partial/error/schema drift와 원천 시간대 미확정을 구별한다. 확증 없는 마감·참가 가능성은 `UNKNOWN`이다.

## 안전한 문서 수집 및 근거 관계

[ADR-006](adr/ADR-006-document-ingestion-security.md)에 따라 공식 API가 제공한 허용된 첨부 식별자에서만 URL을 만든다. HTTPS 호스트/목적지 IP/redirect/streaming 상한/MIME·magic bytes 검증을 거치고, 네트워크 차단·CPU/메모리/시간 제한된 최소권한 parser에서 초기 PDF만 추출한다.

[ADR-003](adr/ADR-003-evidence-retrieval.md)의 근거 모델:

```text
NoticeRevision
 -> SourceDocumentVersion(raw hash, URL, observed time)
 -> ParsedArtifact(parser/version)
 -> Passage(id, source version, location)
 -> ExtractedRequirement(priority, condition, passage id)
 -> Claim(assertion, result state)
 -> EvidenceLink(passage id, support relation, structure + semantic validation state)
```

LLM이 돌려준 citation ID는 서버가 존재 여부·원문 버전·해당 분석 범위를 확인한다. **ID가 실재한다는 사실과 주장 내용을 의미상 지지한다는 사실을 분리하고**, 후자가 검증되지 않으면 긍정 확정 판정을 제한한다. 재파싱 또는 원문 갱신으로 과거 출처 링크를 바꿔치기하지 않는다.

## 적합성 판정과 상태 전이

[ADR-007](adr/ADR-007-analysis-state-evaluation.md)을 따른다.

```text
질의/정규화 -> 공고 검색 -> 최신성 검증 -> AI/SW 후보 분류
 -> 허용된 PDF 취득 및 passage 추출
 -> 필수/선택 참가조건 추출
 -> 프로필 항목과 비교
 -> [필수조건 UNKNOWN?] 예: 질문/NEEDS_REVIEW, 아니오: 유효 근거로 보수적 판정
 -> 결과와 출처 버전 표시
```

단일 분석 실행은 도구·LLM 호출, 토큰, 시간, 상태 전이, 질문 수 예산을 가진다. 실행/판정/최신성 3축을 구별하고, 공개 배포에서는 별도 worker의 DB job lease와 CAS로 장기 분석·재시작·취소 경쟁을 처리한다. 모델에 범용 shell/SQL/URL fetch를 허용하지 않는다. 취소/재개는 별도 권한·idempotency 검사를 거친다.

기술 적합성과 필수 참가자격은 별도 판단이다. UNKNOWN_PRIORITY의 중요한 조항이 하나라도 남으면 SUITABLE을 금지하며, UNSUITABLE은 의미상 검증된 필수조건 상충일 때만 사용한다. `SUITABLE`은 법적 자격 확인을 의미하지 않으며 필수 요건 UNKNOWN이 남았으면 사용하지 않는다.

## LLM/검색 설계와 비용

- [ADR-004](adr/ADR-004-llm-auth-cost.md): ChatGPT 플랜 기반 사용자별 추론은 **공개 원격 서비스 참여 요건 확인 전 비활성**. Google 로그인이 ChatGPT 추론 권한을 부여하지 않는다.
- 모델 경계는 `disabled / fake / approved provider`를 사용한다. 테스트용 fake와 실제 AI 추론을 섞어 홍보하지 않는다.
- [ADR-003](adr/ADR-003-evidence-retrieval.md): 처음에는 결정적 검색 baseline. Embedding 공급자·차원·비용·이용조건 확인과 품질 개선 증거가 있어야 pgVector로 확장한다.
- LangGraph는 실제 분기/질문/재개 단계에 따른 유지보수 편익을 확인해 도입한다. MCP는 실제 독립 tool 경계가 필요할 때만 도입한다. 키워드 때문에 빈 추상화나 거대한 인프라를 만들지 않는다.

## 배포, 데이터 생명주기, 검증

- [ADR-005](adr/ADR-005-hosting-operations.md): HTTPS edge, 비공개 DB, 로그 최소화, 백업/복원, 오류 관찰, 호출 제한.
- [ADR-008](adr/ADR-008-profile-privacy.md): 프로필 최소수집, 원문 내 제3자 개인정보 처리, 세션·worker 취소를 포함한 계정 삭제, 삭제 저널/재가입, 모델 전송 allowlist.
- [03 테스트 계획](03-test-plan.md)에서 각 위협 경계와 오류·복구·출시 평가 게이트를 검증한다.
- 사용하지 않는 데이터 수집, 법적 입찰 자격 확정, 실제 전자입찰 제출은 범위 밖이다.

## 남은 외부 검증

실제 조달 API 필드/정정 관계/파일 형식, 배포 도메인 및 OAuth 콘솔 설정, 유료 API 사용 없이 원격 ChatGPT 연동이 허용되는지, 문서 원문 재배포·보존 범위는 확인 전까지 `UNVERIFIED`다. 의사결정 미완료를 구현 완료로 표시하지 않는다.

## R3 수정: 완전성·지속 권한·소모량 계약

- 현재 공고 선택은 [ADR-002](adr/ADR-002-procurement-data-lifecycle.md) `EffectiveNoticeProjection`에서 단일 유효 revision, 마지막 완전 동기화 시점, 상태·마감시각을 별도로 판정한다. 접수 불명확/오래된 snapshot의 긍정 판정을 막는다.
- 문서 추출은 parser 성공과 별도로 원문 페이지 처리·표/스캔 누락을 포함한 `extraction_completeness`를 유지한다. 불완전 추출은 `NEEDS_REVIEW`로 전달한다.
- SSE는 연결 이후에도 매 이벤트 전송 전에 세션 generation·계정 상태·run 소유권을 검증하고 logout/탈퇴/철회 시 연결을 종료한다.
- React는 모든 공고/모델 출력의 기본 표시를 text node로 한정하고, 공식 출처 URL만 안전한 링크로 변환한다. HTML 직접 렌더링은 MVP에서 금지한다.
- 후속 질문은 승인된 비민감 스키마와 option으로만 제공한다. 회사 기밀·계약/연락처/계좌/실적 원문은 업로드/자유 입력/LLM 전송을 허용하지 않는다.
- 분석 worker는 [ADR-007](adr/ADR-007-analysis-state-evaluation.md)의 DB `RunBudget/UsageAttempt` 영속 장부를 사용하고, 모델 호출 전 예약·응답 후 사용량을 조정한다. timeout·중복 작업·취소에도 시도 예산을 되돌리지 않는다.

## Codex R4 설계 보완 사항

- 근거는 [ADR-003](adr/ADR-003-evidence-retrieval.md)의 단일 `verification_status`, `review_source`, `semantic_relation`, `validator_ref` 계약을 따르며 의미 검증이 되지 않은 자기신고는 공식 검증 결과로 취급하지 않는다.
- 공공 API 최신성은 [ADR-002](adr/ADR-002-procurement-data-lifecycle.md)의 원천 조회조건·페이지 coverage 및 공고별 authoritative detail 확인을 통해 판단한다.
- 장기 실행은 [ADR-007](adr/ADR-007-analysis-state-evaluation.md)의 run/user/day/provider/day/service/day DB 원자 예산 예약을 통과한 경우에만 외부 도구·모델을 호출한다.
- HTTPS edge/CDN은 사용자별 profile/run/citation/export를 공유 캐시하지 않고 SSE에는 streaming cache·buffering 제한을 적용한다([ADR-001](adr/ADR-001-auth-session-ownership.md), [ADR-005](adr/ADR-005-hosting-operations.md)).
- 계정 삭제 시 외부 provider에 이미 보낸 요청은 provider 정책에 따라 취소를 시도하며, 늦은 결과의 로컬 기록을 차단하고 외부 보존 상태는 별도 안내한다([ADR-008](adr/ADR-008-profile-privacy.md)).

## 2026-10-10 단일 AI 분석 경로

Codex 1개가 선택된 경우 LangGraph는 independent_analysis에서 1회 호출하며, peer_critique에서 실행을 생략하고 comparison은 `single_or_failed`로 표시합니다. 사람 검증 상태와 최종 참여 결정은 변화하지 않습니다. Windows npm 경로는 `codex.cmd`, 호출 모델은 ChatGPT 인증 Codex용 `gpt-5.6-terra`이며 개인정보/회사업무 정보는 동의 후 전송합니다.

## 2026-10-10 참여 판단 Y1 품질·검증 경계

2026-10-18 P07 보완: 로컬 수동 AI 경로의 `decision_support`는 항상 `DRAFT`이며, 정규화된 `citations`의 source ID·추출 텍스트 SHA·문자 범위·직접 인용을 현재 메모리 자료와 대조한다. 이는 의미/공식 원본/회사 적격 검증이 아니다. 서버가 기록한 `ai_draft_context_sha256`이 없거나 달라지면 과거 AI 주장을 위험 분류에 사용하지 않고, AI·의존성·사유·출처 부족도 `RULE_BASED_FALLBACK`으로 표시한다. GET `/api/state`는 파생 판단을 재계산하되 파일을 쓰지 않으며, 최종 `decision`/이력은 기존 사용자 명시 경로만 갱신한다. 새 의존성·외부 전송 경로·dashboard 자동 AI 기능은 추가하지 않았다. [계약/테스트](reviews/P07_SYNTHETIC_RECOMMENDATION_DRAFT_2026-10-18.md).

`cross_review.py`의 모델 원문 의견과 `decision_support.py`의 결정적 보수적 규칙 위험 분류를 분리합니다. `ai_reports[*]`와 `ai_draft`는 미검증 모델 추출, `decision_support`는 Hard Gate 실패/미확인/사용자 충돌 위험, `decision`은 오직 사용자만 갱신합니다. 사용자 보정(`/api/save`) 뒤에도 보수적 검증 분류가 다시 계산됩니다. 위험 분류는 법적 적격, 수주확률, 실제 계약 행위를 뜻하지 않습니다.

## 2026-10-10 문서 입력 가이드 계약

단일 마스터 `local_app/document_guide.json`에 5개 추천 문서 묶음(외부 2종/회사 내부 3종)과 20개 변수의 `sources`, `missing_question` 정의를 관리. `GET /document-guide.json`은 정적 JSON(모델 외부 전송/DB 저장 없음)을 제공하며, `app.js`가 사용자 최초 접속 시 공고와 관계없이 매핑을 렌더링한다. 문서 가이드 조회만으로 AI 모델 요청/업로드/민감정보 저장이 발생하지 않는다. 이 JSON은 업로드 파일 유형 자동분류·증빙 법적 진위 검증을 수행하는 규칙 엔진이 아니다. 직원/고객 개인정보와 원가 원문을 회사 승인 없이 외부 AI로 전송하지 않는다.

## 2026-10-10 운영 기준과 입찰별 원가 분리 (ADR 미승인 기능 검증)

로컬 운영 기준 `operations.json` schema_version=1, revision 카운터 및 `roles[{role,cost_per_mm_krw,available_mm}]`, `overhead_pct`, `reserve_pct`를 보유. 직원 개인 급여/이름을 저장하지 않음. 공고별 `cases.json` 각 case에 `cost_plan`(역할별 투입 MM, 외주비/직접경비/제안비, VAT 제외 예정 공급가액)과 계산된 `cost_estimate`(revision, 금액, 경고) 저장. GET `/api/operations`, POST `/api/operations/save`, POST `/api/cost-plan`; 기존 localhost Host/Origin/CSRF, 잠금, 원자 저장, optimistic revision 검증 유지. 순수 함수 `operations.calculate`로 인건비/간접비/충당/이익률 결정적 계산. 기준정보 업데이트 시 기존 견적을 명시적으로 stale 표시(기존 값 변경하지 않음). `prompt_for`는 원래 입찰공고 설명/첨부 텍스트만 전달하며 운영 기준·원가계획을 자동 직렬화하지 않음. 배치계획/수금 현금흐름/실제 회계·법적 입찰 적격 추정은 이 수직 슬라이스 범위 밖.

- `operations.json.registers`: 8개 자료 분류별 `status` (`not_collected`, `needs_refresh`, `reviewed`), 승인된 짧은 요약(`summary`), 문서명(`source`), 확인일(`reviewed_on`). 화면/GET 응답의 메타데이터는 `REFERENCE_SECTIONS` 단일 진실이며, 내용은 Codex/Claude 및 견적 원가에 자동 직렬화하지 않는다. 이는 단순 자료 준비도 기록이지 원장 통합/민감자료 검증이 아님.

## 2026-10-12 RFP 배치와 대시보드의 JSON 프로세스 간 경합 보호

- 기존 `os.replace` 원자 쓰기를 유지하고, 서로 다른 로컬 Python 프로세스의 **최신 JSON 읽기 → 검증/병합 → revision 증가 → 저장** 전체를 동일 `.dashboard-rfp.lock` 파일에 대한 운영체제 잠금으로 직렬화한다. Windows는 `msvcrt.locking`, Linux는 `fcntl.flock`을 사용하며 추가 외부 패키지는 없다. 서버 내부 `threading.RLock`은 그대로 유지한다.
- 대상 경로: 공식 공고 수집 성공/실패, 상세 면허·첨부, 재분류, RFP enrichment, 담당자 최종 판단, RFP 배치 결과 및 `rfp_batch.json` 진행 원장. 외부 공공 API/첨부 다운로드 및 OCR 중에는 JSON 트랜잭션 잠금을 보유하지 않는다.
- `.rfp-batch-worker.lock`의 수명 잠금으로 다른 프로세스의 같은 배치 중복 실행을 차단하고, 별도 프로세스에서 실행한 pause의 원장 상태를 다음 문서 처리 전에 확인한다. 비정상 프로세스 종료 시 운영체제가 잠금을 해제한다.
- 공고 재수집은 이미 확보한 공식 상세 RFP 첨부 링크를 덮어쓰지 않고 URL 기준 중복 제거해 유지한다. 이전 RFP 증거·사람 결정·판단 이력은 읽기-병합 경로에서 보존한다.
- 잠금 획득 제한시간 10초 초과 시 저장 전 실패 처리(HTTP 503). 잠금 파일에는 비밀·공고·인력 데이터가 없으며 활성/비활성 잠금 파일을 임의 삭제하지 않는다. **프로그램 이외의 직접 파일 수정, 여러 컴퓨터 간 네트워크 공유 파일 시스템의 잠금 보장, 두 JSON 파일을 통째로 하나의 DB 트랜잭션처럼 커밋하는 기능은 이 변경의 범위 밖**이다.
- 검증: `local_app/test_json_transaction.py`에서 별도 Python 프로세스 2개 실제 동시 갱신의 revision/이력/원문 보존, 제한시간, 강제 종료 후 잠금 회수, 배치 중복 실행 차단·원격 pause, 재수집 후 RFP 첨부 보존을 합성 임시 디렉터리로 테스트한다. 실제 사용자 `dashboard.json`/`cases.json`/`workforce.json`은 수정하지 않는다.

## 2026-10-12 비공개 문서 청크 저장 경계 (개발 브랜치)

기존 `dashboard.json`의 요약 발췌는 유지하고, 신규 RFP 배치가 반환받은 본문 최대 44,000자를 별도 로컬 content-addressed JSON 캐시에 4,000자 청크로 저장한다. 기존 일반 GET 응답은 레퍼런스/해시/글자수/절단 상태만 포함하며 본문 청크는 공개하지 않는다. 추출 문자열 offset은 실제 PDF/HWP 페이지·표 위치와 다르며, 파서의 44,000자 절단은 그대로 경고한다. 사이드카 파일과 대시보드 참조는 단일 DB 트랜잭션으로 커밋되지 않으므로 지연 재처리·복구/청소 정책은 후속 구현한다. [설계](design/RFP_FULLTEXT_CHUNKS_2026-10-12.md).

## 2026-10-12 구 RFP 증거의 청크 이관 버전 검증
- 신규 RFP 청크 저장소와 별도로 기존 EXTRACTED의 `document_evidence.sha256`, 첨부 identity, chars, excerpt를 공개 원본의 재다운로드·파싱 결과와 대조한다.
- 전부 일치한 경우 기존 evidence에 `fulltext_ref`만 증분 기록하고 별도 작업 원장으로 수동 25문서 단위 재개한다. 다른 SHA/발췌·첨부 링크는 격리하며 사람 결정/기존 RFP 요약은 불변.
- 비공개 개인 PC 검증 전용이며 더 최신 공고 정정 여부, 참가자격의 확정, 인가·호스팅·AI 모델 전송 보장과 별개다. [설계](design/RFP_BACKFILL_VERIFIED_2026-10-12.md).


## Windows 로컬 예약 공식 공고 갱신 (2026-10-13, 구현 단위)

Windows 사용자 로그인 세션의 Task Scheduler (일일 09:00) → 같은 사용자 Python 3.12 `local_app/scheduled_collection.py` → DPAPI 인증키 복호화(프로세스 메모리 전용) → 공식 용역 OpenAPI 지난 7일 구간 순차 요청 → 페이지별 총건수와 중단 검증 → 공고 ID 최신 데이터 병합 → 운영 `dashboard.json` 최신 revision 재조회와 공통 OS 파일 잠금 → 기존 담당자 결정, 이력, 첨부/RFP 원문 보존한 원자 저장. 서버가 실행 중인 경우에도 같은 JSON 잠금을 사용한다. 모델/외부 AI 전송 없음. 배포 저널 PREPARED 또는 임의 변조/손상 감지 시 갱신 중지. API 통신 실패 시 기존 공고는 그대로 보존하고 수집 상태만 실패로 표시할 수 있음. 원문 정정감지·기존 RFP stale 표시 및 AI 의미 분석은 다음 단계.


## 2026-10-13 공식 정정·취소 공고 반영
- 조달청 공식 목록 API의 `bidNtceNo`(공고번호), `bidNtceOrd`(차수), `ntceKindNm`(공고종류)만으로 취소 및 후속 차수의 존재를 판별합니다. 제목에 취소·변경 표현이 있다는 이유만으로 확정하지 않습니다. 같은 공고번호의 숫자 차수가 더 높으면 과거 차수는 `notice_lifecycle=SUPERSEDED`, 공식 공고종류에 취소가 명시되면 해당 최신 차수를 `CANCELLED`로 보관합니다. 추가 원문 정정 이력 API의 전수 조회는 이번 범위 밖입니다.
- 공고 JSON과 기존 사람 최종 결정, `history`, 저장된 RFP 원문·SHA·첨부 증거를 삭제하지 않습니다. 저장 문서가 있는 공고의 공식 중요 메타데이터·신규 첨부 또는 후속 차수 변경은 `rfp_review_status=STALE`로 표시하고 수동 최신성 검증이 필요함을 UI에 안내합니다. 기존 추출 증거로 자동 입찰 적격 확정이나 재검증을 하지 않습니다.
- 규칙 기반 추천은 `CANCELLED`, `SUPERSEDED`, 차수 중복 검토 상태 `REVIEW`, RFP 최신성 `STALE`을 제외합니다. 보관된 공고 목록과 과거 판단 이력은 유지하고 공식 링크·후속 차수와 근거를 화면에서 확인할 수 있습니다.
- 기존 로컬 데이터 확인(미변경): `python local_app/notice_lifecycle_cli.py --data-dir <개인 JSON 폴더>`. 결과를 적용하려면 `--apply`를 추가합니다. 현재 저장된 공고를 공식 메타데이터로 재분류하며 API나 AI를 호출하지 않습니다. 이후 일상적인 API 수집 결과에도 동일 규칙을 적용합니다. 모든 저장은 기존 잠금·배포 가드를 사용합니다.
- 한계: 동일 공고번호의 정정 정보가 최근 7일 API 목록에 보이지 않으면 새로운 변경을 탐지하지 못하며, 원공고가 다른 공고번호로 재공고되는 경우 자동 동일성 판정을 하지 않습니다. 다음 작업의 RFP 의미 분석·AI 추천과 별도입니다.


### 2026-10-13 Codex 1차 NO_GO 후 보완
- 같은 공고번호와 **숫자 차수**가 같으면 공식 차수 표기 `0`, `00`, `000`을 기존 보존 ID에 합쳐, 사람 결정·기추출 문서가 다른 레코드로 갈라지는 문제를 방지합니다. 기존에 표기 변형이 별도 저장되어 있으면 임의 삭제·자동 병합하지 않고, 그중 공식 취소가 확인된 경우 해당 숫자 차수 전체를 취소 상태로 차단합니다.
- 한 번 확인한 동일 차수 `CANCELLED`은 이후 일반공고 응답으로 자동 해제되지 않습니다. 새로운 **더 높은 차수**가 발행되면 그 새로운 차수를 따로 검토하며 이전 취소 이력은 보존됩니다. 기본 공고 목록에서 취소·과거 차수·중복 차수 검토 항목은 제외하되 전체 보기에서 확인할 수 있습니다.
- 저장된 RFP가 `STALE`이면 기존 원문을 계속 보존하고 추천을 보류합니다. **현재는 최신 공식 증거로 재추출·재검증을 완료한 뒤 STALE을 해제하는 자동 전이가 없으므로**, 명시적 후속 검증 전에는 안전을 위해 추천에 다시 진입시키지 않습니다. 원문 재추출과 재검증 UX는 사용자 다음 개발방향 결정 이후 별도 구현입니다.


## 2026-10-13 RFP 요건 구조화 1단계: 추출 문구와 원문 근거 조회

- 기존 RFP 추출·SHA-256 검증 청크를 **읽기 전용**으로 재사용하는 `local_app/rfp_requirements.py`와 `GET /api/dashboard/rfp-requirements?id=...`를 추가했습니다. 취소·구차수·STALE 공고에서는 분석을 보류하며, 실제 참가 가능성/법적 자격/원가를 확정하지 않습니다. 모델 API 호출이나 외부 전송, 사용자 JSON·사람 판단 갱신 없음.
- 참가자격/면허/실적/과업/기술/인력·공수/기간/예산의 8개 영역을 **원문 관련 표현 후보**로 구조화합니다. 문서 이름·원본 SHA-256·발췌 최대 220자·추출 텍스트 offset·불완전성 경고를 반환합니다. 원본 페이지 번호·필수 요건 여부는 추정하지 않습니다. 캐시 위변조/출처 불일치면 분석 실패로 명시합니다.
- `/decision-preview` → 공식 공고 전체 상세 → `참가자격·과업 확인` → `RFP 요구사항·출처 근거 확인` 버튼에서 분류·근거를 직접 검토할 수 있습니다.
- 실제 비공개 RFP 대표 20건에서 규칙 기반 표현 후보 561건 탐지, 원문 참조 가능한 현행 후보 66건(당일 저장상태 기준), 일부 절단/부분 텍스트 4건. 이 결과는 원문 의미 적격 판정이 아닙니다. 자세한 계약은 `docs/design/RFP_REQUIREMENTS_SLICE_2026-10-13.md` 참조.


### Codex 독립 검수 지적에 따른 출처 결속·증거 순회 보완
- 공식 첨부 identity로 확인된 **실제 첨부 파일명만** 응답에 표시. 저장된 `document_evidence.name`이 공식 첨부명과 다르면 불일치 경고를 남기고 증거를 제외합니다.
- 증거 이력 최대 120개 항목을 살펴보고 **정상 SHA/파일명/본문 검증에 성공한 문서 2개**까지 선택합니다. 앞의 기록이 실패해도 이후 정상 기록을 탐지하고, 처리 상한·중복·충돌을 경고합니다. 같은 첨부 identity의 다른 원본 SHA가 있으면 둘 다 제외합니다.
- 요건 표현 후보는 필수 조건 여부와 원본 페이지가 미확인입니다. 캐시나 문서 이름의 불일치가 있으면 자동 분석 결과를 확정하지 않습니다. 이는 실제 문서 의미를 판단하는 AI 기능과 구분합니다.


### Codex 2차 지적: 공식 첨부 목록의 조용한 절단 보완
- 공식 첨부 목록은 **400건 이내에서 identity를 대조**합니다. 121번째의 정상 공식 첨부는 분석 대상에 포함됩니다. 400건을 초과하면 공식 첨부 탐색 상한을 `PARTIAL`과 명시적 경고로 표시하고 누락 원인을 감추지 않습니다.
- 합성 회귀 2건(121번째 정상 첨부 인식, 401번째 이후 탐색 상한 경고)을 추가했습니다. 앞의 Codex 개선 사항(출처 파일명 결속 및 최대 120개의 증거 이력에서 성공 2개 선정)은 유지합니다.
