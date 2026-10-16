# RFP 원본 구조 위험 및 인적 검토 기록 (2026-10-16)

## 변경 범위 및 안전 경계

- 사용자 선택 RFP 원본 파일 SHA·캐시 재현 성공한 경우에만 document_quality.py를 별도 subprocess로 호출하여 PDF 페이지별 추출 문자수·이미지 객체, HWPX 표·각주 XML 마커를 계산합니다. 원본 파일 보존·외부 모델 전송 없음. 본문 텍스트·첨부 URL·해시는 진단 API에 반환하지 않습니다.
- rfp_audit_labels.py와 RFP 상세 화면 및 GET /api/dashboard/rfp-audit?id=..., POST /api/dashboard/rfp-audit/save는 참가자격·평가기준·과업 **세 유형** 중 현재 화면에 표시된 추출 텍스트 후보만 수동으로 분류합니다. 서버가 원본 SHA·검증된 캐시 참조·문자 위치·텍스트 해시를 다시 검증합니다.
- 사람 라벨과 변경 이력은 독립 비공개 로컬 JSON rfp_review_annotations.json에 원자적으로 보관합니다. 원문 발췌/첨부주소/직원정보/원가를 라벨 파일로 복사하지 않습니다. 여러 번 바뀐 라벨은 이력 보존하되 현재 집계는 근거별 최신값만 적용합니다. 과거 공고 차수 비결속=VERSION_UNVERIFIED, 근거·차수 변경=STALE_REVIEW.
- rfp_review_queue.py의 GET /api/dashboard/rfp-review-queue는 부서·마감 전 검토 대상 공고 ID, 고정 위험 플래그·우선순위만 제공합니다. 취소/구차수/REVIEW 제외. 원문/개별 경고/파일명/URL/해시 미반환.
- **독립 원본 전체 라벨·참가자격·Precision/Recall/F1 및 OCR 품질·표/각주 완전성은 NOT_VERIFIED**. 표현 후보에 사람이 "맞음"을 선택한 것만으로 실제 정답/법적 자격으로 확정하지 않습니다.
- 사용자 UI 최종 승인, main/공개배포, 회사 원본 외부 AI 전송, 자동 입찰 제출, 과거 7일 API 오류 원인 조사(D-10)는 범위 제외.

## 실행 결과 (최종 검증 확인 전 초안)

- Windows venv 집중 합성 테스트: test_rfp_audit_labels test_document_quality test_rfp_review_queue test_rfp_original_workflow **10 PASS**; node --check frontend/public/dashboard-live.js PASS.
- Codex 1차 read-only 독립 검수 **NO_GO 2건**: 저장된 annotation JSON의 이벤트 schema 검증이 느슨하여 라벨/공고 출처 값 위조가 합계에 영향을 줄 수 있음; Windows 문서 구조 분석 subprocess에 강제 메모리 상한 없음. 수정: 라벨 events exact-key·SHA/offset/enum/공고차수/시간대 포함 timestamp까지 엄격하게 검증하고 불일치 시 실패. `process_limits.py`는 Windows Job Object PROCESS_MEMORY 512MiB 및 KILL_ON_JOB_CLOSE로 stdout·stdin 전달 이전에 제한을 등록, POSIX RLIMIT_AS/CPU를 설정. 격리 실패 시 진단 `UNAVAILABLE`.
- 수정 후 집중 `test_process_limits test_rfp_audit_labels test_document_quality test_rfp_review_queue -q`: **11 PASS**. 실제 Windows 자식 프로세스의 128MiB 메모리 제한 상태에서 300MiB 메모리 요청 실패를 합성 검증.
- **Windows CPython 3.12 로컬 전체 319 tests PASS (exit 0)**; 문서 동기화 PASS, Node dashboard-live.js 구문 PASS, git diff --check PASS. 합성 집중 11 PASS.
- Codex 2차 독립 읽기 전용 재검수 **GO, 차단 지적 0건** (세션 `01a1447d-0a66-7de3-a15b-267a06f99583`). Codex 자체 테스트는 read-only 정책으로 NOT RUN, 작성자 Windows 실행으로 별도 확인.
- 안전한 로컬 서비스 재시작 전 확인: 루프백 127.0.0.1:8765 PID 18308은 로컬 venv 부모의 `server.py --no-browser`, RFP 배치 PAUSED, 릴리스 저널 COMPLETED. 해당 프로세스만 재시작 후 새 루프백 PID 5320.
- 적용 smoke: GET /decision-preview 및 /dashboard-live.js HTTP 200, 새 JS에 라벨·위험 큐 포함. GET /api/dashboard/rfp-audit는 revision 0 / Recall NOT_MEASURABLE, GET /api/dashboard/rfp-review-queue는 모니터링 위험 대상 180건·STORED_METADATA_TRIAGE_ONLY. **읽기 GET만으로 기존에 없던 라벨 파일이 생성되지 않음**.
- Chrome headless 실제 localhost DOM 렌더링 검증: 신규 RFP 위험 검토 패널 있음, 기존 dashboard-live.js 연결됨. 실제 사람의 상세 탭 클릭·파일 선택·라벨 입력/저장과 실제 원본 대조 E2E는 NOT RUN.
- 기존 비공개 JSON 40개 + RFP 캐시 124개 총 **164개 SHA-256 사전/사후 집계 일치**. 새 테스트/GET/Chrome 조회로 기존 파일 수정 없음. GitHub 최신 commit/CI 결과는 확인 후 추가.
- 기존 사용자 JSON 40개+RFP 캐시 124개 총 164개 SHA-256 불변성은 로컬 배포 전후 재확인 필요.
- 실제 원본 PDF/HWP/HWPX 파일을 사람의 정답과 비교한 적 없음(REAL ORIGINAL AUDIT NOT RUN).

## 재개 방법

- [우선순위·선행조건·완료기준 전수 실행표](../design/REMAINING_EXECUTION_ROADMAP_2026-10-16.md)
- [TASKS.md](../../TASKS.md), [CURRENT_STATE.md](../../CURRENT_STATE.md), [DECISIONS.md](../../DECISIONS.md)
