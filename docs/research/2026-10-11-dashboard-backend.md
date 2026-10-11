# 입찰 공고 대시보드 백엔드 계약 (2026-10-11)

## 요구와 현재 결과

사용자가 확인한 `bid-decision-dashboard-preview.html`을 우선 사용한다. 로컬 메인 화면은 해당 퍼블리싱 화면의 화면구성/메뉴/상세탭을 유지하면서 백엔드에 연결한다. 독립 HTML 파일은 합성 디자인 시안으로 유지하고 실제 데이터와 섞지 않는다.

## 공개 API 근거

- 공식 출처: [조달청_나라장터 입찰공고정보서비스](https://www.data.go.kr/data/15129394/openapi.do)
- 무료 REST, JSON+XML, 이용허락범위 제한 없음, 개발단계 자동승인, 개발계정 트래픽 1000. 용역용 오퍼레이션만 1차 구현.
- 초기 범위: `https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoServcPPSSrch`.
- 요청: `serviceKey`, `type=json`, `inqryDiv=1`, `inqryBgnDt`/`inqryEndDt`(YYYYMMDDHHMM), `pageNo`, `numOfRows`.
- 작업 전 공식 데이터 카탈로그 및 공개 개발 예시를 조사했다. **실제 서비스 키 기반 호출/응답과 각 필드 규격 전수 검증은 미완료**, 인증키가 없는 환경에서는 버튼 비활성/424를 표시한다. 공식 상세 명세를 추가 확보하면 해당 오퍼레이션을 계약 테스트로 고정할 것.

## 데이터·상태/오류 계약

- `GET /api/dashboard`: dashboard.json의 공고 목록/판단이력/수집상태, 저장 revision, CSRF, 키 설정 여부만 전달한다. 키 값 자체 미노출.
- `POST /api/dashboard/collect`: 키 확인·고정 HTTPS 도메인·timeout 12초·응답 최대 1MB·최대 3페이지/100행, 24시간 윈도우. 페이지 누락/응답 포맷 오류는 실패, 기존 공고 유지.
- `POST /api/dashboard/action`: `expected_revision` 필요, ID 존재 검증, recommendation/human_bid/human_no_bid/human_hold enum, 사람 결정 사유 필수. 409 동시 변경·400 잘못된 입력·503 손상파일. 저장 시 프로필 버전 및 별도 스냅샷 기록.
- 수집 메타의 `last_scanned`은 API에서 읽은 행 수, `last_count`는 제목 기반 관심공고 수이며 전체 유효 공고 수/수주 대상이 아니다.
- 식별자 `G2B-{bidNtceNo}-{bidNtceOrd}`: 원문 차수별 보존. 동차수 메타 수정은 목록 항목 갱신, 사용자 결정/이력 유지. 취소는 **취소로 자동 전환하지 않는다**.
- `source_url`은 공식 HTTPS g2b.go.kr 링크로 검증되는 경우만 화면 제공. 원문/RFP·자격/실적·사업원가·점수는 빈값/미확인 표시.
- 이름 키워드 필터는 탐색의 임시 베이스라인으로 누락 가능성이 있고 재현율 검증 전. 개인회사 실적/비공개 내부자료 자동 수집/외부 모델 전송은 미실시.

## 남은 출시 게이트

실제 API key와 샘플 확보, 정정/취소/마감 시간 신뢰성, 호출 쿼터, 실제 공고 원문 안전한 처리, 신규 수집/의사결정 사용자 UX, 테스트 및 AGY/Codex 독립 최종 리뷰 완료 이전에는 public 공개·main 병합하지 않는다. 현재 구현은 로컬 수직슬라이스이며 정기 스케줄러나 AI 자동판정 완료가 아니다.
