# P05 공식 출처·차수·STALE 합성 검증 (2026-10-18)

- 상태: **IMPLEMENTED / TESTED**, 독립 Codex **NO_GO/P1 보완 후 재검수 대기 / REVIEW_DEBT**. 아래 최초 76 PASS 기록과 후속 91 PASS를 구분한다. orchestrator 재검수·Git 기록 인계용이며 REVIEWED/RELEASED가 아니다.
- 범위: D-06/D-09, P05. 공개 소스와 직접 생성한 합성 공고/TXT/임시 캐시만 사용. 사용자 JSON·실제 RFP·회사 증빙 접근·전송 없음. D-10/P11 과거 7일 API 장애 진단은 제외.
- 기준: 개발 브랜치 `feat/sprint1-search-demo`, 로컬 ref `8b7f7192703441955bdb268bfeaf43dad85a2ce1`. CONTROL 및 지정 handbook 원본은 연결된 GitHub 읽기 도구로 확인. shell GitHub 요청은 네트워크 제한으로 실패했으나 보안 설정을 변경하지 않았다.

## 변경과 재현

`dashboard_backend.normalize`가 공고번호를 32자, 차수를 5자로 자른 뒤 검사하여 길이 초과나 끝의 잘못된 문자를 정상 ID로 수용했다. 예를 들어 `000001`과 `00000!`은 모두 `00000`으로 바뀌었다. 기존 행과 잘못 병합하거나 취소/정정 차수를 오인할 수 있다.

양끝 공백 제거라는 기존 호환 동작은 유지하되 **전체 문자열**에 기존 정규식 계약을 적용한다. 잘못된 입력은 기존 `ProviderError` 경로로 거부한다. 정상 ID 형식·숫자 차수 별칭 병합·저장 형식·수명주기 정책은 변경하지 않는다. 의존성/마이그레이션/STALE 해제 경로 추가 없음.

새 `local_app/test_official_source_safety.py`의 14개 테스트는 다음을 확인한다.

- 잘못된 식별자 유형·길이·문자 거부, 허용 길이 경계의 원래 ID 보존.
- 비공식 source·불일치 ID를 정정/취소 연결에 사용하지 않음.
- `2/009/010`의 6가지 도착 순서에서 숫자 차수 선택, 입력 사본·원문·사람 판단·이력 보존.
- `0/00/000`의 6가지 도착 순서에서 각 행을 별도 병합했을 때 동일 차수 취소 유지. **최초 시험은 같은 배치 손실을 검출하지 못했다(아래 NO_GO 보완 참조).** 기존 별칭 중복은 삭제하지 않고 REVIEW로 차단.
- 빈/구차수/일반 응답 재수집에도 취소·구차수와 후속 ID 연결 유지. 반복 갱신에 lifecycle event 중복 없음.
- 13개 중요 메타데이터 변경의 STALE 전이, 관측시각/누락 첨부만으로 정정 추정 금지, 과거 메타 복귀 시에도 STALE 유지.
- 취소/구차수/REVIEW/STALE이면 일치하는 합성 원본이 있어도 캐시·파서 진입 전 보류. 요구사항 구조화 및 추천 차단.
- 구형/다른 공고·차수 증거는 캐시 진입 전 보류. 위장 공식 URL은 identity 해시가 맞아도 파싱 거부.
- 정상 원본 재현은 메모리·합성 캐시를 바꾸지 않고 페이지/표/OCR 완전성과 구형 파서 설정을 NOT_VERIFIED로 유지.

## 실행 증거

환경: Windows CPython **3.12.0**, 신규 패키지 설치 없음.

수정 전 `python -B -m unittest test_official_source_safety -v`: 14개 실행, 길이 초과 식별자 4개 subtest **FAIL**. 나머지 테스트는 PASS. 수정 후 아래 실행은 **76 PASS**, 오류/skip 없음.

`local_app` 디렉터리에서:

```powershell
python -B -m unittest test_official_source_safety test_notice_lifecycle test_notice_lifecycle_cli test_dashboard_backend test_rfp_original_workflow test_rfp_original_compare test_rfp_requirements -v
```

기존 HTTP 시험은 임시 합성 JSON과 루프백 서버/모의 공급자를 사용한다. 기존 7일 수집 회귀 역시 합성 시험이며 보류된 실제 과거 장애를 조사한 것이 아니다.

파일 수준 정적 확인 **PASS**: 변경 Python 2개 AST 파싱, 이번 변경 파일 10개의 충돌 표식 부재, 두 README의 P05 안내/보고 링크 동기화, 새 파일의 trailing whitespace 부재. 이 확인은 커밋 기반 CI나 독립 검수를 대신하지 않는다.

## 잔여 검증과 인계

- **NOT RUN:** 전체 저장소 회귀, 실제 공식 API·원본 최신성/문서 완전성 실증, Chrome 사용자 인수, CI, 수정분 독립 Codex 재검수, 운영 반영/배포.
- **BLOCKED:** 이후 sandbox Git status/diff는 저장소 소유권 검사(`dubious ownership`)로 실행 불가. safe.directory·권한·보안 설정을 바꾸지 않았다. 커밋 기반 문서 동기화 CI는 orchestrator의 검수 후 커밋에서 확인해야 한다.
- 두 README 및 상태/백로그를 이번 변경과 동기화했다. 기존 사용자 자료를 읽지 않았으므로 실자료 SHA 보존 검증을 했다고 주장하지 않는다.
- `git add/commit/push`, main 변경, 배포/공개, 자동 입찰 없음. 독립 검수는 이 보고와 공개 소스 diff·합성 테스트를 대상으로 수행하며 실제 원본은 입력하지 않는다.

## NO_GO/P1 후속 보완: 같은 배치 취소 손실

사용자가 전달한 독립 검수는 **NO_GO**였다. 식별자 검증 회귀와 별개로, 기존 `000` 정상 공고에 취소 `00`→일반 `0`을 한 번에 병합하거나 두 응답 모두 `000`인 경우 후행 메타데이터가 `notice_kind`를 덮어썼다. 배치 종료 후의 `reconcile`에는 취소 신호가 남지 않았다. 최초 테스트는 각 행마다 병합하여 이 결함을 놓쳤다. finding **ACCEPTED**, 수정 후 독립 GO는 아직 없음.

`dashboard_backend.preserve_cancellation`은 같은 공식 ID/숫자 차수로 매칭된 응답에서 이미 관측한 취소 공고종류를 일반 응답으로 덮지 않도록 한다. 정규화된 수명주기/마감 상태도 취소로 유지하며, 다른 필드는 최신 응답 값을 사용한다. 입력 객체는 변경하지 않는다. 이를 다음 손실 지점에 적용했다.

- `dashboard_backend.collect`: 같은 페이지 및 페이지 사이 동일 ID 중복 제거.
- `scheduled_collection.fetch_window`, `server.py` 수동 수집: 조회기간 사이 동일 ID 중복 제거.
- `dashboard_backend.update_collection`: 기존 ID와 숫자 차수 별칭 병합. 원문·사람 판단·이력 및 기존 ID 보존, 최종 수명주기 조정은 기존 `reconcile` 사용.

새 스키마·마이그레이션·STALE 해제·의존성 변경은 없다. 이미 손실된 과거 취소를 추정 복원하지 않는다. 과거 D-10 장애 조사는 수행하지 않았으며, 조회기간 시험은 모의 공급자만 사용한 현재 취소 결함 회귀다.

### 수정 전후 실행 증거

Windows CPython **3.12.0**, `python -B`, 합성 자료만 사용했다. 새 테스트 4개를 수정 전 실행한 결과 **29개 subtest FAIL / ERROR 0**. 수정 후 관련 8개 모듈 **91 PASS / FAIL 0 / ERROR 0 / SKIP 0** (12.297초).

새 회귀 범위:

- 동일/별칭 `0/00/000`의 취소·일반 쌍 18개 순열 + 3행 6개 순열을 기존 공고 유/무에서 검사: **48개 배치 사례**. 최초 입력·원문·증거·사람 결정·이력 보존, 취소 상태/추천 제외, 반복 병합의 lifecycle event 불변.
- 취소/일반 양쪽 순서 × 동일 페이지/다른 페이지: **4개 사례**, 중복 제거 후 실제 저장 병합까지 검사.
- 예약 수집의 7일 각 위치에서 취소 관측: **7개 사례**, 모의 collector 입력 불변.
- 수동 HTTP 수집의 7일 각 위치에서 취소 관측: **7개 사례**, 임시 합성 JSON과 루프백 서버만 사용. 원문·사람 결정·이력·별도 cases 파일 보존 및 실제 저장 결과 일치.

`local_app`에서 실행:

```powershell
python -B -m unittest test_official_source_safety test_notice_lifecycle test_notice_lifecycle_cli test_dashboard_backend test_rfp_original_workflow test_rfp_original_compare test_rfp_requirements test_scheduled_collection -v
```

이 91 PASS는 이번 구현 작업의 실행 증거다. 독립 검수, 실제 RFP/법적 적격 검증 또는 OCR 실행 파일·언어팩 fingerprint 검증으로 해석하지 않는다. 전체 회귀·CI·운영 반영은 NOT RUN이며, 기존 Git 소유권 제한을 완화하지 않았다. 독립 재검수와 Git 기록은 orchestrator에 인계한다.

추가 메모리 재현 **2/2 PASS**: 검수자가 제시한 `00→0`, `000→000`을 RFP 없는 기존 정상 공고에 한 번에 병합하여 `CANCELLED`, 추천 1→0, 입력 불변을 확인했다. 후행 정상 응답의 예산 갱신도 유지된다. 정적 확인 **PASS**: 변경 Python 5개 AST, 이번 수정 파일 12개의 충돌 표식 부재, 두 README 링크·P05 재검수 상태 동기화, 개발 브랜치 HEAD 유지. 커밋 기반 문서 동기화 CI/Git diff 검증을 대신하지 않는다.
