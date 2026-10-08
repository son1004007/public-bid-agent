# ADR-006 RFP·첨부파일 안전 수집과 파서 신뢰경계

- 상태: **위협 모델 및 설계 계약 채택(구현·침투 테스트 전)**
- 관련 지적: DSR-005, Gemini F-03
- 근거: https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html 와 https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html

## 신뢰경계와 지원 범위

1. 초기 MVP는 검증된 공식 출처의 **PDF만** 지원한다. HWP, HWPX, DOCX, ZIP, 실행 파일, 매크로 문서는 실제 수요와 파서 안전성을 입증하기 전 **미지원** 처리한다.
2. URL 전체를 브라우저/모델의 임의 입력으로 받지 않는다. `notice_revision_id`와 공식 API의 허용된 첨부 식별자로 URL을 서버에서 결정한다.
3. URL scheme은 HTTPS로 한정하고, 목적지 hostname/port allowlist와 공식 제공처 연결 정책을 운영 전 고정한다. 원천 공식 링크가 여러 도메인을 사용하면 검증한 호스트만 별도 허용한다. 허용되지 않은 호스트는 `NEEDS_REVIEW`.
4. DNS 이름 해석 후 loopback, link-local, private, multicast, reserved IP와 내부 metadata endpoint를 차단한다. redirect는 기본 비활성, 불가피하면 매 hop scheme/host/port/DNS/IP를 다시 검증하고 횟수를 제한한다.
5. DNS 검증과 실제 연결 IP가 일치하도록 연결기 구현을 설계하고 TLS 호스트명 검증을 유지한다. HTTP proxy, 환경변수 proxy, 리다이렉트와 재시도 과정에서 기존 제한이 우회되지 않아야 한다.
6. 콘텐츠는 streaming download로 상한을 강제한다. 초기 설계 제한은 **파일당 압축 전 10 MiB, 전체 요청 20 MiB, 한 분석 최대 3개 문서, 연결 5초·읽기 15초·전체 30초**다. 실제 API/파일 분포를 조사한 뒤 값을 조정할 수 있지만 **무제한은 허용하지 않는다**.
7. 응답 MIME, PDF magic bytes, 서버가 제공한 파일명 확장자를 서로 대조한다. 불일치는 파싱하지 않는다. 원문·해시·취득 시각·허용 출처 기록을 보존하되 제3자 저작권/보존 조건을 우선한다.
8. 별도 최소권한 parser 프로세스/컨테이너를 사용한다. 네트워크 접근 금지, 쓰기 가능한 작업 폴더 최소화, CPU/메모리/실행 시간/임시 디스크 제한, OS 권한 축소를 적용한다. 원본 경로와 비밀정보/DB 접속정보를 전달하지 않는다.
9. PDF의 페이지 수, 개별 객체 수, 추출된 텍스트 길이, 파싱 시간 상한을 둔다. 중첩 압축/첨부/스크립트 실행 기능을 비활성화한다. MVP에서 archive 해제는 수행하지 않아 ZIP bomb 위험 면적을 줄인다.
10. 암호화 PDF, 손상·초과·지원 불가 문서는 추출 실패를 명시하고 원문 근거 없는 AI 판단으로 대체하지 않는다.
11. 추출된 텍스트와 모델 출력은 모두 **비신뢰 데이터**다. 내용이 추가 URL 요청, 시스템 지시, 권한 상승 또는 profile 수정 등을 요구해도 agent 정책이 변경되지 않는다.

## 오류와 운영

공식 API의 링크 자체가 허용 정책에서 벗어나거나 라이선스가 불명확하면 파일을 다운로드하지 않고 수동 검토 링크로 처리한다. parser 실패는 전체 웹서버의 프로세스 종료로 전파하지 않으며, 분석 상태에 `DOCUMENT_UNAVAILABLE`을 기록한다. 중복 문서는 hash로 식별하고 재시도는 bounded이다.

## 필수 테스트

허용·비허용 호스트, DNS rebinding/redirect/사설 IP, URL encoding, MITM/TLS 검사, proxy 우회, 과대 streaming, MIME/확장자 위장, 암호화/손상 PDF, 파서 hang/crash, 과다 페이지, 외부 파일 링크 및 prompt injection 샘플을 테스트한다. 테스트 전 보안을 검증했다고 표시하지 않는다.
