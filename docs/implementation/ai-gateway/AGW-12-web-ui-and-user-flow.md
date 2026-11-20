# AGW-12 | React AI 계정 설정·세션/교차 검증 화면

- 기준: 2026-11-20 KST / 설계 단계, **구현·테스트·운영 배포 미완료**
- 우선순위: P1; 의존관계는 [작업 단위별 목차](README.md)와 [HBR 원장](../../../TASKS.md) 참고
- 설계 정본: [사용자별 서버 로그인·세션 Resume](../../server-migration/16-user-cli-session-and-blind-cross-check.md), [권리·모델 실행 정책](../../server-migration/15-mcp-provider-executor-subscription-policy.md)
- 공통: 회사 비공개 자료 외부 전송/계정 중계/기존 운영 환경 변경은 허용된 경로와 공식 승인 확인 전 OFF. 본인 로그인/세션 보관·사용자별 접근 통제 유지. 독립 AI 코드 리뷰는 선택, 기능/보안/회귀 테스트는 필수.

## 화면 목록 및 데이터 흐름
- /settings/ai-providers: Codex/Claude 각각 등록, 연결 방식/실제 정책 상태, 공식 CLI 본인 로그인 가이드, auth/READY/QUOTA_LIMITED/OFF 상태, 마지막 확인 시각. password/OAuth token 입력 필드 없음.
- /notices/:id/analysis: 최신 notice_version/snapshot/근거 범위, 이용 가능한 공급자 0/1/2개와 예정 실행 모드, 개별 분석/진행/부분 실패, 사용자 명시 실행 버튼. 기본 NEW session 생성은 첫 실행과 복구 승인 필요 시에만.
- /notices/:id/analysis/:runId: 두 AI의 requirement 판정/인용 evidence, 구조화 차이와 불확실성, 서버 법적·손익 계산과 사람 결정 분리, 원문 span 바로보기.
- /notices/:id/analysis/:runId/issues: 중요 불일치만 담당자가 재검증 승인, issue-packet/supplier와 추가 요청 안내, 최종 사람 판단·이력.
- /settings/ai-sessions: 사용자 본인의 provider/공고별 세션(활성/일시중단/인증필요/복구필요)과 재개/검토/보존 메타데이터만 제공. 타인의 transcript 및 raw session ID 노출 금지.

## 접근성·UX 계약
1. 0 READY는 'AI 사용 불가'와 이유 안내, RAG/SQL 자료조회 계속 가능.
2. 1 READY는 단독 분석(교차 검증 미완료), 2 READY는 독립 2개 수행 후 비교로 안내. 실행 전 회사 전송/공급자별 예상 호출 수·계정 요금 책임을 알림.
3. 같은 공고 재방문 때 기존 세션 사용 상태를 표시. 인증 만료는 '공식 CLI 다시 로그인' 상태이지 '대화 초기화' 버튼 표시 아님.
4. 두 번째 실행 실패하면 첫 결과 제공하되 '교차 검증된 결과' UI 표시 금지. 법적 불확실/근거 부족은 명확히 보류.
5. 쓰기 기능은 CSRF·업무 ACL·expected_revision·Idempotency-Key. 취소는 실제 공급자 호출 취소/요금 회수 보장 아님을 안내.
6. 원문 RFP 링크·인용은 사용자 ACL 통과한 단편만; 내부 증빙 전체 다운로드 버튼/개인별 급여 정보는 만들지 않음.
7. loading/polling의 다중 요청·늦은 응답·권한 철회·정정 RFP·stale result 응답을 정확히 표시.

## 테스트·완료
- Chrome 390px/1440px, keyboard tab/focus/스크린리더 기본, 401/403/409/422/503 오류, 비어 있음/실행 중/단독/양쪽 동의/불일치/두번째 오류/세션 만료.
- 합성 2명×2개 부서 반출 제한 확인, 비용 안내 및 의도 없는 버튼으로 모델 실행 안 되는지 검증.
- 실제 UI 코드/브라우저 E2E 및 사용자 시안 검토 증거가 없으면 구현 완료로 표시하지 않음.

## 작업 종료·인계
- 설계에 적힌 API/DB/명령은 제안 계약이며 설치된 공급자 CLI 및 실제 코드 기준과 불일치하면 official-source-first로 수정합니다.
- 코드 구현 뒤 해당 SHA 테스트/실행 증거, 실패 대응과 남은 차단은 CURRENT_STATE.md에 기록하고 TASKS.md 해당 AGW ID 상태만 갱신합니다.
