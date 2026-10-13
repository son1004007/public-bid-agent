# 2026-10-14 RFP 구조화 1단계 소스 독립 검수 및 결정 문서화

## 범위
- 프로젝트: Public Bid Agent `feat/sprint1-search-demo`, 개인 Windows 11 로컬 127.0.0.1 MVP용 읽기 전용 RFP 표현 후보 구조화.
- 사용자 최신 선택: Stage 1 RFP 요구사항 구조화. 7일 배치 API 오류 진단은 동일 문제 재발까지 제외. Stage 2/AI 자동 추천 착수는 이번 변경의 승인 대상이 아님.
- 데이터 경계: 원본 사용자 로컬 JSON과 비공개 문서 캐시를 Codex 검수에 제공하지 않았다. 샘플 결과는 비식별 집계만 저장소에 기록한다.

## 실제 완료된 검증
- 기존 공식 44,000자 fulltext 청크 기반 8개 분류의 원문 표현 후보 추출. 공식 첨부 identity/이름/원본 SHA/캐시 청크 SHA 및 원문 텍스트 offset을 결속. 원본 페이지 ID는 `null`, 필수 조건·법적 적격성 `UNVERIFIED`.
- 2026-10-13 로컬 현재·비STALE·RFP 근거 보유 후보 66건 중 결정론적 20건 표본: 탐지 원문 표현 561건, 부분 텍스트 4건, 분석 실패 0건. 이는 실질적인 회사 적격성 분석이나 RFP 필수요건 561건을 뜻하지 않는다.
- Windows 3.12 전체 회귀 **274 PASS** (2026-10-13 로그), 구조화 전용 16 PASS, JavaScript/Python 구문 PASS, Git diff 체크 및 문서 동기화 체크 PASS. 실제 원본 RFP와 JSON 쓰기 없음.
- Codex 독립 읽기 전용 1차 `NO_GO`: 증거 파일명 표시가 공식 첨부 파일명에 결속되지 않음, 처음 실패 evidence 2개 뒤 정상 증거 누락. 공식 첨부 canonical 이름 대조 및 정상 증거 최대 2개 탐색(스캔 최대 120)으로 수정.
- Codex 2차 `NO_GO`: 공식 첨부 목록 120개 무경고 절단. 400개 공식 첨부 상한과 `PARTIAL` 경고 추가, 121번째/401번째 경계 테스트 추가.
- **Codex 3차 GO:** 신뢰 단일 Windows 사용자 localhost 범위; HIGH/MEDIUM 미해결 결함 확인되지 않음. 검수 AI는 코드를 읽어 판단했으며 테스트 실행은 별도 Windows 실제 실행 기록에 근거.

## 구분해야 할 상태
- **구현/테스트/독립 소스 검수:** 완료됨(해당 제한 범위).
- **현재 로컬 서버 재시작으로 새 API 실제 서비스 반영:** 아직 확인된 실행 증거 없음.
- **실제 Chrome 버튼 클릭 E2E·원본 JSON 40개/RFP 캐시 124개 전후 SHA 일치 확인:** 기준 원본 SHA 매니페스트는 생성됨; 새 코드 적용 후 최종 비교는 **미수행**.
- **GitHub CI:** 이 문서를 저장한 커밋의 실행 결과를 확인 후 별도 갱신. 소스 테스트 성공을 CI 성공이나 인터넷 공개 릴리스로 표현하지 않는다.
- **main 통합·사용자 UI 승인·대외 공개:** 미실행. 별도 승인.

## 참고
- [최신 확정 결정](../../DECISIONS.md)
- [RFP 구조화 계약](../design/RFP_REQUIREMENTS_SLICE_2026-10-13.md)
- [실제 RFP 표본 20건 비식별 결과](RFP_REQUIREMENTS_LOCAL_EVIDENCE_2026-10-13.md)
- `local_app/rfp_requirements.py`, `local_app/test_rfp_requirements.py`
