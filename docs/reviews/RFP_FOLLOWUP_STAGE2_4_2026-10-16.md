# RFP Stage 2~4 후속 구현·검증 — 2026-10-16

## 구현 범위

- `local_app/rfp_fulltext.py`: 기존 캐시의 파서 신고 길이/절단 상태 충돌 감지 후 안전 오류. 새 청크는 fsync 된 임시 파일을 원자적 `os.link`로 게시하여 두 프로세스가 동시 생성해도 기존 파일을 덮지 않는다. 실제 업무 RFP 캐시 재작성 없음.
- `local_app/rfp_original_workflow.py`: 신규 증거의 공고 ID/번호/차수까지 확인한 뒤 원본 SHA·첨부·캐시 결속 비교. 구형 증거에는 차수 메타데이터가 없어 `PROVENANCE_VERSION_UNVERIFIED`로 보류한다. STALE/취소/구차수도 보류하며 공식 최신 원본과 동일함을 추정하지 않는다.
- `local_app/server.py`: POST `/api/dashboard/rfp-original-compare` 사용자가 제공하는 원본 bytes를 localhost CSRF+8MiB 범위에서 파서 subprocess로 검증한 뒤 고정 enum만 반환. **원본/파서 오류 원문 미저장·외부 모델 미전송**. GET `/api/dashboard/readiness` 상태만 응답, POST `/api/dashboard/outcome` 수동 상태 전이 저장.
- `frontend/public/dashboard-live.js`: 상세 RFP 원본 파일 선택 대조, 부서 증빙 확인, 제출·평가·낙찰 이력 수동 기록.
- `local_app/bid_readiness.py`: 회사 운영자료 확인표의 6개 등록/실적/배치/재무/제안/위험 항목의 상태만. 회사 내부 원가·개인정보·서술 문구는 출력하지 않음. `reviewed`는 사용자 입력 기록이며 법적 적격이 아님.
- `local_app/bid_outcomes.py`: 이미 기록된 담당자 bid 의사결정에서만 SUBMITTED 시작, 순차 EVALUATED→AWARDED/NOT_AWARDED/WITHDRAWN, 날짜·출처 필수, 점수 유효범위·revision 충돌 차단. 기존 `final`·AI `rec`·`history` 유지, 자동 제출·서명/낙찰 확정 없음.
- 신규 합성 `test_rfp_original_workflow.py`, `test_bid_outcomes.py`, `test_bid_readiness.py`; 수정 `test_rfp_fulltext.py`. 실제 회사 자료/원본 문서 테스트에 사용 금지.

## 검증 범위 및 실사용 제약

- Windows TD-kiseok 가상환경 집중 Python 최초 **19 PASS**, 전체 Python **307 PASS**. Codex 독립 1차 **NO_GO 2건**(동시 생성 캐시 덮어쓰기/차수 미결속), 원자적 게시 및 신규 evidence 차수 결속·구형 차수 검증 불가 보류로 수정. 이후 집중 `test_rfp_fulltext test_rfp_batch test_rfp_original_workflow test_bid_outcomes test_bid_readiness` **23 PASS**. Node JS 구문·문서 동기화 PASS. 수정 후 전체 재검증/최종 Codex/CI는 별도 기록.
- 현재 운영 비공개 JSON 40개+RFP fulltext 캐시 124개 **164개 SHA-256 집계 기존 기준과 일치**(실측).
- **Windows 전체 Python 308 PASS, exit 0** (2차 Codex 수정 후), 문서 동기화 PASS, Node JS 문법 PASS, `git diff --check` PASS(Windows 개행 사전 알림만 존재). Codex 2차 독립 **GO, 차단 지적 0건** (세션 `01a14409-1e6c-7863-9907-306fecf500ec`); Codex sandbox는 read-only 정적검수이며 자체 테스트 `NOT RUN`.
- 로컬 8765 적용 전 `server.py --no-browser` 부모 venv·루프백 프로세스 PID 19680, RFP 배치 `PAUSED`, 릴리스 저널 `COMPLETED` 확인 후 해당 서버만 재기동(PID 18308). `/decision-preview`와 `/dashboard-live.js` HTTP 200, `GET /api/dashboard/readiness` 6개 검증 항목·`legal_eligibility=UNVERIFIED`, 불량 원본 비교 POST HTTP 400, 기존 `GET /api/dashboard/rfp-coverage` 활성 180건. 실제 원본 첨부/제출사실을 전송하거나 변경하지 않음.
- 비공개 사용자 JSON 40개+RFP 캐시 124개 **164개 SHA-256 집계 사전/사후 완전 일치**, 파일 변경 0건. 실제 Chrome 원본 파일 선택 클릭/모바일 화면 및 사용자 최종 승인 `NOT RUN`. GitHub commit/CI는 별도로 결과 기록.
- 실제 PDF/HWP 파일의 텍스트 완전성, 원본 버전 자동 취득, 페이지 표/각주/OCR Recall, 실제 회사 면허/실적/원가 증빙, 외부 LLM 추천·RAG/LangGraph 공급자 동의, 실제 제출/수주 결과 인수 및 사용자 최종 UI·main/인터넷 공개는 **미완료**.
- 운영 파일 읽기·쓰기 게이트 및 사용자 최종 승인: 기존 D-06/D-08/D-10/D-13 준수. 저장 원본/직원/비용·API Key가 GitHub/Codex 검수 입력에 노출되지 않도록 한다.

## 남은 작업 및 타 AI 재개

- [단계별 완료/미검증 및 후속 실행](../design/STAGE2_4_EXECUTION_PROGRESS_2026-10-16.md)
- [TASKS.md](../../TASKS.md), [DECISIONS.md](../../DECISIONS.md)
- 합성 구현 테스트 통과 ≠ 실제 회사/문서 품질 승인 ≠ 사용자 UI 승인 ≠ main/공개 배포.
