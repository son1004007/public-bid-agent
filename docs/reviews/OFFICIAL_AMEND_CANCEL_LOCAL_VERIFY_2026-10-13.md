# 2026-10-13 공식 입찰 정정·취소 수명주기: 독립 Codex 검수 및 로컬 실증

## 결론
- 범위: TD-kiseok Windows 개인 PC, 127.0.0.1:8765, 공식 나라장터 서비스 입찰 공고번호/차수/공고종류 기반 정정·취소 추적. 기존 7일 배치 API 오류 분석은 사용자 요청으로 명시적 제외.
- 개발 브랜치: feat/sprint1-search-demo. 소스 구현 a8896be, Codex 1차 NO_GO 보완 23ff078.
- 정정/취소 기능: 기존 동일 공고번호의 최신 숫자 차수와 후속 차수로 과거 차수 SUPERSEDED, 공식 공고종류에 취소가 명시된 최신 차수 CANCELLED, 나머지 CURRENT. 취소 차수는 이후 일반공고 응답에도 sticky. 차수 `0`/`00`/`000`은 단일 숫자 차수로 결합해 기존 ID와 판단·RFP 자료 유지. 불명확한 동일 차수는 안전 보류.
- 중요 공식 메타데이터·새 첨부 변경 / 구차수·취소로 이전 저장 RFP 증거 최신성 검증 필요 시 `rfp_review_status=STALE`; 기존 본문/문서 증거 및 최종 사람 결정/이력 변경 없음. 추천은 CURRENT이면서 STALE이 아닌 공고만 고려하며 회사 실제 참가자격·인력·원가는 여전히 미검증.
- 변경된 목록·상세 UI에 정정·취소, 구차수/후속 공고 ID, RFP 최신성 재확인 상태 표시. 전체 보기에서 이전 공고 유지; 기본 목록에서는 보류 상태 숨김.

## 실행 근거
- Windows Python 3.12 회귀 **258/258 PASS**. 정정·취소 신규 합성 테스트 18 PASS: 동일 차수 취소 유지, 숫자 표기 변형 병합, 사람 판단·RFP 본문 유지, 순서가 다른 목록, 신규/기존 취소, 중복 폴백, stale 상태.
- Python compile 및 실제 JS node --check PASS.
- Codex 1차 독립 읽기 전용 검수 NO_GO: 취소 상태 비보존, numeric 차수 alias로 인한 중복·취소 손실(P1 2건), stale 자동 해제 없음(P2), 기본 UI 구차수 표시(P2). 수정을 수행하고 **Codex 2차 독립 읽기 전용 검수 GO**(신뢰 단일 사용자 localhost 범위), 신규 HIGH/P1/데이터 손실 P2 발견 없음. Codex는 실제 사용자 자료·인증키에 접근하지 않았고 테스트도 직접 실행하지 않았음.
- GitHub Actions 23ff078 CI success.
- 로컬 운영 변경 전 백업: `%LOCALAPPDATA%/PublicBidAgent/Lab/notice-lifecycle-backups/before-20261013-145316`, 비공개 JSON 6개 및 RFP sidecar 124개 SHA 확인.
- `local_app/notice_lifecycle_cli.py --data-dir [private] --apply` 성공. 실제 3,049건: CURRENT **2,653**, CANCELLED **167**, SUPERSEDED **229**, RFP STALE **8**. 전체 공고 ID 3,049/3,049 유지, 13개 보호 필드 포함 비수명주기 필드 원본 완전 동일, 사람 이력 동일. 그 외 private JSON 5/5 및 RFP sidecar 124/124 SHA 원본과 동일.
- 8765 서버 기존 사용자가 소유한 프로젝트 프로세스 종료 후 같은 cmd로 재시작. Chrome 실제 목록 3,049건 바인딩·전체 상세보기·수집관리 패널, 390px 모바일 넘침 검사 PASS. `/api/dashboard`, 추천, RFP GET 모두 200. 읽기 전용 실제 추천 API: 상세검토 우선순위 총 147건/화면 최대 30건, 추천 내 CANCELLED/SUPERSEDED/STALE **0건**.
- 사용자 확인 URL: `http://127.0.0.1:8765/decision-preview` (해당 PC 로컬 전용).

## 제한 및 다음 결정
- 기존 7일 자동수집 API 실패의 원인 조사는 수행하지 않음. 기존 예약 작업은 그대로 유지.
- 이번 처리에 사용된 신호는 저장된 공식 목록 공고번호·차수·공고종류로, **공식 변경이력 전용 API 전체 조회나 다른 공고번호로 재공고된 사업의 동일성 판별**은 아직 구현하지 않았음.
- RFP STALE 8건은 기존 본문·SHA·인력 근거를 보존하고 추천에서 제외. 최신 공식 자료 재추출·검증 후 stale을 해제하는 자동 업무 흐름은 후속 사용자 방향 결정 후 구현.
- 인터넷 서비스 공개, main 병합, 추가 LangGraph/RAG 추천 구현은 이번 작업 범위에 포함되지 않음.
