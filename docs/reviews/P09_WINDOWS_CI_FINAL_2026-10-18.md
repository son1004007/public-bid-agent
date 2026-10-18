# P09 Windows CI 복구와 로컬 적용 최종 검증 (2026-10-18)

## 현재 판정

- **VERIFIED (개발 브랜치 합성 구현/테스트/독립 검수/CI/Windows 로컬 적용)**. 사용자 UI 최종 승인, 실제 회사·RFP 적격 검증, `main` 병합 및 인터넷 공개는 각각 **NOT VERIFIED/NOT RUN**.
- 대상: `son1004007/public-bid-agent`, `feat/sprint1-search-demo`. 이전 P09 코드 커밋 `bf3dca42e15eb77eead9f636d161025f8c96d583`, 현재 로컬 적용 **`f06a3faebbcf3995f6d1ac2fd3fe5c1f9b978c86`**. 상태·근거는 `CURRENT_STATE.md`, `TASKS.md`, 로컬 `AgentRunner/state-journal.jsonl` 마지막 유효 줄과 `last-local-release.json`에서 교차 확인.
- 2026-10-18 17:17:48 KST: immutable Git SHA만 Windows `127.0.0.1:8765`에 반영. 원본 보호 파일 318개 백업 및 SHA 검증 전·후 동일. 로컬 서버 HTTP 200, P06 준비도 하위 계약, 배포 후 read-only Chrome 8단계 PASS (종료 코드 0). 백업은 공개 GitHub 외부 로컬 디렉터리.

## 재현된 실패 원인과 수정

- 최초 Windows Actions [39094326827](https://github.com/son1004007/public-bid-agent/actions/runs/39094326827)에서 51개 중 1 FAIL/1 ERROR.
- `test_bid_outcomes.py`: Windows 기본 `cp1252`로 UTF-8 JSON을 `read_text()`해 `UnicodeDecodeError`. 수정: 파일 읽기에 `encoding="utf-8"` 명시.
- `test_local_acceptance.py`: Korean TXT 추출 subprocess가 `ensure_ascii=False` JSON을 Windows `cp1252` stdout으로 인코딩하면서 오류, 상위 서버에 `PARSER_UNAVAILABLE`이 표시됨. 수정: `extractors.py` CLI 정상/오류/예외 JSON 출력의 `ensure_ascii=True`. 역직렬화 후 텍스트는 원문 문자열로 동일하게 복원되고 추출 정책은 유지.
- `test_local_acceptance.py`에서 `PYTHONIOENCODING=cp1252`로 자식 프로세스를 강제 실행하여 한국어 문자열이 훼손되지 않고 정상 처리되는 회귀를 추가. 루트 및 `local_app` README를 동일 커밋에서 갱신.
- 새로운 의존성을 설치하거나 기존 Chrome sandbox·CSP·보안 정책을 완화하지 않음.

## 실측 결과

| 게이트 | 결과 | 구분 |
| --- | --- | --- |
| Windows `cp1252` 집중 테스트 | **3 PASS**, 종료 0 | 수정한 두 실패 및 신규 로캘 회귀 |
| Windows CI와 동등한 6개 Python 모듈 | **52 PASS**, 종료 0 | 2026-10-18 로컬 Windows 강제 `cp1252` |
| 전체 Python `unittest discover` | **403 PASS**, 종료 0 | 로컬 Python 3.12 |
| README 동기화 스크립트, Node 구문, `git diff --check` | **PASS**, 종료 0 | GitHub workflow의 최종 결과도 별도 확인 |
| Codex 독립 read-only 검수 | **VERDICT: GO**, CLI 종료 0 | 현행 수정 다섯 파일 검증. 실제 사용자 원본 사용 없음 |
| [기존 Sprint 1 CI 39110626764](https://github.com/son1004007/public-bid-agent/actions/runs/39110626764) | **SUCCESS** | SHA `f06a3fa` |
| [Windows synthetic CI 39110626835](https://github.com/son1004007/public-bid-agent/actions/runs/39110626835) | **SUCCESS** | 동일 SHA. Python 보안·복구와 Chrome 합성 E2E 실행 |
| Windows Chrome 합성 E2E, 단독 재실행 | **PASS**, 종료 0 | 동시 Python 전체 시험 중의 최초 불안정 1회는 숨기지 않고 기록 |
| 적용 후 실사용 로컬 서버 Chrome 읽기 전용 | **8단계 PASS**, 종료 0 | 목록, 추천 새로고침, 상세, 근거 GET, 종료 상태; 사용자 최종 인수 아님 |
| 적용된 실제 비공개 파일 | **318개 SHA 불변** | source-only 교체/백업. 내용은 외부 미전송 |

## 경계와 다음 단계

- 앞선 `CURRENT_STATE.md`/P09 최초 인수 보고의 **BLOCKED/NO_GO/NOT RUN은 그 시점 기록**이며 최신 P09 구현 결과는 위의 새 독립 검수 및 GitHub Actions 근거를 우선한다.
- 합성 API/Chrome 성공은 실제 PDF/HWP 전체 페이지, 표, 각주, OCR 누락률/필수 요건 Recall이나 회사 실제 면허·가용 인력·원가·법적 적격 증거가 아니다. 실제 데이터에 대한 사람의 검토와 UI 승인 별도.
- 선언한 전체 의존성 설치/버전/라이선스/SBOM/보안 취약점, 실제 운영 고장/복구·전원 장애, 다중 사용자 인증, 인터넷 서비스 공개 등은 별도 검증. 일부 선택 의존성은 이전 보고 당시 누락된 것으로 확인되었으며 이를 이번에 새로 설치했다고 주장하지 않는다.
- P10 `main` 병합/인터넷 공개·실제 입찰/서명/계약은 별도 승인 필요. 과거 7일 API 오류의 선제 조사(P11)는 사용자 D-10에 따라 계속 보류.
- 데이터 보존 검증용 실제 파일 경로, 내용, 회사 자료, API 키 및 백업은 공개 저장소에 기록하지 않는다.
