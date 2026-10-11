# 나라장터 인증키 자체 등록 UI 구현 계약 (2026-10-11)

## 출처 및 요청 규격

- 출처: 사용자 첨부 **조달청_OpenAPI참고자료_나라장터_입찰공고정보서비스_1.2.docx**, 2026.04.10 개정 내용 포함.
- 오퍼레이션 12는 `getBidPblancListInfoServcPPSSrch` (나라장터검색조건에 의한 입찰공고용역조회).
- 명세의 요청 필드명은 대소문자 포함 **`ServiceKey`**, `type`=`json`, `inqryDiv`=1(공고게시일시), `inqryBgnDt`/`inqryEndDt`=`YYYYMMDDHHMM`, `pageNo`, `numOfRows`. 기존 소문자 `serviceKey`를 수정.
- 공공데이터포털 공식 신청 페이지: https://www.data.go.kr/data/15129394/openapi.do. 신청/로그인/승인은 포털에서 사용자가 진행. 시스템은 내부 발급 자동화·OAuth 가정하지 않는다.

## 사용자 시나리오

1. 로컬 Windows PC에서 `/decision-preview` → 수집 관리로 이동.
2. 공식 사이트 버튼으로 직접 활용신청/발급 후 일반 키나 URL 인코딩 키를 비밀번호 필드에 붙여넣음.
3. 등록 버튼은 loopback/Origin/CSRF만 수락하고 서버가 형식검사 후 사용자 범위 Windows DPAPI 암호화 파일로만 보관. 브라우저 입력칸 즉시 지움.
4. 연결 확인은 기존 수집 API를 전체 페이지 실행하지 않고 `numOfRows=1` GET로 resultCode 00와 본문 존재만 검증. 공고 저장/자동 배치와 분리.
5. 필요 시 저장 키 삭제. 운영체제 환경변수 키는 삭제하지 않으며 이 경우 폴백 사실만 화면에 표시.

## 보안/실패 정책

- 키 평문을 GitHub/문서/로그/응답/브라우저 저장소/로컬 JSON에 저장하지 않는다. 암호문은 Windows LOCALAPPDATA 사용자 폴더 안에만 원자 저장하고 CryptProtectData의 사용자 범위(LOCAL_MACHINE 사용 금지)로 보호한다.
- 사용자 프로필/PC 변경, DPAPI 데이터 손상 시 fail-closed, 재등록 안내. Windows 외 OS는 웹 저장 미지원·환경변수만 사용. HTTP response에는 key/마스킹/마지막 글자/해시를 반환하지 않는다.
- 인증 확인 실패는 명세상의 20/22/23/30/31 등과 관계없이 사용자에게 안전한 오류만 반환하고 원격 URI/키를 노출하지 않는다.
- 대외 서비스·Google 멀티유저 로그인·키 공유 기능이 아니다. 로컬 임의 프로그램/브라우저 확장/OS 계정 탈취로부터의 완전한 보호는 제공하지 못한다. 독립 보안 검수 및 사용자 최종 승인 전 main merge/공개 배포 HOLD.
