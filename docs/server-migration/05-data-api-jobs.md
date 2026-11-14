# 05. PostgreSQL·파일·API·작업 데이터 계약

[전체 목차](README.md)

## 1. 논리 데이터 모델 초안

| 엔터티 | 책임/관계 |
|---|---|
| User / Membership | 계정·해시·active/잠금·강제변경·auth_epoch, 소속/역할/데이터 범위 |
| Notice / NoticeVersion | 공식 공고번호+차수·관측시각·정정/취소/마감, 버전 불변·현재 포인터 |
| Document / DocumentVersion | 공식 첨부 출처·identity·binary SHA·원본 version 관계·비공개 파일 참조 |
| ExtractionRun / Chunk | 문서 버전+추출기 버전·페이지/offset/표·OCR 정보·잘림/경고·해시 |
| ReviewScope / ReviewEvent / GoldSpan | 독립 정답·위치·분류·승인/보류·작성자·시각·수정/이전 버전 |
| EvaluationRun | 승인 표본 집합·prediction snapshot·규칙 버전·TP/FP/FN·범위/한계 |
| CompanyEvidence | 회사/면허/실적/인력/MM/원가 근거·확인일·접근 범위·유효 기간 |
| DecisionProfile / DecisionEvent | 기준 버전·가중치·판단 당시 근거·사람 선택/사유·이력 |
| CollectionConfig / Job / JobAttempt | 예약·명시 실행·멱등키·시도·lease/heartbeat·오류/결과 참조 |
| AuditEvent | 누가/어떤 범위/언제/무슨 변경을 했는지 최소 감사 |

필드명/인덱스/보존기간은 상세 migration 설계에서 확정한다. 공고·문서·검수·평가·판단의 버전 관계와 FK/unique를 DB 제약으로 보호한다. JSONB는 원천 응답의 필요한 부가 필드에 제한적으로 사용하고 핵심 관계·권한을 자유 JSON 하나로 저장하지 않는다.

## 2. 원본·파일·검수 불변조건

원본 bytes는 비공개 volume에 불변 저장하고 DB에 SHA/크기/형식/버전을 보관한다. 원본 변경 시 새 DocumentVersion과 새 추출 작업을 만들며 기존 승인 정답을 자동으로 새 버전에 복사하지 않는다. 과거 관계를 입증할 수 없는 기존 캐시는 VERSION_UNVERIFIED로 이관한다. 추출 offset을 원본 페이지라고 변환하지 않는다.

파일 경로/스토리지 키를 클라이언트가 지정할 수 없게 하고, 다운로드/뷰어 요청마다 객체 권한을 검사한다. 추출·원본·회사 정보가 로그나 에러 body에 들어가지 않는다. DB와 파일의 백업 세대를 manifest로 연결한다.

## 3. API 공통 계약

인증 계약은 [03](03-authentication.md)을 따른다. API 경로는 `/api/`로 통일한다. 목록·상세는 서버 범위 필터/페이지네이션, 변경은 CSRF·권한·입력 검증·transaction·expected_revision을 적용한다. 타 범위 객체는 일관된 접근 거부 정책을 적용하고 존재 여부를 누설하지 않는다.

- 조회: `/api/notices`, `/api/notices/{id}`, `/api/document-queue`, `/api/reviews`, `/api/evaluations`, `/api/jobs/{id}`.
- 명시 변경: `/api/collection-runs`, `/api/extraction-runs`, `/api/reviews/{id}/events`, `/api/decisions`, `/api/jobs/{id}/cancel`.
- 401 미인증, 403 변경 필요/권한 없음, 409 revision/멱등키 충돌, 422 입력 불일치, 503 의존 서비스/스냅샷 불가를구분한다. Django 기본 응답과 명시 API 계약을통일하는 구현이 필요하며 기존 동작이 이 계약을 충족한 것으로 취급하지 않는다。
- POST의 Idempotency-Key는 사용자+업무범위+동작에 묶고 request digest와 결과를 보존한다. 동일 키/동일 요청은 기존 작업·결과를 반환하고 다른 요청은409. timeout 후 무조건 새 작업 ID로 재제출하지 않는다.

## 4. 작업 원장과 재시도

Redis 전달은 중복될 수 있다는 전제로 PostgreSQL 원장을 정본으로 삼는다. 업무 저장과 전달 요청은 같은 DB transaction의 outbox에 기록하고 dispatcher가 broker 전달을 재개한다. 워커는 unique 업무키/lease·fencing token으로 소유권을 검사하고 외부 호출과 저장을 멱등 처리한다. 단순 Redis lock 하나로 원본 보존을 보장한다고 쓰지 않는다.

작업 상태는 QUEUED/RUNNING/SUCCEEDED/FAILED/CANCEL_REQUESTED/CANCELLED/REVIEW_REQUIRED. 시도는 별도 이력이며 기존 성공 결과를 실패 시도로 덮지 않는다. 다운로드 실패/추출 실패/근거 부족/권한 철회/worker 단절을 구분한다. heartbeat 유실은 자동 완료가 아니다. 취소는 요청과 실제 종료/cleanup 증거를 구분한다.

일정 dispatcher는 하나만 운영하고 scheduled occurrence를 unique key로 중복 방지한다. 일시 네트워크 오류에만 횟수/전체 시간 상한과 backoff를 적용한다. 인증·자격·SHA/버전 충돌·문서 악성 입력은 자동 반복하지 않는다. PDF/OCR CPU 작업은 별도 동시성/시간·메모리/입출력 한도를 둔다. 사용자가 중지한 PC 스케줄러를 서버 전환 작업이 자동 재활성화하지 않는다.

## 5. 지표와 비밀

지표는 기존 BID06의 독립 승인 정답·정규화/1:1 매칭·부분/오분류/중복 기준을 유지한다. 정답0이면 NOT_EVALUATED/null, 전체 문서 대표성 미확인 유지. 프런트에서 지표를 별도 재계산하지 않는다.

공식 API·AI 공급자·DB/Redis 비밀은 서버 secret 참조로 주입하고 화면/DB export/로그에서 평문 공개하지 않는다. 사용자 로그인 암호와 API 공급자 키는 별개이며 단일 공통 기본 암호를 만들지 않는다.

인증·암호 변경에는 위 일반 업무 결과 재전달 규칙을 그대로 적용하지 않는다. [인증 계약](03-authentication.md)의 commit 결과 불명·재로그인 절차를 따르고 암호/세션 비밀/인증 응답 원문을 멱등 결과로 캐시·재노출하지 않는다.
