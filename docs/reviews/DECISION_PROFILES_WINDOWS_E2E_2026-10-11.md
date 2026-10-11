# 판단기준 프로필 백엔드 Windows·Chrome E2E 검증 (2026-10-11)

## 대상 및 범위

- Repository: `son1004007/public-bid-agent`
- Commit under test: `bb06ff1d8b5bbe0482a50126cf1a68a61b32b5f7`
- Device: Windows `TD-kiseok`, CPython 3.12, 기존 프로젝트 개발 브랜치 Fast-forward.
- 기존 사용자 `user-json` 데이터는 테스트 입력으로 사용하지 않음.
- 브라우저 E2E는 별도 임시 데이터 폴더와 `127.0.0.1:8766`의 합성 데이터 서버·임시 Chrome 프로필로 수행.
- 실제 사용자 로컬 앱은 기존 `127.0.0.1:8765`를 동일 데이터 경로로 재시작. 로컬 프로필 저장을 본인 실사용 파일에서 수행한 것은 아님.

## 수행 결과

| 단계 | 확인 결과 |
| --- | --- |
| 기존 소스 `fafb0f2` → `bb06ff1` | PASS, FF-only, git clean |
| Windows Python `unittest discover -s local_app -p 'test_*.py' -q` | PASS, 60 tests |
| 별도 Chrome 초기 합성 공고 8건 렌더링 + 프로필 API 연결 | PASS |
| 기준 프로필 `minFit=77` 저장 및 revision 1 | PASS |
| 새로고침 이후 프로필 저장값 복원 | PASS |
| 12요인 가중치 `technical=14`, `risk=6`, 총합 100 저장 및 revision 2 | PASS |
| 새로고침 이후 가중치·버전 복원 | PASS |
| 이전 revision 1 재저장 시 HTTP 409, 현재 revision 2 유지 | PASS |
| 기존 앱 8765 프로세스 본인 서버임을 확인 후 한정 재시작 | PASS |
| 새 프로필 GET, 기존 앱 메인·상세·JS 정적 경로 | HTTP 200 |
| 기존 `cases.json` SHA-256 재시작 전후 동일 및 API 공고 5건 | PASS |
| 임시 Chrome·8766 서버·임시 파일 정리 후 8765 앱 유지 | PASS |

## 잔여 게이트

- Windows Chrome 실브라우저 상호작용은 **임시 합성 데이터 환경**에서 확인했다. 원래 8765의 사용자 데이터로 영구 저장 버튼을 누르지 않았다.
- 사용자 UX 승인 및 AGY/Gemini·Codex **독립 최종 의미/보안 검수**는 미완료.
- 기존 Windows 간헐 CSRF 연결 강제종료 가능성은 이번 정상 60테스트 통과만으로 근본 원인을 해결한 것이 아니다.
- 현재 기능은 **두 프로필의 로컬 JSON 저장**에 한정. 정기 나라장터 자동 수집, 실제 AI 추론, 공고별 최종 Bid/No-Bid·판단 이력의 새 UI 저장은 미구현.
- 따라서 **main 병합·공개 배포 HOLD**, Draft PR 유지.

## 관련 증거

- [프로필 API 구현 커밋](https://github.com/son1004007/public-bid-agent/commit/10a0dfb39496d6c25a82ec3308f4316c726b18dc)
- [코드 CI Push](https://github.com/son1004007/public-bid-agent/actions/runs/38059273249)
- [코드 CI PR](https://github.com/son1004007/public-bid-agent/actions/runs/38059276328)
- [상태문서 CI Push](https://github.com/son1004007/public-bid-agent/actions/runs/38059471772)
- [상태문서 CI PR](https://github.com/son1004007/public-bid-agent/actions/runs/38059475389)

Windows 실제 실행 결과는 원격 PC의 프로세스·API·브라우저 자동 조작으로 확인하였다. 이 보고서는 사용자 UX 승인이나 독립 보안 검수를 대체하지 않는다.
