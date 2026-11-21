> **2026-11-21 P0-02 운영 DB 상태 정본:** 개인 NAS 운영 PostgreSQL ai_gateway 0001~0004 실제 migration/SourceLink table·trigger **APPLIED PASS**. 기존 운영 DB/비공개 HWPX 5개/capture 2개 백업 및 독립 복원 PASS, 기존 사용자 1/문서 8/Chunk 14,612 및 메인 UI HTTP 200 확인. **실 원본 SourceLink INSERT 0건, 유효 staff 계정 0명으로 [USER ACTION #35](https://github.com/son1004007/ai-agent-workflow-playbook/issues/35) 전 차단**. [실운영 근거](docs/implementation/ai-gateway/AGW-05-P0-02-OFFICIAL-SOURCE-RECONCILIATION-2026-11-21.md#8-2026-11-21-실제-nas-운영-postgresql-스키마-적용-사용자-명시-요청). 운영 앱 이미지·역할·예약 변경 0, PUBLIC/모델/회사 data1 OFF, PR #5 Draft/credential #26 유지.

> **2026-11-21 P0-02 실 NAS 격리 DB/복구 인수:** [격리 PostgreSQL migration·복구·실원본 대조](docs/implementation/ai-gateway/AGW-05-P0-02-OFFICIAL-SOURCE-RECONCILIATION-2026-11-21.md#6-2026-11-21-격리-db-배포복구-및-실원본-검증). 작업 브랜치 e2756f38의 별도 임시 checkout + 네트워크 차단 PostgreSQL 16.15 tmpfs 환경에서 신규 0004 테이블/불변 트리거 설치, 합성 SourceLink 1건 INSERT, 독립 DB 백업·복구 및 rollback/reapply 모두 **PASS**. 실제 공식 원본과 기존 운영 DB는 정확한 최신 검증 함수로 **읽기 전용 PASS**. **운영 DB migration/실원본 INSERT는 NOT_APPLIED**, 격리 DB로 실제 raw 바이트 INSERT는 도구 안전검사에서 차단되어 **NOT_RUN**. 임시 컨테이너·checkout 폐기, 기존 NAS 앱 running. 직원 승인/AI 반출/회사 배포 및 PR #5 release 차단 유지.

> **2026-11-21 P0-03 최신 정확 코드 CI 확인:** SHA `80ef1409750de4c8672f877802249d7ece64d6dc` [core 94 PASS](https://github.com/son1004007/public-bid-agent/actions/runs/44818921068), [Django Windows/Linux/PostgreSQL 각각 437 tests PASS](https://github.com/son1004007/public-bid-agent/actions/runs/44818921064) (migration --check PASS). 기존 P0-03 synthetic test의 예외 catch를 구체화한 최신 코드까지 검증됨. NAS 실원본 5/5 read-only preview 14,743 chunks/단축 표 셀 149/1800 초과 0·원본·DB 무변경 (Gateway job_01M7XD0K8Z00PV044MDX3RXN6K). 운영 DB 재추출/업무 승인/모델 반출은 수행하지 않음.

> **2026-11-21 P0-03 코드 및 NAS 읽기 전용 검산:** [P0-03 HWPX 원문 보존 Chunk·실제 NAS 5건 읽기 전용 검증](docs/implementation/ai-gateway/AGW-05-P0-03-EXTRACTION-COVERAGE-2026-11-21.md). 한글/이모지 포함 출처 텍스트를 정확히 1,800 UTF-8 bytes 이하로 무손실 분할하여 char/byte offsets·source/span SHA·기존 DocumentVersion SHA를 Chunk에 결속, 1~5글자 표 셀 및 실제 각주 텍스트 Chunk 추가. 모든 새 추출은 coverage.complete=False/status=PARTIAL/structure_fidelity=UNVERIFIED로 fail-closed. 실제 NAS 기존 5건 5/5 SHA/ACL/read-only 검산과 **새 예상 Chunk 14,743건(기존 14,594 대비 짧은 표 셀 149건 포함)**, 초과 0건, 기존 complete 전부 MISSING PASS (Gateway job_01M7XD0K8Z00PV044MDX3RXN6K). 합성 CI 코드 SHA a34847c2 [core 94 PASS](https://github.com/son1004007/public-bid-agent/actions/runs/44818463555), [Django Windows/Linux/PostgreSQL 각 437 tests PASS](https://github.com/son1004007/public-bid-agent/actions/runs/44818463609). **실제 NAS DB 새 Chunk 저장/재추출 NOT_RUN**, P0-02 실제 DB SourceLink migration 미적용, staff PUBLIC/모델 egress OFF.

> **2026-11-21 P0-02 코드 합성 인수 PASS:** [P0-02 source-link 증거](docs/implementation/ai-gateway/AGW-05-P0-02-OFFICIAL-SOURCE-RECONCILIATION-2026-11-21.md). `7fe897c4ff7681a51d6132238cbb7aec54eda203`의 [core 94/94 PASS](https://github.com/son1004007/public-bid-agent/actions/runs/44817182658) 및 [Django Windows/Linux/PostgreSQL 각 431건 PASS](https://github.com/son1004007/public-bid-agent/actions/runs/44817182690). NAS 실제 공식 raw digest != 기존 canonical digest read-only 재검증, 새 불변 DB SourceLink/0004 SQL trigger/기본 dry-run·명시 apply 구현. **현 NAS DB 새 migration/실원본 mapping INSERT는 아직 OFF/NOT_RUN**, P0-03 추출 coverage 및 P0-04 staff 승인·모델 송신은 별도. 기존 보안 release 차단 유지.

> **2026-11-21 P0-02 원본 출처 결속 코드·실측:** [상세 설계·코드·테스트·NAS read-only 검산](docs/implementation/ai-gateway/AGW-05-P0-02-OFFICIAL-SOURCE-RECONCILIATION-2026-11-21.md). 새 OfficialSourceLink 모델/0004 migration(PostgreSQL UPDATE·DELETE 방지 트리거), manifest/원본 HWPX 검증, read-only 기본 CLI·명시 apply·동일차수 conflict 차단, POSIX 0700/0600 저장 경로 검증 구현. 실제 NAS 원본 5,764bytes SHA와 기존 NoticeVersion canonical SHA 불일치·공식 제목/차수/문서 SHA 일치 **읽기 전용 PASS** (Gateway job_01M7XC404100Y0KQR7614K9TF7). 기존 NAS 앱 DB migration/row 적용/운영 배포는 NOT_RUN이며 PUBLIC staff 승인 및 모델 export OFF. 최종 코어·Django CI 상태는 정확한 Actions SHA에서 별도 확인; 단순 코드 생성만으로 운영 완료 아님.

> **2026-11-20 P0-01 실제 NAS 검증 인계:** [실제 RFP 5건 SHA/DB/ACL·공식 02 공고+첨부 목록 1건 E2E 증거](docs/implementation/ai-gateway/AGW-05-P0-01-LIVE-NAS-VERIFY-2026-11-20.md). 5/5 기존 보호 원본 일치, 1/5 공식 실응답 5,764 bytes/첨부 894,665 bytes SHA 일치. 기존 URL-인코딩 API 키의 이중 인코딩 수집 오류 수정, CI core 91 / Django 415×3 PASS. **실제 원본 HTTP 응답 영속 저장 및 별도 DB source identity, 추출 complete, staff 승인/운영 AI 호출 미완료**. TASKS 최상단 큐 01 read-only 완료/원본 저장 잔여 기준.

> **2026-11-20 official raw capture 추가:** [AGW-05 수동 수집·비공개 원본 SHA 계약](docs/implementation/ai-gateway/AGW-05-OFFICIAL-RAW-CAPTURE-2026-11-20.md) 코드·합성 6 tests 구현. 이력 저장/attestation/모델과는 격리. 다음 연결은 **NoticeVersion canonical-metadata SHA != 공식 원문 바이트 SHA**와 **ExtractionRun coverage.complete 미검증**부터 해결. 실공고 수집/인증 승인/유료 호출/배포는 아직 NOT_RUN.

> **2026-11-20 AGW-05 실코드 인계:** [공식 출처 RFP 근거/무결성 승인 및 최신 결과 검증](docs/implementation/ai-gateway/AGW-05-PUBLIC-PROVENANCE-2026-11-20.md): `snapshot.py`, `analysis_service.py`, `public_source.py`, `PublicRfpAttestation/0003`, `test_ai_gateway_public_source.py`. 공개처럼 보이는 URL만으로 허용하지 않고 staff raw bytes SHA/최신 공고·완전한 추출/별도 내보내기 승인을 요구. 현재 코드+합성 CI만 진행; 실제 데이터/모델/회사 배포 OFF. 다음 AGW-08, official ingest/원문 추출 후 실제 RFP E2E.

> **2026-11-20 최신 AGW 개발 인계:** [AGW-05/09 RFP 합성 packet/근거 검증·DB 분석 이력 구현](docs/implementation/ai-gateway/AGW-05-09-IMPLEMENTATION-2026-11-20.md). `snapshot.py`/`result_contract.py`/`ai_gateway/models.py`/`analysis_service.py` + 0002 migration, 코어 77/77 + Django 378×3 합성 CI PASS. 모델이 RFP만 보고 MET/NOT_MET 확정 못하게 차단. 운영 불변 SQL trigger/회사 실데이터/실제 Job/worker 연결은 미완료.

> **2026-11-20 NAS 최신 버전 전환 실측:** Codex `0.171.0` / `gpt-6.2-sol` / `medium`이 NAS 호스트의 기본 설정과 Docker 이미지 모두에서 **실제 모델 응답 PASS**. 제한된 설치 실행기 source SHA·deny canary 검증, 구버전 롤백 보존. [실제 runtime/source 정본](https://github.com/son1004007/device-control/blob/main/docs/SYNOLOGY_AGENT_RUNTIME.md), [현재 상태](CURRENT_STATE.md), [작업 원장](TASKS.md). 이전 0.163.0/6.1 모델 문구는 역사적 실측이며 현 기본 설정이 아님. 사용자별 등록/다중 사용자 실행 정책 및 company data1 운영은 미완료.

> **2026-11-20 P0 최신 NAS 증거 및 코드:** [AGW NAS 2 Docker-container 실제 Codex 동일 세션 Resume 실측](docs/implementation/ai-gateway/AGW-NAS-SESSION-E2E-2026-11-20.md). `session_service.py` DB User/Notice/SessionBinding lock/fence/timeout/mismatch, `nas_docker_codex.py` Synology Docker 실행·홈 격리·세션 재개. 실측 synthetic 4요건/3증빙 NOT_MET, 두 컨테이너 동일 session, 두 호출 exit0. AGW core 50 PASS/Windows/Linux/PostgreSQL Django 334 PASS; Windows Chrome CDP 1차 실패 후 재실행 통과. **실제 제품 서비스 연결/사용자별 인증·egress 승인은 미완료**. NAS Linux 커널 Docker `--cpus` 불가, 프로덕션 실행 default OFF 유지.

> **2026-11-20 AGW 실제 구현/검증 인계:** [AGW 첫 실행·검증 기록](docs/implementation/ai-gateway/AGW-RUN-2026-11-20.md). 개인 Windows Codex 모델 실제 호출+동일 session resume PASS; Codex CLI adapter/JSONL parser, Django ProviderProfile/SessionBinding 및 사용자별 GET 상태 API 구현. AGW core 35건·Server foundation Win/Linux/PostgreSQL 303건씩 CI PASS. 실제 서버의 사용자별 CLI 등록/로그인·세션 worker/공개 RFP 자동 분석 및 회사 data1 배포는 아직 NOT_DONE. 다음 P0은 AGW-03/04/06 격리 runner 결속.

> **2026-11-20 최신 사용자 우선순위:** 유료 Codex·Claude 모델 실제 호출 허용, 빠른 구현·정확한 입찰 판단 중심. [AGW 계획](docs/implementation/ai-gateway/README.md)과 TASKS P0-R1/R2: 첫 provider 실제 유료 공개 RFP E2E+resume를 조기 수행하고 0/1/2 도메인 코어 테스트는 병행. 회사 자료 반출/서버 배포/구독 중계는 여전히 별도 정책·승인. 실제 모델 실행 완료로 주장하지 않는다.

> **2026-11-20 AGW 구현 재개 인덱스:** [AGW-00~15 작업 단위별 상세 설계/구현 계획](docs/implementation/ai-gateway/README.md). 16개 카드별 입력/출력 계약·Django/CLI·실패/복구/테스트·선행조건을 확인한 후 해당 상태는 TASKS/CURRENT_STATE에서 최신 확인. 설계서 게시만으로 실제 API/CLI/운영이 구현되었다고 주장하지 않는다.

> **2026-11-20 최신 사용자별 서버 실행·세션 resume 설계:** [16](docs/server-migration/16-user-cli-session-and-blind-cross-check.md). 서버의 각 사용자 자체 provider 로그인, Codex/Claude 기존 session 유지·resume, 최초 판단은 독립, 상호 확인은 구조화 근거 비교부터, **불일치 이슈 때만 별도 검증 session에 상대의 짧은 근거를 공유**. 장기 세션/OS 실행 프로세스 분리, 교차 사용자 인증 재사용 금지. 자동 호출·회사 자료 전송/배포 승인 전 OFF.

> **2026-11-20 최신 조건부 교차 검증 계약:** [15 Codex+Claude 0/1/2 가용 상태 및 독립 검증 설계](docs/server-migration/15-mcp-provider-executor-subscription-policy.md). 준비된 하나면 단독, 둘이면 동일 snapshot/근거에서 서로의 답변을 보지 않는 1차 결과 각각 수집→검증 후 구조화 비교. 수동 CLI는 사용자 직접 실행·업로드; 회사 공용 구독 중계 금지. 기존 1개만 선택 제안보다 우선; 구현·테스트 미실행.

> **2026-11-20 최신 Codex/Claude Code 독립 프로필 방향:** [15 사용자별 직접 실행·JSON 검증 설계](docs/server-migration/15-mcp-provider-executor-subscription-policy.md). 3-provider 자동 멀티 라우터보다 Codex와 Claude Code 개별 등록·사용자 직접 CLI·JSON 가져오기 우선. Gemini 제외(사용자 환경에서 3.8 Flash 확인). 개인 구독을 회사 서버가 대신 호출하지 않음. 구현/운영 배포 미수행.

> **2026-11-20 MCP 모델 실행 최신 진입점:** [15 subscription CLI/MCP provider 실행 계약](docs/server-migration/15-mcp-provider-executor-subscription-policy.md). 사용자는 비용 절감을 위해 서버가 MCP로 Codex/Claude/Gemini 실행기에 JSON 분석을 요청하는 방식을 검토한다. Google AI Pro는 Antigravity에서 Gemini 4 Neon/Argon 지원하나 타사 MCP 래핑은 소비자 약관상 지원되지 않음; 개인 Claude 구독 중계도 금지. 정본은 DECISIONS/TASKS, 실제 provider 연결 NOT_IMPLEMENTED.

> **2026-11-20 전사 역량 및 부서 협업 확장:** [12 전사 역량·협업 Hybrid RAG 설계](docs/server-migration/12-enterprise-capability-hybrid-rag.md)를 HBR 최신 상세로 적용한다. 법인 자격/실적과 주관·지원 부서 역량/가용성을 분리, 정량 SQL + 정성 RAG, 자체/사내/외부/혼합 시나리오 및 전사·주관 손익 비교. 기존 자료 승인/개인 원가 금지/업무권한 유지. 개인 프로젝트 독립 AI 리뷰는 최신 CONTROL에 따라 선택; 필수 자체 검증·실제 결함·회사/운영 승인 유지.

> **2026-11-20 Hybrid RAG MVP 우선:** [기술 설계](docs/server-migration/10-hybrid-rag-bid-decision.md) · [사업 담당자용 설명](docs/server-migration/11-hybrid-rag-business-guide.md) · [TASKS.md HBR-00~08](TASKS.md). 기존 실제 RFP를 사용한 검색/판단 수직 슬라이스, 사업부 RAG + SQL 정형 조회/손익 계산을 우선. 기존 보안·승인·독립 검수 유지. 상태는 CURRENT_STATE.md 참조.

> **2026-11-17 사업부 집계 원가·공동 사업 검토:** [사업부 집계 원가·공동 검토 설계](docs/server-migration/09-aggregate-cost-and-shared-review.md)을 서버 전환의 최신 요구로 적용한다. 개인별 급여·인건비 및 급여 원장을 수집/저장하지 않고 사업부 총인건비와 집계 MM만으로 원가를 산정한다. 승인된 사업부 사용자 모두 동일한 안전한 분석 결과를 조회하며, 기준정보 변경과 최종 참여 결정은 업무 권한으로 제한한다. 개인 작업/비밀/증빙 원본 접근권한은 완화하지 않는다. 설계 반영이며 구현·배포 승인은 별도다.

> **2026-11-14 최신 서버 전환 설계:** [서버 전환 설계 목차](docs/server-migration/README.md)부터 읽는다. React/TypeScript + Django/DRF + PostgreSQL, 서버 작업 워커/일정, DB 계정·최초 비밀번호 변경 강제, SSO 제외. 조직 정책은 공개 Git 밖의 승인된 연결 설정에서 원본을 읽고 적용한다. **설계 문서만 작성됨(NOT_IMPLEMENTED)**; 과거 로컬 전용/SSO 목표 문구보다 이번 결정을 우선하되 기존 운영·데이터·작업은 보존한다.

## 2026-11-02 H02-1: A01 날짜 오류 수정·검증

구현 `38c18e9c5b968fb500c6a7c88320b2a33d0f92fc`를 개발 브랜치 `feat/harness-h01`에 게시했습니다.
`normalize(item, *, at=...)`의 고정 관측 시각을 기록과 마감 판정에 공유합니다. 기존 운영 마감 정책은 유지합니다.
관련 16 tests PASS, Linux 감사14/하네스15/Node34 PASS, Sprint 1 CI backend/frontend PASS,
독립 Codex 코드 검수 GO(A01 범위). 전체 Windows 인수의 별도 실패와 환경 제약은 검증 기록을 확인합니다.
[실행 기록](docs/reviews/H02_A01_CLOCK_2026-11-02.md). **H02 전체 DONE 및 main 병합/운영 배포는 아님.**
다음: H02-2 전체 검사 adapter 연결 → H02-3 동일 SHA 독립 검수/CI 증거 결속.
H01 단일 검사 실행 결과의 missing_checks/WAITING_REVIEW/WAITING_CI는 아직 유지됩니다.

## 2026-10-31 H01 실행 구현·반복 사용 검증 완료

H01의 작업 정의/실행기/검증기/실행 기록이 실제 코드로 추가되었습니다.
[사용법](docs/implementation/HARNESS_USAGE.md) · [검증 기록](docs/reviews/H01_HARNESS_ACCEPTANCE_2026-10-31.md) · [PR #2](https://github.com/son1004007/public-bid-agent/pull/2).
구현 기준 `3b7ff8b789bba2c44a48db487dba5d8f40e0bfe7`: Linux/노트북 Windows 자체 테스트 각각 15 PASS,
GitHub Ubuntu/Windows 하네스 CI PASS, 독립 Codex 코드 검수 GO(H01 한정, 독립 테스트 NOT RUN).
노트북 A01 run/verify/status 모두 VERIFY_FAILED와 task_complete=false로 기존 날짜 오류를 재현했습니다.
다음 작업은 H02: A01 날짜 계약 수정·전체 회귀·외부 검수/CI 결속입니다. H03 resume/전체 잠금은 미구현입니다.
개발 브랜치에 게시했으며 main 병합/운영 배포 및 A01 전체 완료는 별도입니다. 아래 날짜별 기록은 당시 상태입니다.

# AI 개발 작업 안내 - Public Bid Agent

> **2026-10-31 하네스 인계:** [명세](docs/design/EXECUTION_HARNESS_SPEC_2026-10-31.md), [Gateway 런북/실측 제한](docs/implementation/GATEWAY_CODEX_HARNESS_RUNBOOK_2026-10-31.md), [H01 Codex 프롬프트](docs/implementation/CODEX_HARNESS_H01_PROMPT_2026-10-31.md). H01 최소 task/runner/verifier/evidence → H02 A01 수정 순서. 하네스 NOT IMPLEMENTED, 노트북 Codex0.163.0/Python3.12.0 도움말 조회만 확인. 인증 상태 조회 timeout·종료 미확인으로 실제 모델 실행 미검증.

> **2026-10-30 검토·인계:** [AI 시작점](docs/implementation/AI_START_HERE.md) → [단계별 카드](docs/implementation/AI_EXECUTION_TASKS_2026-10-30.md) → [설계/구현 검토](docs/reviews/PRODUCT_REVIEW_AND_RESTART_PLAN_2026-10-30.md). 최신 확인 main a4440a2의 CI는 날짜 의존 테스트 1건 실패(40881574416). 첫 재개 작업 A01, 이후 BID-06 실제 정답/범위 평가. 아래 10월 19일 운영 수치는 과거 스냅샷이며 현재 PC는 이번에 확인하지 않았습니다. 이번 작업은 문서화이며 구현·운영 변경 없음.

> **2026-10-19 BID-06 최신 실행:** 독립 정답 검수·표본 평가 **IMPLEMENTATION_DONE**: Python504·Node42·Chrome390/1440·Codex GO·실행a4b7cd4 개발2/main CI·기존localhost API/두폭 화면·393파일 백업/불변 인수 PASS. 실자료5718·승인 정답0·차수 결속 미검증으로 실자료 NOT_EVALUATED, 기존393파일 불변. 도구 IMPLEMENTATION_DONE과 실자료 VALIDATION_DONE은 별도이며 전체 DONE 금지. 최신 사용자 승인 범위는 독립GO/CI 후 main·기존localhost 배포까지, BID07/실제 입찰/외부 공개는 금지. [현재 검증](docs/reviews/BID06_GROUND_TRUTH_2026-10-19.md).

> **최신 BID-05 DONE (16:10 KST):** 문서 후속 작업/보류 큐·기존 화면/API·공식 첨부/차수/SHA·캐시 제한 검증. Python482·Node36·Chrome390/1440 PASS, 독립Codex GO(지적 해결). 실행de8c294의 개발2/main CI SUCCESS, main fast-forward·기존 localhost 운영 인수 및 첨부/설정 포함393파일 백업·전후 동일 PASS. 실제5,718/작업2,870·보류2,848(16:11), 회사 증빙/공식 최신성 UNVERIFIED/BLOCKED_EVIDENCE 유지. BID-06·인터넷 공개·실제 입찰/자동 투찰 미수행. 아래 BID05 미착수·대기 문구는 이전 이력. [최종 검증](docs/reviews/BID05_DOCUMENT_FOLLOWUP_2026-10-19.md).

> **최신 BID-04 DONE:** 실행 `4f1743d`, Python468·Node27·Chrome390/1440 PASS, 독립 Codex GO, 개발 두 CI·main CI SUCCESS. 사용자 직접 승인 범위로 main fast-forward·기존 localhost 배포 완료, API/운영 두 폭·393파일 백업/전후 보존 PASS. 회사 증빙 BLOCKED_EVIDENCE/적격·수익 UNVERIFIED 유지. BID-05 미착수, 인터넷 공개·실제 입찰 없음. 아래 대기/NO_GO는 이전 이력이다. [최종 기록](docs/reviews/BID04_UI_DEPLOY_2026-10-19.md).

> **최신 BID-04 인계:** 기존 작성자 종료 후 원본 보존/외부 백업 완료. CLI+화면/API, Python468·Node27·Chrome390/1440 PASS, Codex 최종 GO. 사용자 이번 직접 대화에서 main 및 기존 localhost 운영 배포를 승인했으며 DECISIONS 최신 절을 우선한다. CI/운영 인수 전 DONE 아님. 아래 이전 NO_GO/금지는 해당 시점 이력. [현재 기록](docs/reviews/BID04_UI_DEPLOY_2026-10-19.md).

> **2026-10-19 BID-04 최종 Codex NO_GO / 완료 게이트 BLOCKED:** 개발 브랜치 `648ca0a` 이후 실제 로컬 집계 CLI/합성 회귀 구현. 실제 5,718건·활성 검토 2,369·부서 비교 불명 2,369, 결과 BLOCKED_EVIDENCE. 원문/ID·회사/인력/원가·개별 SHA 미노출, 보호 파일393개 전후 동일. 최종 local_app440 PASS/0 skip/309.928초, 감사14/backend11·Node22·build PASS. 별도 Codex는 독립10 PASS/소스 중대 결함 없음이나 Chrome 시작 실패·GitHub OS 소켓 차단으로 **NO_GO**. 문서 포함 commit/push/DONE/main/배포/실제 입찰 없음. [검증 기록](docs/reviews/BID04_LOCAL_AGGREGATE_2026-10-19.md) 및 실행 백로그 최신 BLOCKERS 우선. 아래 미착수는 이전 이력.

> **2026-10-19 BID-03 DONE:** 기존 미커밋 작업 보존.전체 local_app 419 PASS(건너뜀 0), 감사 14·backend 11·Node 22 PASS·build PASS. 기본 sandbox Chrome 155 실제 390px/1440px 세 큐·보류·UNVERIFIED·기존 상세/수기 이력 E2E PASS. 별도 읽기 전용 Codex GO 후 구현 `f642796` 개발 브랜치 푸시, 동일 SHA [Sprint 1 CI](https://github.com/son1004007/public-bid-agent/actions/runs/39198868801)·[Windows synthetic](https://github.com/son1004007/public-bid-agent/actions/runs/39198868837) SUCCESS. [검증 기록](docs/reviews/BID03_SHORTLIST_UI_2026-10-19.md)과 실행 백로그 우선. 다음 BID-04는 미착수. 운영·main·실제 제출 변경 없음.

> **BID-02 DONE / 2026-10-18:** 커밋 `9f3ab29`, 전체 Python 418 PASS, Codex GO, GitHub Sprint 1/Windows synthetic CI SUCCESS. 다음 BID-03 화면; 실제 수익·법정 자격은 계속 UNVERIFIED.

> **BID-02 진행:** `GET /api/dashboard/bid-now-shortlist`가 실제 공고·관심분야·운영 준비도를 같은 잠금에서 평가하는 비식별 로컬 큐. 역량/분야 부족으로 자동 탈락시키지 않고 보완/수익성을 별도 UNVERIFIED로 분리합니다. 실데이터 5,691건을 읽기 전용 확인해 matching 178, augmentation review 2,158, preregistration review 393. 문서/실제 비용·면허/기한의 확인이 없으면 입찰 가능 판정 금지. [계획·BLOCKERS](docs/implementation/DEPARTMENT_BID_NOW_EXECUTION_2026-10-18.md).

> **최신 D-20(2026-10-18):** 사용자는 *지금 현재 부서가 보완 가능한 역량 부족까지 고려하여 수익성 있는 공고를 검토* 먼저 보길 원함. 법적 적격/인력·원가 근거 없는 분야 후보를 실제 입찰 가능한 것으로 표시하지 말 것. [단일 실행 백로그/BLOCKERS](docs/implementation/DEPARTMENT_BID_NOW_EXECUTION_2026-10-18.md)의 BID-01부터 순차 개발. 매회 작은 구현/테스트/Codex GO/개발 브랜치 Git 푸시/CI. 비공개 실제 RFP·회사 인력·원가 외부 전송, main, 공개/실제 제출 금지. 과거 상태 모니터링은 비활성 유지.

> **2026-10-18 감사 환경 분리:** P09 운영 Python과 별도인 `AgentRunner/audit-venv`에 `jsonschema/packageurl-python/pip-audit/license-expression/cyclonedx-python-lib` 도구 설치 완료. 공급망 감사 결과와 라이선스 원본 검증 한계는 [LOCAL_AUDIT_TOOLS_2026-10-18.md](docs/reviews/LOCAL_AUDIT_TOOLS_2026-10-18.md). 실제 RFP 독립 정확도/인력·원가 증빙/사용자 승인 미확정; `main` 및 외부 공개 미진행.

> **2026-10-18 SBOM/복구 진행:** Python 가상환경 연결 패키지 48개 CycloneDX 1.5 / 49 dependency / 관찰 pins 48개 공식 스키마 0 errors. P09 보호 백업 318개가 현행과 모두 일치하며 격리된 318개 복원 파일로 별도 localhost 서버 구동/읽기 전용 API smoke 성공을 확인. 실제 데이터 24건 준비도 GET 정상·Chrome 실제 UI E2E PASS. [1~6단계 검증](docs/reviews/FOLLOWUP_SIX_STAGE_2026-10-18.md). 실제 복원·전체 라이선스/배포 승인·회사 원본 인수는 별도. [실측 보고](docs/reviews/PYTHON_SBOM_AND_BACKUP_CHECK_2026-10-18.md).

> **다른 AI/Codex가 이 저장소를 처음 읽을 때**
>
> 1. [AGENTS.md](AGENTS.md)와 전역 `son1004007/ai-agent-workflow-playbook/CONTROL.md` (보안·검수·구현 기준)
> 2. **[DECISIONS.md](DECISIONS.md)** (사용자의 확정 의사결정, 명시적 제외 범위, 다음 단계 승인 경계)
> 3. [CURRENT_STATE.md](CURRENT_STATE.md) (시점별 구현/검수·로컬 반영 증거), [TASKS.md](TASKS.md) (남은 작업)
> 4. 실제 저장소 `feat/sprint1-search-demo`의 최신 소스·커밋·CI 및 로컬 실행 상태
>
> 과거 파일의 오래된 수치보다 최신 실행 증거가 우선이다. **결정사항은 DECISIONS.md를 단일 원본으로 관리하며, 시점별 수치와 검수 결과를 사용자 결정으로 오해하지 않는다.**

## 2026-10-18 P09 이후 공급망 보완

- `Vite` npm High 권고를 `7.1.12 -> 7.3.7`으로 해결, React 시안 `package-lock.json` 추가. Python 가상환경 10개 직접 의존성 충족, 전체 51개 목록, OSV 48개 조회 결과 0건, npm audit 0건 및 시안 빌드 PASS.
- 운영 서버 비식별 수집 품질 집계: 활성 220, 추출 87, 원문 확보 대기 130. [독립 원본·회사 증빙 인수 절차](docs/reviews/RFP_REAL_EVIDENCE_GATE_2026-10-18.md). 원본 RFP/회사 자료는 외부 검수에 전송하지 않았음. 라이선스 고지·전체 Python 릴리스 lock/SBOM, 실제 원본 필수요건 정확도·회사 증빙·사용자 UI 인수는 미완료. [세부 감사](docs/reviews/DEPENDENCY_SECURITY_AUDIT_2026-10-18.md).

## 최신 검증 기준: 2026-10-18 P09 완료

- `feat/sprint1-search-demo`의 P04~P09 구현/합성 검증 완료. P09 최종 실행 소스 커밋은 `f06a3faebbcf3995f6d1ac2fd3fe5c1f9b978c86`이며 Windows 로컬 서버 `127.0.0.1:8765`에 동일 SHA로 적용됨.
- Windows `cp1252` 호환 파서·테스트 수정, Python 403 PASS, Windows 대응 52 PASS, Codex read-only GO, 두 GitHub Actions SUCCESS 및 배포 후 Chrome read-only E2E PASS. 실제 원본 보호 파일 318개 SHA 동일.
- `CURRENT_STATE.md` 최신 섹션과 [P09 최종 실행 근거](docs/reviews/P09_WINDOWS_CI_FINAL_2026-10-18.md)를 우선 확인. 아래 P08/P09 독립 검수 대기/Chrome BLOCKED 항목은 당시 기록이다.
- **잔여:** 실제 고객/회사 자료 기반 법적·기술적 충족 판정, 사용자 UI 인수, SBOM/라이선스·운영 복구 실증, P10 main/공개 릴리스 승인. P11/D-10 보류, 실제 입찰 자동 실행 금지.

## 1. 현재 프로젝트/실행 아키텍처

- 목적: 공식 나라장터 용역공고 전체 수집 → 공고 상세/RFP 추출·분석 → 실제 부서의 입찰자격·실적·기술·인력·원가와 비교 → 사람의 참여 결정·제출·평가·수주 추적을 지원하는 근거 기반 웹서비스.
- **현 기준 웹:** `http://127.0.0.1:8765/decision-preview`; `local_app/server.py` (Windows CPython 3.12, 127.0.0.1 전용) + `frontend/public/bid-decision-dashboard-preview.html` + `frontend/public/dashboard-live.js`. 현재 비공개 로컬 JSON 데이터와 SHA 결속 RFP 캐시 사용.
- `frontend/` React와 `backend/` FastAPI 코드는 별도 개발·시안 자산이다. 실제 인터넷 공개 서비스/Google 로그인/원격 계정·다중 사용자는 아직 운영 중이지 않다.
- 서비스 로컬 데이터는 비공개 사용자 PC에 두며, 회사 문서/인력·원가/DPAPI API 인증키를 GitHub나 Codex 검수 입력으로 전송하지 않는다.
- 기존 LangGraph와 Codex/Claude CLI 수동 교차 검토는 제한적 별도 기능으로, 모든 공고에 실제 LLM 기반 AI 추천이 서비스된다는 뜻이 아니다.

## 2. 날짜·검증 단위를 명확히 구분한 현황

### 2026-10-18 P09 NO_GO/P1 배치 fixture 격리 수정

- `RFP_BATCH`를 임시 root/차단된 외부 어댑터의 새 manager로 교체. 기존 manager/root 접근 거부와 IDLE·RUNNING GET/worker lock 회귀 추가, API **11 PASS**. 아래 최초 48 PASS는 배치 격리를 검증하지 못한 과거 기록이다.
- Chrome 재실행도 sandbox 종료로 **BLOCKED**. 독립 재검수/Git 기록은 orchestrator 인계이며 GO 아님. 실제 자료·배포·main·add/commit/push 없음, D-10/P11 보류. [검증](docs/reviews/P09_SYNTHETIC_ACCEPTANCE_2026-10-18.md).

### 2026-10-18 P09 Windows 합성 인수 게이트

- 신규 API 8개 포함 보안·파서·이력·복구 회귀 **48 PASS**. Chrome 파일 선택/수기 저장·새로고침 runner 및 Windows CI 추가, 실제 앱 코드 변경 없음.
- Chrome 155는 sandbox 진단과 함께 새 페이지 생성 중 종료(`2147483651`), **CHROME_E2E BLOCKED**. 테스트 작성/실제 브라우저 통과/사용자 UI 승인을 구분한다. 의존성 일부 누락·버전 불일치, 전체 라이선스/CI/독립 검수·운영 적용 미완료.
- CONTROL/handbook 원본은 GitHub 연결로 확인. 공개 소스·합성 fixture만 사용했고 사용자 자료 접근·배포·Git 기록 없음. D-10/P11 보류. [검증·다음 실행](docs/reviews/P09_SYNTHETIC_ACCEPTANCE_2026-10-18.md).

### 2026-10-18 P08 수기 이력 복구 합성 회귀

- 실행 코드/API/저장 형식은 유지하고 신규 11개 테스트 및 기존 백업 fixture를 보강했다. 수기 이력 재조회·중복·원자 저장 실패 후 재시도·실제 두 프로세스 revision 충돌과 백업/복구의 기존 이력·최신 편집 보호를 확인했다. 관련 Python **53 PASS**, 공백 검사 PASS, README 2종 동기화.
- 공개 소스·임시 합성 데이터만 사용. 독립 Codex 검수/CI/실 운영 복구·Chrome 인수 NOT RUN, orchestrator 인계. 실제 자료·외부 AI·자동 입찰·main·배포·add/commit/push 없음. D-10/P11 보류. [상세 증거·미검증 범위](docs/reviews/P08_SYNTHETIC_HISTORY_RECOVERY_2026-10-18.md).

### 2026-10-18 P07 구형 검증 NO_GO/P2 보완

- 공백 근거 구형 `verified=true`를 조언·요약·UI 지표/체크박스에서 일관되게 미검증 처리. 원본 기록·최종 결정·이력 보존. 합성 Python **88 PASS**, Node **11 PASS**, JS/공백 검사 PASS. 독립 재검수는 orchestrator 인계이며 GO 아님. [기록](docs/reviews/P07_LEGACY_VERIFICATION_FIX_2026-10-18.md).
- 이번에는 GitHub 연결로 CONTROL 및 지정 handbook 원본을 확인했다. 실제 문서·외부 LLM·운영 적용·Git 기록 없음. D-10/P11 보류 유지.

### 2026-10-18 P07 입력 절단 NO_GO/P2 보완

- 자료 헤더 포함 90,000자 상한의 실제 범위·누락을 공통 계산/저장하고 UI에 표시. 미전달 인용 거부, 불완전 입력은 AI 조건·점수 제외 및 보수적 보류. 사용자 결정·이력 보존. 관련 Python **82 PASS**, Node **8 PASS**, JS/공백 검사 PASS; 독립 Codex 재검수는 orchestrator 인계이며 아직 GO 아님.
- 공개 소스·합성 fixture만 사용. 외부 정책 원본 네트워크 접근 BLOCKED; 실제 문서·LLM·운영 반영 없음. D-10/P11 및 Git/배포 금지 유지. 아래 75/6은 수정 전 검증 이력. [인계](docs/reviews/P07_SYNTHETIC_RECOMMENDATION_DRAFT_2026-10-18.md).

### 2026-10-18 P07 수동 AI 초안·출처·규칙 fallback

- 로컬 수동 AI 화면(`/`)의 추천/항목별 DRAFT와 출처 ID·추출 텍스트 SHA·문자 범위·인용 대조를 연결했다. 서버 입력 버전이 없는 구형 초안/입력 변경, AI 누락·의존성 장애는 fallback. 사용자 `unknown`/공백 근거는 확인 완료로 인정하지 않는다. 최종 결정과 이력 보존.
- 합성 Python 7개 모듈 **75 PASS**, Node **6 PASS**, JS 문법 PASS, 기존 결함 2개를 HEAD 코드로 재현 후 수정 확인. 실제 LangGraph는 `langchain_core` 미설치로 BLOCKED; 그래프 경계는 합성 mock, 외부 LLM·실자료·운영 반영·독립 검수/CI/브라우저 인수는 NOT RUN. [인계](docs/reviews/P07_SYNTHETIC_RECOMMENDATION_DRAFT_2026-10-18.md). add/commit/push·main·배포 없음, D-10 보류.

### 2026-10-18 P01/P06 합성 위험 검토·부서 준비도 보완

- PDF 페이지별 OCR 대조 신호와 HWPX 섹션별 표·각주·병합 표식을 표시. 준비도는 증빙 요약/출처/확인일 누락·미래 확인일 및 가용 MM/원가 자료 부족 사유를 제공한다. 공고별 비교 NOT_PERFORMED, 실제 적격·수익성 UNVERIFIED 유지.
- 관련 Python **82 PASS**, 기존 Node 요약 **3 PASS**, JS 문법 PASS. 합성 fixture/임시 JSON만 사용. 독립 검수·CI·브라우저 인수·실문서 평가·운영 반영 NOT RUN. orchestrator 검수/Git 기록 인계, D-10 제외 및 add/commit/push·main·배포 금지. [근거](docs/reviews/P01_P06_SYNTHETIC_READINESS_2026-10-18.md).

### 2026-10-18 P05 합성 출처·차수·STALE 회귀 및 NO_GO 보완

- 길이 초과 공고번호/차수를 잘라 정상 ID로 수용하던 정규화 경로를 전체 문자열 검증으로 보완. 신규 14개 합성 시험과 관련 회귀 **76 PASS**; 취소·구차수·STALE 차단, 원문·사람 판단 보존 확인. [재현·검증 기록](docs/reviews/P05_SYNTHETIC_SOURCE_SAFETY_2026-10-18.md).
- 이후 독립 검수 **NO_GO/P1**: 위 76 PASS는 같은 배치의 취소→일반 응답 손실을 놓쳤다. 신규 4개 테스트에서 수정 전 29개 subtest FAIL 재현 후 페이지·조회기간 중복 제거/저장 병합의 취소 보존을 보완. 관련 8개 모듈 **91 PASS**, 독립 Codex 재검수 대기.
- 전체 회귀/CI/실원본 검증/운영 반영은 NOT RUN. 실제 사용자 JSON/RFP/회사 증빙을 읽거나 전송하지 않았고 STALE 자동 해제 없음. D-10 제외, main·배포·add/commit/push 금지인 이번 작업 지시를 우선. 재검수/Git 기록은 orchestrator 인계.

### 2026-10-16 P04 미래 추출 parser provenance fingerprint

- 신규 추출 근거에만 `parser_provenance` schema 1(코드/Python/패키지/환경 설정 및 method fingerprint, OCR 바이너리/언어팩 NOT_CAPTURED)을 남기고 재추출 일치 여부를 보수적으로 검사. 구형 근거는 `NOT_VERIFIED`; 기존 캐시를 수정하거나 실제 원본 전체 누락률을 확정하지 않음.

### 2026-10-16 P00~P11 잔여 실행표 및 텍스트 라벨링·문서 품질 위험 진단

- Windows 전체 **319 PASS**, Codex 독립 2차 **GO**, 로컬 /api/dashboard/rfp-audit /api/dashboard/rfp-review-queue smoke 및 Chrome headless 위험 패널 검증 PASS, 사용자 JSON/RFP 캐시 **164개 SHA 불변**. 구형 증거/실제 원본 전수·법적 적격/실 AI/GUI 최종 승인/배포는 미완료.
- 필독: [실행 순서/선행조건/검증/미완료](docs/design/REMAINING_EXECUTION_ROADMAP_2026-10-16.md). PDF/HWPX 구조 위험 메타 분석 `local_app/document_quality.py`, 실원본 SHA 일치 뒤 subprocess 호출. `local_app/rfp_audit_labels.py`는 사람 검토를 별도 비공개 JSON 이력으로 보존하며 현재 근거 SHA·offset에 결속. 화면 후보 라벨의 갱신은 전체 원문 TP/FP/FN/Recall이 아님. `rfp_review_queue.py`는 비식별 신호 기반 처리 큐. 실제 회사 근거/원문 독립 라벨·비공개 외부 AI 승인/사용자 UI 승인·main/공개 배포는 진행되지 않았음.

### 2026-10-16 원본 업로드·캐시 안전성·부서 준비도·제출/평가 이력 (후속 연결)

- 선택한 공식 RFP 원본의 로컬 메모리 SHA·캐시 대조 API/화면, 원자적 청크 등록과 메타데이터 충돌 안전 실패, 부서 6개 증빙 준비도, 담당자 수동 제출→평가→선정/미선정 이력을 추가. **신규 추출 근거에만 공고 번호/차수 결속**, 구형 데이터는 차수 검증 불가로 보류. Windows 전체 **308 PASS**, Codex **2차 GO**, 8765 새 API smoke PASS, 사용자 JSON/청크 캐시 **164개 SHA 불변**. 실 PDF/HWP 원문 전체 완전성, 직원/회사 자격 확정, AI 종합 자동추천, 실제 제출·낙찰 인수·Chrome GUI 사용자 승인/공개 배포는 미완료. [현재 실행/잔여 범위](docs/design/STAGE2_4_EXECUTION_PROGRESS_2026-10-16.md), [검증 보고](docs/reviews/RFP_FOLLOWUP_STAGE2_4_2026-10-16.md).

### 2026-10-16 공식 원본·캐시 오프라인 비교 준비 (후속 5단위)

- `rfp_original_compare.py`는 공식 원본 바이트를 **별도 확보한 경우에 한해** SHA·첨부 identity·검증된 캐시의 5개 증거 필드·현재 파서 재추출 텍스트와 길이를 비교하는 독립 순수 함수(파서 version/OCR `NOT_VERIFIED`). Windows **299 PASS**, Codex **3차 GO**, 기존 비공개 164개 SHA 집계 불변. 원본 PDF/HWP 실제 대조와 웹서버 신규 기능 적용은 **NOT RUN**. [후속 10단계 계획](docs/design/RFP_ORIGINAL_AUDIT_PLAN_2026-10-16.md).

### 2026-10-16 RFP 추출 문자 손실 정량 진단 (후속 4단위)

- 문서별 파서 메타데이터의 저장 문자 수 차이를 비식별 집계하여 로컬 수집 화면/API에 표시. 절단/검증 불가/불일치·경고를 분리. **Windows 292 PASS, Codex GO, 로컬 8765 API PASS, 비공개 자료 SHA 164/164 동일**, 실제 파서 보고 657453자(12공고). 원본 PDF/HWP의 실제 문자·표·각주·요건 손실은 증명하지 않는다. [변경/검증 기록](docs/reviews/RFP_EXTRACTION_LOSS_LENGTH_2026-10-16.md).

### 2026-10-16 RFP 확보 품질 메타데이터 진단 (후속 3단위)

- 기존 RFP 확보 진단/API·로컬 수집 화면에 `STALE`, 원문 캐시 참조(무결성 미검증), 발췌/근거 부재, 파서 절단/경고·처리 상한의 **중복 가능 비식별 건수** 추가. Windows 전체 **287 PASS**, Codex 최종 GO; 8765 로컬 GET에서 부서 후보 287·활성 180, 파일 SHA 164/164 동일 확인. 실제 Chrome 조작/전체 RFP Recall·법적 적격은 미검증. [검증 기록](docs/reviews/RFP_QUALITY_METADATA_2026-10-16.md).

### 2026-10-16 분류 정량 평가 도구 추가 (후속 2단위)

- 순수 메모리 입력·숫자 집계만 수행하는 `local_app/rfp_taxonomy_benchmark.py`로 **독립 라벨링된 추출 텍스트 한 줄**의 3분류 TP/FP/FN·Precision/Recall/F1을 계산. 실제 원본 전체 라벨 데이터는 없으므로 실 RFP 정량 정확도는 미측정. [범위 및 라벨링 절차](docs/reviews/RFP_TAXONOMY_BENCHMARK_PROTOCOL_2026-10-16.md).

### 2026-10-16 후속 구현 D-17 (범위별 승인 상태 유지)

- RFP 근거 표현의 유형별 표시 상한 5건을 유지하면서 실제 추출 텍스트에서 더 발견된 중복 제외 후보 수를 `omitted_count`로 계수·UI 표시. 이는 Recall/Precision 또는 전체 필수 요구사항 수 측정이 아니며, 회사 자격 판단·원본 수정·외부 AI 호출도 하지 않는다.
- 로컬 Python 전체 279 PASS, Node UI 계약 3 PASS, Codex 1차 NO_GO 보완 뒤 최종 GO; 서버 재기동 후 실제 8765 API에서 9유형/표시 19·생략 14/2문서, 파일 SHA 164/164 동일 확인. Chrome 실제 GUI와 UI 최종 승인은 별개. [검증 보고](docs/reviews/RFP_CAP_VISIBILITY_2026-10-16.md).
- 후속 Stage 2·AI 의미 추천은 합성·비공개 데이터 경계가 충족되는 단계로 분리한다. 7일 API 과거 실패 선제 진단·main 병합·공개 배포는 기존 보류 유지.


### 2026-10-15 RFP 후보 3분류 개선 (D-16)

- 규칙 기반 기존 8개 유형에 `evaluation`(평가기준·선정방식) 신설, **9개/schema_version=2**. 공동수급 허용/구성과 공동수급 평가 점수, 사업 과업과 평가·목차·계약관리 안내를 구분하도록 필터 강화. `참가자격/evaluation/scope` 3그룹에 대해 정답이 지정된 합성 문장 테스트와 실제 RFP 20건 읽기 전용 표본을 확인. **Recall·법적 적격성·완전성 미확인**.
- 실제 로컬 8765 서버의 schema v2 전환 및 Chrome 9개 분류·32개 원문/출처 접힘·390px 모바일 PASS, 전체 Python 276 PASS, Codex 1~3차 NO_GO 지적 수정 후 4차 GO, 사용자 데이터 SHA 164/164 동일. 사용자 UI 승인과 main 병합은 별도.
- 근거: [실제 분류 표본·한계](docs/reviews/RFP_TAXONOMY_3WAY_2026-10-15.md), [결정](DECISIONS.md) D-16. 2026-10-13 당시 8유형 및 561개 표현 수치는 과거 버전 기록임.

### 2026-10-15 RFP 원문 우선 UI 개선 (D-15)

- 사용자 요청에 따라 RFP 요구사항 표현 후보는 전체 너비 원문 세로 목록으로 보여 주고, 원본 파일·SHA-256·추출 문자 위치 등은 각 항목별 기본 접힌 네이티브 `details/summary`에서만 펼쳐 본다. 다른 `requirementRow` 기능/API/원본 자료는 변경하지 않음.
- 실제 Windows Chrome 공식 공고 → 상세 → RFP 구조화: 원문 후보 31건, 메타정보 접힘 31/31, 펼치기·접기 PASS, 모바일 390px 가로 넘침 없음. Python 전체 274 PASS, 비공개 파일 164/164 SHA-256 기존 기준값과 일치. **Codex 신규 UI 변경 독립 검수 1차 NO_GO CSS 격리 지적 수정 후 2차 GO**. [UI 변경·검증](docs/reviews/RFP_ORIGINAL_FIRST_UI_2026-10-15.md).

### 2026-10-15 최신 로컬 운영 및 검증

- **로컬 서버·실제 Chrome 검증 완료:** `TD-kiseok`의 기존 로컬 시작 스크립트로 127.0.0.1:8765 기동. 공식 공고 3,777건(CURRENT 3,263/CANCELLED 201/SUPERSEDED 313), STALE RFP 10건. RFP fulltext 참조가 있는 현행·비STALE 공고 65건.
- 2026-10-15 UI 개편 이전 실증한 RFP 요구사항 구조화 읽기 전용 GET의 **당시 8개 유형/schema v1**에서 원문 표현 후보 31개/출처 문서 1개, 파일 SHA 및 추출 문자 위치, `page=null`, 법적 적격 `UNVERIFIED` 확인. 취소·구차수·STALE 분석 보류 및 잘못된 ID 처리 확인.
- **Chrome 실제 UI:** 공고 목록→상세→참가자격·과업→RFP 요구사항 근거 조회 버튼과 출력 PASS. 모바일 390px PASS. 비공개 JSON 40개 + RFP 캐시 124개 **SHA-256 164/164 동일**, Python 전체 **274 PASS**, JS·문서 동기화 PASS, Codex 독립 GO, GitHub CI 성공.
- **상태:** `LOCAL_APPLIED` + `CHROME_E2E_VERIFIED`. 사용자 화면 최종 승인, `main` 병합, 인터넷 공개, 다음 Stage 2와 보류된 7일 API 실패 원인 조사는 미수행. [실제 검증 보고](docs/reviews/RFP_STAGE1_LOCAL_ACCEPTANCE_2026-10-15.md).

### 2026-10-13 실제 로컬 운영에 반영된 사실 (당시 기록)

- 공식 공고 저장 **3,049건**: `CURRENT 2,653`, `CANCELLED 167`, `SUPERSEDED 229`. 정정/취소 반영 뒤 구차수와 취소 공고를 기본 추천에서 제외했다.
- 중요 메타 변경으로 원문 확인이 필요한 RFP `STALE 8건`: 원문·판단·이력 보존, 재확인 전 추천/구조화 보류.
- 매일 오전 09시 Windows Task Scheduler (`PublicBidAgent-OfficialCollection`)가 현재 사용자 로그인 조건으로 등록됐다. **첫 예약 실행의 성공 여부는 현재 연결된 PC에서 재확인**해야 한다. 첫 7일 수집 실패 원인 진단은 사용자가 명시적으로 제외했으며 같은 문제가 다시 발생한 경우에만 별도 논의한다.
- 현재의 규칙 기반 추천은 상세 검토 순위이고 법적 입찰 가능·수주 확률·회사 적격성 확정이 아니다.
- 근거: [정정·취소 확인](docs/reviews/OFFICIAL_AMEND_CANCEL_LOCAL_VERIFY_2026-10-13.md), [자동수집](docs/reviews/AUTO_G2B_COLLECTION_2026-10-13.md).

### 2026-10-13~14 RFP 요구사항 구조화 1단계: 당시 소스 검수 기록

- `local_app/rfp_requirements.py`: 공식 첨부 identity/원본 SHA-256/개인 PC의 44,000자 RFP 청크에서 **8개 유형의 원문 표현 후보** 추출; 누락/절단 경고와 추출 텍스트 시작·끝 offset, `page=null` 반환.
- `GET /api/dashboard/rfp-requirements?id=...` / 상세 화면 `RFP 요구사항·출처 근거 확인` 버튼 추가 개발. 취소·구차수·STALE 공고 분석 보류, AI 추론/법적 필수요건 확정 없음, 소스 저장·외부 전송 없음.
- 실제 비공개 데이터 **후보 66건 중 균등 20건** 샘플: 원문 표현 후보 **561건**, 텍스트 일부 보존 4건, 오류/0건 0. 구체적인 문서 내용은 공개 repo에 기록하지 않았다.
- **Windows 회귀 274 PASS, Codex NO_GO 지적 3종 수정 후 독립 최종 GO** (신뢰된 개인 Windows localhost 전제). 소스·테스트 검수와 **실제 PC 서버 재시작/브라우저 새 버튼 확인/로컬 적용**은 서로 다르며 뒤 항목은 2026-10-15 최신 로컬 검증 절에 확인 결과가 기록됐다.
- 근거: [설계](docs/design/RFP_REQUIREMENTS_SLICE_2026-10-13.md), [대표 20건 검증](docs/reviews/RFP_REQUIREMENTS_LOCAL_EVIDENCE_2026-10-13.md), `local_app/test_rfp_requirements.py`.

## 3. 현재 승인/보류 범위

- **결정됨:** RFP 구조화 1단계를 실제 근거와 함께 검증한다. 원본 페이지나 확정 참가요건을 만들어내지 않는다. 직전 자동 수집 API 오류 진단을 선제 진행하지 않는다.
- **사용자 다음 결정 대기:** 부서 역량 비교, LangGraph/RAG 기반 의미 추천, STALE 8건의 안전 재검증, 공식 변경이력/별도 공고번호 재공고 매칭, 인터넷 공개·멀티유저.
- 소스 변경 시 루트와 `local_app/README.md` 동기화, 애자일 작은 구현 단위·합성/실제 자료 분리 검증, **Codex만 독립 검수**를 적용한다. 사용자 승인 전 `main` 병합·전체 인터넷 릴리스 선언을 하지 않는다.

## 4. 이전 날짜 기록을 읽는 기준

과거 문서(예: 2026-10-09~12)의 `공고 2,223건`, `자동 수집 미구현`, `정정/취소 미반영`은 **당시 시점 기록**이다. **현재 상황으로 재사용하지 말 것.** 최신 사용자 결정은 `DECISIONS.md`, 실행 상태는 `CURRENT_STATE.md`, 다음 단계는 `TASKS.md`와 실제 repo/CI/PC 증거로 판단한다.
