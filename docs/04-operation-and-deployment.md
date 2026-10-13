# 04 운영 및 배포 설계

## 현재 상태

**로컬 배포와 인터넷 공개 서비스를 분리합니다.** 2026-10-13 개인 Windows PC의 `127.0.0.1:8765/decision-preview`에서 공고 2,223건과 관련 로컬 API 조회에 성공했습니다. 2026-10-12 RFP 70개 공고/127개 문서 **지정 범위**의 로컬 운영 이관 저널 `COMPLETED`, 비공개 본문 저장 파일 124개·백업 1개도 확인했습니다. 전체 RFP 작업 원장은 `PAUSED / DONE 109 / PENDING 34`이며 별도로 남아 있습니다. 127개 문서 근거와 124개 파일은 동일 집계 단위가 아니며 세부 대응 관계는 후속 검증 대상입니다. 이는 **로컬 이관 완료 확인**이며 전체 브라우저 사용자 검수/복구 품질 보증/앱 전체 Codex 보안 최종 검수/인터넷 공개 배포의 완료가 아닙니다. 아래 HTTPS·React·FastAPI·PostgreSQL·Google 로그인은 미구현 공개 인터넷 서비스의 **목표 운영 설계**입니다. 인터넷 호스팅은 미정이며 현재 출시 대상이 아닙니다.

## 향후 인터넷 공개 서비스 구성과 환경 (미구현)

- HTTPS edge/reverse proxy → React 정적 웹 → FastAPI BFF/API → 비공개 PostgreSQL. 하나의 backend로 시작한다.
- Google OAuth/OIDC client ID·client secret, 공공데이터 service key, 세션 비밀, DB 자격증명, 승인된 모델 provider 인증정보는 서버 전용 보안 저장소를 사용하며 Git에 기록하지 않는다.
- `.env.example`에는 변수 이름과 안전한 예시만 작성한다.
- 같은 origin/redirect URI/Google 콘솔 설정과 `__Host-` 세션 쿠키·CSRF 정책을 실제 배포 주소에서 시험한다.
- 실제 사용 가능한 모델 제공자 없는 경우 API 전환 없이 `disabled` 모드와 안내 문구를 제공한다. 앱 전체를 무단 Codex 계정에 결합하지 않는다.

## 보호 장치

1. 요청, 계정 및 `AnalysisRun`별 실행·도구·모델 요청 횟수, 처리 시간, 문서 바이트 예산은 [ADR-007](adr/ADR-007-analysis-state-evaluation.md)에 따른다.
2. 공공 API 및 공식 문서 다운로드에는 서버 측 allowlist/timeout/크기/MIME/redirect/DNS·IP 제한과 격리 파서를 적용한다([ADR-006](adr/ADR-006-document-ingestion-security.md)).
3. 로그인 성공만으로 데이터 접근을 허용하지 않고 Profile·AnalysisRun·Question·EvidenceSet·SSE 구독·취소에 대해 객체 소유권을 검증한다([ADR-001](adr/ADR-001-auth-session-ownership.md)).
4. 원문/요건/모델 출력의 출처 상태를 구분하고 공고 수정이나 취소 시 분석을 stale로 표시한다([ADR-002](adr/ADR-002-procurement-data-lifecycle.md)).
5. AI 모델과 외부 parser에는 사용자 권한 결정이나 비밀 설정 변경을 허용하지 않는다.

## 개인정보·로그·권리

- 인증 토큰, 세션/CSRF 키, API 키, 민감정보, 프로필 본문 또는 전체 프롬프트는 로그에 저장하지 않는다.
- `correlation_id`, `run_id`, 요청/외부 API 지연과 안전한 오류 범주만 기록한다. fetch URL의 서명 query/path와 임시 token은 로그·DB·화면 링크에 기록하지 않으며 공개 canonical URL을 별도 생성한다.
- 사용자 프로필 최소수집, 공식 PDF의 제3자 정보, 30일 분석 결과 보존과 백업 순환, 별도 삭제 저널 및 재가입 시 새 내부 사용자 ID 계약은 [ADR-008](adr/ADR-008-profile-privacy.md)에 기록한다. 실제 운영 전 고지·삭제·복원 테스트와 일치시킨다.
- 제3자 공고/RFP는 저작권·재배포·임베딩 조건을 독립적으로 확인하며 공개 GitHub에 파일 원본을 임의 업로드하지 않는다.

## 복구·운영 품질

- 데이터 분류: 사용자 프로필과 계정 연결/분석 기록은 `authoritative`, 검색 인덱스와 복원 가능한 파생 자료는 `rebuildable`, 공공 API 원천 자료는 `external`이다.
- 초기 복구 목표는 **RPO 24시간 / RTO 24시간**으로 설정하지만 실제 측정 전 보장하지 않는다.
- migration 전 백업, backward-compatible 배포, 오류 시 롤백/forward recovery, 계정 삭제 후 별도 보호된 삭제 저널의 복원 시 재적용을 시험한다. 공개 장기 분석은 FastAPI 요청과 분리된 PostgreSQL lease/heartbeat/CAS worker 경계로 관리하며 중복 실행·취소 경쟁을 검증한다.
- request ID, analysis run ID, 외부 API 오류, parser 오류, 비용/토큰 범주를 진단하며 개인정보/secret 로그 저장은 금지한다.
- 제공자별 인증 승인, 비용 한도, 사용자 동의/철회, rate limit을 실제 운영에서 확인한다. 비로그인 공개 검색은 별도 IP·전역 동시성·캐시·reverse proxy 신뢰 정책으로 남용을 막는다.

## 개발과 배포의 별도 승인

- **개발 단계:** 로컬/합성 fixture·비공개 데모와 공개 GitHub 소스코드 수정은 단계적으로 진행한다. 커밋했다고 사용자 서비스에 배포했다고 주장하지 않는다.
- **활성 기능의 출시:** API/인증/AI/개인정보 등 실제 켜진 기능에 해당하는 체크리스트와 독립 검수를 충족해야 한다. 미구현 기능은 OFF로 고정하고 사용자에게 제공 중이라고 표현하지 않는다.
- **공개 AI 추론:** 별도 공식 모델 사용 자격 및 예산·보안 검증이 끝나기 전에는 비활성 상태를 유지한다.
- **전체 서비스 출시:** 아래 체크리스트의 모든 관련 항목과 사용자 승인을 통과해야 한다.

## 공개 서비스 출시 게이트

- [ ] 법률·서비스 약관 및 공식 API 이용/원문 보존·재배포 조건 확인
- [ ] Google OIDC state/nonce/PKCE·ID Token·HTTPS·쿠키·CSRF/CORS E2E
- [ ] 다중 사용자 권한·SSE/취소·재연결 안전성 테스트
- [ ] 실제 공공 API 스키마/정정·취소·마감 시각 계약 테스트
- [ ] 공식 PDF 수집 SSRF/파서 격리/과대 파일 제한 테스트
- [ ] 원문 근거 추적·불확실 상태·평가 결과 검증
- [ ] 데이터 보존·삭제·백업/복원, 기밀/로그 노출 검증
- [ ] 배포 HTTPS edge/DB 접근·모니터링/비용 한도 확인
- [ ] 실제 공개 원격 LLM 사용 허용 여부 확인(미허용이면 AI 기능 비활성 고지)
- [ ] 테스트 기록/최종 독립 코드 리뷰/사용자 승인

## 비용 경계

호스팅과 모델 사용량의 정액/종량 비용을 구분해 기록한다. 별도 종량제 API 비용이 MVP 필수조건이 아니라는 사용자 요구를 운영 전체가 완전 무료라는 뜻으로 해석하지 않는다.

상세 배포 원칙과 미확정 운영 목표는 [ADR-005](adr/ADR-005-hosting-operations.md)를 따른다.

## Codex R3 배포 선행조건

- 최신 공고 유일성·완전 동기화·마감 UTC 충돌을 fail-closed로 처리하는지 검증한다.
- 스캔·표·부분 PDF 추출 시 원문 요건 포괄성 실패를 명시한다.
- 열린 SSE 연결의 세션 철회 후 이벤트 전송 차단을 시험한다.
- React 기본 텍스트 렌더링, 공식 HTTPS 원문 링크 allowlist 및 CSP·XSS 브라우저 테스트를 통과한다.
- 후속 질문·답변의 비민감 enum 입력 제한과 개인정보/기업기밀 비수집을 검증한다.
- 실제 공개 모델 이용 시 영속적인 입력·출력 토큰/재시도 예약 장부와 사용자별·전역 한도가 설정되어 있어야 한다.
- 외부 모델 계정 연결·해제/계정 삭제/전체 export는 최근 인증과 1회용 승인 확인을 통과한다.

## Codex R4 공개 배포 게이트

- [ ] 공식 공고별 `SyncCoverage`와 authoritative detail refresh 검증
- [ ] 자기신고 항목과 행정적 요건 공식 검증 분리 및 오인 방지 UI 확인
- [ ] 다중 사용자·provider·서비스 전체 원자적 예산 예약 E2E
- [ ] 프로필/분석/근거/export/SSE의 CDN 공유 캐시·buffering 격리 E2E
- [ ] 계정 삭제 직전 외부 provider 요청 취소 및 늦은 응답 차단·보존 고지 검증
- [ ] 실제 선택한 Google OIDC 최소 scope·동의 화면 확인

## Windows 로컬 8765 검증 RFP 배포 및 복구 (2026-10-12)

이 절차의 배포 범위는 사용자 개인 PC에서 127.0.0.1로 바인딩한 로컬 서비스이며, 외부 인터넷의 공개 호스팅이 아니다. Codex만 독립 최종 검수를 수행하는 사용자 최신 지시를 따른다.

1. 개발 브랜치 코드/테스트와 GitHub CI를 확인한다. 실제 운영 자료는 사용자 PC 내 격리 사본으로만 시험하고 공개 저장소에 기록하지 않는다.
2. 실제 사용자 원본과 분리한 디렉터리에서 70개 공고/127개 문서/124개 캐시 및 추천·RFP 진단·배치 현황/브라우저 동작을 검증한다. 예외 후 복원과 중단 저널 복구를 재현한다.
3. Codex 독립 검수 GO를 확보한 다음 운영 8765 서버를 종료하고, 다른 쓰기 작업이 없는지 확인한다. 운영 JSON의 SHA와 권한 및 신규 백업 위치를 확인한다.
4. scripts/promote_verified_rfp_stage.py의 --live, --stage로 먼저 dry-run한다. --apply --backup으로 백업 후 70개 공고의 문서 근거·자동 분류만 갱신한다. 업체 정보·인력·비용·담당자 결정은 보존한다.
5. 두 JSON이 서로 다른 상태에서 중단되면 PREPARED 저널로 서버 기동이 차단된다. --recover --backup은 양쪽 새 JSON 해시가 일치하면 COMMIT, 아니면 검증된 두 백업으로 복원한다. 수동 --rollback도 PREPARED 기록 후 복원한다.
6. 로컬 server.py --no-browser를 운영 환경의 동일 데이터 위치, PUBLIC_BID_LOCAL_PORT=8765로 다시 시작한다. 모든 관련 읽기 전용 API, 실제 Chrome 목록/상세 이동, 공고 수·담당자 결정·원본 해시를 검증한다.
7. 문제가 있으면 서버를 중지한 뒤 새 사용자 수정이 없는 상태에서 --rollback하고 백업 SHA 복구를 확인한다. 데이터가 변경된 상태라면 자동 롤백을 거부하며 수동 병합이 필요하다.

개인 원본, 발주 문서 전체, 공고 URL/인증키/인력·원가 자료는 공개 커밋 또는 Codex 검수 프롬프트에 입력하지 않는다. 외부 배포 출시 게이트는 여전히 별도이며 실제 입찰 적격성을 보장하지 않는다.


## 2026-10-13 로컬 RFP 배포 안전성 보강 (개발 브랜치)

Codex NO_GO 지적의 4개 범위에 대해 서버 수명 독점 잠금, SQLite 동기식 PREPARED/COMPLETED 복구 의도, Windows 파일교체 MoveFileExW WRITE_THROUGH 및 POSIX 디렉터리 fsync, Windows CreateFileW 디렉터리/상위경로 핸들(GENERIC_READ, FILE_SHARE_DELETE 비허용, OPEN_REPARSE_POINT)을 유지해 경로 이름 변경을 차단하고 reparse 검사·파일 동일성도 재확인, 중단된 부분 백업의 원본 SHA 확인 후 재개 절차를 추가했습니다. 복구 의도 SQLite는 `PRAGMA synchronous=FULL`과 DELETE 저널을 사용합니다. 원래 `.rfp-release-transaction.json`도 유지합니다. SQLite가 PREPARED인 동안 서버 시작과 요청을 차단합니다. 로컬 서버가 실행 중이면 오프라인 배포/롤백/복구 도구는 별도 OS 프로세스 잠금 충돌로 거부됩니다.

배포 작업은 로컬 Windows 사용자 데이터와 별도 백업 경로가 있어야 하며 서버 종료 뒤 실행합니다. 부분 백업 재개는 `.backup-intent.json`의 기존 운영 JSON 해시가 동일하고 알 수 없는 파일이 없는 경우만 허용합니다. `recover`는 텍스트 저널이 사라졌어도 SQLite PREPARED 의도로부터 두 파일을 검증된 세대로 복구합니다. 버전이 다른 JSON은 제공하지 않고 서버가 실패하도록 설정했습니다.

**제한:** Windows 파일시스템·장치의 물리적 전원 장애를 여기서 직접 시험하거나 완전한 영속성을 보장하지는 않습니다. Microsoft MoveFileExW의 WRITE_THROUGH는 파일 이동을 플러시하지만, 모든 같은 볼륨 메타데이터 영속성의 증명은 아닙니다. SQLite FULL의 내구성도 OS/디스크의 fsync/FlushFileBuffers 계약에 의존합니다. 실제 종료 및 완전한 검수 전까지 공개 운영 배포와 main 통합은 별도 승인 대상입니다.

실행: `python -m unittest discover -s local_app -p 'test_*.py'` 및 독립 Codex 읽기 전용 재검수. 실제 사용 데이터의 손상·이력 보존은 테스트 폴더와 별도 원본 해시 점검으로 확인합니다.


## 2026-10-13 Windows 로컬 공식 공고 예약 갱신 (개발 기능)

- `local_app/scheduled_collection.py`: 사용자 DPAPI 조달청 인증키를 이용하여 공식 전체 용역 공고를 **7개 연속 24시간 구간**으로 조회. 오래된 순서에서 최신 순서로 동일 공고 식별자를 병합하고, 기존 담당자 판단·판단이력·저장 RFP 추출 본문은 변경하지 않음. 제목 키워드로 원천 공고를 제외하지 않음.
- `--data-dir "<사용자 비공개 데이터 폴더>" --days 7`은 원천 API 조회만 하는 **dry-run**이며, `--apply`를 붙일 때만 로컬 `dashboard.json`을 공통 다중 프로세스 잠금 후 병합 저장. `collection.mode=SCHEDULED_INCREMENTAL`, `lookback_days`, `window_end`를 기록함.
- 공식 API 한 일자라도 실패하거나 페이지 총건수 불일치 시 전체 적용을 중단. 조회 과정의 실패는 `collection.status=ERROR`로 기록할 수 있지만 기존 공고·사람 판단은 보존. 외부 API 키·원본/비밀 데이터는 로그에 출력하지 않음. **일시적인 공식 API 연결 실패는 동일 구간을 한 번 재시도하며, 상세 RFP 원문 자동 갱신은 아직 미구현**.
- Windows Task Scheduler: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install_local_collection_schedule.ps1 -Action Install`을 실행하면 **매일 오전 09:00 (PC 로컬 시각)**, 로그인된 현재 Windows 사용자로 7일 중첩 갱신을 수행하도록 등록. 기본 설정은 노트북 배터리 허용, 일정이 누락되면 가능할 때 실행, 중복 인스턴스 방지, 최대 60분. PC 로그인 세션이 없는 경우에는 실행되지 않음.
- 작업 확인/해제: 같은 스크립트에 `-Action Status` 또는 `-Action Remove` 지정. 키는 해당 사용자 Windows DPAPI 보관소에 있으며 스케줄러 인수/파일에 포함되지 않음. 실제 정정/취소의 자동 판별과 RFP 근거 무효화·AI 추천은 후속 구현 및 검증 대상.
- 로컬 웹서버는 기존 `127.0.0.1:8765` 실행 상태와 공통 JSON 잠금을 공유하며 서버를 강제로 종료하지 않음. 배포 `PREPARED` 저널 상태일 때 갱신 요청을 거부함.


## 2026-10-13 공식 정정·취소 공고 반영
- 조달청 공식 목록 API의 `bidNtceNo`(공고번호), `bidNtceOrd`(차수), `ntceKindNm`(공고종류)만으로 취소 및 후속 차수의 존재를 판별합니다. 제목에 취소·변경 표현이 있다는 이유만으로 확정하지 않습니다. 같은 공고번호의 숫자 차수가 더 높으면 과거 차수는 `notice_lifecycle=SUPERSEDED`, 공식 공고종류에 취소가 명시되면 해당 최신 차수를 `CANCELLED`로 보관합니다. 추가 원문 정정 이력 API의 전수 조회는 이번 범위 밖입니다.
- 공고 JSON과 기존 사람 최종 결정, `history`, 저장된 RFP 원문·SHA·첨부 증거를 삭제하지 않습니다. 저장 문서가 있는 공고의 공식 중요 메타데이터·신규 첨부 또는 후속 차수 변경은 `rfp_review_status=STALE`로 표시하고 수동 최신성 검증이 필요함을 UI에 안내합니다. 기존 추출 증거로 자동 입찰 적격 확정이나 재검증을 하지 않습니다.
- 규칙 기반 추천은 `CANCELLED`, `SUPERSEDED`, 차수 중복 검토 상태 `REVIEW`, RFP 최신성 `STALE`을 제외합니다. 보관된 공고 목록과 과거 판단 이력은 유지하고 공식 링크·후속 차수와 근거를 화면에서 확인할 수 있습니다.
- 기존 로컬 데이터 확인(미변경): `python local_app/notice_lifecycle_cli.py --data-dir <개인 JSON 폴더>`. 결과를 적용하려면 `--apply`를 추가합니다. 현재 저장된 공고를 공식 메타데이터로 재분류하며 API나 AI를 호출하지 않습니다. 이후 일상적인 API 수집 결과에도 동일 규칙을 적용합니다. 모든 저장은 기존 잠금·배포 가드를 사용합니다.
- 한계: 동일 공고번호의 정정 정보가 최근 7일 API 목록에 보이지 않으면 새로운 변경을 탐지하지 못하며, 원공고가 다른 공고번호로 재공고되는 경우 자동 동일성 판정을 하지 않습니다. 다음 작업의 RFP 의미 분석·AI 추천과 별도입니다.
