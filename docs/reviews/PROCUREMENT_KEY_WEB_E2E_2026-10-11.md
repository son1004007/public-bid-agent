# 나라장터 OpenAPI 인증키 웹 설정: Windows/Chrome E2E (2026-10-11)

## 대상 및 코드

- 개발 브랜치 `feat/sprint1-search-demo`, 기능 `3ecaadf`, 테스트 가상 키 개선 `7e0f32f`, UI 성공 알림 수정 `acd8653`.
- 사용자 첨부 공식 조달청 OpenAPI 참조자료 v1.2의 `ServiceKey` 필드 및 용역 `getBidPblancListInfoServcPPSSrch` 오퍼레이션 기준 확인.
- 발급 신청 페이지 버튼은 공식 https://www.data.go.kr/data/15129394/openapi.do 연결. 신청·로그인 동작은 포털에서 본인이 진행.

## PC 검증 증거

| 검증 | 결과 |
| --- | --- |
| Windows Python 3.12 `unittest discover -s local_app -p 'test_*.py' -q` | **74 PASS** |
| Windows DPAPI 현재 사용자 CryptProtectData / CryptUnprotectData 사용자 범위 왕복·손상 검출 | PASS |
| Chrome Headless 초기 '미등록' → 인증키 설정 패널 동작 | PASS |
| 별도 임시 서버/폴더에 **가상 키** 등록 → DPAPI 암호문 존재·평문 비존재·입력창 초기화 | PASS |
| 연결 확인 버튼 → 가상 provider API validator 1회 호출 (공식 외부 호출 없음) | PASS |
| 실제 수집 버튼 → 가상 provider → 로컬 JSON 공고 등록 | PASS |
| 등록 키 삭제 → 암호문 제거·수집 버튼 다시 비활성·공고 JSON 키 비노출 | PASS |
| 실제 로컬 127.0.0.1:8765 서버 재시작·GET `/`, `/decision-preview`, `/dashboard-live.js`, `/api/dashboard`, `/api/procurement-key`, `/api/decision-profiles` | 6경로 HTTP 200 |
| 실제 기존 `cases.json` SHA-256 재시작 전후 동일, 공고 5건 유지 | PASS |
| 실제 사용자 발급키 입력/공식 조달청 API 응답 검증 | **NOT RUN: 사용자 키를 입력하지 않았음** |

GitHub CI:
- [acd8653 Push](https://github.com/son1004007/public-bid-agent/actions/runs/38113357140): SUCCESS
- [acd8653 PR](https://github.com/son1004007/public-bid-agent/actions/runs/38113360004): SUCCESS

## 보안·잔여 검수

- 실제 발급 키 값을 채팅/GitHub/진단 로그/문서에 입력하거나 확인하지 않음. 실제 사용자의 키 파일도 수정하지 않음.
- DPAPI 사용자 암호문은 `LOCALAPPDATA/PublicBidAgent/secrets` 아래에 보관. 계정이 바뀌면 복호화 실패 처리.
- 서버는 Host/Origin/CSRF 검사를 그대로 수행하고 127.0.0.1에서만 동작. 인증키 GET은 `configured/source/can_save/can_delete`만 반환.
- 실제 API 연결 검사는 사용자가 로컬 UI에 직접 키를 등록하고 클릭해야 수행 가능. 이 검증이 완료되기 전 실공고 수집 성공을 주장하지 않는다.
- 독립 AGY/Gemini/Codex 최종 보안/의미 검수·사용자 UX 승인 미완료. Draft PR 유지, main 병합·대외 배포 HOLD.
