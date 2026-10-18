# P09 후속 검증 및 Codex 사용량 차단 복구 기록 (2026-10-18)

## 작업 범위·상태

- 기준: `feat/sprint1-search-demo`, 직전 검증 완료 커밋 `c0dcfff` (P08). P04~P08 커밋·CI 이력은 보존하고 P09 미커밋 변경만 계속 검증한다.
- **P09 코드·합성 테스트: 실행 가능 / 독립 Codex GO: BLOCKED / P09 commit·push·GitHub Actions: NOT RUN / 로컬 운영 P09 적용: NOT RUN.**
- 2026-10-18 11:40 KST 무렵의 `Codex CLI 0.154.0` 재현: 로그인 `Logged in using ChatGPT` 정상, `gpt-6-astra` 독립 테스트 실행이 `You've hit your usage limit`로 종료 코드 1을 반환했다. CLI에는 2026-10-25 오전 5:47 이후 재시도 안내가 있었으나 표시 시간대는 확인되지 않았다.
- 이전 orchestrator가 `CODEX_FAILED 1 P09-review-0` 두 차례로 중단된 직접적인 원인은 **사용량 제한**이다. 명령 출력이 저널에 보존되지 않아 초기에는 원인 분류가 되지 않았다. Linear/Neon MCP 인증 경고도 같이 출력됐지만, 최종 실행 차단 문구는 Codex 사용량 제한이었다.
- `P09`는 중복 재구현하지 않는다. quota 해제 후 **독립 read-only Codex 검수부터** 재개한다. GO이면 전체 회귀 결과·변경 범위 점검 후 개발 브랜치 commit/push 및 CI를 확인한다. NO_GO이면 지적 수정 후 같은 게이트를 반복한다.

## Chrome E2E 후속 재현 및 개선

- 최초 `scripts/test_chrome_synthetic.cjs`: Chrome/155.0.8059.40에서 CDP 세션이 열렸고 `Chrome synthetic E2E`를 출력했으나 `list/detail/XSS` 단계의 버튼 탐색에 실패했다.
- 공개 대시보드 `frontend/public/dashboard-live.js`의 실제 상세 버튼 표시가 `전체 상세보기`인데 합성 runner가 `상세보기`를 찾고 있었다. 선택자를 실제 UI 문구에 맞게 수정했다. 보안·Chrome sandbox/HTTP/제품 코드는 변경하지 않았다.
- 수정 후 Windows Node 22 합성 fixture/새 임시 Chrome 프로필에서 **`PASS CHROME_SYNTHETIC_E2E`, exit 0**:
  - 공고 목록·상세 텍스트의 HTML 미실행
  - RFP 로컬 원본 미선택/해시 불일치/합성 TXT 추출 일치
  - 제출·평가 수동 이력 필수 필드·저장·새로고침 후 유지, 기존 사람의 최종 판단 보존
  - 모바일 390px 가로 넘침 없음, JavaScript 예외 없음, 외부 페이지 요청 없음
- 보관된 기존 P09 보고서의 `Chrome BLOCKED` 내용은 **최초 실행 이력**이며, 이 문서의 후속 성공으로 갱신한다. 합성 결과는 실제 비공개 RFP 전체 분류 정확도, 모바일 실기기·사용자 최종 인수 또는 운영 배포 증거가 아니다.

## 최종 승인 전 남은 게이트

1. quota 복구 후 최신 diff의 Codex 독립 `VERDICT: GO` (현재 미확보).
2. 전체 Windows Python 회귀, Node 구문 및 Chrome E2E 재현 결과 검증. 실패 또는 새 변경 발생 시 다시 실행.
3. 정확한 P09 커밋·푸시 및 GitHub Windows+기존 CI 모두 성공 확인. 실패한 CI를 성공으로 표시하지 않음.
4. 선언 의존성 버전 충족, 전이 라이선스·NOTICE·SBOM·취약점 검토, 실제 사용자 승인·운영 적용은 별도 게이트. 모의 로컬 브라우저 PASS로 대신하지 않음.
5. 기존 Windows 공식 데이터·RFP·사람 판단·비공개 키는 합성 개발/검수에 사용하지 않음. main 병합, 인터넷 공개, 실제 입찰 제출 금지. D-10 조사 보류.

## 1시간 감시

- ChatGPT의 `Public Bid Agent 매시간 상태 점검` 감시를 2026-10-18에 활성화했다. 실질 상태가 달라졌을 때만 알림.
- Windows 실행기 source of truth는 `AgentRunner/state-journal.jsonl` 마지막 유효 레코드, 상태는 `BLOCKED` P09, 재개 시 P08 이전 단계를 반복하지 않는다.
