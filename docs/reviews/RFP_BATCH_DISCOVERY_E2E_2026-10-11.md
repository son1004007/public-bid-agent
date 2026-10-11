# 실제 G2B RFP 배치·누락 발굴 검증 (2026-10-11)

## 근거 및 범위
- 전역 Control 및 대상 저장소 AGENTS/현재 브랜치 Draft PR #1 확인.
- TD-kiseok 로컬 Python 3.12 전용 `.venv`에서 Python 102 tests PASS; JavaScript syntax PASS.
- 기존 사용자 파일: `user-json/dashboard.json` 수집공고 2,223건 (CANDIDATE 143/REVIEW 2,080), 원래 RFP 본문 추출 성공 5건. 사용자 `cases.json`은 별도로 관리.
- 사용 JSON을 직접 배치하지 않고 바이트 동일한 `rfp-batch-e2e-data/dashboard.json`으로 복사하여 별도 8766 서버에서 실공고 처리.
- 복사본 배치 1건 처리 후 DONE 2/FAILED 0/PENDING 141, 다음 3건 후 DONE 5/FAILED 0/PENDING 138, 분리 Chrome 클릭 2건(2회 검증) 후 DONE 7/FAILED 0/PENDING 136 (합계 143; 이미 EXTRACTED 후보 1건은 중복 분석하지 않음).
- 실제 예시 `G2B-R26BK01735571-001` 공식 첨부 문서 2개 추출 상태 기록 및 기존 2,223건/담당자 판단 이력 개수 유지. 추출의 의미 정확성과 업체 자격은 검증 전.
- 검토대기 2,080건에서 공식 API `information_business`, `procurement_classification`, `attachments[].name`, `title` 등을 이용한 read-only 상세 우선 후보 227건 발굴.
- `G2B-R26BK01763641-000` 순천향대학교 학습경험플랫폼(LXP) 구축(1단계) 용역은 기존 REVIEW의 개발 관련성 검토 사례. RFP/정정/입찰 가능 업체 자격 미확인, 자동 후보 승격 없음.

## 격리/제약
- 실제 사용자 로컬 파일 4종(cases/dashboard/department_profile/decision_profiles) 변경 없음이 요구됨; 커밋 및 운영 적용 전에 SHA 재확인.
- 공식 공고 문서만 추출, 비밀키 출력·보관/외부 AI 전송 없음. 회사 보유 요건을 임의로 생성하지 않음.
- 부서 카테고리는 현재 AI/SW/DATA/SECURITY 기존 선택 기능 재사용; REVIEW 227건은 가설적 검토 우선순위이므로 수행가능 건수로 해석 금지.
- 최대 2개 문서의 12,000자 발췌 제한 때문에 RFP 전체 조항 검증과 페이지/조항 위치 정밀 추적은 후속. 확정 적격성 0건, 회사 입찰자격 확인 미완료.
- 독립 AGY/보안 의미 검수·사용자 UI 승인 전 Draft PR 유지/main 병합 금지.

## 독립 Codex 1차 검수 / 수정 후 회귀
- Windows Codex CLI 0.154.0, gpt-5.6-terra / read-only + 코드만 stdin 전달 방식으로 독립 검수 실행. 다른 앱의 MCP OAuth 오류가 있었으나 코드 자체 리뷰 결과 수신.
- High: 느린 배치 작업의 최신 RFP 덮어쓰기 경합 -> 문서 필드 signature 검증 후 낡은 작업 결과 저장 거부.
- Medium: 기존 본문 교체시 소실 -> `document_prior_versions`에 이전 본문/출처/근거 저장 (최대 10 버전; 이후 결과 덮어쓰기 거부). 실패한 문서 추출은 기존 비어 있지 않은 본문을 덮어쓰지 않음.
- Medium: e발주 상세 API 비정상 응답시 배치 고착 -> 상세 첨부 목록 형태 확인, 문서별 예외를 기록해 다음 처리로 진행.
- Low: 실패 재시도 버튼에서 선택 건수만 처리한다고 명확히 표시. 동시 변경된 이미 추출완료 문서의 관련 첨부 자동 병합은 하지 않으며 기존 보존을 우선 (잔여 개선).
- 추가 동시 덮어쓰기 및 이전 본문 보존 합성 단위 테스트 2건 신설. Python 전체 102 PASS, JS syntax PASS.
- Codex 독립 **재검수는 별도 결과 확인 전**; 1차 지적사항 수정·테스트와 별개로 완료 판정 금지.
