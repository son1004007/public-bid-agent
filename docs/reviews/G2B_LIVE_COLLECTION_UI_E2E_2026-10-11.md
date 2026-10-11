# 실제 나라장터 API 수집·목업/실데이터 Chrome E2E (2026-10-11)

## 실행 환경·판정

- Local PC: `TD-kiseok`, `127.0.0.1:8765` Windows 현재 사용자 로컬 Python 앱.
- Commit: 기능 `498e10d` → 사용자 인증키가 있는 환경에서도 테스트를 격리한 `0da18f7` → 실제/합성 KPI 문구 구분 `80bb885`.
- 인증키: Windows DPAPI 저장 여부 `configured=true`, `source=WINDOWS_DPAPI` 확인. **값을 조회·출력·저장소 기록하지 않음**.
- `POST /api/procurement-key/verify`: 실제 조달청 API `ok=true, verified=true`; 이전 버전에서 수정한 `ServiceKey` 파라미터로 정상 응답.
- `POST /api/dashboard/collect {"days":1}`: 실제 원본 1건 스캔, 제목 기반 관심공고 0건, 수집 SUCCESS. 일요일/공휴일/주말의 적은 공고량 때문에 정상임에도 UI 항목이 비어 있는 문제 확인.
- 추가 공개 API 진단 (실제 인증키는 내부에서만 사용): 2026-10-08 일일 원본 700건/관심 제목 90건, 2026-10-09 원본 10건/관심 제목 2건.
- 수집 범위를 UI에서 1일/7일 중 선택하도록 구현. 최근 7일은 일일 조회 7회를 모두 성공해야 기록하고, 공고번호·차수로 중복제거하며 기존 저장·사람 결정 보존.
- `POST /api/dashboard/collect {"days":7}` 실 API **SUCCESS**: 원본 `last_scanned=2227`, 제목 기반 `last_count=275`, 실제 저장 `275`, 신규 `changed=275`, `revision=2`, `lookback_days=7`, 사람 결정/이력 0건 유지. 호출 시간 약 26초.

## 실제 저장 275건 데이터 품질/범위

- 제목에 기반한 임시 분야 분류: AI 104건, SW 97건, DATA 74건.
- 공식 G2B 링크 검증 및 저장: 275/275.
- 오늘 점검 시 입찰 마감이 미래인 항목: 209건. 마감 미확인: 37건. 숫자는 수집 시점 정보 기준이며 실시간 입찰 참가 가능 여부가 아님.
- 법적 참가조건·실적·RFP·수익률 및 AI 적합성은 전부 미확인/미판단 상태로 유지.
- 키워드 제목 필터로 인해 유지보수/행사 운영/비개발 분석용역 등이 섞이며, 관련 분야 누락도 가능. 실 사업 적합도나 최종 지원 추천으로 사용하지 말 것.
- 예시 확인: `R26BK01752388-001` LCDC 플랫폼 앱 개발, `R26BK01756417-000` 한서대학교 글로벌 전문가 Pool DB 통합 구축 등. 공개 공식 API 메타데이터 기반.

## 보안·기능 검증 증거

| 검증 항목 | 결과 |
| --- | --- |
| Windows Python unittest (실 DPAPI 사용자 키 읽기를 mock으로 격리) | **76 PASS** |
| GitHub Actions `80bb885` Push / PR | **SUCCESS / SUCCESS** |
| 실제 데이터 Chrome 목록 275행·공식 API 출처 표시 | PASS |
| 실제 수집 이력·7일 조회기간·등록된 키 상태 표시 | PASS |
| 실제 공고 상세 화면 및 8개 참가자격/12개 영향인자 '미확인' 처리 | PASS |
| 브라우저 새로고침 후 실 목록 275건 복원 | PASS |
| 실 공고 1건 **격리된 임시 JSON 사본**에 보류 사유·프로필 버전 스냅샷 저장 | PASS |
| 격리 사본 새로고침 후 결정 이력 유지 | PASS |
| 실사용 `dashboard.json`과 기존 `cases.json` 파일을 E2E 전후 바이트 단위 비교, 무변경 | PASS |
| 최신 UI의 시연용 KPI 오인 문구 제거 후 위 7개 E2E 재검증 | PASS |
| 실제 사용자의 입찰 참여/불참 결정 기록 생성 | **NOT RUN** (의도적으로 실사용 데이터 미변경) |
| 정기 예약 수집·실 RFP 분석·Codex 자동 판단·정정/취소 완전추적·실입찰 제출 | 미구현 |

연관 CI:
- [GitHub Push](https://github.com/son1004007/public-bid-agent/actions/runs/38114456978) SUCCESS
- [GitHub Pull Request](https://github.com/son1004007/public-bid-agent/actions/runs/38114459846) SUCCESS

## 상태·잔여 작업

- API 사용자의 **활용신청/인증키 등록/실제 API 연결·수집**은 이제 실동작 VERIFIED. 중앙 User Action #20은 완료 처리 가능.
- 독립 AGY/Gemini 및 Codex의 의미/보안 검수, 사용자 화면 최종 승인: **NOT RUN**, PR #1 Draft 및 main merge HOLD 유지.
- 후속 우선순위: (1) 제목만이 아니라 실제 입찰 자격/업무 영역/마감·상태 필터링, (2) 공식 원문/RFP 첨부·정정/취소/변경이력, (3) Codex 근거 분석과 별도 담당자 결정, (4) 예약/증분수집 및 호출한도 보호.
