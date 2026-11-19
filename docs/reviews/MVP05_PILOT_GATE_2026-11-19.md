# MVP-05 시범 배포 게이트

2026-11-19 · 후보 브랜치 전용 · RELEASE NO_GO

## 실행 순서
1. 정확 후보 SHA의 기존 4 CI workflow 및 migration check, PostgreSQL 회귀.
2. 합성 실제 Chrome: 최초 암호 변경 → 공고 → RFP 근거 → 손익 → 공유 견적 → 의견 → 참여 결정 → 다시 열기 → 로그아웃. 1440/390 viewport와 저장 이벤트 검증. 일반 사용자/다른 사업부/세션 폐기 음성 사례는 API 회귀에서 확인.
3. 별도 문맥 독립 최종 검수(AGY/Gemini 금지), 실패 수정 후 동일 SHA 재검증.
4. 승인된 실제 조달 수집원/공식 RFP 샘플, 조직 집계 정책·권한·가공 수준, 운영 계정 처리 확인. 실자료 정확도와 실제 설치 승인은 별도.
5. 대상 환경 승인 및 격리 사전 점검: 전용 DB/파일/서비스 계정, HTTPS/접근제한, 인바운드 및 비밀관리. 기존 서비스 보존.
6. 일관된 DB/파일 백업 범위 승인, 격리 복원 및 마이그레이션, 이전 버전 복구/롤백 rehearsal. DB 개별 복원은 통합 복원 증거가 아님.
7. 승인 범위 내 제한 pilot 설치, smoke test 및 사용자 피드백. 게이트 전체 충족 전 main merge/실제 설치 금지.

## 증거와 차단
- b37faa6 server foundation Windows CDP 실패(job 135405606098), Ubuntu·PostgreSQL PASS. 원인 가설: in-memory SQLite 공유 연결의 concurrent access. 정확 새 SHA 결과를 CURRENT_STATE.md에 기록.
- 기존 중앙 비공개 사용자 조치 미해결. 실제 계정/원가/운영 데이터 변경 금지.
- 조직별 구성원/승인권한 부여와 기준 등록 절차 및 데이터 검증은 승인 전 미실행; 정책 불명확하면 fail closed.
- 독립 reviewer 미확보 REVIEW_DEBT. 본 문서는 개발/시범 준비용이며 승인·실제 배포 증거가 아니다.


## 2026-11-19 추가 검증
- 19f14e0 exact hosted Chrome CDP full business flow PASS at 1440/390; PostgreSQL and Ubuntu foundation PASS. Windows synthetic local/Sprint1 not final at observation.
- V2 recovery candidate must prove nonempty MVP table content, current selected table counts, verified storage copy and rolled-back synthetic write. The uploaded dump/manifest hashes must be from a trusted private record. Not a release rollback or live coordinated snapshot. Legacy v1 has limited coverage; prior schema backup uses pinned compatible scripts, not v2.

- c5b35d9 actual hosted PostgreSQL nonempty MVP DB+file restore/content test PASS (135409832456); count/fingerprint and recovery only, not operational cutover rollback. Targeted author review candidate hardens stale cost publication and approver eligibility; new SHA verification pending. Independent review remains outstanding.

- Read-only pilot preflight and [operations handoff](MVP05_PILOT_OPERATIONS_2026-11-19.md) added as candidate. Production target not authorized, no deployment/reviewer GO. CHECKS_PASS is not release approval.

- NAS isolated synthetic candidate 4853ab2 runs locally with focused 24 tests PASS and anonymous access denied. Tailnet HTTPS route authorization denied; no remote browser/login evidence. Production gate unchanged.

- Owner registered isolated NAS preview tailnet route. Independent Windows client HTTPS health/workspace 200 and anonymous notice access 401; existing routes unchanged. Authenticated acceptance and reboot persistence remain open, no production release.

- Owner-authorized NAS G2B live call/import: 892 returned rows / 847 logical latest real notice records, 847 idempotent replay, synthetic records preserved; local workspace response passed. Real link projection blocked by current filter, real RFP/authenticated UI/persistent DB/reboot remain open. Synthetic cost inputs not approved company values. No production release.

- b272f27 4/4 CI + NAS 35 tests. Official links recollected/matched 847/847; isolated clone enrichment and relay switch verified, old DB state preserved, separate Windows HTTPS updated shell 200 and anonymous 401. Runtime banner labels simulated cost/decisions. No authenticated manual click verification, durable PostgreSQL, real RFP, independent review, or production release.

- Dedicated NAS PostgreSQL 16.15 live preview cutover PASS. Private persistent SQLite and PostgreSQL archives; 3,621 object exact migration parity, 850 notices/1,697 versions/847 links, account maintained, sessions excluded. Read-only socket connection and separate client HTTPS/anonymous 401 PASS. Archive full read verified; actual restore, restart-safe web/relay/collector and reboot acceptance pending. Existing DB/services unchanged, no release approval.
