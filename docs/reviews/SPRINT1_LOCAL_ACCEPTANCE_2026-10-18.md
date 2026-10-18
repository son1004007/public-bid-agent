# Sprint 1 Windows 로컬 읽기 전용 실사용 검증 (2026-10-18)

## 범위
- Windows 단일 사용자 127.0.0.1:8765/decision-preview 실사용화 Sprint 1
- 상태는 소스 구현/합성 테스트, 운영 localhost, 사람 승인, 회사 원본 검증을 별개로 판단
- P04 개발 브랜치 커밋 8b7f719 및 GitHub Actions 39080710759 success는 검증됨
- P05 별도 독립 Codex와 GitHub Actions는 이 기록 작성 시 **진행 중**이며 GO/CI 없이 완료 판정하지 않음

## 실제 Windows 확인 결과
- 읽기 전용 HTTP 확인: /decision-preview 200, /dashboard-live.js 200,
  /api/dashboard/rfp-coverage 200,
  /api/dashboard/rfp-review-queue 200,
  /api/dashboard/recommendations 200
- RFP ID 검증: 형식 오류 400, 존재하지 않는 합법 형식 ID 404
- Chrome headless DOM 로드 PASS
- Chrome CDP 사용자 조작 PASS: 대시보드 mount, 공고수집 화면 클릭, 추천 목록 새로고침,
  실제 추천 카드 렌더링, 공고 상세 버튼, RFP 요구사항 탭,
  원문 근거 GET 버튼, 근거 조회 종료 상태 확인 (8 PASS, exit 0)
- SHA-256 읽기 전용 전후 비교: 로컬 보호 JSON/TXT/RFP 관련 파일 318개 중 변동 0개.
  이것은 해당 조회 구간 한정이며 모든 영구 기록·전체 개인정보 보호 인수 증거가 아님.
- 별도 집중 재현 unittest: 동일 배치 취소 보존·중복제거·다중 날짜 순서 3 PASS (exit 0).
- 보호된 원본 내용, 개별 해시, 회사 증빙, 개인 인력/원가, API Key는 이 문서에 기록하지 않음

## 남은 Sprint 1 완료 게이트
- P05 수정 후 전체 Python 회귀·JS/문서 검사 PASS
- 별도 Codex 독립 검수 GO 및 지적사항 해소
- feat/sprint1-search-demo에 변경 커밋/푸시, 해당 SHA GitHub Actions SUCCESS
- 변경 코드의 실제 로컬 서비스 적용 및 적용 뒤 Chrome/GET 확인과 기존 파일 보존
- 실제 PDF/HWP 페이지/표/각주/OCR 완전성·법적 적격성·직원/기업 증빙은 NOT VERIFIED
- 사용자 최종 UI 승인, main 병합, 대외 공개는 사용자 별도 승인 필요

## 실행기
- 개인 Windows에서만 state-journal.jsonl append-only 체크포인트와 Task Scheduler 작업을 사용.
- 앱 외부 운영 스크립트: AgentRunner/sprint1_acceptance.py, sprint1_chrome_cdp.cjs
- 인용된 테스트는 현재 로컬 서비스에서 수행된 읽기 전용 작업이며 실제 입찰 제출·계약·자동 사용자 결정 없음.
