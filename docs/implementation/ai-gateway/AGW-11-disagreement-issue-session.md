# AGW-11 | 불일치 이슈 등록·최소 주장 공유·1회 재검증

- 기준: 2026-11-20 KST / 설계 단계, **구현·테스트·운영 배포 미완료**
- 우선순위: P1; 의존관계는 [작업 단위별 목차](README.md)와 [HBR 원장](../../../TASKS.md) 참고
- 설계 정본: [사용자별 서버 로그인·세션 Resume](../../server-migration/16-user-cli-session-and-blind-cross-check.md), [권리·모델 실행 정책](../../server-migration/15-mcp-provider-executor-subscription-policy.md)
- 공통: 회사 비공개 자료 외부 전송/계정 중계/기존 운영 환경 변경은 허용된 경로와 공식 승인 확인 전 OFF. 본인 로그인/세션 보관·사용자별 접근 통제 유지. 독립 AI 코드 리뷰는 선택, 기능/보안/회귀 테스트는 필수.

## 목표
평상시 Codex/Claude ANALYSIS 세션은 비공유로 유지합니다. **중요 불일치나 근거 누락이 발생한 경우에만** 별도 ISSUE_REVIEW 세션을 만들고 필요한 짧은 주장·근거를 공유해 상호 검증합니다.

## 상태/자료
- IssueReview: id, parent_comparison_id, disputed_requirement_ids, issue_kind, sanitized_claims_hash, reviewer_provider, reviewer_session_binding_id, round_count, opened_by, review_status.
- 상태: OPEN → REVIEW_QUEUED → REVIEWING → RESOLVED_WITH_EVIDENCE / HUMAN_REVIEW_REQUIRED / CANCELLED.
- 동일 parent comparison+issue_key 재실행은 이슈/세션 재사용, 새로운 이슈는 신규 ISSUE_REVIEW 세션 생성. **기존 ANALYSIS session은 계속 그대로 유지**.

## 알고리즘
1. AGW-10 diff에서 법적/입찰참가/원가 등 중요한 불일치가 있거나 evidence missing 시 사람에게 비교 화면 제공. 자동 전송 허용된 범위라도 사용자의 실행 정책·비용 상한 체크.
2. 상대방의 전체 대화가 아닌 다음만 issue-packet으로 구성: requirement_id, claim_A/claim_B 축약, 유효한 근거 span ID 및 승인된 짧은 인용, exact source version/hash, 검증 질문.
3. 사용자·부서·provider 데이터 반출 승인/ACL와 범위 재검사. 상대가 접근할 권한이 없으면 해당 인용/자료 생략 → HUMAN_REVIEW_REQUIRED; 보안 우회를 위한 요약 생성 금지.
4. ISSUE_REVIEW 세션을 사용자×provider×notice×issue_key로 bind, 기존 issue 세션이 유효하면 resume. 근거 충돌 하나에 대해 AI 추가 왕복은 기본 최대 1회; 세션이 정상인데 토큰을 아끼기 위해 매번 신규 생성하지 않음.
5. 해당 모델의 반박을 새 AnalysisRevision 또는 IssueReviewOutcome으로 저장하되 1차 분석 결과 수정/교체 금지. 서버 확정 근거·SQL 계산에 따라 충돌 해결 혹은 HUMAN_REVIEW_REQUIRED.
6. 최종 인적 승인에서 담당자/근거/결론/시각을 append-only로 기록; 모델끼리 합의 강요나 무한 토론 루프 금지.

## 주의·실패 설계
- 근거가 없는 양쪽 추정이나 설득력 있는 수사는 사실로 승격 금지.
- 이슈 재질의 도중 API quota/timeout: 기존 issue/analysis 세션 보존하고 PENDING 상태 유지.
- 공고 정정으로 parent comparison stale: 이슈 재검증 중지/새 snapshot의 독립 분석부터.
- issue packet 생성 중 회사 기밀 노출 위험: 정책 차단; 사람의 승인 경로로 보냄.
- 동일 이슈 순환 호출/추가 모델 비용: DB round_count와 idempotency로 최대 1회.

## 인수
- 두 모델의 1차 세션에는 상대 result 미포함 테스트, issue input 최소화 스냅샷 검사, 1회 round 상한, 사람 검토로 종료, 옛 세션/결과 보존, 다른 사용자 이슈 접근 거부.
- 독립성 유지와 서비스 계약·정책 승인 사이의 차이를 문서화; 실제 외부 모델에게 issue packet을 전송하는 것은 별도 승인이 필요합니다.

## 작업 종료·인계
- 설계에 적힌 API/DB/명령은 제안 계약이며 설치된 공급자 CLI 및 실제 코드 기준과 불일치하면 official-source-first로 수정합니다.
- 코드 구현 뒤 해당 SHA 테스트/실행 증거, 실패 대응과 남은 차단은 CURRENT_STATE.md에 기록하고 TASKS.md 해당 AGW ID 상태만 갱신합니다.
