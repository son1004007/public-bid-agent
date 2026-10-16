# RFP 확보 품질 메타데이터 진단 — 2026-10-16

## 범위 및 코드

- 사용자 후속 순차 작업 D-17 / 관련 백로그: 원문 누락 가능성 식별.
- 변경: `local_app/rfp_coverage.py`, `local_app/test_rfp_coverage.py`, `frontend/public/dashboard-live.js`. 기존 `GET /api/dashboard/rfp-coverage`에 새 집계 필드만 추가.
- 기존 관심부서 `CANDIDATE` 선정·마감조건을 활용한다. 취소/구차수/REVIEW 표시는 마감 전 활성 후보에서는 제외하지만 전체 선택 후보에서 보존한다.
- 결과: `by_quality_all` / `by_quality_active`; 표준화된 12개 위험/상태 코드별 비식별 **공고 건수**. `LIFECYCLE_REVIEW`는 취소·구차수 상태와 구분한다. 동일 공고가 여러 조건에 포함될 수 있으므로 숫자를 더해 전체 후보 수와 비교하지 않는다.
- `FULLTEXT_REFERENCE_UNVERIFIED`는 원문 SHA 결속 또는 파일 존재·해시를 확인했다는 뜻이 아니다. 비공개 JSON의 64자리 캐시 참조 형식만 보고 식별한다.
- `EXCERPT_OR_LEGACY_ONLY`는 발췌만 있는 추출 근거가 하나 이상; `EXTRACTED_WITHOUT_PROVENANCE`는 EXTRACTED 표시 대비 확인 가능한 기록이 없음. 과거 RFP STALE, parser 잘림/경고 플래그, 추출 문서 2개 및 첨부/증거 탐색 상한을 각각 표시한다.
- 파서·저장 캐시 자체를 읽지 않는다. API 응답에는 공고 ID/명, 파일명/URL, 원문·발췌, 비공개 직원·원가, API Key, 개별 SHA나 경고 원문을 포함하지 않는다. 외부 AI/나라장터 호출과 원본 쓰기 없음.
- 추출 실패를 자동 재시도하거나 원본 전체 PDF/HWP 페이지/표·OCR 정확도·요구사항 Recall을 판정하지 않는다.

## 검증 분리

- 합성 `test_rfp_coverage.py`: 품질 카운트, 중첩 가능성, 메타데이터 손상/상한, 비밀값 출력 금지 및 GET API 원본 보존 검증.
- Windows 실제 실행 1차: 프로젝트 CPython 3.12 가상환경 `python -m unittest discover -s local_app -p 'test_*.py' -q` **286건 OK, exit 0**. `node --check frontend/public/dashboard-live.js` PASS, 문서 동기화 PASS. 이 결과는 아래 Codex 지적 수정 전임.
- Codex 1차 읽기 전용 검수 **NO_GO**: REVIEW와 취소/구차수를 혼합한 명칭, 120건 초과 근거 탐색, 검증 기록 미기재. `LIFECYCLE_REVIEW` 분리 및 실제 리스트 탐색 범위를 최대 120건으로 제한·추가 합성 테스트 작성.
- 지적 수정 후 2026-10-16 Windows TD-kiseok CPython 3.12 프로젝트 venv에서 `cd local_app; python -m unittest test_rfp_coverage -q`: **6건 OK, exit 0**. 개인 원본을 사용하지 않은 합성 fixture/임시 HTTP 서버만 검증.
- 지적 수정 후 2026-10-16 같은 가상환경에서 `python -m unittest discover -s local_app -p 'test_*.py' -q`: **287건 OK, exit 0**. `node --check frontend/public/dashboard-live.js` PASS, `python scripts/check_documentation_sync.py` PASS, `git diff --check` PASS (Windows 개행 변경 안내는 경고만 발생).
- 실제 비공개 로컬 운영 JSON은 별도 **읽기 전용** 분석(본문/링크/공고명/해시 미출력): 선택된 후보 287건 중 마감 전 후보 180건. 마감 전 캐시 참조 57건(무결성 미확인), 발췌만/일부 발췌 31건, 파서 절단 표시 12건, 파서 경고 표시 21건. 합계가 후보 수와 일치해야 하는 지표가 아님.
- 원본 로컬 JSON 40개와 RFP 캐시 124개, 합계 164개 SHA-256 집계 기준값을 읽기 전용으로 확보했고 변경·백업 복사·외부 전송하지 않음.
- Codex 2차 검수: 실제 메타데이터 탐색·REVIEW 구분 결함 해결 판정, 보고서 검증 결과 누락으로 NO_GO. 본 섹션에 전체/대상/실측을 추가했고 재검수 대상은 최신 문서 정합성임.
- Codex 독립 리뷰는 공개 소스만 읽기 전용으로 수행하고 개인 RFP/JSON/인증키를 읽지 않는다.
- Codex 최종 재검수 **GO, 차단 지적 0건** (세션 `01a1434f-aa5c-7e23-aa4c-221c7c6dbb2b`). Windows 실행 결과는 작성자 런타임 증거이고 Codex read-only 샌드박스는 테스트를 직접 실행하지 않음.
- 검수된 코드 적용: 배포 저널 `COMPLETED`, RFP 배치 `PAUSED`, 기존 서버 루프백 포트·프로세스 부모·실행경로를 확인한 뒤 **해당 8765 서버만 재기동**. 화면 `/decision-preview` HTTP **200**, 실제 `/api/dashboard/rfp-coverage` HTTP 200 및 `quality_mode=UNVERIFIED_STORED_METADATA_ONLY`; 후보 287, 마감 전 180, 캐시 참조 57, 발췌/부분 발췌 31, 파서 절단 12, 파서 경고 21로 직전 읽기 전용 집계와 일치.
- 재기동 전후 비공개 JSON 40개+RFP 캐시 124개 **총 164개 SHA-256 집계 일치**, 파일 내용 변경 0건 확인(개별 해시·경로는 공개하지 않음). 실제 Chrome 버튼 클릭/모바일 렌더링은 이번 단위에서는 `NOT RUN`; API와 페이지 HTTP 확인만 `PASS`.
- 사용자 UI 최종 승인 및 `main` 병합은 별도.

## 미완료 (이번 단위와 분리)

1. 실데이터 원본 전체 정답 라벨·파서 누락률 및 오류별 원인 분석.
2. 회사별 실적·면허·가용 MM 근거 대조/AI 추천의 법적 책임 경계.
3. RAG/LangGraph 의미분석 외부 전송 승인, 실제 입찰 제출·평가·낙찰 추적의 전체 E2E.
4. 7일 배치 API 과거 실패 원인 진단은 사용자 명시 보류.
