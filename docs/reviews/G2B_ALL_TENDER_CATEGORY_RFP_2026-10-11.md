# 나라장터 전체 용역 수집·부서 관심 분류·공식 RFP/참가제한 검증 (2026-10-11)

## 사용자 요구 및 설계

제목 키워드만으로 선필터하면 관심 있는 용역을 누락할 수 있으므로 **용역 전체 수집** 후, 공공조달분류/공고상태/마감일·등록마감/첨부파일·RFP 추출본문 근거로 부서 관심 사업을 2차 분류. 실제 회사별 법적 입찰 가능 여부는 자격등록·면허·실적 자료가 없으므로 `UNVERIFIED`.

공식 근거: 사용자 제공 `조달청_OpenAPI참고자료_나라장터_입찰공고정보서비스_1.2.docx` 및 실제 2026-10-11 API 필드 표본. 고정 용역 API `getBidPblancListInfoServcPPSSrch`, 필드 `pubPrcrmntClsfcNm`, `infoBizYn`, `ntceKindNm`, `bidQlfctRgstDt`, `ntceSpecFileNm1..10` / `ntceSpecDocUrl1..10`. 개별 상세 면허/지역/e발주 첨부는 공식 3개 오퍼레이션으로만 조회.

## 실제 인증·수집 증거

- 사용자 발급 키는 Windows 현재 사용자 DPAPI에 등록되어 있으며 **키 값·요청 URL 출력·GitHub 저장 없음**.
- `POST /api/dashboard/collect {"days":7}`: SUCCESS, 원본 2,225행 스캔, 공고번호+차수 중복 제거 후 **2,223개 고유 공고 로컬 저장**, 기존 제목필터 275건 모두 보존. 2,011건에 공식 첨부 링크.
- 최초 느슨한 분류: CANDIDATE 317 / REVIEW 1,906. 범용 '개발/구축/고도화'의 단독 SW 오탐을 줄인 후 POST `/api/dashboard/reclassify` **2,223건 로컬 재분류**: CANDIDATE 143, REVIEW 2,080.
- 앱 기본 목록은 부서 관심 후보 + 취소/마감 제외 = **125건**. 사용자가 화면에서 `전체/마감·취소 포함` 및 `분야 전체/누락 방지`를 고르면 전체 **2,223건** 표시. 데이터 삭제/판단 변경 없음.
- 최초 수집 메타기준 상태 OPEN 1,651 / REGISTRATION_REVIEW 6 / UNKNOWN 250 / CLOSED 204 / CANCELLED 112. 이 상태는 시간·메타데이터 기준이며 실제 업체 참가자격과 다름.
- 기존 `cases.json` 5개, 실제 담당자 Bid/No-Bid 이력 0건 보존.

## 실제 RFP/첨부 추출

- `G2B-R26BK01747983-001` 산업용 무선통신망 통합관제 NMS 소프트웨어 개발 용역의 공식 PDF 제안요청서 **6,284자 추출 SUCCESS**. 공공조달분류 SW에 더해 RFP 텍스트 근거로 AI/DATA 분류 확인.
- 별도 명시적 POST `/api/dashboard/enrich-batch` 초기 시범 5건 중 4건 텍스트 추출 성공·1건 실패. 당시 대상에 불필요한 일반 행사용역이 포함된 문제 확인, 이후 일괄 추출을 `CANDIDATE` + 사용자가 선택한 부서카테고리 + 마감 전 + 관련 제안요청서/과업지시서 우선, 5건 상한으로 수정.
- 현재 실 저장 `EXTRACTED` 5건, 실패 1건, 나머지는 문서 본문 미추출. **2,223건 전체 RFP가 파싱되었다는 주장은 금지**.
- 기존 공개 official g2b.go.kr HTTPS만 접근, redirect 거절, 용량 최대 8MiB, subprocess 추출/최대 12,000자 보존, 외부 AI 전송 없음.

## 공식 참가제한 추가 조회

- `/api/dashboard/related`로 공식 3개 API: `getBidPblancListInfoLicenseLimit`, `getBidPblancListInfoPrtcptPsblRgn`, `getBidPblancListInfoEorderAtchFileInfo` 조회, 저장된 공고번호/차수 한정.
- **실 공고 `G2B-R26BK01747983-001` HTTP SUCCESS**, `related_status=FETCHED`, license list 0건, region list 0건, 기존 첨부 2건 유지. 구체적인 제한 목록이 없더라도 **실회사 법적 자격은 UNVERIFIED**.
- 각 API 오류/부분결과는 저장하지 않으며 기존 담당자 판단/공고를 보존.

## 검증 및 품질

| 항목 | 결과 |
| --- | --- |
| Windows CPython 3.12 전체 unittest (신규 상세/HTTP/보안 경계 포함) | **93 PASS** |
| JavaScript 로컬 및 CI syntax 검사 | PASS |
| GitHub CI `09e95ea` Push | [SUCCESS](https://github.com/son1004007/public-bid-agent/actions/runs/38117518610) |
| GitHub CI `09e95ea` PR | [SUCCESS](https://github.com/son1004007/public-bid-agent/actions/runs/38117521593) |
| Chrome 실제 공고 2,223건 로딩·기본 후보 125건·부서 설정·전체 데이터 필터 | PASS |
| Chrome 실 공고 검색 / 공식 RFP 첨부·추출문단 상세 표시 / 8개 필수조건 미검증 | PASS |
| Chrome 공식 면허/지역/e발주 별도 조회 버튼 표시 및 기조회 근거 | PASS |
| 실제 Chrome 브라우저 E2E | **7 PASS** |
| 실제 8765 Python 서버 최신 코드 재시작, user JSON hash | 기존 cases.json 및 dashboard.json 변경 없이 PASS |
| 실제 사이트 키와 출처 | 본인 로컬 DPAPI, API와 링크만. 키 비노출 |

## 남은 범위 및 게이트

- 관심 카테고리 AI/SW/DATA/SECURITY는 사용자가 수정 가능한 **초기 기본값**이지, 실제 부서의 승인된 상세 업무 분류를 대표하는 정보가 아님.
- **실제 나라장터 참가자격 '가능' 판정 미완료**: 업체의 보유 업종코드/면허/실적/지역/입찰자격 증빙이 없고 공식 목록도 실 회사 자격이 아니므로, 검토 가능성/마감상태까지만 분리한다.
- 신청/취소/정정 차수의 전수 법적 영향 검증, RFP 전체 자동 배치, 문서유형 미지원, Codex 근거 분석, 실제 입찰 제출/예약수집 미구현.
- 안전한 로컬 구현 단계. 독립 AGY/Gemini·Codex 최종 의미/보안 검토와 사용자 UX 승인은 **NOT RUN**; PR #1 **Draft**, main 병합 및 외부 공개 HOLD 유지.
