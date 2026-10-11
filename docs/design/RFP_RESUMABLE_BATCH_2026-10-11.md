# 실제 공고 RFP 순차 처리 - 2026-10-11

## 목표와 범위
- 전체 용역 원본 2,223건, 후보 143건, 검토대기 2,080건을 삭제하지 않는다.
- 1차 대상은 현 부서 프로필과 매칭되는 `CANDIDATE` 전체 (마감·취소도 기록 보존). OPEN 우선 처리.
- 기존 수집 관리 UI에 실행/중단/재개/실패 재시도와 진행률을 추가한다.
- 사용자 직접 요청 시에만 공개 HTTPS 문서 다운로드한다. 유료 AI·내부 업무자료 전송/입찰 제출 없음.

## 변경 계약
- `rfp_batch.json`: schema_version=1, revision, status, target_ids, items (PENDING/DONE/FAILED, attempts, updated_at). 기존 프로필·결정 데이터와 별도.
- `dashboard.json.notices[].document_evidence`: 문서별 식별 SHA-256, 문서명/출처, 본문 SHA-256·문자 수·최대 6,000자 발췌, 추출 경고 및 실패 상태.
- `document_status=EXTRACTED`이면 재다운로드하지 않는다. 동일 문서 식별자가 이미 성공이면 캐시 근거를 재사용한다.
- 문서 최대 2개/공고, 요청마다 1·3·10·25개, 단일 worker·3초 간격. 기존 URL 제한과 8MiB/첨부, subprocess 90초 한도 사용.
- 관련 RFP 이름이 없는 공고는 공식 e발주 첨부 목록을 API로 추가 조회하고 본문 확보를 시도한다. 공식 3개 상세 API 오류는 기존 첨부 분석을 차단하지 않는다.
- 실패는 검토대기로 보존, 수기 판단/이력·기존 추출 성공·회사 적격성에는 영향 없음.
- 프로그램 종료 중 미완료 공고는 PENDING으로 남으며 재시작 시 읽기 상태는 PAUSED; 재개 버튼으로 이어서 실행한다.
- 비정상 작업 중지는 현재 처리 중 문서를 끝낸 후 중단한다. PC 종료에 의한 처리중 손실은 마지막 원자 저장 지점부터 재개한다.

## 로컬 API
- `GET /api/rfp-batch`: 작업 상태·건수, CSRF 값. 내부 문서·키는 반환하지 않음.
- `POST /api/rfp-batch/start`: `{"limit":3}` - 처리 대상을 처음 확정하거나 미완료분 재개.
- `POST /api/rfp-batch/pause`: 현재 작업 완료 후 정지.
- `POST /api/rfp-batch/retry`: `{"limit":3}` - 실패 대상으로 한정하여 재시도.
- 기존 localhost Host/Origin/CSRF 검증을 그대로 적용한다. 서버의 JSON 원자 쓰기·단일 전역 LOCK을 재사용한다.

## 미완료/위험
- 본문 추출 성공은 참가자격 충족이나 실제 입찰 가능 확인이 아님.
- 공급자 문서 링크의 동적 교체/정정, 외부 파일 악성 파싱·Windows Job Object 자원 제한은 별도 보안 검수 대상.
- 바이너리 영구 캐시를 남기지 않으며 성공한 텍스트 근거를 JSON에 저장한다.
- e발주 목록 세부 API 실패 시 추출 불가 원인·원문 수동 확인 필요.
- 회사 등록/면허/실적이 없으므로 `legal_eligibility=UNVERIFIED` 유지.
- 검토대기 2,080건에 대한 비싼 전수 다운로드는 차후 우선순위 스크리닝 작업에서 처리한다.
- Draft PR 및 독립 AGY/Codex 검수·사용자 UI 승인 미완료 상태에서 main 병합·외부 배포 금지.
