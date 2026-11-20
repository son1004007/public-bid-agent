# 서버 사용자별 공식 CLI 격리·파일/프로세스/네트워크

- 작업 ID: AGW-02
- 상태: DESIGN_READY / IMPLEMENTATION_NOT_STARTED (GitHub 문서만 작성)
- 범위: public-bid-agent AI Gateway 실행기 설계. 참조 [작업 목차](README.md), [상위 세션 설계](../../server-migration/16-user-cli-session-and-blind-cross-check.md).
- 실행 정책: 중앙 CONTROL 및 대상 AGENTS 우선, 실제 회사 자료·외부 호출·data1 운영 배포는 승인 이전 차단, 별도 AI 코드 리뷰는 선택·기능/보안/회귀 검사는 필수.

## 목적
서버에 사용자가 로그인한다는 요구가 OS 차원에서 다른 사용자의 Codex/Claude 자격증명과 세션 기록을 볼 수 없음을 전제로 합니다. 기존 data1의 실제 운영 container/port/볼륨은 건드리지 않습니다.

## 실행 토폴로지
Django/DRF → Celery job/outbox → AI Gateway scheduler → 허용된 사용자별 sandbox-runner → 해당 사용자 공식 CLI.
- 웹 user UUID를 OS 실행 identity/container에 일대일 매핑합니다. 사용자별 UID·파일 namespace/credential store를 격리하고, provider별 persist home을 분리합니다.
- 추천 마운트: (1) 공개/승인 근거의 불변 snapshot read-only, (2) 해당 사용자·provider만 접근 가능한 session/auth home, (3) 신규 job 전용 일시 output. 호스트 Docker.sock/SSH key/관리자 home/postgres 자격 증명 마운트 불가.
- provider별 설정 환경변수는 실제 버전 및 공식 도움말로 확인. CODEX_HOME, HOME 등 설정 가능성은 실측 없이 확정하지 않습니다.
- CLI가 임의 명령·파일·MCP 도구를 실행하지 못하도록 전용 workspace, tool permission 제한과 non-root OS/cgroup/FS 정책 적용. '읽기 전용 프롬프트'만으로 sandbox 대체 금지.
- subprocess shell=False, exec allowlist, argv 고정, 입력 데이터는 stdin 또는 안전한 파일로 전달. 사용자 입력을 명령 인수에 임의 삽입하지 않습니다.
- 리소스 제약: 요청당 timeout, 출력 바이트 상한, CPU/memory/process limit, egress 허용 대상과 로그 리다이렉션 제한. 계정 로그인 공식 흐름이 접근해야 할 도메인도 조직 승인 전에는 차단합니다.

## 잠금·보안 경계
- 동일 SessionBinding에 대해 단일 lease만 부여합니다. 워커 중단 시 lease 만료·fencing token이 이전 실행기를 무효화합니다.
- OS 계정↔웹 user 매핑 변경 시 기존 home/session 재사용 금지; 사용자 퇴사·계정 잠금은 즉시 신규 작업 BLOCKED, 저장 세션은 감사 규칙 하 보존.
- 콘솔/로그는 사용자에게 성공/실패 이유 코드만, 토큰/기기코드/프롬프트 전문/환경변수/직원별 자료는 노출 금지. login CLI가 출력하는 기기 코드도 일반 감사 로그 금지.
- CLI가 내부 사설 IP/메타데이터/사내 네트워크를 임의 접속하지 못하도록 egress 정책 및 proxy 정책 설계.

## 실패 선제 대응
- CLI 도구 실행 오류/권한 상승 요구: CONFIG_BLOCKED; 보안 예외로 전체 root 실행 금지.
- 컨테이너 재생성: persistent user+provider home 및 session id만 복원, 기존 credential 접근 권한 재검증.
- 사용자 A가 B의 CLI session id를 입력: 서버 소유권 거부 + sandbox 읽기 불가.
- OS 정책으로 login 불가: 개인 계정 패스워드를 DB에 대신 보관하지 말고 허용된 인프라 경로 재설계.

## 검증/수용
- 두 테스트 사용자×두 공급자 home 격리, symlink traversal, 작업 디렉터리 탈출, stdout 누출, 무허가 egress, 30초 강제 timeout 후 child tree 정리, volume 복구, 동시 2 job race.
- 별도 격리 개발 runner에서 정책 통과 후 회사 승인된 배포 mapping·백업/복구·운영 자원 증거 필수. data1 직접 운영 설치는 HOLD.

## 구현 의존성/다음 작업
- 이 문서는 모듈 단위 설계이며 실제 엔드포인트·DB schema·CLI 명령이 구현된 상태를 주장하지 않습니다. 바뀐 계약/버전은 구현 시 증거와 함께 이 문서를 갱신합니다.
- 다음 작업은 [AGW 작업 인덱스](README.md)의 선행 의존 관계와 기존 [HBR 작업 원장](../../../TASKS.md)을 따릅니다.
