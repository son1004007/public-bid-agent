# 공식 공고 웹 검토순위 증거 - 2026-10-12

## 변경 단위
- local_app/recommendations.py: 수집 공식 공고·부서 분야 기반 읽기 전용 상세검토 순위. 공식 분류/추출된 RFP 발췌 구분, 현재 마감 갱신, 담당자 불참 제외.
- local_app/server.py: GET /api/dashboard/recommendations, localhost Host 계약 유지, 개인 인력/원가/RFP 본문 비반환.
- frontend/public/dashboard-live.js: 기존 수집 관리 화면에 순위·근거·검토 필요·상세 이동 UI 추가.
- local_app/test_recommendations.py: 정상/마감/취소/사람결정/0개 프로필/사본 불변/응답 내용 제한/HTTP 검증.

## 실 데이터 경계
- 비공개 user-json 원본 2,223건에 대한 순위 **read-only** 계산: 현 시점 마감·분야 반영 후보 111, 반환 상위 30, 현재 추천 대상의 RFP 발췌 확보 0. dashboard/profile SHA 비교 일치; 원문·인력·실명/급여·키는 외부 검수 입력과 로그에 미전송.
- 143개 후보의 공식 RFP 3건 추가 추출은 사용자 데이터 격리 사본에서 실시: 시험 사본 장부 DONE 총 4, FAILED 0, PENDING 139. 새 우선 검토 목록에서 RFP 근거 연결 3건. 격리 사본은 실행 후 삭제되고 실제 사용자 원본 SHA 불변.
- 기존 사용자 포트 8765는 작업 당시 구 버전 서버였으며, 실제 웹 적용은 별도 백업·복원 확인 및 런타임 재시작이 필요하다.

## 수행 검증
- Python 전체 184건 PASS, JavaScript 구문 PASS. git diff --check 최초 공백 1건 수정 후 재확인.
- 신규 회귀 단독 7건 PASS. GET HTTP 원본 byte 불변 및 비공개 마커 누락 PASS.
- 첫 독립 Codex 격리 read-only 리뷰는 140초 제한으로 결과 미확보(BLOCKED). 원문·SHA는 PC 비공개 user-json/review_recommendations_20261012_result.json. 더 작고 중립적인 입력으로 재시도.
- 독립 AGY/Gemini 최종 검수, 운영 실제 브라우저 UI 승인, 전체 RFP 분석 및 진짜 Bid 추천은 미완료. RECOMMENDATION_READONLY 슬라이스 검증과 실제 추천·Release는 구분한다.

## 후속 게이트
- 최소 후보 RFP 수집·실패 원인 분류/인력요건 전체 문서 정밀도 검증, 부서 실제 면허·실적·인력 가용성·원가 검증, AI 전송 동의, 최종 추천 및 사용자 승인.
- public repo는 코드와 비식별 합성 fixture만; 운영/원본 RFP/회사 비용 원문은 로컬 비공개 저장.

## 독립 Codex 검수 및 수정 (2026-10-12)
- 두번째 읽기 전용 Codex 검수 입력 SHA-256 1ecb4c7070d72a5e8d3e7c73d4f53f5cf7f2d3b1c2babbdb4503c4a9c2be7ceb: 5개 구체적 경계 결함 제기. 사용자 기밀 미전송, 원문은 로컬 user-json/review_recommendations_focused_result.json.
- 마감/취소/유찰·담당자 불참 값의 대소문자 및 보관 상태 → 제외 규칙 강화.
- 저장된 category_evidence 문구만으로 RFP 추출 근거 인정 → 추출 성공 형식·해시와 실제 본문 발췌에 대한 별도 분야 재탐지로 전환.
- REVIEW 재발굴 때 프로필과 무관한 공고 노출 → 현재 프로필의 관심 분야 탐지 결과가 없는 공고는 순위에서 제외(원본과 기존 discovery 패널에는 남음).
- final 자유문자 응답에 포함 → 허용된 담당자 상태만 공개, 기타 값은 null로 마스킹.
- nullable 선택 필드의 오류 → 선택 필드에 안전한 기본값 및 fail-closed 검증 추가.
- 독립 검수 보완 후 사용자 원본 2,223건 read-only 평가에서 현재 상세검토 후보 111건, RFP 확보 0건. 대시보드 SHA 불변. 합성 신규 테스트 12건 PASS. 이후 전체/독립 재검수 및 CI 결과 확인 필요.

## 추천 근거 강화 및 실제 웹 검증 - 2026-10-12
- 2회차 독립 Codex 검수 입력 SHA-256 d10b015b5920a85977cb3e44e7faa5d03a584dcd3ebc579b9239ffbaf0de6225, 원문은 개인 PC 비공개 user-json/review_recommendations_recheck_result.json에 보관한다.
- 추가 지적: 소문자 취소 상태, 첨부 근거의 형식상 SHA 위조 가능성, 비정규 첨부 데이터로 전체 순위 실패. 수정: 상태 대소문자 정규화, 공식 첨부 URL·문서명으로 계산한 identity와 저장된 원문 발췌의 일치 확인, 비리스트 첨부 안전 처리 및 회귀 테스트.
- 공고 제목/기관명은 서버가 기존에 정규화한 공개 나라장터 원천에 한하여 추천 응답에 포함한다. 이 로컬 사용자 화면은 이미 전체 공고/상세를 표시하는 같은 신뢰 경계이며, 회사/인력 파일은 읽거나 반환하지 않는다. 입력 원문 자체의 개인정보/악의적 텍스트 여부에 대한 독립 감수는 공개 배포 전 추가 필요.
- 보유 SHA-256 형식 및 identity 비교는 저장 기록의 일관성 확인이며 원본 바이너리의 재다운로드 검증이 아니다. 법적 적격·과업 의미 확인·인력 및 실적 증명은 별도.
- 데이터 보호: 기존 로컬 공고·사례·운영정보·인력 4개 파일을 PC user-json/backups 아래 버전 백업, SHA 동일 및 임시 복원 확인. 실제 운영 데이터 변경 없이 격리 Chrome으로 수집관리 화면의 추천 카드/상세 이동·JS 오류 0 PASS.
- 실제 공고 2,223건에서 현재 분야·마감 조건 상세검토 우선 111건, 이 중 RFP 근거 확보 0건, 반환 상위 30건. 실 공고 제목·RFP 텍스트·사내 인력/급여·인증키를 GitHub/독립 AI 입력에 포함하지 않았다.
