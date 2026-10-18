# P01/P06 문서 위험 검토·부서 준비도 합성 검증

- 기준: 2026-10-18, 개발 브랜치 `feat/sprint1-search-demo`, 시작 HEAD `1d0e515`의 미커밋 변경.
- 요구: D-02/D-06/D-07/D-17/D-19, P01/P06 및 이번 사용자 한정 지시. CONTROL/저장소 진입 문서·P00~P11을 확인했다.
- 상태: IMPLEMENTED / TESTED. 독립 Codex 검수는 orchestrator 인계 대기이며 CODEX_GO/REVIEWED/RELEASED 아님.

## 변경과 계약

- `document_quality.inspect`: PDF 각 페이지에 고정 `flags` 추가. 텍스트가 충분해도 직접 이미지 객체가 있으면 OCR 육안 대조 대상으로 표시한다. 희소 페이지는 스캔 확정이 아니다. 이미지 메타데이터 오류는 페이지/전체 `image_object_count=null`; 오류 내용은 반환하지 않는다. PDF 표·각주 구조 미검증을 항상 명시한다.
- HWPX `section_details`는 숫자 섹션 순서로 표·각주·병합 표식과 `page=null`을 반환한다. `cellSpacing`과 span 1은 병합으로 세지 않는다. 숫자 본문 섹션이 없으면 진단 실패다. 원문 텍스트·파일명·해시를 반환하지 않는다.
- `rfp_review_queue.build`: 저장 메타데이터 큐에 페이지/표/각주/OCR 수동 검토 안내를 추가한다. `structural_diagnostic=NOT_PERFORMED_BY_QUEUE`; 실제 구조 진단이 큐에 저장되거나 실행된 것처럼 표시하지 않는다.
- `bid_readiness.assess`: 기존 6개 확인표를 유지하며 `evidence_gaps`, `data_gaps`, `required_review`, `requirement_comparison=NOT_PERFORMED`, `evidence_verification=UNVERIFIED`를 추가한다. reviewed 기록의 출처/요약/확인일 형식·누락/미래 확인일은 `EVIDENCE_RECORD_INCOMPLETE`로 표시한다. `today`는 합성 테스트용 선택 인자이며 HTTP 입력으로 받지 않는다.
- 기존 `operations.clean_profile` 수치 검증을 재사용하여 직무 미등록, 가용 MM 미정/전체 0, 0원 단가, 급여만 기록된 원가 기준 등을 구분한다. 직무명/개별 값/출처/요약은 반환하지 않는다. 모든 자료가 기록돼도 실제 자격·실적 충족·사업기간별 가용성·수익성은 확정하지 않는다.
- 대시보드는 원본 대조 결과를 기본 접힌 페이지/섹션 목록으로 제공하고 준비도 누락 사유와 대조 항목을 텍스트 노드로 표시한다. 입력/파일 저장, 새 외부 호출, 새 패키지 및 보안 설정 변경 없음.

## 실행 증거

Windows CPython 3.12.0, 설치된 pypdf 6.14.2/reportlab 5.0.0/Pillow 10.3.0을 사용했다. 의존성 설치/변경 없음. 테스트마다 `PUBLIC_BID_LOCAL_DATA`를 새 임시 경로로 지정했고 HTTP 시험은 임시 JSON과 임의 loopback 포트만 사용했다.

`local_app`에서:

```powershell
$env:PUBLIC_BID_LOCAL_DATA = Join-Path ([IO.Path]::GetTempPath()) ('pba-synthetic-' + [guid]::NewGuid().ToString('N'))
python -B -m unittest test_document_quality test_bid_readiness test_rfp_review_queue -v
# PASS: 17 tests
python -B -m unittest test_document_quality test_bid_readiness test_rfp_review_queue test_operations test_staffing_requirements test_rfp_original_workflow test_rfp_original_compare test_rfp_coverage test_bid_decision_preview -q
# PASS: 82 tests, 8.266 seconds
```

저장소 루트에서:

```text
node --check frontend/public/dashboard-live.js
# PASS
node --test scripts/test_rfp_evidence_summary.cjs
# PASS: 기존 요약 계약 3 tests (새 UI 브라우저 검증을 대체하지 않음)
```

신규 9개 시험과 기존 검증 강화: 이미지+텍스트 합성 PDF, 페이지별 OCR 위험, 이미지 조사 오류 비노출/null, 섹션 정렬/위치/병합 오탐, 잘못된 본문 구조, 크기/페이지/엔터티 제한, 근거 누락/미래 확인일, 준비 자료가 모두 있어도 미검증 유지, 인력/원가 부족 사유, 취소·구차수·STALE 보류. HTTP 검증에서는 비공개처럼 표시한 합성 sentinel 비노출과 임시 JSON/캐시 불변을 확인했다.

`git diff --check` PASS. 작업 트리의 두 README 변경·P01/P06 설명·82 PASS 기록·검증 문서 링크 일치 검사 PASS. `scripts/check_documentation_sync.py`는 HEAD 커밋 비교용이므로 미커밋 작업의 검사로 오용하지 않았으며, 커밋 이후 CI는 orchestrator에 남겼다. Git 소유권 확인은 해당 읽기 명령에만 정확한 저장소 경로를 지정했고 전역 Git/시스템 설정은 변경하지 않았다.

## 한계와 인계

- CONFIRMED: 위 합성 실행 결과와 입력 불변성. 실제 사용자 JSON/RFP/회사 증빙 접근·전송 없음. 실제 운영 데이터 SHA를 검사했다고 주장하지 않는다.
- UNKNOWN/NOT RUN: 실문서 페이지/표/각주/OCR 정확도·전체 Recall, 실제 업체 근거의 유효성, 공고별 요건 비교, 기간별 가용 MM/총원가, 브라우저 GUI 인수, 전체 회귀, GitHub CI, 운영 적용 및 독립 검수.
- PDF 이미지 수는 직접 XObject만 센다. 중첩 Form/인라인 이미지 전수 탐지와 OCR 자체 실행은 이 진단 범위 밖이다. HWPX 표식 개수는 실제 셀/각주 텍스트의 정확도나 완전성이 아니다. 정상 텍스트 추출로 표·각주·OCR 정확도를 보증할 수 없다는 [pypdf 공식 문서](https://pypdf.readthedocs.io/en/stable/user/extract-text.html)의 한계를 유지한다.
- 출처 문자열/확인일이 있다는 사실만 검사하며 증빙 파일을 열거나 등록·면허 유효기간을 자동 인증하지 않는다. freshness 만료 정책을 임의로 만들지 않고 기존 needs_refresh를 유지한다. 운영자료 누락은 부적격 판정이 아니다.
- orchestrator: 이 diff의 독립 Codex 읽기 전용 검수 → 지적 수정/관련 회귀 → 허용된 Git 기록/CI 순서로 인계한다. 이번 작업에서 git add/commit/push, main 변경, 배포/공개, 자동 입찰, 시스템 보안 완화 없음. D-10/P11은 계속 DEFERRED.
