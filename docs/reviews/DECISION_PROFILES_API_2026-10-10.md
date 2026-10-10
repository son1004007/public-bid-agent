# 로컬 판단 프로필 API 구현·CI 증거 (2026-10-10)

## 변경 의도

- 공고 목록/상세 퍼블리싱 이후 두 프로필의 서버 저장을 첫 번째 백엔드 수직 슬라이스로 연결한다.
- 사용자 요청으로 UI 승인 대기 상태에서도 로컬 합성 JSON 개발은 진행하고, 독립 최종 검수와 공개 배포 Gate는 유지한다.

## 범위

- 판단 기준: 이름/기술점수/최소 이익률/증빙 조건 3종, 버전 및 immutable snapshot.
- 영향인자: 기본 8 Hard Gate(변경 불가 표시), 12 Soft Factor 가중치(0~25 정수 및 합계 100), 개별 버전.
- 저장: `decision_profiles.json` 별도 파일, 기존 `cases.json`/`operations.json` 데이터 보존.
- 로컬 GET `/api/decision-profiles`와 CSRF 보호 POST `/api/decision-profiles/save`, 충돌 시 409, 손상 파일 503 및 자동 덮어쓰기 금지.
- 정적 HTML 파일 실행 시 서버 연결 없이 기존 시연 모드; `/decision-preview`는 로컬 API로 저장/새로고침 복원.
- 공고/판단/최종결정 기록은 여전히 합성 브라우저 메모리 시연. 실제 공식 조회·Codex 사용·입찰 제출 없음.

## GitHub evidence

- Commit: [10a0dfb](https://github.com/son1004007/public-bid-agent/commit/10a0dfb39496d6c25a82ec3308f4316c726b18dc)
- Push CI: [38059273249](https://github.com/son1004007/public-bid-agent/actions/runs/38059273249) - backend/frontend SUCCESS
- PR CI: [38059276328](https://github.com/son1004007/public-bid-agent/actions/runs/38059276328) - backend/frontend SUCCESS
- Local JSON unittest: 60 PASS (6.017s); FastAPI pytest: 11 PASS (0.26s), GitHub Linux runner.
- Frontend Vite/TypeScript build, Node JS syntax, static UI and README-sync gates: PASS.

## 미완료

- Windows 실제 로컬 사용자 브라우저 조작·재실행·동시탭 충돌 E2E: NOT RUN.
- AGY/Gemini 및 Codex 독립 의미/보안 최종 검수: NOT RUN / REVIEW_DEBT.
- public deployment, main merge, 사용자 최종 UX 승인: HOLD.
- 실제 나라장터 수집/판단 기록 영구저장·모델 추론: 미구현.

이 보고서는 CI 범위 외의 실제 사용자 환경 검증 또는 릴리스를 주장하지 않는다.
