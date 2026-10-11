# 제목 누락 방지·원문 중심 부서 관심 용역 분류 (2026-10-11)

공식 근거: 사용자 첨부 조달청_OpenAPI참고자료_나라장터_입찰공고정보서비스_1.2.docx. 입찰공고용역 검색 getBidPblancListInfoServcPPSSrch(요청 ServiceKey) 응답에 pubPrcrmntClsfcNm, pubPrcrmntClsfcNo, infoBizYn, ntceKindNm, bidClseDt, bidQlfctRgstDt, indstrytyLmtYn, bidPrtcptLmtYn, ntceSpecDocUrl1~10/ntceSpecFileNm1~10, bidNtceDtlUrl 포함. 별도 API getBidPblancListInfoLicenseLimit, getBidPblancListInfoPrtcptPsblRgn, getBidPblancListInfoEorderAtchFileInfo는 추가 연동 후보.

1차: 전체 용역 원본을 저장하고 메타데이터 taxonomy와 파일명/제목, 마감/취소를 보수적으로 판단. 모든 공고 ID(번호+차수)를 보존한다. 정보화사업 여부만으로 SW 개발 확정하지 않으며 업종/입찰참가제한 여부만으로 법적 참가자격 충족 주장하지 않는다.

2차: 공고별 RFP 첨부의 공개 g2b HTTPS URL에서 한 문서를 명시적 클릭 시 8MiB/12초 제한으로 내려받고 기존 추출기를 subprocess에서 호출한다. 본문 추출을 성공하면 최대 12,000자에서 분야 분류를 갱신한다. 위험 URL/리다이렉트/미지원 문서는 FAILED/확인필요 상태로 기록한다. 최대 5건 batch는 사용자가 클릭해야 실행된다. 비공개 회사 자료/AI 모델로 전송하지 않는다.

부서 분야 AI/SW/DATA/SECURITY의 선택·미분류 포함 여부는 별도 JSON 설정으로 저장한다. 목록 기본 필터는 관심후보·검토대기 및 마감 전/마감 미확정이며 전체/마감/취소 공고도 검색할 수 있다. 화면 필터 적용 여부는 수집 DB와 개별 사람 판단 이력에 영향을 주지 않는다.

한계: 실제 업체 업종등록/실적/지역 조건 판정 미구현, 첨부 전체 자동 분석 미구현, 정정/취소 전체 이력·공식 면허 지역 API 연동 미구현. 사용자가 관리하는 법적 자격과 AI 추천이 혼동되지 않게 구분한다.
