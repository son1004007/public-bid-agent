# Public Bid Agent 잔여 작업 전수 실행표 (2026-10-16)

> 현황 기반: `AGENTS.md`, `DECISIONS.md`, `TASKS.md`, `CURRENT_STATE.md`, `docs/design/STAGE2_4_EXECUTION_PROGRESS_2026-10-16.md`, 개발 브랜치 `feat/sprint1-search-demo` / 기존 HEAD `a2ef102`.
> 목적: 다른 AI가 문서만으로 착수 순서, 완료 조건, 금지 경계, 증거를 확인하고 단계별로 재개.
> 상태는 DONE(코드·테스트·Codex 검수), PARTIAL(기능 일부), TODO(실행 가능), BLOCKED(실증/회사 승인 필요), USER_APPROVAL(최종 결정 대기)로 구분. 합성 테스트와 실제 원본·실사 평가를 혼동하지 않는다.

## A. 순차 실행 백로그

| ID | 선행 | 세부 작업/산출물 | 완료·검수 기준 | 현재 상태 / 제한 |
| --- | --- | --- | --- | --- |
| P00 | 없음 | 전역 결정/현재 Git·운영 배치·원본 보존 확인, 이 실행표·AI 맥락 갱신 | 브랜치·SHA, 원본 SHA-256 count, 금지 조건 기록 | DONE (문서+로컬 SHA 검증) |
| P01 | P00 | PDF 페이지 단위 문자 수·이미지 수 및 HWPX 표·각주 메타 위험을 로컬 subprocess에서 진단 | 합성 문서 페이지·스캔·오류·8 MiB·비노출 테스트, Windows Job Object 강제 메모리 제한. 원문 전체 Recall과 구분 | IMPLEMENTED/WINDOWS_TESTED/CODEX_GO/LOCAL_APPLIED; 실제 업무 원본 전수 인수 BLOCKED |
| P02 | P00 | 사람이 RFP 세 가지 핵심 유형의 추출 후보를 판단한 기록을 별도 로컬 파일에 보관/조회 | 공고/차수/SHA/offset/분류 v2 및 저장 이벤트 strict validation, revision 충돌, 추출 변경 시 STALE, 텍스트 비보관 | IMPLEMENTED/WINDOWS_TESTED/CODEX_GO/LOCAL_APPLIED: 표시 후보에 한정; 실제 원본 독립 FN 라벨 BLOCKED |
| P03 | P02 | 현재 텍스트 후보별 최신 사람 라벨 집계/변경 이력 보존 | 중복 수정 전부 보존하되 근거별 최신값만 count, 독립 원문 FN/Recall은 측정 불가 | PARTIAL/TESTED; 독립 전수 정답 라벨 구축 BLOCKED |
| P04 | P00 | 새 추출 증거의 파서 코드·Python·라이브러리/설정 식별정보를 고정 fingerprint로 기록, 재추출 일치 시 비교 | 구형 증거는 NOT_VERIFIED, OCR 바이너리/언어팩 버전은 NOT_CAPTURED, 44,000자 이후 원본 누락/Recall 별도 | IMPLEMENTED/TESTED for future extractions; 실제 원본 재검증 BLOCKED |
| P05 | P00 | 정정·취소·STALE와 구형 RFP version 증거 재검증·복원 경로 | 이전 결정·근거·기록 보존; 사용자가 승인한 원본이 없으면 STALE 자동 해제 금지 | PARTIAL; 2026-10-18 NO_GO/P1 같은 배치 취소 손실·수집 중복 제거 보완, 관련 합성 회귀 91 PASS, 독립 재검수 대기([증거](../reviews/P05_SYNTHETIC_SOURCE_SAFETY_2026-10-18.md)); 실제 최신본 비교는 BLOCKED |
| P06 | P02 | RFP 품질 위험 검토 큐 + 등록·실적·면허·가용공수/원가 근거별 비교 | 메타데이터 기반 큐 구현/테스트, 부서 준비도는 기존 API 재사용. 실제 회사 증빙 없으면 모두 UNVERIFIED | PARTIAL/TESTED; 회사 증빙/권한 BLOCKED |
| P07 | P03/P06 | AI 분석 초안·근거 확인/불확실성 안내·안전한 fallback | AI 추천과 사람 최종 선택 분리, 출처 연결, 부정확 사례 검수; 외부 LLM은 사용자 매번 명시 동의 후 | PARTIAL; 비공개 전송은 BLOCKED |
| P08 | P00 | 제출·평가·수주 이력의 예외/복구/중복·정정 검증 | 원자적 로컬 JSON, concurrency/revision, 실제 제출 동작 금지, 합성 E2E | PARTIAL |
| P09 | P01~P08 | Windows localhost 실제 Chrome UI·브라우저 파일/입력·안전한 배포 게이트 | 실제 버튼·오류 상태/로그 없이 정보 노출 여부, 사용자 데이터 SHA 보존, Codex 독립 GO, CI | PARTIAL; 최종 사용자 UI 인수는 USER_APPROVAL |
| P10 | P09 | 최종 main 병합, 외부 배포, 사용자·회사 승인 | 사용자 명시 승인, 라이선스·인증/보안/백업, 서비스 운영 책임자 | USER_APPROVAL; 자동 진행 금지 |
| P11 | 별도 | 과거 7일 배치 API 단일 장애 재조사 | **D-10에 따라 현재 수행 대상 제외.** 재발 및 사용자 재요청 시에만 착수 | DEFERRED |

## B. 이번 요청에서 수행할 수 있는 경계

> **2026-10-18 P01/P06 작업 갱신:** 페이지/섹션별 표·각주·병합/OCR 검토 신호와 부서 증빙·가용 MM·원가 자료의 부족 사유를 합성 데이터로 보완했다. 관련 Python 82 PASS, 기존 Node 요약 3 PASS, JS 문법 PASS. 독립 검수/실문서·회사 검증/브라우저 인수/운영 적용은 NOT RUN이며 P01/P06 전체 완료가 아니다. [검증·계약](../reviews/P01_P06_SYNTHETIC_READINESS_2026-10-18.md). 이번 사용자 지시로 아래 일반 Git 기록 지시보다 **add/commit/push·main·배포 금지, orchestrator 인계**를 우선한다. D-10/P11 보류 유지.

- **순차로 즉시 진행:** P00~P04 중 합성 검증 가능한 코드/문서, P05~P08의 비공개 권한 불필요한 테스트·회귀, P09의 루프백 서버 smoke 및 가능한 GUI 테스트. 모든 단계 독립 Codex 읽기 전용 검수 및 작은 단위 Git commit + push.
- **실제 문서/업체 정보 선행:** PDF/HWP 바이너리의 실제 텍스트·페이지·표/OCR·각주와 그 정답은 합성 데이터에서 얻을 수 없다. 로컬에서 안전하게 파일을 읽고 독립 사람이 검토한 근거만 실제 TP/FP/FN에 포함.
- **보안:** RFP 본문·첨부 URL·원본 SHA·실제 직원명·원가·인증정보를 공개 GitHub/Codex/외부 모델에 전송하지 않는다. 데이터 변경은 안전한 파일 트랜잭션·revision 충돌 거부, 원본 164개 SHA 집계 불변, 기존 최종 판단 보존. 무단 자동 제출/계약 금지.
- **완료 표기:** IMPLEMENTED, WINDOWS_TESTED, CODEX_GO, LOCAL_APPLIED, CHROME_E2E, REAL_ORIGINAL_AUDITED, USER_APPROVED, MAIN_MERGED, PUBLIC_RELEASED를 분리.
- **커밋별 상태:** 실제 테스트/CI 결과 확인 후 `docs/reviews/`, `TASKS.md`, `CURRENT_STATE.md`, `AI_CONTEXT.md` 갱신. 코드 변경과 함께 root/로컬 README를 갱신.
