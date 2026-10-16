# RFP 추출 문자 손실 메타데이터 정량 진단 — 2026-10-16

## 업무 목표 및 판정 경계

- 사용자 후속 작업 D-17. 이전 `RFP_QUALITY_METADATA_2026-10-16.md`에서 발견된 절단 12공고 및 파서 경고를 보다 정밀하게 구분한다.
- 목표는 **저장된 추출기 메타데이터만으로 계산 가능한 문자 수 차이** 및 재검증 필요 범위를 확인하는 것이다. 비공개 원본 PDF/HWP 바이너리 대조나 원문 필수요건 전체 정답 라벨은 현재 없다.
- 그러므로 **실제 원문 누락 문자 수, 의미적 요구사항 Recall, 표/각주/OCR 정확도, 입찰 적격**은 `NOT VERIFIED`. `657,453`자를 원문 문서에서 독립 검증된 손실량이라고 주장하지 않는다.

## 구현 계약

- `local_app/rfp_extraction_loss.py`: 기존 `document_evidence` 메타데이터만 처리하는 순수 함수. 증거 기록별 최대 120건, 최대 길이 2,000만자, 저장 길이 44,000자, 캐시 참조 식별 형식 검증. 원본 파일을 열지 않는다.
- `fulltext_truncated is True`와 `fulltext_reported_chars > fulltext_chars`이고 기타 형식 조건이 충족될 때만 기록된 미보관 문자 수 차이를 합산한다. 잘못되거나 빠진 근거는 계산 불가로 분류한다. 잘림이 아닌데 길이 차이가 있는 경우 별도 불일치 신호로 분류한다.
- `local_app/rfp_coverage.py`: 기존 부서 관심분야·마감·취소/구차수/REVIEW 분류 경계 그대로 유지; `extraction_loss_all`과 `extraction_loss_active` 및 `loss_mode=STORED_PARSER_METADATA_UNVERIFIED_ORIGINAL`를 추가. 숫자는 **증거 기록 건수/해당 공고 건수/메타데이터 합계**이지 중복 제거한 문서 수가 아니다.
- `frontend/public/dashboard-live.js`: 수집 화면에서 마감 전 후보 기준 절단·정량화/불가·경고·기록된 미보관 문자 수를 추가 표시. API에 새 필드가 없으면 기존 화면 유지.
- **비공개 데이터/출력 제한:** 개별 공고 ID/명, 원문, 발췌, 첨부 파일/URL, 개별 SHA, 경고 원문, 비공개 인력·원가를 새 API 응답으로 반환하지 않음. 로컬 파일 원본 쓰기·수집/모델 요청 없음.
- **확정하지 않는 것:** 원본 RFP PDF/HWP 표·각주·OCR·문서 구조가 누락된 정도, 공식 원본 전체 문자 수, 사람의 Bid/No-Bid.

## 검증 기록

- Windows `TD-kiseok`, 프로젝트 CPython 3.12 가상환경: `cd local_app; python -m unittest test_rfp_extraction_loss test_rfp_coverage -q` **11 PASS** (합성·로컬 테스트만).
- 실제 로컬 저장자료 **읽기 전용 비식별 집계**, 마감 전 부서 후보 180공고: `extracted_records=161`, `truncation_records=13`, `quantified_truncation_records=13`, `notices_with_reported_loss=12`, `reported_unstored_characters=657453`, `warning_records=23`; 증거 레코드 수와 공고 수는 다른 단위.
- 수치는 동일 문서/증거의 여러 레코드 복제가 있을 수 있으므로 유일 원문 손실량으로 해석하지 않는다.
- Windows CPython 3.12 프로젝트 가상환경 `python -m unittest discover -s local_app -p 'test_*.py' -q`: **292건 OK, exit 0**. `python scripts/check_documentation_sync.py` **PASS**, `node --check frontend/public/dashboard-live.js` PASS, `git diff --check` PASS (Windows 개행 안내 경고만 표시).
- Codex 읽기 전용 **초기 독립 검수 GO, 차단 지적 0건** (세션 `01a14366-c0b2-78f2-b497-a7d870d934c5`), 기존 상태 보존·수치 단위·비밀 비노출·숫자 정밀도/상한 확인. 검수는 정적이며 Codex 샌드박스에서 테스트 직접 실행은 NOT RUN.
- Codex 비차단 보완 제안: 신규 손실 집계 테스트에는 SUPERSEDED만 명시되어 있고 취소종류·REVIEW 각각의 손실 제외 전용 assertion은 없음. 이 상태들은 기존 `rfp_coverage.py`의 공통 필터와 기존 수집 품질 테스트를 그대로 재사용하며 추가 검증은 후속 가능.
- 실사용 비공개 로컬 JSON 40개 및 청크 캐시 124개 **총 164개 SHA-256 집계 기준값 확보**. 내용·해시는 공개 보고서에 기재하지 않는다.
- **로컬 서버 적용 PASS**: 릴리스 저널 `COMPLETED`, RFP 배치 `PAUSED`, 127.0.0.1:8765 프로세스·Python 부모 실행경로 확인 후 기존 서버만 재기동. `/decision-preview` HTTP 200, `/api/dashboard/rfp-coverage` HTTP 200. API에서 `loss_mode=STORED_PARSER_METADATA_UNVERIFIED_ORIGINAL`, 부서 후보 287, 마감 전 180, 추출 증거 161, 절단 13, 공고 12, 메타데이터 신고 미보관 657453자, 정량화 불가 0, 경고 기록 23건 확인.
- **비공개 원본 보존 PASS**: 로컬 JSON 40개 + 청크 캐시 124개 **164개 SHA-256 집계 동일**(읽기 전용 전후 비교). 원본 문서의 실제 전체 누락률은 여전히 NOT VERIFIED.
- Windows 실제 Chrome 버튼 클릭·모바일 렌더링은 이번 단위에서 **NOT RUN**; localhost 페이지/API 응답만 실증. GitHub commit/CI는 실제 확인 후 기록한다.
