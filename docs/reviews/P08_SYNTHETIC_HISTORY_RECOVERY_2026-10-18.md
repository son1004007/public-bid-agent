# P08 수기 제출·평가·선정 이력 복구 합성 회귀

- 범위: D-03/D-06/D-07, P08. 공개 소스와 테스트가 생성한 임시 JSON/가짜 문서만 사용.
- 기준: `feat/sprint1-search-demo`, 시작 HEAD `d5a8feb`, 시작 작업 트리 clean. 이번 변경은 테스트·문서뿐이며 실행 코드/API/저장 형식은 변경하지 않는다.
- 규칙 확인: GitHub 연결로 CONTROL, registry, 지정 handbook 8개 원문 확인. 중앙 관련 열린 USER ACTION 검색 결과 0건. 로컬 AGENTS/DECISIONS/AI_CONTEXT/CURRENT_STATE/TASKS와 P00~P11 로드맵 확인. 셸 및 웹 원문 접근 실패는 GitHub 연결로 보완했다.
- 금지 경계: 실제 사용자 JSON/RFP/회사 증빙 미접근·미전송, 외부 모델/공식 API 호출 없음. main·실 운영 적용·배포·공개·자동 입찰·git add/commit/push 없음. D-10/P11 조사 보류.

## 검증 계약

`local_app/test_bid_outcome_recovery.py`에 6개 테스트를 추가한다.

| 위험 | 합성 시험 및 판정 기준 |
| --- | --- |
| 재시작/재조회 시 이력 누락 | 임시 HTTP 서버를 단계마다 다시 생성해 SUBMITTED → EVALUATED → AWARDED/NOT_AWARDED/WITHDRAWN의 모든 필드·날짜·점수·출처 표식과 revision을 디스크/GET/POST에서 대조 |
| 재전송·종결 기록 덮어쓰기 | 동일 요청 재전송 및 종결 이후 변경은 409, 저장 바이트 불변. 기존 계약에는 종결 후 정정 API가 없으며 이를 새로 구현하지 않음 |
| 원자 저장 실패 | 실제 `persist`의 부분 JSON 쓰기·fsync·replace 경계에 OSError 주입. 500 응답에 내부 오류 설명 미노출, 기존 바이트/다른 JSON 보존, pending 파일 정리, 같은 revision 재시도 1회 성공 후 재전송 409 |
| 교체 중 부분 JSON 노출 | 실제 os.replace 직전에는 기존 파일과 완성된 임시 파일, 직후에는 새 전체 JSON이 보이는지 대조. fsync 실패 주입도 함께 검증하되 전원 장애 내구성을 입증하지 않음 |
| 저장 파일 손상 | 잘린 JSON·배열 최상위·boolean revision의 GET/POST가 503을 반환하고 손상 파일을 그대로 보존 |
| 실제 프로세스 revision 경합 | 별도 Python 프로세스 2개가 같은 평가 완료 revision으로 AWARDED/NOT_AWARDED 기록을 경쟁. 실제 공통 OS 잠금 아래 한 번 저장·한 번 충돌, 기존 두 사건과 사용자 판단 보존 |
| 수집과 수기 기록의 충돌 | 모의 수집 병합으로 revision이 바뀌면 이전 요청 409, GET 재조회 후 정상 기록. 제출·평가 이력·갱신된 제목 보존 |

`local_app/test_release_rfp_stage.py`에는 5개 테스트를 추가하고 기존 fixture와 복구 assertions를 보강한다.

- 기존 **합성** 2,223개 공고/127개 가짜 문서/124개 청크 fixture에 제출·평가·선정·미선정 및 이관 대상 밖 철회 이력을 포함한다. 이 수치는 현재 운영 건수가 아니다.
- stage의 상충하는 사람 기록을 병합하지 않고, 현재 이력·결정·추천을 보존한다. 백업/복원은 원래 JSON 바이트와 일치해야 한다.
- 백업 후 새 수기 평가 기록의 revision 변경 또는 동일 revision의 사건 내용 변경이 있으면 rollback을 거부하고 현재 기록과 백업을 보존한다. 동일 revision 직접 편집은 보호장치 시험용이며 지원 정정 절차가 아니다.
- 백업 내 미선정 사건을 선정으로 변조하면 rollback 및 PREPARED 복구를 거부하고 현재 JSON·손상 백업을 보존하며 PREPARED를 해제하지 않는다.
- 두 번째 백업 파일 복사에서 실패한 뒤 새 수기 평가가 기록되면 기존 부분 백업을 새 세대로 덮어 재개하지 않는다.
- 기존 중단 복구의 rollback/commit, rollback 중 두 번째 파일 교체 실패 경로에서도 수기 사건 전체 보존을 확인한다.
- 모든 `apply/rollback/recover`는 테스트 소유 임시 경로에만 호출한다. 실제 배포 도구 실행/운영 적용은 없다. 기존 도구는 특정 RFP 이관용이며 일반 사용자 이력 백업 API로 확대하지 않는다.

## 실행 증거

환경: Windows, CPython 3.12.0, 표준 unittest. 새 의존성 없음.

```powershell
$env:PYTHONPATH='local_app'
python -m unittest test_bid_outcomes test_bid_outcome_recovery test_release_rfp_stage test_json_transaction test_dashboard_backend -v
```

- 1차 집중 시험: 9개 중 8 PASS/1 ERROR. 새 수집 연계 테스트의 합성 공고에 `org` 등 정규화 필수 필드가 누락된 fixture 오류였다. 공개 `normalize()`에 합성 API 필드를 제공하도록 수정했으며 제품 결함으로 기록하지 않는다.
- 위 5개 모듈 최종 실행: **53 PASS, 127.341초, 실패/오류/skip 0**. 모듈별 3/6/22/7/15개이며 신규 11개(6+5), 기존 42개다. 기존 dashboard 모듈의 모의 7일 수집 회귀 실행은 D-10의 과거 실제 장애 원인 조사가 아니다.
- `git diff --check`: **PASS**. README 2종에 같은 P08 범위·한계·결과 문서를 연결했다. 커밋 검사 스크립트는 HEAD 커밋만 보므로 이번 미커밋 변경의 검증 근거로 사용하지 않는다.

## 인계 및 미검증 범위

- 독립 Codex 최종 검수: **NOT RUN**, orchestrator 인계. 테스트 통과를 GO/REVIEWED 또는 P08 전체 완료로 표시하지 않는다.
- 전체 Python/CI/실제 Chrome UI/사용자 인수/실 운영 복구/전원 중단: **NOT RUN**. 루프백 HTTP와 실제 두 프로세스의 합성 저장 경합만 확인한다.
- 이력 전용 자동 백업, 손상 이력의 자동 복원, 종결 사건 정정 UX를 새로 구현하지 않았다. 승인된 백업 범위·최신 기록 보존·복원 전 확인을 포함한 실 운영 절차는 후속 인수 대상이다.
- Git 기록·CI·독립 검수 및 그 이후 판단은 orchestrator 담당. 배포/공개·main은 이번 승인 범위 밖이다.
