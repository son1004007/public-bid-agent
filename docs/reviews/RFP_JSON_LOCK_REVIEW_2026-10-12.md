# RFP JSON 프로세스 간 트랜잭션 검수 (2026-10-12)

## 검수 단위와 출처

- 사용자의 현재 요청: RFP 배치와 대시보드의 다중 프로세스 JSON 갱신 충돌 방지. 원본 파일 보존.
- 대상: `json_transaction.py`, `rfp_batch.py`, `server.py`, `dashboard_backend.py`, 합성 테스트 2개.
- 실행 장비: Windows TD-kiseok, Python 3.12 가상환경. 비공개 인력/회사 운영 JSON과 실제 공고 데이터는 AI 검수 입력에서 제외했다.
- 독립 Codex 첫 검수: 격리 읽기 전용 `gpt-5.6-terra`, 공개 코드 변경분 입력 SHA-256 `6028ecfcbece0fc6200fb13c913eb1b05990383d8b9e116b6e08c92b857ebd8b`. 결과 원문은 사용자 PC 비공개 `user-json/rfp_json_transaction_review_round1.json`에만 보존한다.
- AGY CLI 개인 환경 검수도 시도했으나 120초 print timeout으로 **최종 결과 없음 (BLOCKED)**. 입력 SHA-256 `28e893c336da2821731b2a9afd950b6d50a821130b6088ef6894e462d877cf81`; 기록은 `user-json/rfp_json_transaction_agy_review.json`에만 보존.

## 독립 지적사항 대응

1. **파일/디렉터리 전원 장애 내구성(BLOCKER로 제기)**: `server.persist`는 이미 임시 파일 `flush + os.fsync` 후 `os.replace`를 수행한다. 따라서 '파일 fsync 없음'이라는 전제는 소스와 불일치. 다만 Linux 디렉터리 메타데이터 및 Windows 전원 장애를 완전하게 입증한 것은 아니므로 **전원 장애 내구성은 별도 운영 위험(미검증)** 으로 남긴다. 이번 프로세스 간 lost-update 검수와 분리한다.
2. **다른 프로세스의 일시중지 후 진행 중인 1건 저장(MAJOR로 제기)**: `docs/design/RFP_RESUMABLE_BATCH_2026-10-11.md`의 **'현재 작업 완료 후 정지'** 계약에 부합한다. 완료된 현재 공고만 저장하고 다음 공고는 시작하지 않는 합성 검증을 수행했으므로 현재 계약상 결함으로 분류하지 않는다.
3. **Thread.start 실패 후 거짓 RUNNING(MAJOR 확인)**: 잠금 보유 중 스레드 시작 실패 시 배치 장부를 `PAUSED`로 복구하고 수명 잠금을 해제하도록 수정. 합성 모킹 검증 및 재시작 테스트 통과.
4. **Windows 동일 프로세스 별도 관리자 중복 시작(추가 실측 결함)**: OS `msvcrt` 바이트 잠금만으로 동일 프로세스의 별도 핸들 경계가 완전히 분리되지 않는 실제 테스트 실패를 재현. 경로별 `threading.Lock`을 결합하여 수정 후 중복 관리자 테스트 통과.

## 결정과 잔여 위험

- RFP 배치/대시보드의 해당 기능에서 read-modify-write 구간은 잠금 범위 안에서 직렬화한다. 네트워크 작업은 밖에서 실행하고 재진입 때 서명을 비교한다.
- 이 변경은 원본 운영 JSON을 직접 수정하지 않았으며, 강제 종료·경합·재개는 임시 합성 파일만으로 검증했다.
- 실제 조달청 실문서 2,223건의 일괄 RFP 추출, 법적 적격성, 전체 앱 보안·운영 UI 승인·배포는 본 검수 범위 밖이다.

## 2026-10-12 추가 독립 검수 및 충돌 복구 보완

- 독립 Codex가 소스·합성 테스트에서 확인한 교차 실행 결함: 구형 `/api/dashboard/enrich(-batch)`의 늦은 추출 결과가 최신 RFP 문서를 덮을 수 있음. 수정 후 저장 직전에 `document_signature`를 다시 비교하고, 신규 RFP가 있으면 해당 후보의 저장을 보류하며 `skipped_conflicts`를 반환함.
- 배치 상태가 `IN_PROGRESS`인 채 프로세스가 종료되면 다음 재개에서 `FAILED`로 격리하고, 사용자의 `retry_failed=True` 요청 전까지 자동 다운로드를 수행하지 않음. 처리 시작 전에 시도 횟수와 진행 상태를 저장해 실패 결과/ledger 저장 사이 강제 종료도 구별함.
- 배치 `RUNNING` 상태의 다른 프로세스 잠금이 유지되고 있을 때는 `PENDING` 건수가 0이어도 `start`를 거부하여 ledger를 `COMPLETE`로 잘못 바꾸지 않음.
- Windows의 별도 관리자 중복 실행 테스트, 2개 독립 프로세스 동시 revision/이력 보존, 일시중지, 잠금 시간 초과, 재수집 첨부 보존, 강제 중단 `IN_PROGRESS` 재개, 실제 루프백 HTTP의 늦은 `enrich` 저장 차단을 임시 합성 JSON으로 실행했다.
- 첫 독립 Codex 검수 SHA-256: `f0dbedb370474f1c2694f499b84f0fb11ad8c7856b0fd7ea591b9960654ee72f`. 지적 3건 중 낡은 성공 저장/실패 ledger 자동 재시도를 수정했고, 이전 세대 JSON 백업 부재는 기존 설계의 별도 복원 기능 이슈로 등록한다. `os.replace`의 원자성과 별도 백업 복구 기능을 동일한 것으로 주장하지 않는다.
- 원문 `cases.json`, `operations.json`, `workforce.json`, 실제 `dashboard.json`은 코드 테스트 및 모델 검수에 제공하지 않음. 기존 8765 서버로 수정을 적용하지 않았음.

## 독립 Codex 재검수와 최종 범위 판정

- 최종 재검수: 격리 읽기 전용 `gpt-5.6-terra`, 검수 입력 SHA-256 `1a059f43a558b86ad37073794e6c5fa0f0cb0b304c85a34539258e4628928a38`, 로컬 비공개 출력 `user-json/rfp_json_transaction_review_final.json`에 저장.
- 정상 **협조 작성자**가 동일 잠금 API와 고정 잠금 파일을 유지할 때, 프로세스 내부·프로세스 간 동시 JSON 쓰기 충돌 및 배치 중복 실행에 대한 로직은 리뷰어가 **PASS**로 인정했다. Thread.start 실패·다른 Manager의 일시중지도 설계 계약과 일치함을 확인했다.
- **위협 모델 불일치 지적**: 외부 프로그램이 의도적으로 `.dashboard-rfp.lock`을 지우고 동일 경로의 새 파일로 교체하면 기존 잠금이 무효화된다. 같은 사용자로 실행되는 비협조·악성 쓰기 프로세스와 잠금파일 임의 삭제는 이번 로컬 앱의 협조적 동시 실행 범위 밖이다. 잠금파일 삭제 금지와 외부 작성자 계약 준수 조건을 공개 문서에 명시했다. 이 위험은 '같은 계정의 임의 악성 프로세스'까지 안전하다는 주장에는 BLOCKER지만, 협조 프로세스 lost-update 수정 범위에서는 재현 조건 밖이다.
- **전원 장애 내구성 지적**: `persist()`는 파일 flush+fsync와 원자 교체를 수행하지만 Linux 부모 디렉터리 fsync, Windows durable rename·journal/복구는 이번 변경에 없다. **전원 장애 직후 커밋 지속성은 미검증**이며 이 한계는 향후 운영 안정성 검수에서 해결한다. 프로세스 크래시 뒤 파일 잠금 회수·파일 형식 안전과 구분한다.
- AGY CLI 검수 시도는 120초 제한으로 최종 verdict를 제공하지 못했다. **AGY 최종 서명과 전체 저장소 RELEASED는 미완료**이며, 현재 결과는 기능 구현·합성 테스트 수준의 검증이다. Draft PR에 올리더라도 main 병합과 운영 반영은 하지 않는다.
- 로컬 최신 전체 회귀 **161 PASS**, JS 구문 PASS, Git diff 형식 PASS, 실제 운영 공고 2,223건의 **읽기 전용 SHA 보존 PASS**. 공고 원문 추가 대량 다운로드나 실제 인력/의사결정 원본 수정 없음.

## 2026-10-12 독립 재검수에서 확인한 배치 상태 경쟁 수정

- 읽기 전용 Codex 추가 검수에서 관찰한 `FAILED` 존재 시 `COMPLETE` 오표기 문제를 수정했다. 미처리 `PENDING` 또는 재시도 대기 `FAILED`가 있으면 상태를 `PAUSED`로 남기며 사용자 명시적 재시도 전 자동 다운로드하지 않는다.
- 다른 프로세스가 `PAUSED`로 표시된 배치를 아직 처리하는 중에는 두 번째 관리자가 `start`를 수행하면서 진행 중 인원을 `IN_PROGRESS -> FAILED`로 오인하지 않도록, **장부 상태와 무관하게 살아 있는 작업자 수명 잠금을 먼저 확인**한다.
- 합성 회귀 테스트 `local_app/test_rfp_race_safety.py`에 실패 상태/명시적 재시도 검증 및 `PAUSED`인 외부 살아 있는 작업자 경합을 추가했다. 기존 `test_json_transaction.py`는 서로 다른 실제 Python 프로세스의 동시 수정·잠금 시간초과를 검증한다.
- 실제 공고 및 회사 인력/운영/사람 결정 JSON은 테스트·검수 입력에 포함하지 않았다. 별도 백업/시점 복구, 전원 장애 영속성, 잠금 규칙을 따르지 않는 구형 외부 도구와의 공존은 남은 위험이다.

## 2026-10-12 독립 Codex 추가 검수: 첨부 보존 BLOCKER/MAJOR

- 읽기 전용 독립 Codex 입력 SHA-256: 49344a67ab431d4740e158abf8e431a291c593bfa4195526e863cd2fca76f4f2. 당시 staged 공개 코드 diff 33,270자만 입력하며 실제 사용자 JSON/키는 제외했다. 출력은 PC 비공개 user-json/rfp_crossprocess_review_20261012.json에 저장했다.
- BLOCKER: 신규 공식 첨부 40건에 기존 RFP 상세 첨부가 밀려 삭제될 수 있었음. 기존 첨부 우선 배치로 수정.
- MAJOR: 동일 URL의 신규 레코드가 기존 파일명·출처·식별 필드를 덮는 문제. 기존 레코드 우선 유지하고 비어 있는 필드만 보충하도록 수정.
- 두 결함을 합성 test_rfp_attachment_preservation.py에 추가하여 실제 실행 PASS. 최종 재검수·전체 회귀·CI는 별도 확인.

## 최종 독립 지적사항 판정 및 재개 계약 확인 (2026-10-12)

- 후속 독립 Codex 검수 입력 SHA-256 `8bfc67cce564723f3ca7861b76c2e6cd2e3210d99f6d2aca69a7b986a0433430`: (1) FAILED 존재 시 COMPLETE 오표기(MEDIUM) 수정, (2) PAUSED 상태지만 살아 있는 타 프로세스 worker를 강제 재개(MEDIUM) 수정.
- 변경 후 독립 재검수 입력 SHA-256 `0aa47e6ac1b86ba6377cfb9c830e705e6299e2590de046d8ef8c628eae09f096`: 살아 있는 PAUSED 작업자 중복 재시도 차단 **PASS**.
- 나머지 지적인 “FAILED와 PENDING이 섞여 있으면 정상 PENDING까지 일체 자동 재개 금지”는 기존 명시적 계약과 다른 제안이므로 **REJECTED AS SCOPE MISINTERPRETATION**으로 판정. 기존 `docs/design/RFP_RESUMABLE_BATCH_2026-10-11.md`와 `test_rfp_batch.py::test_resume_failure_retry_and_decisions_preserved`가 명시하는 동작은 실패 `FAILED`만 `retry_failed=True` 필요, 미처리 `PENDING`은 사용자가 다음 `start`를 요청하면 계속 처리한다는 것이다.
- 반례를 추가 테스트 `test_rfp_race_safety.py::test_pending_items_resume_without_retrying_failed_items`로 검증: 첫 건 FAILED + 다음 PENDING에서 사용자가 정상 start를 다시 누르면 PENDING 한 건만 처리하고, FAILED는 재시도하지 않으며 전체 status는 PAUSED를 유지한다.
- 안전한 저장과 별개인 장기 JSON 백업/복원 세대 관리·갑작스러운 전원 장애 내구성은 미구현/후속 작업이다. 잠금 규칙을 따르지 않는 구버전 서버 동시 실행은 금지하고, 운영 적용 전 프로세스 재시작 및 백업 정책 확인이 필요하다.

- 저장된 기존 첨부는 URL이 같아도 서로 다른 문서·정정·근거 식별자가 있을 수 있으므로 두 레코드를 모두 유지한다. 신규 첨부에 한해 동일 URL 기존 첫 항목의 누락 필드를 보충한다. 합성 test_two_existing_evidence_records_sharing_url_remain_distinct PASS.

## 2026-10-12 첨부 병합 추가 재검수 반례 2건

- Codex 읽기 전용 검수 입력 SHA-256: a648df5f76b5cb1aeb9ef059fa00b3ec31fe1591d2069ee9b95fe3cc9173f4f9. 로컬 비공개 원문: user-json/rfp_attachment_review_final2_20261012.json.
- 신규 공고에서 첨부 41건이 그대로 저장되는 경우 수정: 새 공고 저장 경로에 동일한 40건 상한 적용.
- 기존 첨부가 없는 공고에서 신규 동일 URL/서로 다른 identity의 두 항목이 합쳐지는 경우 수정: 신규 항목끼리는 URL로 병합하지 않고 독립 기록 보존.
- test_new_notice_limits_attachment_count_to_forty, test_incoming_duplicate_url_preserves_distinct_new_evidence 합성 회귀 PASS. 최종 재검수 및 전체 테스트 별도 확인.

### 독립 검수에서 추가 발견된 3개 병합 경계 (2026-10-12)

- 독립 Codex 입력 SHA256: c6642ae16e7861512d4b80c9cb8ab9a29e01b5fc6bef51820c03a24f7e5df01f, 원문은 PC 비공개 user-json/rfp_attachment_review_final4_20261012.json.
- 불완전한 공고 메타데이터(None/빈 문자열)로 기존 유효 값을 덮는 유실 가능성: 값 존재 검증 후 기존 값 보존하도록 수정.
- 동일 URL의 출처/파일명이 다른 증거가 강제로 병합되는 문제: identity 및 이름/출처 동치 확인 후 누락 필드만 채우고, 다른 근거는 별도 항목 보존.
- 기존 복수 근거 중 첫 URL 인덱스만 사용하여 두 번째 identity와 같은 신규 첨부를 중복 추가하던 문제: 동일 URL 후보 전체에서 identity를 찾아 병합.
- 합성 회귀 test_rfp_attachment_preservation.py에 부분 수집 메타데이터 불변, 서로 다른 출처, 중복 identity 재수집 테스트가 포함됨. 현재 자동 적격 판단 및 8765 서버 적용은 제외.

### 2026-10-12 최종 첨부/evidence 보존 보완

- 첨부 저장 상한은 120개로 상향하였다. 기존 공식 상세 첨부 40개와 추가 RFP 1개가 총 41개로 저장되고 재수집 후에도 유지된다. 121번째 신규 독립 첨부는 저장 실패로 처리해 기존 첨부를 자르지 않는다.
- 동일 URL의 독립된 `identity=A/B` 근거는 둘 다 유지한다. 같은 URL에서 B를 새로 수집한 경우 B에만 누락된 정보를 보충하며 A를 변경하지 않는다.
- RFP 배치 재추출로 상위 2개 파일이 달라져도 이전 `document_evidence`의 독립 문서 식별자를 보존한다. 합성 원문이 같은 경우도 포함한다.
- 독립 Codex 최종 수정 재검수: 위 3가지 **PASS**, 심각한 신규 회귀 미발견. 입력 SHA-256 `328a2d103cc60a04bbd228bf11419bd69a1865cab6f7c50267dd838dd1dbadcc`; 출력 원문은 개인 PC `user-json/rfp_evidence_review_retest.json`에 비공개 보관.
- 최종 Windows 합성 Python 전체 **177 PASS**, JavaScript 문법/Git diff 검사 PASS, 실제 2,223건 `dashboard.json` 원본 SHA 보존 PASS. 8765 원본 서버 변경 없음. 본 변경의 범위는 협조 프로세스/로컬 파일 시스템이며 정전 내구성·임의 잠금파일 교체·대량 실 RFP 추출은 별도 검증이다.
