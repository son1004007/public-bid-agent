# 공식 RFP 원본·캐시 재현성 대조 수직 슬라이스 — 2026-10-16

## 목표·구현

- 기존의 증거 메타데이터 집계(`rfp_extraction_loss.py`) 다음 단계. **원본 PDF/HWP가 별도 확보되기 전에는 독립 원문 비교를 수행할 수 없다**는 제약을 명확히 하고, 준비 가능한 오프라인 순수 함수를 먼저 구현했다.
- 파일: `local_app/rfp_original_compare.py`, `local_app/test_rfp_original_compare.py`. 사전 결속: g2b 공식 HTTPS attachment.name/URL 기반 identity, 기존 EXTRACTED proof.name/identity/sha256/ref, 원본 bytes SHA, `rfp_fulltext.load()`가 검증한 cache record/source SHA/text SHA/참조.
- 파일 크기는 공식 문서 수집 허용치 8MiB 이내. 지정된 신뢰된 로컬 `server.extract_in_subprocess` 파서를 주입하여 재추출된 앞부분 텍스트 및 신고된 전체 문자 수·절단 표시 재현을 비교한다. 증거 측 `fulltext_chars`, `fulltext_reported_chars`, `fulltext_chunks`, `fulltext_truncated`, `fulltext_position_basis`를 캐시와 모두 대조하고 schema v1·형식·값 범위·bool/정수 혼동을 검사한다. 함수 자체는 **파일 읽기·쓰기, 네트워크 호출, 외부 AI 호출, 자동 다운로드, 사용자 결정 변경을 수행하지 않는다**.
- 고정 상태만 반환: `INVALID_EVIDENCE`, `ORIGINAL_UNAVAILABLE`, `ORIGINAL_SHA_MISMATCH`, `CACHE_MISMATCH`, `PARSER_UNAVAILABLE`, `REEXTRACTED_TEXT_DIFFERS`, `PARSER_METADATA_CHANGED`, `REPRODUCED_TEXT`, `REPRODUCED_TRUNCATED_PREFIX`. 마지막 두 개는 저장된 **파서 텍스트 및 길이·절단 상태**의 재현 여부만 의미한다. `length_truncation_metadata_reproducibility`를 별도 표시하고, **파서 method/warnings/버전/설정/OCR 구분은 `parser_method_version_ocr_reproducibility=NOT_VERIFIED`로 고정**한다.
- 반환값에 실제 원문·파일명·공고번호·개별 SHA·공식 첨부 URL·파서 오류 메시지가 들어가지 않는다. **PDF/HWP 원본 페이지·표 레이아웃·각주·스캔 OCR/필수요건 Recall 판정은 항상 `NOT_VERIFIED`**.
- 기존 API/UI, 캐시 저장 및 나라장터 수집 흐름은 건드리지 않는다. `main`/인터넷 공개·7일 API 오류 진단은 제외.

## 실제 테스트와 진단

- 2026-10-16 Windows TD-kiseok 프로젝트 venv, 1차 `cd local_app; python -m unittest test_rfp_original_compare -q`: **합성 5건 PASS**. Codex 1차 **NO_GO** (증거 측 fulltext_*와 cache 메타데이터 미결속, 파서 버전/방법 확인 불가 표시 누락) 수정 후 **합성 7건 PASS**: PDF reportlab·표가 들어간 HWPX·TXT, 공식 SHA 변조/캐시 변조/파서 오류/메타데이터 변경/절단 접두 일치, 5개 증거 메타 필드별 변조/캐시 schema·bool/정수 변조 및 방법/OCR 경고 미검증 표시 회귀.
- 테스트 중 기존 `rfp_fulltext.store()`의 동일 원본·동일 텍스트 재사용 시 기존 저장된 reported_chars/truncated_by_parser와 신규 `store()` 응답 메타데이터가 다를 수 있는 **미해결 위험** 관찰. 신규 테스트는 버전이 다른 합성 원본 SHA로 분리. 운영 캐시 정책은 수정하지 않았으며 `TASKS.md`에 별도 후속 기입.
- 실제 운영 RFP **원본 바이너리 대조는 NOT RUN**. 문서 캐시 SHA만으로 PDF/HWP 파서 정확도를 인정하지 않는다.
- Windows CPython 3.12 프로젝트 venv에서 수정 전 전체 **297건 PASS**, Codex 지적 수정 후 `python -m unittest discover -s local_app -p 'test_*.py' -q` **299건 PASS, exit 0**. `python scripts/check_documentation_sync.py` PASS, `node --check frontend/public/dashboard-live.js` PASS, `git diff --check` PASS (Windows 개행 교정 예고 경고만 존재).
- 기존 비공개 JSON 40개+RFP 캐시 124개 총 **164개 파일 SHA-256 집계가 이전 검증값과 동일**. 신규 도구는 업무 파일을 열거나 수정하지 않음.
- 로컬 서비스 `/decision-preview`의 서버/API 변경 없음: 이번 모듈은 **원본 제공 시 실행하는 오프라인 순수 함수**이며 운영 적용·실제 RFP 대조는 NOT RUN.
- Codex 1차 **NO_GO**: 증거 측 5개 fulltext 메타 필드와 캐시 결속 누락 및 파서 method/version/OCR 검증 여부 미표시. 메타데이터 검증·경계 필드 추가, 합성 변조 테스트 2건 추가.
- Codex 2차 **NO_GO (문서 정합성)**: 검토 도중 전체 299건 회귀가 아직 종료되지 않았던 이전 시점의 문서(297건)를 읽었고, README/코드 주석의 '동일 파서'가 버전 검증이 된 것처럼 오인될 수 있다고 지적. 실제 전체 299건 PASS 결과를 반영하고 '현재 지정한 로컬 파서'로 정정, 기존 버전/방법은 `NOT_VERIFIED` 유지.
- Codex **3차 최종 독립 재검수 GO, 차단 지적 0건** (세션 `01a14391-9fd5-7992-90b3-6161104aa2f1`). 증거 5개 필드와 캐시 메타의 정확한 결속, method/version/OCR `NOT_VERIFIED`, 수정된 표현과 Windows 299 PASS 기록 정합성 확인. Codex 자체 테스트는 read-only 정책상 **NOT RUN**.
- GitHub 개발 브랜치 커밋·CI는 실제 결과를 확인한 뒤 기록한다.

## 남은 작업 링크

- [원본 획득, 형식별 페이지/표/각주/OCR, 독립 라벨링, 저장 정책, 인적 확인, AI 및 제출관리 전체 실행계획](../design/RFP_ORIGINAL_AUDIT_PLAN_2026-10-16.md)
- [작업 항목과 상태](../../TASKS.md)
