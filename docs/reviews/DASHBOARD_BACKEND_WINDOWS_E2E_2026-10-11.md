# 새 공고 대시보드 실제 백엔드 연결·Windows 검증 (2026-10-11)

## 구현 SHA와 작업 범위

- 대상: `feat/sprint1-search-demo` Draft PR #1
- 구현: `24276e7` (로컬 dashboard.json 공고 조회/수집/사람 판단 이력); 이후 UI 실제/합성 안내 정정 `3abef44`, Windows CSRF 거절 연결 개선 `7d25549`, 일일 수집 범위 상한 조정 `514183b`.
- 공식 데이터 수집 라이브 호출은 인증키가 없는 환경으로 불가능함. 실제 API 키·실공고 응답은 아직 미검증.
- 외부 서비스를 사용하지 않는 합성 provider(네트워크 미호출)로 브라우저 실제 버튼/API/JSON 저장 경로를 검증함.

## 실행 증거

| 항목 | 결과 |
| --- | --- |
| Windows Python 3.12 전체 unittest | **66 PASS** |
| Node `--check frontend/public/dashboard-live.js` | **PASS** |
| 별도 임시 데이터를 이용한 Chrome headless DOM·버튼 E2E | **5 PASS** |
| 브라우저 공식 목록 초기 0건 표시 (합성 자동 혼합 방지) | PASS |
| 수집 버튼 → fake provider → 로컬 공고 저장·목록 1건 표시 | PASS |
| 상세 화면 필수조건 8개 미확인 표시 | PASS |
| 담당자 불참 사유 입력·최종 결정 JSON 이력 | PASS |
| 새로고침 후 해당 결정 복원·기존 cases.json 불변 | PASS |
| 실제 PC 127.0.0.1:8765 최신 서버 GET `/`, `/decision-preview`, `/dashboard-live.js`, `/api/dashboard`, `/api/decision-profiles` | 모두 HTTP 200 |
| 기존 실사용 `cases.json` SHA-256 재시작 전후 동일 | PASS |
| 기존 로컬 분석 공고 5건 | 유지 |
| 인증키 미설정 → POST `/api/dashboard/collect` HTTP 424, JSON 미생성 | PASS |
| 실제 조달청 API 인증·공고 수집 E2E | **BLOCKED: 인증키 미설정** |

CI evidence:
- [514183b Push CI](https://github.com/son1004007/public-bid-agent/actions/runs/38111295081) SUCCESS
- [514183b PR CI](https://github.com/son1004007/public-bid-agent/actions/runs/38111297786) SUCCESS

## Windows CSRF 일시 오류

- 수정 전 같은 66개 Windows 테스트 중 새 CSRF 거절 HTTP 테스트가 간헐적 `WinError 10053`으로 실패.
- BaseHTTPRequestHandler는 요청 본문이 남은 채 조기 403 응답 후 연결 종료 시 Windows에서 TCP reset 가능성이 있어, 수정 후 **허용된 최대 POST 크기 내에 한해 2초의 제한시간으로 잔여 본문을 읽고 403 반환**.
- 수정 후 Windows 66개 테스트 PASS. 이 재실행만으로 모든 장기 간헐 원인에 대한 완전한 재현/제거를 주장하지 않는다.

## 보안·미완료 게이트

- PC의 `DATA_GO_KR_SERVICE_KEY` 및 `G2B_API_KEY` 설정은 둘 다 없음. **실제 공식 API 1건 수집은 아직 불가능**. 사용자가 발급·PC 환경에 설정해야 하며 값은 Issue/코드/채팅에 기록하지 않는다.
- 중앙 User Action: [공공데이터포털 활용신청·인증키 설정 #20](https://github.com/son1004007/ai-agent-workflow-playbook/issues/20). blocking scope = TASK.
- 제한된 공식 목록 메타데이터만 노출. 실제 RFP, 정정/취소/평가점수, 가격/원가, Codex 자동 판정/제출/정기 스케줄러 미구현.
- 실제 Google 로그인·공개 멀티유저 서비스·운영 배포 없음.
- 독립 AGY/Gemini 및 Codex 최종 의미·보안 검수, 사용자 UX 승인 미완료: **Draft PR 유지 / main merge HOLD**.

## 다음 반복

1. 사용자 개인 키 환경 설정 후 실제 API 표본 조회·시간형식·정정·첨부 필드 검증.
2. 공식 상세·원문/RFP 수집 계약과 AI 분석 연결.
3. 정기 공고 수집 배치(공공데이터 호출 한도·실패/재시도·종료 포함) 별도 테스트 및 승인.
