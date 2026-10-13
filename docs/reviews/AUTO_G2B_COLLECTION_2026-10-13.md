# 2026-10-13 Windows 자동 공식 용역 공고 수집 구현·실검증

## 결론

- 개발 브랜치 `feat/sprint1-search-demo`의 예약 수집 코드 추가, Windows Task Scheduler **등록 완료**. 매일 09:00 PC 로컬 시각, 로그인 중인 현재 Windows 사용자로 실행. 다음 예정 시각 **2026-10-14 09:00**.
- 초기 설치 직후 `Get-ScheduledTask`의 사용자 표시가 `User`로 축약돼 상태 조회가 잘못 차단된 문제는 Windows SID 동일성 검사로 보완. `Status` 재조회 결과 `Ready`, 다음 실행시간 정상.
- Python 3.12 Windows 전체 unittest **240 PASS**, 자동 수집 신규 테스트 **11 PASS** (마지막 실행), 실 API 조회 1일 dry-run **820건**, 7일 dry-run **3,053건**. 예약 실행기 독립 Codex 재검수 **GO** (단일 사용자 개인 PC localhost 한정), 코드 GitHub CI 성공.
- 첫 7일 실제 `--apply` 실행은 **공식 API ProviderError로 실패**하고 공고 원본을 변경하지 않음. 실패 상태만 `collection.status=ERROR` 기록; 수집 구간 오류 원인 상세 및 장기 재시도 검증은 미완료.
- 이어 실행한 1일 실제 `--apply` 성공: **826건 조회/826건 신규 저장**, 기존 2,223건에서 **3,049건**으로 증가, `collection.status=SUCCESS`, 수정 필드 계수 826, lookback_days 1.
- 이전 사용자 공고 2,223건 ID 전부 유지, 기존 담당자 최종 결정/추천/사유/RFP 본문 및 문서 증거 보호 필드 **13개 항목 모두 동일**, 전체 사람 판단 이력 동일. 다른 비공개 JSON 4종 SHA-256 동일.
- 적용 후 Chrome 실제 화면: 공식 목록 3,049건 바인딩, 상세 버튼 이동, RFP 수집관리 패널, 대시보드/추천/RFP API 3개 200, 모바일 390px 가로 넘침 없음.
- Task Scheduler는 **아직 첫 예약 시각이 오지 않았으며**, 설치 후 표시된 `LastTaskResult=267011`은 최초 실행 전 상태. 일일 7일 예약 배치의 실제 성공은 검증 전이며 과장하지 않음.
- 전체 사업정보 최신성 확정, 옛 공고 정정·취소 상세 재조회, 장기간 10,000건 저장 한도 초과, 자동 RFP 원문/요구사항 구조화, LangGraph/AI 사업 추천은 별도 구현.

## 보존 및 운영 계약

- 실제 데이터 변경 전 기존 private JSON 5개 별도 백업, 원본/백업 SHA 확인. 기존 RFP 저장 자료와 DPAPI 키는 공개 코드/문서나 Codex에 제공하지 않음.
- API 7일 구간 중 어느 일자나 페이지라도 실패하면 전체 결과를 일부 정상 수집으로 저장하지 않고 이전 공고·사람 판단을 보존.
- API 일시 오류는 같은 구간을 한 번 재시도. 중단된 배포 저널 및 Windows 경로 재분석 여부를 확인하고, 서버와 동일한 OS JSON 잠금으로 저장.
- Task Scheduler 로그인 조건: PC가 켜져 있고 해당 Windows 사용자 로그인 세션이 있어야 실행 가능. 놓친 실행은 StartWhenAvailable로 예약되지만 로그아웃 상태의 무인 서비스 수준을 보장하지 않음.
- 작업 상태: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install_local_collection_schedule.ps1 -Action Status`. 예약 제거: `-Action Remove`. 서비스 화면: `http://127.0.0.1:8765/decision-preview`.

## 다음 작업

1. 다음 실제 7일 예약 실행의 성공/실패, 공개 API 이용한도·응답 변화 확인; 실패 유형별 코드/재시도·감시 기록 강화.
2. 정정·취소 공고 원천 상세 API를 재조회해 기존 RFP 근거 stale 표시 및 재추출 대상 관리.
3. 공식 RFP 요구사항을 구조화(참가자격, 실적, 면허, 인력등급·공수, 과업범위, 금액/마감, 원문 페이지·추출 한계)한 뒤 부서 보유역량·수익성을 매칭하여 근거 기반 추천을 구현.
