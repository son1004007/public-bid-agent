# AGW-13 | 합성 CI·운영 배포 승인·복구·관측성

- 기준: 2026-11-20 KST / 설계 단계, **구현·테스트·운영 배포 미완료**
- 우선순위: P1/HOLD; 의존관계는 [작업 단위별 목차](README.md)와 [HBR 원장](../../../TASKS.md) 참고
- 설계 정본: [사용자별 서버 로그인·세션 Resume](../../server-migration/16-user-cli-session-and-blind-cross-check.md), [권리·모델 실행 정책](../../server-migration/15-mcp-provider-executor-subscription-policy.md)
- 공통: 회사 비공개 자료 외부 전송/계정 중계/기존 운영 환경 변경은 허용된 경로와 공식 승인 확인 전 OFF. 본인 로그인/세션 보관·사용자별 접근 통제 유지. 독립 AI 코드 리뷰는 선택, 기능/보안/회귀 테스트는 필수.

## 환경 및 배포 단계
- Source-only design → GitHub-hosted ephemeral CI(합성/무토큰/무실행기) → 승인된 격리 staging → data1 운영 전 검수·인수(회사 별도 승인).
- 기존 server Django settings.test와 migrations/DRF test harness를 재사용하고 공개 저장소의 CI에 인증 파일·회사 RFP·실제 공급자 계정 접근을 넣지 않습니다.
- 실제 data1은 기존 다른 업무 container/포트/방화벽/저장소 보존. 승인되지 않은 workspace mapping/운영 접근 권한 상승·root SSH 실행 금지.

## CI job 제안
1. lint/type/정적 보안 검사 + migration check + OpenAPI 계약 검증.
2. AGW-01/03 모델·가용성·RBAC 테스트, AGW-04 세션 lease/concurrency/restart mock.
3. AGW-05/09 canonical JSON·ACL·evidence·malicious prompt 검증.
4. AGW-06/07 mock CLI 오류 매트릭스; 인증 비밀, 실제 공급자 요청 0건.
5. AGW-08 0/1/2 READY routing, JobAttempt/outbox 재전달·idempotency.
6. AGW-10/11 증거 diff, 순차 vs 독립 컨텍스트 격리, issue round 한도.
7. AGW-12 프런트 계약/접근성/경쟁 상태, AGW-14 synthetic quality baseline.
8. 각 job SHA, 환경 버전, coverage, 실패 케이스 및 정책 검증 증거를 docs/reviews 또는 CURRENT_STATE에 기록. 문서만 변경한 CI는 실제 실행 성공의 증거로 사용하지 않습니다.

## 격리 staging 준비
- 공식 CLI 설치 가능 OS/CPU/FS/출구 네트워크, 사용자별 UID·홈·권한, 비밀 파일 ACL, session storage 백업/복구, 만료 후 재인증, worker fencing/동시성 리밋 검증.
- 운영 이전: DB+해시 manifest+세션 volume의 일관된 backup generation(자격증명은 승인된 보안 절차의 별도 경로), 복원 리허설, 기존 서비스 unaffected, rollback.
- 재배포 후: 같은 user/provider/notice SessionBinding resume, 0/1/2 READY 수직 기능 E2E, 데이터 전송/사용량 감사, 실패시 서비스 OFF로 빠르게 전환.
- 가용성/지표: login state(개인 식별자 가림), successful resumes / resets, queue wait, p50/p95 elapsed, invalid JSON, evidence disagreement, quota, permission denial, external calls, 비용 추정. prompt/raw RFP/credentials는 metrics/logs 금지.

## 차단·검증
- 회사 승인이 없거나 공급자별 계정 사용·외부 자료 전송 정책이 불명확하면 공식 모델 호출/배포 HOLD.
- 인증 만료/권한 철회→신규 호출 즉시 금지, 기존 세션/결과는 접근 범위 보존; 실제 stop과 신규 호출 0건 확인.
- '성공'은 동일 SHA CI 및 승인된 staging/운영 실제 사용자 경로 실행 증거로만 인정. 문서의 계획만으로 배포 주장 금지.

## 작업 종료·인계
- 설계에 적힌 API/DB/명령은 제안 계약이며 설치된 공급자 CLI 및 실제 코드 기준과 불일치하면 official-source-first로 수정합니다.
- 코드 구현 뒤 해당 SHA 테스트/실행 증거, 실패 대응과 남은 차단은 CURRENT_STATE.md에 기록하고 TASKS.md 해당 AGW ID 상태만 갱신합니다.
