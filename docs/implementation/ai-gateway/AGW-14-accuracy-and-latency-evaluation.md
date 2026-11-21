# AGW-14 | 입찰 판단 정확도·시간·비용 평가 계획

- 기준: 2026-11-20 KST / 설계 단계, **구현·테스트·운영 배포 미완료**
- 우선순위: P1; 의존관계는 [작업 단위별 목차](README.md)와 [HBR 원장](../../../TASKS.md) 참고
- 설계 정본: [사용자별 서버 로그인·세션 Resume](../../server-migration/16-user-cli-session-and-blind-cross-check.md), [권리·모델 실행 정책](../../server-migration/15-mcp-provider-executor-subscription-policy.md)
- 공통: 회사 비공개 자료 외부 전송/계정 중계/기존 운영 환경 변경은 허용된 경로와 공식 승인 확인 전 OFF. 본인 로그인/세션 보관·사용자별 접근 통제 유지. 독립 AI 코드 리뷰는 선택, 기능/보안/회귀 테스트는 필수.

## 목표
'전체 대화 공유 vs 독립 분석 후 제한 공유'의 실제 효과를 느낌이나 모델 합의 횟수로 판단하지 않고, 입찰 자격/필수조건/회사 역량/예상 손익에 대한 외부 정답셋으로 정량 평가합니다.

## 평가 세트(미구축, 출처/권한 확보 필요)
- 가능하면 공식 RFP 10~20개로 시작하고 법적 참가자격, 최소 실적·인력 기준, 공동수급 가능 여부, 과업 누락/정정, 원문 추출 불완전 등 유형별 균형을 확보. 단순 표본 규모만으로 모집단 대표성 주장 금지.
- 각 문제에 대해 independent human reviewer가 근거 문서 버전/원문 span/판정·사업부 실제 가용성 확인(회사 실자료 승인이 없는 경우 합성 역량만 사용)을 연결. gold evidence와 모델 출력은 분리하고 과거 모델 응답을 정답으로 재활용 금지.
- 테스트셋과 튜닝셋을 분리; 한 번 본 오류를 그대로 정답셋에 유출하지 않음. RFP 정정 시 기존 snapshot/evaluation stale.

## 비교 조건
A. Codex 단독,
B. Claude 단독,
C. Codex+Claude 독립 1차 병렬 + deterministic evidence compare,
D. C 후 중요 불일치가 있을 때만 ISSUE_REVIEW 1회,
E. 참고 비교용 처음부터 상대 대화 공유 방식은 **합성 데이터/허용 범위에서만** 선택적으로 평가, 운영 기본값은 아님.
- 각 조건은 동일 notice version, evidence snapshot, prompt version, 모델 버전·quota, 동일 요구사항 판정 기준으로 고정. 수행 순서·cache 영향, 로그인·모델 warming, network/queue delay를 분리 기록.
- 첫 답 정확도, 문제 요건 누락률(FN), 근거 오인율, 잘못된 법적 자격 충족 판정률, 잘못된 Bid 권고율, 사람 검토 유발 비율, false consensus, 근거 미확인 비율; P50/P95 벽시계 지연, 총 CLI 모델 실행 수/사용량, 구독·API 비용 구분.

## 판정/수용
- 법적 자격 false-positive와 실적 증빙 왜곡은 critical risk. 단독보다 실제로 개선했는지 gold 기준으로 비교하지 않으면 교차 검증 효과 'UNKNOWN'.
- 둘 다 동의하더라도 잘못된 근거를 낸 사례를 별도 측정. 디베이트 반복은 기본 최대 1회로 제한하여 시간/토큰 폭증을 막음.
- 통계상 근거 부족·평가 부족이면 정확도 개선 % 주장하지 않고 사례/한계만 기록.
- 업무 담당자의 실제 최종 Bid/No-Bid은 별도 결정 API에 귀속; 모델이 자동 투찰하거나 직책자 승인 우회하지 않음.

## 인수
- evaluator로 0개 모델/no-gold/부분추출/빈 정답 분모 null, 결과 누출 차단, 같은 조건 재현, run SHA/스냅샷 해시·모델·prompt 버전·시간 기록 PASS.
- 실제 회사 자료 평가/외부 전송은 사내 공식 승인 후만, 결과는 비식별 집계 또는 승인된 비공개 장소에 저장.

## 작업 종료·인계
- 설계에 적힌 API/DB/명령은 제안 계약이며 설치된 공급자 CLI 및 실제 코드 기준과 불일치하면 official-source-first로 수정합니다.
- 코드 구현 뒤 해당 SHA 테스트/실행 증거, 실패 대응과 남은 차단은 CURRENT_STATE.md에 기록하고 TASKS.md 해당 AGW ID 상태만 갱신합니다.
