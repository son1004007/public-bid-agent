# BID-06 독립 정답 검수 도구 검증

## 범위와 현재 상태

기준 b20f515, feat/sprint1-search-demo. 시작 추적 변경 없음, 기존 사용자 승인 메모 미추적 보존. 실행 중 프로세스를 종료/변경하지 않았고 동일 저장소 다른 작업 세션 task_complete, 기존 하위 검수 세션 completed 확인. 최신 사용자 순서에 따라 구현 후 독립 Codex 최종 검수만 수행(사전 독립 설계 검수 NOT RUN). 전역 정책9개 원격 main 읽기, BID05 설계/검증과 관련 추출/라벨/보안/저장 구조 확인. BID07 미착수.

현재 IMPLEMENTED / 전체 회귀·Chrome·독립 검수·CI·운영 게이트 대기. IMPLEMENTATION_DONE/VALIDATION_DONE 또는 전체 DONE 아님.

## 구현 및 판정 기준

[설계](../design/BID06_GROUND_TRUTH_2026-10-19.md). 기존 표시 후보는 서버 snapshot에서 읽으며 독립 정답으로 복사/승격하지 않는다. 선택한 원본 bytes SHA만 메모리 대조하고 원본 저장/다운로드/외부 전송 없음. 공식 차수·identity·캐시·서명 티켓과 사람 최신성/원본 페이지·표·각주·이미지/OCR 확인 전 승인 불가. 별도 로컬 이벤트에 gold 구절·페이지/위치·분류·추출 snapshot·승인/수정/보류·시각 보존. Host/Origin/CSRF/release guard·프로세스 간 transaction/원자 replace·revision 충돌·멱등키 보호.

지표는 승인 현재 표본에만 동일 분류+NFC/공백 정규화 동일 구절의 1:1 매칭. 부분 일치/분류 오류는 FP+FN, 중복 예측 추가는 FP, 동일 위치 중복 정답 거부. 겹치는 승인 범위 거부. 경로는 사람이 확인한 TEXT/TABLE/FOOTNOTE/IMAGE/OCR. 후보 상한/생략·경고/잘림 표시, 전체 문서 정확도/대표성 미확인. 승인 정답0 또는 분모0은 null. 사람의 최신성 확인은 시점별 진술이며 공식 사이트 자동 인증이 아니다.

## 실제 로컬 읽기 전용

전체5718 / 보관 문서 공고70 / 차수 결속 문서0 / 차수 미검증 문서127 / 표시 후보757. 독립 승인 정답0, 검수 이벤트0, 실자료 정확도 NOT_EVALUATED. 보호393파일 전후 SHA 모두 동일(일시 lock 제외). 원문·개별 ID/URL·회사 정보·개별 SHA·파일명/경로는 공개 로그/Git/독립 검수에 제공하지 않았다. 안전 집계/비공개 baseline만 TEMP 보관. BID05 과거108건과 새 문서 선택/캐시 결속 범위가 달라 동일 지표로 재사용하지 않는다.

## 실행 증거

- 변경 영역 Python21 PASS, Node6 PASS.
- 관련 포함 Python63 PASS / 실패0 / 오류0 / 12.957초. Temp bid06-related-20261019.log.
- Node6: 명시 저장만 POST·승인 전 확인·HOLD·알 수 없는 응답 재전송 멱등키·최신 조회 우선·오류 비반사·대표성 제한.
- 새 의존성/자동 다운로드/파서·배치 재실행·실제 입찰 없음.

## BLOCKERS / 재개 조건

- 실자료 VALIDATION_DONE: 공식 최신 원본/차수·SHA와 사람 독립 정답0. 책임자가 승인된 최신 원본을 로컬에서 대조하고 선택 페이지/표/각주/이미지/OCR 정답·위치를 직접 승인한 후 범위 한정 실측과 결과 독립 검증 필요. 구현 자체 검증과 구분한다.
- 회사 자격·원가·인력/MM·수익 UNVERIFIED/BLOCKED_EVIDENCE 유지. BID07은 별도 승인·증빙 선행, 자동 시작하지 않는다.

## 최종 검증 진행 기록

- 최초 전체 local_app478 PASS/226.344초, 감사14/backend11 PASS(합계503), Node42 PASS(기존36+신규6), build/정적·구문/diff PASS.
- 저장 최대 크기의 공백/들여쓰기를 실제 persist(indent=2)와 일치시켜 한도 근처에서도 새 파일이 다시 읽힐 수 있게 보호했다. 조회 중 dashboard 변화는 고정503으로 거부한다. 신규 경계 테스트 추가 후 표적22 PASS. 해당 서버 변경으로 local_app 전체를 마지막 한 번 재실행 중이며 감사/backend/Node는 변경 없어 성공 근거 재사용한다.
- Chrome155/Node22.14 기본 sandbox, 지정 CPython3.12 venv/합성 전용 프로필: 최종390/1440 전체 E2E PASS. 새 원본 파일 SHA 대조·사람 독립 정답3개·TP2/FP0/FN1·수정/HOLD·0개 재평가·이력 재조회·범위 제한·가로 넘침 없음. 기존BID03/04/05·원본 누락/불일치/정상·담당자 이력 저장/재조회·결정 보존·XSS·외부 요청 없음까지 PASS. Temp bid06-chrome-final-20261019.log 및 합성 PNG 두 폭 직접 확인.
- Chrome 실패 이력: 최초 기존 이력 새로고침 구간의 합성 stderr(원인 UNKNOWN), 진단 추가 후 CDP Invalid InterceptionId 확인. Network.loadingFailed의 같은 요청 취소가 확인된 localhost continue 오류만 제한 처리하며 다른 protocol 오류·외부 요청은 계속 실패한다. 요청 완료를 대기하고 새 BID06 모바일 흐름 뒤 기존 이력 시험의 원래 데스크톱 전제를 복원했다. 중간 모바일 상태의 persisted-history 대기 실패2회 후 원래 폭 복원한 최종 전체 PASS. 당시 저장 유실/정확 원인으로 단정하지 않는다. 같은 오류 무의미 반복/보안 완화 없음. [CDP Fetch/Network 공식 진입점](https://chromedevtools.github.io/devtools-protocol/).
- 배포 실행안은 기존 immutable SHA·두 개발CI/main CI·알려진 PID·이전 소스·전체파일 검증 백업/복귀 절차를 재사용하고 새 읽기 전용 API/두폭 검수 목록·보류 화면 인수만 추가했다. 아직 실행하지 않았으며 독립 검수에 포함한다.
- 고정 소스11개 bundle 15ed20d64983123baa8f470f3c8fbb0d061db5d8b3e658fa9567419825ce1d9e. Ops Python 6669d28eb429673b85a184d343da10328ec46bd35ba3a3a3586f9e6441e251a1, Node 0272b877e5f84b7b8c7450cbd7496b4254731ffc05cbf7b2ea0cc1f19720f96b.

- 최종 수정본 local_app479 PASS /217.288초, 실패·오류·건너뜀0. 감사14/backend11 포함 Python504 PASS, Node42 PASS, 전체 Chrome390/1440/build/정적 PASS. 최종 full 원시 로그 bid06-python-local-final-20261019.log. 현재 독립 최종 검수 대기이며 Git/main/운영 변경 없음.

## 독립 검수 최초 NO_GO 및 지적 수정

별도 fresh-context 읽기 전용 Codex /root/bid06_final_readonly: **NO_GO / MAJOR1**. 도구 소스 추가 BLOCKER/MAJOR 없음, 독립Node6 PASS 및 전체 로그/PNG 확인. 고정11파일 bundle 시작/종료 동일, 운영 원본/승인 메모 미접근·서버/배포/Git 쓰기 없음. 원 요구/제약·고정 manifest·정책·설계·원시 로그/PNG·두 ops 실행안만 제공했으며 결론 주입 없음.

MAJOR 수용: 재사용 배포 smoke가 이전 소스 listener를 정상 성공으로 허용해 신규 SHA 기록 가능. 검수자가 AST 순수 메모리 모형으로 재현했다. 정상 인수는 명시 NEW_RELEASE start와 정확 신규 소스/launch instance·listener 계보 일치만 허용하도록 수정. 이전 소스는 명시 ROLLBACK start 후 인수만 허용. Windows venv redirector의 launch PID와 실제 직계 자식 listener PID가 다를 수 있으므로 양쪽 command line/ProcessId/ParentProcessId/CreationDate를 검증하고 저장 성공 전후 instance를 재대조한다. launcher metadata 조회 실패는 기존 rollback 경계 안의 smoke 실패로 처리한다.

실제 운영에서 기존 기록 launch PID와 listener가 직계 부모/자식인 것만 읽기 전용 확인했고 개인 경로나 실제 내용을 출력하지 않았다. 순수 모형7개 PASS: 신규 direct/child 성공, 이전 소스 재등장 거부, 무관 PID 거부, 명시 rollback 허용, start 없음/launch 재사용·생성순서 오류 거부. 실제 프로세스/백업/Git/Chrome 변경 없이 AST 코드만 실행. Temp bid06-deploy-model-test-20261019.py. 수정 Ops SHA 42e1e72e4844c6b7c1fa662196ac25962aa75333a791d0797094ca7db525338f, Chrome ops SHA는 기존과 동일. 앱11파일은 미변경이므로 성공 회귀는 재실행하지 않으며 같은 검수자에게 지적된 ops만 후속 확인한다. 최종 GO 전 commit/push/main/배포 금지.

## 최종 독립 검수 GO / Git·운영 게이트 대기

같은 fresh-context read-only Codex의 지적 범위 재확인 **GO**, 기존 MAJOR RESOLVED, 미해결 BLOCKER/MAJOR 없음. AST모형7 PASS 및 독립 추가 경계4 PASS. 앱11파일·Chrome ops 불변, 수정 ops SHA42e1e72e4844c6b7c1fa662196ac25962aa75333a791d0797094ca7db525338f 일치. 이 GO는 구현 검수이며 실자료 VALIDATION_DONE이나 실제 배포 성공이 아니다. 사용자 승인 범위에서 개발2CI→main 조상/충돌 확인·CI→검증 백업/복구→기존localhost 운영 API/두폭 화면·전체파일 무결성 인수를 수행한다.
