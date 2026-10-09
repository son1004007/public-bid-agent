# 02 아키텍처 설계

## 현재 상태

**애자일 Sprint 1 구현 준비 / 공개 서비스 활성화 HOLD.** 실제 소스 코드·통합 테스트·배포는 미실행이다. 합성 fixture 기반 로컬 공고 검색 수직 슬라이스는 먼저 구현하고, 사용되는 경계에 대한 계약과 테스트를 반복적으로 확장한다. 장기 설계 요소는 현재 구현의 필수 선행조건이 아니다.

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
