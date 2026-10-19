# BID-05 문서 후속 작업 검증

- 시작: feat/sprint1-search-demo / bd1c072, 추적 변경 없음·로컬 승인 메모 미추적 보존. 같은 저장소 작성 중인 타 Codex 없음. 기존 BID-04의 공통 정책/운영 인수 근거 재사용, 이번 사용자 직접 승인 범위를 DECISIONS에 먼저 기록했다.
- 구현: 새 읽기 전용 큐/API/후보 화면, 공식 첨부 identity·차수·저장 원문 SHA/청크 해시 검증, 보류·선정 근거/확인 소요·다음 작업/재평가 제한. 승인된 기존 batch의 실패 단계만 추가. 자동 다운로드/배치 실행·재시도·LLM·실제 입찰 없음, 기존 성공/회사 설정/사람 이력 보존. 상세는 설계 문서.
- 표적 검증: 최초 관련46개 중45 PASS·1 FAIL은 등록기한 경과 공고를 보류로 분리한 새 계약과 HTTP 기대값의 차이였다. 기대값 수정 후 HTTP2 PASS. 실제 집계에서 미추출을 부분 추출로 중복 표시하고 확인된 취소 상태를 불명으로 표시한 분류를 수정했다. 해당 회귀와 cache 상한/중복 JSON 검사를 포함한 최종 신규14 PASS. 기존 관련33개는 앞 실행 PASS.
- Node 계약32 PASS. 처음 파일 glob에 Chrome runner가 포함되어 결합 결과는32 PASS/Chrome1 FAIL이었다. 새 큐의1440/390 검증과 기존 파일 선택은 통과했지만 기존 수기 이력 단계에서 합성 fixture stderr 감지로 중단했다. 이 최초 실패는 최종 PASS와 구분한다. build PASS. 기존 안전 설정/사용자 Chrome 프로필을 변경하지 않았다.

## 실제 로컬 읽기 (2026-10-19 15:37 KST)

- total_notices: 5718
- needs_attention_count: 5718
- action_required_count: 2872
- held_count: 2846
- reason_counts: {'CANCELLED': 314, 'DEADLINE_PASSED': 2366, 'DEADLINE_UNKNOWN': 682, 'DOWNLOAD_PENDING': 4991, 'EXTRACTION_WARNING': 22, 'FAILED_STAGE_UNKNOWN': 19, 'NO_EXTRACTED_TEXT': 5610, 'OFFICIAL_ATTACHMENT_MISSING': 618, 'OFFICIAL_ORIGINAL_RECHECK': 5718, 'PARTIAL_EXTRACTION': 92, 'REGISTRATION_AFTER_CLOSE': 6, 'REGISTRATION_PASSED': 2398, 'REGISTRATION_UNKNOWN': 686, 'SOURCE_VERSION_UNVERIFIED': 108, 'STALE_SOURCE': 11, 'SUPERSEDED': 514, 'TEXT_OR_TABLE_TRUNCATED': 13, 'UNSUPPORTED_FORMAT': 1208}
- snapshot_check: STABLE_OBSERVED_READS
- release_metadata_state: LEGACY_COMPLETED_UNVERIFIED
- protected_files: 393
- protected_files_unchanged: True

건수는 중첩 위험 신호이다. 문서·회사/인력·원가·개별 ID/첨부명·URL·SHA/경로는 출력/검수/공개 기록에 넣지 않았다. 원본 binary/공식 최신성·적격·수익·인력/MM은 UNVERIFIED, BLOCKED_EVIDENCE 유지. 차수 결속이 없는 과거 성공108건을 최신 분석으로 재사용하지 않고 재평가를 보류한다. 보호 파일393개 전후 동일, 원본/사용자 데이터 쓰기·외부 원본 접근 없음.

## 남은 게이트

전체 Python·별도 Chrome·최종 독립 Codex·개발2/main CI·main 반영·검증 백업/운영 API/화면/전후 무결성 전 DONE 아님. BID-06은 시작하지 않는다.

## 최종 로컬 검증

- 전체 local_app **457 PASS / FAIL0 / ERROR0 / SKIP0**, runner215.469초·unittest210.192초, 원시 로그 `bid05-full-regression-20261019.log`. 감사14/backend11 PASS 포함 **Python482 PASS**. 운영 Python/패키지 변경 없음, 별도 CPython3.12.0 venv 사용.
- Node 계약 **32 PASS**, 화면 변경 후 신규5개 재확인 PASS. build/정적·문법·공백 PASS. 신규 Python14·기존 관련33개·전체 회귀로 경계 확인.
- Chrome155.0.8059.40/Node22.14.0, 기본 sandbox·전용 임시 프로필·지정 venv의 최종 **390/1440px 전체 E2E PASS** (세션39310 exit0): 새 문서 큐/작업2·보류4/위험·UNVERIFIED/재시도 없음/기존 상세 연결·가로 넘침 없음, 기존 BID03/04·XSS/파일 선택·수기 이력/재조회·외부 요청 없음. 합성 PNG 두 폭 보존, 모바일 육안 확인.
- Chrome 오류 처리: 새 상세에서 큐로 복귀할 때 기존 shortlist 재로딩 대기를 빠뜨린 시험 assertion을 수정했다. 모바일 큐에서 기존 requirementRow 다열 배치가 부적절해 단일 카드로 수정하고, 실제 pointer 위치에 대상이 보이는지 검사를 추가했다. 최종 기존 수기 이력까지 PASS. 최초 합성 fixture stderr는 최종 환경에서 재현되지 않았으며 과거 원인은 UNKNOWN, 성공으로 재분류하지 않는다. 샌드박스/Origin/CSP 완화나 기존 Chrome/사용자 설정 변경 없음.
- 로컬 배포 실행안은 BID-04의 명시 refspec/정확 SHA·개발2/main CI·정확 이전 소스/PID·393파일 전체 백업/전후 SHA·이전 소스 복귀를 그대로 재사용하고 신규 API/GET 전용390/1440 큐 인수만 BID-05에 맞췄다. 아직 실행하지 않았으며 독립 검수 범위에 포함한다. 기존 last-local-release의 실행 소스4f1743d 및 private backup이 기준이다.
- 현재 **VERIFIED / 독립 최종 검수 대기**, GO·CI·운영 전 DONE 아님.

## 독립 최종 검수 NO_GO 및 지적 수정

- 별도 fresh-context read-only Codex가 공개 소스/정책/설계/합성 로그·PNG/배포 실행안만 검토했다. 운영 원본·승인 메모 미접근, 서버/Chrome/Python/설치/Git 쓰기 없음. Node24 직접 PASS. 시작/종료 source bundle e9aad1…775b9 및 ops2 SHA 일치.
- 최초 **NO_GO / MAJOR1**: 최신 문서 큐가 기존 메모리의 과거 CURRENT/EXTRACTED 상세를 바로 열 수 있었다. 검수자가 실제 fragment/openFullDetail의 순수 Node 반례로 확인했다. **MINOR1**은 AI_CONTEXT의 과거 BID05 미착수 및 CURRENT_STATE의 Chrome 대기/성공 혼재였다.
- MAJOR 수정: 제한 캡처의 dashboard_revision 반환·정수 검증, 상세 클릭마다 기존 reload GET 후 큐 revision/ID 대조. 변경/실패면 상세를 열지 않고 큐 갱신 및 고정 안내, 중복 클릭/조회 경합·다른 화면 이동도 늦은 상세 열기를 차단한다. 자동 다운로드/쓰기 추가 없음. 문서 MINOR도 최신 상태로 정리했다.
- 수정 후 Python 표적14 PASS, Node 신규9 포함 전체36 PASS(Temp/bid05-node-final-20261019.log), Chrome 기본 sandbox390/1440 전체 E2E 다시 PASS(세션36931 exit0). 같은 ID STALE/취소·신규 ID·큐 이후 정정·GET 실패/비반사·새 조회/중복 클릭·화면 이동 경합을 직접 테스트한다.
- API/UI 계약 변경으로 고정 수정본 전체 회귀를 한 번 더 수행하며, 이전457 PASS와 구분한다. 감사14/backend11은 코드 변화 없음. 독립 지적 재확인·최종 GO 전 Git/운영 기록 없음.

## 최종 독립 GO 및 개발 반영 게이트

- 같은 read-only Codex의 지적 재검수 **GO**, MAJOR1·MINOR1 RESOLVED, 추가 BLOCKER/MAJOR 없음. 실제 상세 함수를 붙인 반례에서도 최신 STALE 메모리 사용·GET1회를 직접 재현, 독립Node28 PASS. 사전 독립 검토는 사용자 명시 순서(구현/테스트 후 독립 검수)에 따라 NOT RUN이며 최종 구현 검수와 구분한다.
- 수정본 전체 **457 PASS / 실패·오류·건너뜀0 /306.891초**, Temp/bid05-postreview-regression-20261019.log(세션5341 exit0). 감사14/backend11 포함 Python482 PASS. Node36 PASS 및 Chrome390/1440 전체재PASS를 직접 로그 확인했다. 최종 source bundle `96d4f7bb29a128258f694a7b68547c939f3dc5485a84ed1b3e6ddebebc4fdbb9`, 시작/종료 동일. 로컬 배포 Python SHA `3fee7ffa2f94089733592c2ddfefed98f73df8b75679cb75816f729516cdcc18`, Node SHA `4b7eccef000f3b364d359c64c1bb6c0ae888aff60daf51e0aa54c57d80df5450` 동일.
- 16:01:45 KST 재확인: 전체5,718 / 확인작업2,870 / 보류2,848 / 보호393파일 전후동일. 시간이 경과해 작업2건이 보류로 바뀌었으며 파일 내용/추가/삭제는 없다. 회사·개별 공고/본문/원본SHA·경로는 출력하지 않았다. source_files_written false, status BLOCKED_EVIDENCE. 실제 자료의 공식 최신성·자격·수익·인력/MM은 그대로 미검증.
- 사용자 메모 원본 불변 및 remote dev/main bd1c072를 확인했다. GO 후 개발 반영·두 CI·main 조상 검사/CI·운영 인수를 진행하며 아직 DONE 아님.

## 최종 Git/CI/운영 인수 (2026-10-19 16:10 KST)

- **BID-05 DONE**. 개발/최초 main 실행 구현 `de8c294d8afc5ddbc3f2ff5ba70eb9d52885c708`. 독립 GO 이후 commit/push, [개발 Sprint 1 CI](https://github.com/son1004007/public-bid-agent/actions/runs/39213540830)·[Windows acceptance](https://github.com/son1004007/public-bid-agent/actions/runs/39213540829)·[main CI](https://github.com/son1004007/public-bid-agent/actions/runs/39213881253) 모두 SUCCESS. 공개 synthetic CI 로그에서 Ubuntu457+14+11 PASS, Windows106 PASS 및 새 문서 큐/기존 전체 Chrome390/1440 PASS 확인. 기본 main bd1c072에서 고유 변경이 없고 조상임을 검사한 뒤 fast-forward, 강제 push/초기화/기존 Lab 작업 트리·설정 변경 없음.
- CI 상태 조회 1회의 PowerShell jq 인용 오류는 구조화 JSON 파싱으로 바로 해결했다. CI/코드 실패가 아니며 같은 명령 반복 없음. 앞선 최초 실패/Chrome 오류/독립 NO_GO는 위 이력을 보존하고 최종 성공과 구분한다.
- 배포: 검수한 ops 두 파일의 SHA 재확인 → 개발/main 정확 SHA/CI/이전 검증 소스4f1743d·private backup/정확 서비스 PID·배치 유휴 preflight PASS → 새 Git archive → 원본 첨부/설정 포함 **393개 전체 파일 백업·SHA 검증** → 알려진 기존 프로세스만 교체·같은 데이터 경로/127.0.0.1:8765 기동 → 새 API/GET 전용 운영 Chrome → **393파일 전후 동일**. 백업은 기존 private-backups에 보존하며 실제 경로·첨부명·개별 SHA·공고 본문은 기록하지 않는다.
- 결과 `LOCAL_APPLIED`, 07:10:32 UTC /16:10:32 KST, stageBID05, HTTP200, bid05_api_verified=true, bid05_390_1440_readonly_ui_verified=true, protected_file_count=393/protected_files_unchanged=true. 새 큐의 작업/보류·선정/다음 작업·명시적 UNVERIFIED/자동 다운로드·재시도 없음·legacy 경고 및 기존 추천/상세/RFP/P06 API 흐름 PASS. 고정 localhost GET만 허용한 새 Chrome 프로필을 사용, 기존 사용자 Chrome/계정·외부 서비스 공개/방화벽/이전/초기화 없음.
- 16:11 KST 재확인: 전체5,718/확인작업2,870/보류2,848, dashboard revision55, BLOCKED_EVIDENCE·analysis_complete=false. UI와 실제 데이터는 원본 확보 전 분석 완료·입찰 가능으로 표시하지 않는다. 15:37과의2건 차이는 시간 경과이며 파일 bytes/추가/삭제는 그대로다.
- 복귀: 신규 API/화면 또는 파일 무결성 실패 시 검증된 이전 고정 소스/같은 데이터로 복귀하는 기존 절차와 시작 실패 보완 경로를 사용한다. 이전 소스/백업의 존재·게이트를 확인했고 실제 배포 성공으로 rollback 실행/데이터 덮어쓰기 복원은 불필요했다. 백업과 모든 기존 성공/검토 이력·설정·원본을 보존했다. 로컬 사용자 승인 메모는 원위치 미추적 보존하며 공개 Git에 포함하지 않았다.
- 문서 마감 커밋은 Markdown만 변경하며 실행/테스트/CI 코드는 위 배포 SHA와 동일하다. 개발/main 최종 문서 HEAD와 배포 실행 SHA를 구분하며, 문서 때문에 서비스를 다시 시작하지 않는다. 최종 문서 HEAD의 개발2/main CI까지 확인하여 최종 보고한다.
- 남은 BLOCKERS: 현재 공식 원본/차수·binary 재확인, 과거 버전 결속 미검증108·실패 단계 불명19, 회사의 적격·인력/MM/원가·이익 증빙 및 legacy 저널 현재 세대 무결성 미검증. 해당 공고의 보류/UNVERIFIED를 유지하며 승인된 최신 공식 원본/로컬 근거로만 재평가한다. 구현 작업 DONE과 실제 참여 가능 확정은 다르다.
- BID-06 선행조건: 승인된 최신 공식 원본·차수/SHA 출처 결속, 전체 페이지/표/각주/OCR에 대한 사람 승인 정답 구절/표본과 독립 대조. 정확도·TP/FP/FN·누락률을 발명하지 않는다. **BID-06 미착수**.
