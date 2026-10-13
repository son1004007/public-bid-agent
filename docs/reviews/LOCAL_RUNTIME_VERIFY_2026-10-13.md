# 2026-10-13 검수 승인 코드의 Windows 로컬 운영 반영 및 실제 Chrome 확인

## 범위와 버전
- 서비스: 개인 PC의 `127.0.0.1:8765`, 외부 공개 배포 아님
- 코드: `feat/sprint1-search-demo`의 `fe499d8` (배포·복구 결함 4건 수정, Codex 한정 GO)
- 기존 서버 실행 코드: `c0a1115` -> `fe499d8` fast-forward, 작업 트리 clean
- 기존 프로세스의 실행 경로가 해당 저장소 서버임을 확인하고 종료. 종료 후 포트 8765 비점유 확인.

## 데이터 백업과 보존
- 서버 종료 후 사용자 로컬 JSON 존재 파일 6개와 RFP 캐시 124개를 로컬 별도 백업 폴더에 복사.
- 원본과 백업의 SHA-256: JSON 6/6 PASS, RFP cache 124/124 PASS.
- 최신 코드 재기동 및 Chrome 검사 후에도 동일 원본/백업 해시: JSON 6/6 PASS, cache 124/124 PASS.
- 개인 사용자 자료, 이름, 공고 전문, 전체 첨부 파일 및 API 키는 이 공개 보고서에 저장하지 않음.
- 이전 70건 RFP는 이미 운영에 승격되어 있었으므로 중복 적용·재수집하지 않음.

## 서비스·브라우저 검증
- 로컬 `start-public-bid-agent.cmd`로 최신 소스 기동 PASS, loopback 127.0.0.1 바인딩 PASS.
- GET 9/9 HTTP 200: `/`, `/decision-preview`, `/app.js`, `/dashboard-live.js`, `/api/dashboard`, `/api/department-profile`, `/api/dashboard/recommendations`, `/api/dashboard/rfp-coverage`, `/api/rfp-batch`.
- 실제 Chrome headless CDP: HTML 렌더 PASS, JS 완료 대기 뒤 로컬 live script PASS, 수집관리 탭 클릭 시 RFP 패널 표시 PASS, 공식 공고 2,223건 데이터 바인딩 PASS, 실제 공고 상세보기 클릭 PASS, 대시보드/추천/RFP API 3/3 HTTP 200, 390px 모바일 레이아웃 가로 넘침 검사 PASS, 메인 화면 렌더 PASS.
- 초기 JS 미준비 시 테스트가 일시 실패했으나 `document.readyState` 및 라이브 함수 초기화 완료까지 대기해 통과. 운영 코드 기능 결함으로 판정하지 않음.

## 비공개 실제 데이터 복구 모의실험
- 운영 JSON 전체의 로컬 비공개 복사본으로 복구 시나리오 실행. JSON 2개 원본 해시 기록, PREPARED SQLite 의도만 기록하고 기존 텍스트 저널 누락을 가정. 그중 1개 JSON에 공백을 덧붙여 세대 불일치 재현.
- `recover` 실행 `RECOVERED_ROLLBACK` PASS, 두 파일 모두 초기 SHA 2/2 복원, SQLite 상태 COMPLETED, 운영 원본 JSON 2/2 불변.
- 시험 사본 자동 삭제 완료. 물리 정전·악의적 동일 계정 프로세스의 완전한 방어는 검증 범위 밖.

## 최신 공고/RFP 상태 (2026-10-13 조회)
- 공고 보관: 2,223건.
- RFP 작업 원장 143건: DONE 109, PENDING 34, FAILED 0, 상태 PAUSED.
- 현재 마감기준 관심 CANDIDATE 106건: 본문 추출 104건, 미지원 파일 형식 1건, 공식 링크 없음 1건. READY_TO_FETCH 0건.
- 마감/상태는 시간 경과에 따라 바뀌므로 원장의 34 PENDING을 현재 지원 가능한 34건으로 해석하지 않음.

## 미완료 / 별도 승인
- 최신 수정 코드의 데이터 안전성 및 로컬 브라우저 범위는 실증. 사용자 화면 직접 검수와 전체 입찰 적격성 확인은 별도.
- 실질 입찰가능 추천: 요건 구조화, 업체 보유 면허/실적 및 실제 인력 공수/원가, RAG+Codex/LangGraph 모델 평가, 근거·정정·오탐 검증 필요. 현재 추천은 read-only 규칙 기반 상세검토 우선순위.
- 정기 증분 수집·정정 취소·백필 34건·14개 parser 절단 문서/표·각주/기업 프로필/추천 근거 QA는 미완료.
- `main` 병합, 인터넷 공개 서버, 다중 사용자 React/FastAPI/OIDC 서비스 배포는 이번 작업에서 진행하지 않음.
