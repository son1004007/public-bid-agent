# AGW-10 | 독립 분석 교차 검증·사실/법적 게이트

- 기준: 2026-11-20 KST / 설계 단계, **구현·테스트·운영 배포 미완료**
- 우선순위: P0; 의존관계는 [작업 단위별 목차](README.md)와 [HBR 원장](../../../TASKS.md) 참고
- 설계 정본: [사용자별 서버 로그인·세션 Resume](../../server-migration/16-user-cli-session-and-blind-cross-check.md), [권리·모델 실행 정책](../../server-migration/15-mcp-provider-executor-subscription-policy.md)
- 공통: 회사 비공개 자료 외부 전송/계정 중계/기존 운영 환경 변경은 허용된 경로와 공식 승인 확인 전 OFF. 본인 로그인/세션 보관·사용자별 접근 통제 유지. 독립 AI 코드 리뷰는 선택, 기능/보안/회귀 테스트는 필수.

## 목표 및 설계 원칙
두 AI의 결론 문장 유사도를 '정답'으로 사용하지 않습니다. 동일 RFP snapshot과 정형 SQL 기준으로 requirement_id/evidence_id/원문 해시와 판단을 비교하고 **법적 필수조건·원가·가용성은 서버가 결정적으로 판정**합니다.

## 비교 엔진 설계
제안 모듈 server/ai_gateway/comparison/engine.py + rules.py, tests/test_cross_validation.py.
1. 입력: 같은 AnalysisRun의 서로 다른 공급자 두 개 AnalysisRevision, immutable snapshot hash, current NoticeVersion, authorized evidence registry, approved organization facts, SQL/Decimal cost result.
2. 준비 검사: provider 서로 다름, 동일 run_id, 동일 snapshot_hash, prompt/schema_version 일치, 두 JSON 각각 검증 완료, 권한/현재 자료 확인; 실패면 INVALID_COMPARISON 또는 STALE_RESULT.
3. requirement_id 별로 Codex/Claude assessment(MET/NOT_MET/UNKNOWN/PARTIAL)를 매핑. 동일 의미 표현 정규화는 허용하되 임의 RFP 요건/증거 추가는 차단.
4. evidence_id 마다 문서 차수·span 해시·유효기간·근거 유형 확인. 법적 참가자격과 평가 가점은 구분하고, hard gate NOT_MET/UNKNOWN이면 두 AI 동의 여부와 무관하게 VERIFIED_BID_READY로 표시하지 않습니다.
5. 회사 역량·MM은 최신 승인된 scope SQL 값과 비교, 인건비/원가/예상 손익은 개인 급여 원본이 없는 집계 기준 및 Decimal 계산 결과만 사용. 모델이 제안한 수치는 시나리오 가정으로 보관.
6. 결과 diff 유형: LEGAL_ELIGIBILITY, RFP_REQUIREMENT, CAPABILITY, RESOURCE, EVIDENCE_INVALID, COST_ASSUMPTION, MISSING_INFORMATION. 근거 ID, 차수, 양쪽 주장, 확정할 수 없는 이유만 민감도에 맞게 표시.
7. 분류: AGREED_WITH_EVIDENCE(각 주장 근거 유효·법적 게이트 별도 통과), PARTIAL_AGREEMENT, DISAGREEMENT, INSUFFICIENT_EVIDENCE, PENDING_SECOND_RESULT, DEGRADED_SINGLE, SINGLE_NOT_CROSS_VALIDATED.
8. 최종 Bid/No-Bid는 권한 있는 사람의 별도 결정. AGREED 상태라도 사실/법적 게이트가 UNKNOWN이면 '보류' 유지.

## 오류·다음 동작
- 동일한 잘못된 근거에 두 모델이 동의: 서버 검증 오류 → INSUFFICIENT_EVIDENCE.
- 한쪽 결과 부재: PENDING/DEGRADED, 다른 모델 답을 대신 생성 금지.
- 이미 검증된 첫 결과를 두 번째 분석에 주입: 1차 독립성 위반으로 실패.
- 긴 자연어 이유 일치도만으로 status 변경 금지.
- 의견 충돌이 있으면 AGW-11 ISSUE_REVIEW로 명시적으로 이관. 이때 상대 전체 대화 기록은 전달하지 않습니다.

## 검증 기준
- 2×2 assessment 조합, 사실/자격 기준 정답과 반대되는 모델 합의, 동일 의미 표현/다른 evidence, 출처 버전 충돌, 소수점 반올림/누락 비용, 빈 결과, 재현 가능한 deterministic diff.
- 비교 재실행이 동일 입력 digest에서 같은 결과를 출력하며 이전 결과 revision을 덮지 않음.
- RFP 전문가가 승인한 정답 집합이 없으면 정확도 개선을 수치로 주장하지 않습니다.

## 작업 종료·인계
- 설계에 적힌 API/DB/명령은 제안 계약이며 설치된 공급자 CLI 및 실제 코드 기준과 불일치하면 official-source-first로 수정합니다.
- 코드 구현 뒤 해당 SHA 테스트/실행 증거, 실패 대응과 남은 차단은 CURRENT_STATE.md에 기록하고 TASKS.md 해당 AGW ID 상태만 갱신합니다.
