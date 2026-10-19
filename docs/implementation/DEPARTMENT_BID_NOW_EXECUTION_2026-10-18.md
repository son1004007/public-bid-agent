# 우리 부서가 지금 참여 가능한 공고 선별: 지속 실행 백로그

- 상태: **APPROVED_DIRECTION / IMPLEMENTATION_IN_PROGRESS**
- 기준일: 2026-10-18, Asia/Seoul
- 저장소: `son1004007/public-bid-agent`
- 개발 브랜치: `feat/sprint1-search-demo` (main 병합 금지)
- 사용자 목적(최신 보완): **현재 부서가 실제 참여해 수익을 낼 수 있는 진행 중 입찰을 찾는다. 자체 기술·인력이 일부 부족해도 외주/협력·채용·공동수급 등 합법적·현실적 보완이 가능하고 보완비용 반영 후 이익이 충분하면 우선 검토한다.** 필수 법적 참가자격, 등록기한 등 하드 게이트는 수익성으로 무시할 수 없다.
- 사용자 승인 범위: 단계별 소스/합성 테스트/로컬 읽기 전용 실증/Codex 독립 검수/개발 브랜치 커밋·푸시 및 정기 후속 실행. **실제 적격 판정·입찰 제출/서명/계약/결제·비공개 외부 LLM 전송·main 병합·인터넷 공개는 승인되지 않음.**
- 기존 결정: `DECISIONS.md` D-01~D-19 특히 D-02/03/06/07/08/09/10/13/17/18/19. 기존의 P04~P09 합성 CI 성공과 실제 적격 검증은 구분.
- 현재 실측 스냅샷(변동 가능): 전체 공고 5,691, 활성 부서 검토 후보 220, 추출 텍스트 87, 공식 첨부 확보 대기 130. 일부 품질 경고/절단. `부서 관심 카테고리`는 업무역량/법적 자격 검증이 아님.

## 1. 화면에 보여야 하는 결정적 구분

- `READY_TO_BID_VERIFIED`는 공고별 최신 공식 원본/정정·취소 상태, 참가업종·면허·실적, 해당 기간 가용인력·기술·원가/일정, 필요 서류를 **실제로 확인한 뒤에만** 사용한다. 증거 없는 자동 판정은 금지.
- 지금의 탐지·추천 단계는 `PRIORITY_REVIEW`, `NEEDS_OFFICIAL_DOCUMENT`, `NEEDS_EXTRACTION_REVIEW`, `REGISTRATION_REVIEW`, `HOLD_OR_EXCLUDED` 같은 **작업 큐**다. `BID`와 같지 않다.
- 현재 보유 역량/분야가 맞지 않더라도 법적 자격·공식 일정이 허용되고 기술·인력 보완(외주/채용/협력/공동수급)으로 이익이 남을 가능성이 있는 사업은 **수익성·보완 가능성 검토 큐**로 보존한다. 금액·원가 증빙이 없으면 마진 점수는 `UNVERIFIED`; 공동수급/하도급 허용은 개별 공고 근거가 있어야 한다.
- 실제 순이익 추정 시 예정가격/낙찰 가능 금액에서 내부 인건비·외주/채용·품질/보안·보험/간접비·세금/부가세 처리·예비비·현금흐름 비용을 구분한다. 업종·면허·지역/실적 등 **필수 하드 게이트는 큰 이익으로 우회 불가**. 이익 금액/율 임계치는 근거와 사용자 결정 없이는 임의 지정하지 않는다.
- 모든 공고의 전체 수집/보존은 유지. 화면 기본 필터는 *활성 부서 후보*만 보여주되 취소/마감/구차수 및 제외 공고는 원본 목록/이력에서 지우지 않는다.
- 비공개 부서 스킬/직급/인원/원가/회사 실적의 원본, 키, 토큰, RFP 전문, 직원·기업명·파일 경로를 공개 GitHub/외부 Codex로 내보내지 않는다. 사람의 적격/투입 승인 전에는 `UNVERIFIED`.

## 2. 실행 단계 (한 번에 한 단계만)

| ID | 우선순위 | 작업과 검증 가능한 종료조건 | 선행 의존성 | 상태 |
| --- | --- | --- | --- | --- |
| BID-01 | P0 | 현행 공고의 취소·구차수·마감·등록기한, 부서 분야, 문서 추출 위험을 재사용하여 **읽기 전용 '지금 검토' 안전 분류 함수** 구현; 역량/분야 부족도 `CAPABILITY_GAP_MARGIN_REVIEW`로 보존, 추정 이익·자격은 `UNVERIFIED`; 합성 경계 테스트+Codex GO+GitHub CI | 기존 `procurement_filter`, `rfp_coverage`, `bid_readiness` | DONE |
| BID-02 | P0 | `GET /api/dashboard/bid-now-shortlist` 읽기 전용 로컬 API 노출; 현재 부서 설정과 운영자료를 한 snapshot에서 조회; GET 데이터 비공개 원문/원가 미노출·원본 SHA 불변·Host/CSP 테스트 | BID-01 | DONE |
| BID-03 | P0 | `/decision-preview`에 `지금 검토 가능한 후보` 별도 탭/필터 및 제외/검토 필요 근거 표시; '법적 적격 미검증' 기본 표시; 기존 목록/상세/결정 화면 보존. Chrome 390px + 일반폭 E2E | BID-02 | REVIEWED / Codex GO·전체 local_app 419 PASS·390px/1440px Chrome E2E PASS; 신규 SHA 두 CI 대기 |
| BID-04 | P0 | **실제** 공고를 로컬 읽기 전용으로 돌려 활성 건수/위험·기한별 건수/일관성 집계; 특정 공고 ID·원문·부서정보는 로컬 로그에서만 처리. 현재 부서 설정이 비어 있거나 운영 스킬·MM/원가 근거 없으면 `BLOCKED_EVIDENCE` | BID-02, BID-03 | PENDING |
| BID-05 | P1 | 공식 첨부 확보 대기/부분 추출/잘림/경고 후보를 소요 대비 우선순위로 자동 작업 큐에 연결; 공개 공식 URL·정정/취소·원본 SHA 결속, 기존 배치의 무단 재시도/다운로드 금지; 공식 자료 확보 후에만 재평가 | BID-04 및 공식 원본 접근 가능 | PENDING |
| BID-06 | P1 | 실제 RFP에서 참가자격·평가기준·과업범위의 독립 정답 구절(전체 페이지/표/각주/OCR)을 로컬에서 대조, TP/FP/FN·누락률 추정 가능 여부 기록; 사람이 승인한 표본 없이 정확도 점수 발명 금지 | BID-05 + 승인된 최신 공식 원본·정답 검수 | PENDING |
| BID-07 | P1 | 공고별 실제 부서 역량 비교: 업종·면허/실적/기술 스택/참여 기간별 MM·겸임·예상 사업이익/외주·협력·채용 비용/필수 제안 서류의 **증빙 출처와 검증일** 기반 차단 게이트. 내부 역량 부족은 무조건 제외하지 말고 보완 비용·기술/일정·합법적 외주/공동수급 가능성을 확인해 이익 기회를 유지. 미확인 값은 무조건 `UNVERIFIED`; 민감 원본 로컬만 | BID-06 + 승인된 회사 증빙 및 책임자 검증 | PENDING |
| BID-08 | P2 | 실제 준비 완료를 객관적 검증한 공고만 `READY_TO_BID_VERIFIED`로 표시하고 미충족 사유/기한 정렬, 사람이 최종 Bid/No-Bid 저장하는 UI E2E; 실제 제출 금지 | BID-07 + 사용자 적격 판단 정책 | PENDING |
| BID-09 | P2 | 실제 Windows 로컬 최종 인수, 복원 및 배포·라이선스 NOTICE 게이트. `main`/인터넷 배포/실제 입찰은 **별도 사용자 승인** | BID-08 + 독립 검수/원문/승인 | PENDING |

## 3. 매회 자동 실행 계약

- 별도 신규 자동 작업: **매시간 1회(Asia/Seoul), 정기 실행**. 사용자의 변경 요청에 따라 기존 매일 8시 실행에서 변경됨. 매번 이 문서를 읽고 가능한 단계 한 건만 처리한다. 새 작업 실행과 비활성화된 기존 단순 상태 모니터링은 구별한다. GitHub/Windows/Codex 권한이 없는 실행에서는 BLOCKED 근거를 보고하며 수행했다고 주장하지 않는다. 예전 매시간 상태 모니터링은 비활성화 상태 그대로다.

1. 시작 시 `AGENTS.md` → `DECISIONS.md` → 이 문서 → `CURRENT_STATE.md`/`TASKS.md` → 최근 GitHub CI·실제 Windows 상태를 다시 읽는다. 같은 실행을 다른 프로세스가 진행하면 충돌을 피한다. 지정된 개발 브랜치와 깨끗한 worktree가 아니면 코드 변경하지 않는다.
2. 위 테이블의 선행조건이 충족된 **가장 이른 PENDING/IN_PROGRESS 단계 하나**만 선택한다. 작은 기능 구현 → 관련 Python/JS 합성 테스트 → 전체 관련 회귀 → 문서 검증 → **별도 Codex read-only `VERDICT: GO`** → 작업 상태 수정 → 개발 브랜치 commit/push → 해당 SHA 두 GitHub Actions 성공 확인. 완료 증거 없는 `DONE` 금지.
3. 선행조건(공식 원본/회사 증빙/사용자 승인/CLI 토큰/디바이스 연결/테스트/Code review/Git 권한)이 없거나 Codex NO_GO/CI FAILED면 **억지로 통과시키지 않는다.** 원인, 영향, 필요한 선행 작업, 외부 의존 대상, 마지막 확인 시각, 재시도 조건을 아래 `BLOCKERS`에 기록하고 개발 브랜치에 **문서만 안전하게 커밋/푸시**. Git 접근 불가면 불가 사실을 그 실행에서 보고하며 완료 주장 금지.
4. 실제 회사/공고 정보는 로컬 범위에서만 검증. JSON/SHA/원문/업무용 파일·RFP/인원·기술·원가·인증키를 공개 Git/AI 리뷰나 메시지로 노출하지 않는다. 외부 상용 LLM에 실제 자료 전송 금지.
5. `main` 병합·외부 서비스 공개·운영 서비스 교체/데이터 쓰기·실제 입찰/서명/계약·계정 변경은 사용자 승인 전 자동화 금지. 과거 7일 API 오류 분석 D-10 계속 보류(동일 문제 재발 확인 때만 별도 조치).
6. 실행 후 `EXECUTION_LOG`에 단계, 수행 시각(Asia/Seoul), commit SHA, 로컬 테스트 수와 결과, Codex verdict, GitHub CI run 결과, 현재 미완료 위험과 다음 단계 한 건을 업데이트한다. 같은 실패로 매번 파일/커밋을 쌓지 않고 의미 있는 변화나 새로운 증거가 있을 때만 기록한다.
7. 완료된 단계는 다시 실행하지 않고 최종 단계나 사용자/외부 원본을 기다릴 때는 안전한 read-only 검증만 하되 사용자가 꺼 둔 **별도 상태 모니터링**을 재활성화하지 않는다. 새로운 작업 실행 일정은 별도이며 작업 결과/차단 사항 보고를 목적으로 한다.

## 4. BLOCKERS (최신 선행문제)

| 확인일 | 단계 | 현상/근거 | 영향/필요한 선행 작업 | 재시도 조건 | 상태 |
| --- | --- | --- | --- | --- | --- |
| 2026-10-19 13:14 KST | BID-03 재개 검증 | 분리 CPython 3.12.0 venv·pip check PASS, local_app 419 PASS(213.041초, 건너뜀 0), 감사 14·backend 11·Node 22 PASS. 동일 Chrome 155·기본 sandbox로 390px/1440px 전체 합성 E2E PASS. GitHub API/fetch 정상 | 아래 이전 세 차단은 현재 실행에서 해소됨. 독립 Codex 재검수 GO와 새 commit의 두 CI 성공은 계속 필수 | GO 후 개발 브랜치 commit/push → 동일 SHA 두 CI SUCCESS 확인 | Codex GO / CI PENDING |
| 2026-10-19 08:07 KST | BID-03 화면 인수 | 이전 Chrome sandbox 종료·합성 origin 거부 이력 | 13:14 재개에서 동일 Chrome/runner 기본 sandbox 390px/1440px E2E PASS. 이전 제한의 근본 원인 UNKNOWN | 정상 실행 증거 확보, 보안 완화/기존 origin 우회 없음 | RESOLVED |
| 2026-10-19 08:07 KST | BID-03 Git/CI 네트워크 | 이전 api.github.com:443 OS 소켓 거부 이력 | 13:14 현재 GitHub API/fetch 정상. 새 SHA CI 성공 여부와 네트워크 복구를 구분 | GO 후 push·새 CI 성공 확인은 상단 게이트 유지 | RESOLVED |
| 2026-10-19 | BID-03 전체 회귀 | 이전 의존성 누락 2 ERROR·HWP/XLS 2 SKIPPED·중단 이력 | 13:14 분리 venv의 전체 local_app 419 PASS, 건너뜀 0, 213.041초. 기존 NO_GO를 자동 GO로 바꾸지 않고 별도 재검수 | 전체 회귀 증거 확보, 독립 재검수는 상단 게이트 유지 | RESOLVED |
| 2026-10-19 08:07 KST | BID-03 정책 확인 | 사용자 제공 GitHub main 검증 로컬 사본 CONTROL 1개/handbook 8개 전체 읽기 완료 | 기존 정책 접근 선행조건 해결. 현재 브라우저/네트워크 차단과 구분 | 재확인 불필요 | RESOLVED |
| 2026-10-18 | BID-06 | 원본 전체 페이지·표·OCR의 독립 정답/TP/FP/FN 없음 | 실제 누락률 계산 불가. 공식 최신 원본 및 사람이 표본 라벨 승인 필요 | BID-05 완료 + 로컬 독립 대조 가능 | OPEN |
| 2026-10-18 | BID-07 | 실제 회사 업종·면허/실적/투입 가능한 인력·MM/원가 근거 검증 미완료 | 회사의 참가 적격·수익성 확정 불가. 승인된 로컬 증빙 필요 | BID-06 및 부서 책임자 증빙 검증 | OPEN |
| 2026-10-18 | BID-09 | 사람의 화면 인수·`main`/공개 릴리스 미승인 | 이 단계는 자동화가 승인 대체 불가 | 사용자 별도 명시적 승인 | OPEN |

## 5. EXECUTION_LOG (append semantic checkpoints)

- 2026-10-19 / BID-03 **독립 최종 VERDICT: GO / CI PENDING**: 별도 fresh-context 읽기 전용 Codex `/root/bid03_final_readonly`가 고정 변경본·정책·회귀 로그·스크린샷·실패/경쟁 경로·CI를 검토, Node 22개 독립 PASS 및 소스 SHA 시작/종료 일치 확인. 미해결 BLOCKER/MAJOR 없음. GO 후 개발 브랜치 커밋/푸시 진행, 동일 신규 SHA 두 CI SUCCESS 전 DONE 금지. [검수 provenance](../reviews/BID03_SHORTLIST_UI_2026-10-19.md).

- 2026-10-19 13:14 KST / BID-03 **VERIFIED / 독립 재검수 대기**: 이전 미커밋 15개 파일을 저장소 외부에 보존, 전역 정책 9개 GitHub 원본 재확인. 공유 Python의 기존 패키지 충돌을 운영 환경 수정 없이 별도 venv로 분리. local_app 419 PASS·감사 14 PASS·backend 11 PASS(합계 444), Node 22 PASS, npm audit 0/build·정적·문법·공백 PASS. Chrome 155 동일 runner·보안 설정 그대로 390px/1440px 후보 세 큐·보류·UNVERIFIED·기존 상세·파일 선택·수기 이력 E2E PASS 및 스크린샷 육안 확인. 이전 시작 실패/전체 실행 정체는 이번 환경에서 재현되지 않았으며 과거 근본 원인은 확정하지 않음. 소스 7개 결속 SHA는 이전과 동일 `de0efff59553e691805bf3d096f8f19cfb07c3cb271d71b41cc26b5643dc0e92`, 현재 새 코드 수정 필요 오류 없음. 최종 Codex GO/두 CI 전 DONE 금지. 운영·main·실제 제출·BID-04 착수 없음.

- 2026-10-19 / BID-03 **최종 Codex NO_GO / 미커밋 인계**: 관련 Python 47 PASS(18.587초), Node UI 11 PASS·기존 Node 3 PASS. 전체 회귀의 기존 두 의존성 import 오류를 별도 재현했으며 전체 실행은 출력 정체 후 종료, 전체 PASS 아님. 독립 검수는 필수 Chrome 인수 미완료와 전체 회귀 미해소로 NO_GO, 소스 수준 추가 중대 결함 없음; 문서 인코딩/상태표 지적은 수정 후 독립 재확인 RESOLVED. 부모·독립 검수자가 모두 읽은 로컬 정책 9개와 지시서 제거. 브라우저 자동 승인 거부·네트워크 권한 우회 없음. GO 조건 미충족으로 커밋·푸시/신규 CI 실행 없음, BID-04 미착수. [상세 증거/재개 조건](../reviews/BID03_SHORTLIST_UI_2026-10-19.md).

- 2026-10-19 08:07 KST / BID-03 **IMPLEMENTED_UNVERIFIED / 브라우저 인수 BLOCKED**: 제공된 정책 9개 전체 확인, 읽기 전용 후보 화면·세 큐·보류·UNVERIFIED·기존 상세 연결 구현. Node UI 11 PASS, shortlist API 6 PASS(합성 세 큐 1/1/1·공식 상태 보류 2·마감 보류 1·임시 원본 불변), 기존 Node 3 PASS·문법/정적·공백 검사 PASS. 전체 Python 회귀 및 최종 Codex 검수 결과 대기. Chrome/GitHub 차단은 위 BLOCKERS 참조. 운영 자료 접근·변경·main/배포·커밋·푸시 없음. BID-04는 미착수. [검증 기록](../reviews/BID03_SHORTLIST_UI_2026-10-19.md). 아래 07:55 기록은 재개 전 이력이다.

- 2026-10-19 07:55 KST / BID-03 **BLOCKED / 구현 미착수**: 지정 브랜치 `feat/sprint1-search-demo`, 시작 HEAD `0df2f58b7157403c5808979830501d878a7af31f`. 시작 시 추적 파일 변경 없음, 유일한 미추적 파일 `BID03_CODEX_TASK_LOCAL.txt`는 사용자 지시대로 제거한 후 `git status --short` 빈 출력 확인. AGENTS/D-20/최신 상태·백로그 확인, 필수 전역 원본 읽기는 위 BLOCKERS 사유로 실패. 이번 변경은 차단 상태 문서뿐이며 API/UI/운영·main 변경 없음. 테스트·Chrome 합성 E2E·독립 Codex 검수·커밋/푸시·CI는 **NOT RUN**. GO가 없으므로 사용자 지시에 따라 커밋/푸시하지 않음. 기존 BID-02의 418 PASS/GO/CI는 이번 BID-03 증거로 재사용하지 않음. 다음 단계는 원본 규칙 접근 복구 후 BID-03 한 건이며 BID-04 및 D-10 조사 착수 없음.

- 2026-10-18 / BID-02 **DONE**: [구현 커밋 9f3ab29](https://github.com/son1004007/public-bid-agent/commit/9f3ab295413725f810fefcc13f7212b340bbd0dc). 전체 Python **418 PASS**, 관련 **21 PASS**, Codex 독립 재검수 **VERDICT: GO**, 추가 28 in-memory PASS. [Sprint 1 CI 39130071318](https://github.com/son1004007/public-bid-agent/actions/runs/39130071318) SUCCESS, [Windows synthetic 39130071253](https://github.com/son1004007/public-bid-agent/actions/runs/39130071253) SUCCESS. 로컬 저장된 실공고 5,691건 읽기 전용 상태 집계: 분야 일치 검토 178, 역량 보완/수익 검토 2,158, 등록 사전 검토 393. 이는 실제 적격/이익 확인이 아닌 **작업 큐**이며 원본 부서/원가·본문은 미반환. **다음 BID-03: 로컬 화면에 세 큐와 미확인 위험/이익 라벨을 표시, 모바일·데스크톱 E2E.**

- 2026-10-18 / BID-02 수정본 **전체 Python 418 PASS**, Codex 독립 재검수 **VERDICT: GO**, 메모리 기반 추가 28 검증 PASS, 문서 동기화 및 `git diff --check` PASS. 비정상 공고 ID/날짜의 보류 처리 확인, 실제 보호 스냅샷 5,691건 읽기 전용 분류. **GitHub CI 성공 전에는 DONE으로 올리지 않음.**

- 2026-10-18 / BID-02 첫 독립 Codex **NO_GO**: 검수 실행과 소스 수정이 겹친 구간에서 ID regex 캡처 그룹 누락을 검출. 캡처/공식 공고번호·차수 일치 검사로 수정하고, 비정상·위조 ID와 극단적 날짜에 대한 추가 회귀를 반영. 수정본 관련 **21 PASS**, 전체 재검수·CI는 이어서 수행. 부정확하거나 신뢰할 수 없는 원본은 삭제하지 않고 표시 대상에서 보류.
- 2026-10-18 / BID-02 로컬 구현+합성 대상 **19 PASS**. 새 `/api/dashboard/bid-now-shortlist`를 공고·부서 설정·운영정보 단일 잠금 조회로 구성하고, 직원·원가·원문 미노출 및 Host/CSP/원본 JSON 불변 확인. 실제 Windows 보호 원본 **5,691개** 읽기 전용 교차검사: 부서 일치 현재 검토 178, 외부역량 보완/이익 검토 2,158, 등록 사전 검토 393, 나머지 마감/취소/구차수/미확인 사유로 분리. **2,158건을 수익성이 입증된 공고로 주장하지 않음.** 아직 예상 이익/공고별 필수 자격은 미검증. 독립 Codex/전체 회귀/CI 후 DONE 판단.

- 2026-10-18 / 사용자 추가 결정: 자체 기술·인력 부족이어도 보완 후 이익이 크면 검토·참여 대상. 법정 입찰 자격은 수익으로 우회 불가. 이에 따라 BID-01과 BID-07에 보완 가능성과 이익 근거 분리 반영.
- 2026-10-18 / BID-01 **DONE** ([구현 커밋 c759c53](https://github.com/son1004007/public-bid-agent/commit/c759c53a16cb8d187433a03d703fe7ee25ce420e)): 전체 412 PASS, Codex GO 및 추가 54 PASS. [Sprint 1 CI 39128145994](https://github.com/son1004007/public-bid-agent/actions/runs/39128145994) SUCCESS, [Windows 합성 인수 39128145903](https://github.com/son1004007/public-bid-agent/actions/runs/39128145903) SUCCESS. **다음 BID-02: 로컬 조회 API와 부서/운영자료를 동일 스냅샷에서 결합**, 실질 법정 적격과 마진은 계속 UNVERIFIED.
- 2026-10-18 / BID-01 IMPLEMENTED + REVIEWED: `local_app/bid_now_triage.py`와 9개 합성 테스트, Windows CI 연결. 최초 Codex NO_GO 2건(라이프사이클 누락·유효하지 않은 사전 등록기한이 검토단계를 통과) 수정. 관련 모듈 **23 PASS**, 전체 Python **412 PASS**, Codex 재검수 **VERDICT: GO** 및 추가 불변/경계 **54 PASS**, `git diff --check` PASS. GitHub CI는 커밋 후 확인해야 하므로 `DONE` 승격 대기.
- 2026-10-18 / 계획 수립: 실제 현재 부서에 적합한 입찰만 다루도록 목표 재정의. BID-01 최초 구현 선정. 소스·테스트·Codex·GitHub 결과는 이후 기록.
