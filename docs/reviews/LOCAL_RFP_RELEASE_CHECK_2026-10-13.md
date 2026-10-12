# 2026-10-13 로컬 RFP 운영 검수 및 재시작 증거

- 대상: `public-bid-agent` 개발 브랜치 `feat/sprint1-search-demo`, 코드 기준 `c0a11159699e14ed0d729c0b44975481e6bb1534`.
- 사용자 PC Python 3.12 전체 unittest: **221 PASS**. GitHub Actions 최신 해당 코드의 frontend/backend: **SUCCESS**.
- 현재 운영 2,223건 중 검증 대상 70건은 **이미** `EXTRACTED` 상태이고 격리 stage의 70개 본문/증거와 일치. 신규 승격 dry-run이 안전하게 중복 병합을 거부하여 실제 추가 apply는 수행하지 않음.
- 이전 배포 저널: `COMPLETED / RELEASE_APPLIED`. 저널상 과거 JSON 2/2 백업 SHA 일치, 활성 JSON 2/2 기대 SHA 일치. 비공개 전체 텍스트 캐시 124/124개 SHA-256이 격리 stage와 일치.
- Codex의 **새로운 승격 기능** 독립 최종 판정은 **NO_GO**: HIGH 두 건(승격 중 서버 정지 보장 부족, Windows 전원 장애 시 저널/파일 교체 영속성), MEDIUM 두 건(경로 교체/재분석지점 위험, 백업 준비 중단 복구). 배포 스크립트는 수정/재검수 전 다시 실행하지 않음.
- Codex 별도 한정 검수: 완료 저널과 SHA 일치, `cases.json` 유효, 신규 승격 없는 GET 전용 localhost 서버 **재시작은 조건부 GO**. 새 승격 NO_GO는 유지됨.
- 기존 런처로 127.0.0.1:8765 로컬 서버 실행. `/`, `/decision-preview`, `/api/dashboard`, `/api/dashboard/recommendations`, `/api/dashboard/rfp-coverage`, `/api/rfp-batch`: GET **6/6 HTTP 200**.
- Chrome CDP 실제 브라우저: 입찰관리 렌더 PASS, 수집관리 탭 클릭 후 공식 RFP 패널 표시 PASS, 브라우저 fetch GET 3/3 200, 모바일 폭 390px 가로 넘침 없음, 메인 렌더 PASS. POST/배치/수집/업로드/LLM 요청 미실행.
- 사용자 운영 데이터 변경을 동반하는 별도 테스트 없음. 임시 데이터 검증 사본은 삭제. 원본 백업 및 기존 운영 자료 유지.
- 공개 인터넷 서비스 배포, `main` 병합, 전체 앱의 독립 출시 승인 및 실제 법적 입찰가능 판정은 **완료 아님**.

## 후속 작업
1. 새 승격의 서버 quiescence, Windows power-loss 일관성, junction/TOCTOU, 백업 중단 복구를 설계·수정하고 합성 강제중단 회귀 테스트 추가.
2. Codex 독립 재검수에서 새로운 승격 `GO` 획득.
3. 실제 RFP 의미·행정 자격·업체 수행역량 추천 정확도 검증과 사용자 UX 승인. 이후 별도 `main` 병합/배포 결정.
