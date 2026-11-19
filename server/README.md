## 2026-11-19 security review: local launcher and recovery contract (candidate)

- Windows loopback staging uses `scripts/start_web_service.ps1`. Preprovision the existing private signing-key file and DB JSON outside Git with restrictive ACLs. The launcher no longer generates keys implicitly, accepts no plaintext `BID_LOCAL_SECRET_KEY`, and validates settings before binding 127.0.0.1:8000. DB JSON must contain exactly HOST, PORT, NAME, USER, PASSWORD; host must be a numeric loopback, not a remote endpoint. Actual local DB name, Windows ACL and listener must be checked before deployment.
- Local artifact storage now requires the explicit process environment variable `BID_LOCAL_PRIVATE_MEDIA_ROOT`, set to the preprovisioned dedicated `%USERPROFILE%/PublicBidAgent-private-media` directory. No fallback to LocalAppData or the separate evidence directory. The Windows launcher checks DACL inheritance, trusted principals, parent mutation rights and reparse points. Use `scripts/start_web_service.ps1 -ValidateOnly` to check settings and ACLs without starting the server. Direct runserver invocation is not a substitute for the launcher ACL check. Backups must use the same explicitly configured root; never assume the historical LocalAppData location. Existing ACLs, data and credentials must not be silently changed.
- Backup generations use unique directories outside Git, reject overlapping/symlink storage roots and do not overwrite existing bundles. Stop writes or use an approved coordinated snapshot for DB + storage; a DB snapshot plus a file copy is not proof of a consistent storage generation.
- Restore rehearsal now requires `--trusted-dump-sha256` from an independently approved record (or `trusted_dump_sha256=` for Python callers), not a digest copied from an untrusted manifest. Only trusted source/admin dumps may be executed in an isolated cluster. PostgreSQL documents arbitrary-code risks: https://www.postgresql.org/docs/17/app-pgdump.html. This check is not a sandbox or signature; an attacker who controls the approved digest or source can still compromise restore.
- Synthetic tests require explicitly configured SM03_TEST_DB_CONFIG_FILE and no longer fall back to the workstation's DB. Foundation and Sprint 1 workflows pin upstream action revisions and disable persisted checkout credentials; other workflows and dependency inventories still need review. GitHub guidance: https://docs.github.com/en/actions/reference/security/secure-use.
- This is a source candidate, not evidence of successful local launch, recovery, independent review or current-head CI. See CURRENT_STATE.md.

# Isolated Django server foundation

SM02 구현 범위: Django/DRF 설정, 공통 API envelope, 안전 오류, process health와 정적 OpenAPI. 기존 local_app과 backend의 패키지/데이터/설정을 변경하지 않는다. SM03 DB 세션 인증과 최초 암호 변경 게이트를 구현했다. 실제 운영 계정/업무/수집/모델/DB 이관은 없다.

## 설치와 단위 검사

CPython3.12.x 전용 별도 venv를 Git 밖에 만든다. 기존 환경에 설치하지 않는다. Windows PowerShell 예시:

```powershell
$sm02Venv = Join-Path $env:LOCALAPPDATA 'PublicBidAgent/sm02-venv'
py -3.12 -m venv $sm02Venv
$sm02Python = Join-Path $sm02Venv 'Scripts/python.exe'
& $sm02Python -m pip install --only-binary=:all: --require-hashes -r server/requirements-dev.lock
& $sm02Python -m pip check
& $sm02Python server/manage.py check --settings=bid_server.settings.test
& $sm02Python server/manage.py test tests --settings=bid_server.settings.test --verbosity 1
```

Linux에서도 외부 venv의 Python으로 동일 manage.py 명령을 사용한다. test 설정은 랜덤 메모리 키와 접속 없는 메모리 SQLite 선언만 사용하고 외부 env/실제 secret을 읽지 않는다. SimpleTestCase에서 DB 호출은 금지다. 테스트 설정을 운영에 사용하지 않는다. 실제 PostgreSQL 연결과 migration은 검증하지 않았다.

## 버전과 잠금

Django5.2.19 LTS, DRF3.18.3, psycopg[binary]3.3.9. 직접 요구는 requirements.in, 전이 버전과 PyPI artifact SHA-256은 requirements.lock에 고정한다. dev lock은 runtime lock과 jsonschema4.26.0 및 전이 의존성을 포함한다. 이미 설치된 패키지의 hash를 pip가 재검사하지 않을 수 있으므로 이번 검증은 force-reinstall/only-binary/require-hashes로 수행했다.

버전 변경은 격리 venv에서 .in 변경→resolver 결과 확인→전이 버전과 공식 PyPI hash 목록 재생성→새 manifest/보안 확인→전체 회귀와 독립 검수로 수행한다. lock 파일을 운영 환경의 pip freeze로 덮어쓰지 않는다. Windows x64와 Linux x64용 binary wheel을 대상으로 CI를 정의했으며 Linux 실행 성공은 별도 확인한다.

패키지 라이선스는 dependency-manifest.json, PyPI advisory 확인은 dependency-audit.json을 참고한다. psycopg 패키지는 LGPL-3.0-only이며 native bundle/libpq/OpenSSL 등의 이미지 배포 고지는 별도다. 이번에는 wheel을 공개 저장소에 복사하거나 컨테이너 이미지를 배포하지 않았다. 라이선스 메타데이터 확인과 모든 재배포 의무 충족은 다르다.

## 실제 설정 로더

.env.example은 입력 이름과 형식의 참고용이다. 자동 .env/ini loader는 없다. Python 환경변수에서 값을 읽고 secret은 *_FILE만 허용한다. DJANGO_SECRET_KEY/DATABASE_PASSWORD/REDIS_URL 평문 env는 빈값이어도 거부한다. 동일 목적의 파일과 평문 중복도 거부한다.

기본 settings는 bid_server.settings.base. 필수 항목:

| 변수 | 계약 |
|---|---|
| APP_ENV | production 기본, 명시 development는 loopback Host/origin만 |
| APP_ALLOWED_HOSTS | wildcard/URL/port 없는 명시 Host 목록 |
| APP_CSRF_TRUSTED_ORIGINS | production은 HTTPS origin, path/query/credential 금지 |
| DJANGO_SECRET_KEY_FILE | 저장소 밖 절대 경로, 정규 파일, UTF-8, 최대4096byte, 키50자/다양한문자 |
| DATABASE_HOST/PORT/NAME/USER | 명시 PostgreSQL 설정, PORT 기본5432, 접속 시도 없음 |
| DATABASE_PASSWORD_FILE | 같은 비밀 파일 경계, 암호를 로그에 출력하지 않음 |
| DATABASE_SSLMODE | production verify-full, 개발 disable/require/verify-full. 실제 DB 인증서는 운영 계약에서 확인 |
| PRIVATE_MEDIA_ROOT | 저장소 밖 절대 경로. startup에서 폴더/파일을 생성하지 않음 |
| REDIS_URL_FILE | 선택 사항. 형식 검사만 하며 broker 연결 없음 |
| PUBLIC_BID_POLICY_SOURCE_FILE | 선택 읽기 전용 설정 경로. loader가 조직 정책을 읽거나 준수 여부를 확정하지 않음 |

비밀 파일은 읽기 권한이 제한된 계정만 접근해야 한다. POSIX는 group/other mode를 거부하고, Windows는 이식 가능한 POSIX mode 대신 운영자가 ACL을 관리한다. symlink/정규 파일 아님/잘못된 UTF-8/크기 초과/내부 개행은 거부한다. 오류는 변수명만 표시하며 값과 파일 경로를 포함하지 않는다.

production은 DEBUG=False, HTTPS redirect와 Secure cookie/CSRF를 사용한다. forwarded header 신뢰 설정은 ingress 검증 전 활성화하지 않는다. 실제 domain/TLS/DB certificate/secret 배포는 이번에 설정하지 않았다.

설정 검사가 성공한 development 환경에서만 다음과 같이 별도 loopback 포트로 실행한다:

```text
<isolated-python> server/manage.py runserver 127.0.0.1:8870 --noreload
```

기존8765를 대체하지 않는다. test settings로 외부 바인딩하거나 개발 runserver를 운영 서버로 사용하지 않는다.

## API 계약

- GET /api/v1/health → {data:{status:"ok",scope:"process"},request_id}. 익명 liveness이며 DB/인증/모델 readiness가 아님.
- HEAD /api/v1/health → 같은 안전 headers, body 없음.
- 그 외 route는404. trailing slash 자동 redirect 없음. 기본 API permission은 SM03 전까지401로 닫고 health만 AllowAny.
- DRF view는 원시 data를 반환하면 renderer가 한 번 감싼다. 목록은 PageResponse를 사용해 page.next_cursor/total을 추가하며 불명 total은null.
- 잘못된 JSON400, 필드 의미422, 미디어415. Django Host/URL/CSRF/크기/500도 error/code/message/fields/retryable/request_id JSON.
- request_id는 서버 UUID이며 요청 헤더를 재사용하지 않는다. 응답 X-Request-ID와 일치한다.
- 모든 오류 메시지는 고정되며 필드 상세는 현재 _schema/INVALID_VALUE 수준이다. 원문이나 민감 값이 포함된 DRF 오류를 그대로 전달하지 않는다.
- 허용 밖 method405, 응답 negotiation406. JSON body1MiB 한도, body 변경 method는 Content-Length 필수411. 제한된 읽기와 CSRF/parser의 bytes 재사용.

Django ASGI의 사전 body 수신과 ingress transport 한도는 이 middleware만으로 제한할 수 없다. 운영 ingress 제한, 실제 ASGI/부하/DB 테스트와 인증/최초 암호 변경 구현은 후속 단계다.

OpenAPI3.1 원본은 openapi.json. 실제 JSON 응답을 공통 schema로 검증한다. document 자체의 외부 OpenAPI validator와 실제 PostgreSQL 통합은 아직 별도다. 세션/업무 endpoint를 구현했다고 해석하지 않는다.

## 검증과 CI

tests/는 합성 파일과 HTTP fixture만 사용한다. 테스트 전용 URL은 production urls에 포함하지 않는다. 실제 loopback WSGI smoke는 임시 포트에 한정하고 종료한다. 새 Server foundation CI는 Linux/Windows3.12에서 같은 명령을 실행하도록 정의했다. 파일 존재를 Actions SUCCESS로 보고하지 않는다.

상세 결과와 미완료는 [SM02 기록](../docs/server-migration/28-sm02-server-foundation.md)을 따른다.


## SM03 DB 세션 인증

[설계와 검증29](../docs/server-migration/29-sm03-authentication.md). AUTH_USER_MODEL=accounts.User를 첫 migration부터 사용한다. 기존 Django auth 테이블에 뒤늦게 대체 적용하지 않는다. `migrate --plan`과 백업/복구 검증 후 운영자 승인 환경에만 migration한다. 이번 작업은 임시 합성 DB만 사용한다.

| API | 계약 |
|---|---|
| GET /api/v1/auth/csrf | masked CSRF token과 cookie 발급 |
| POST /api/v1/auth/login | username/password, CSRF 필수, session과 CSRF 회전 |
| GET /api/v1/auth/session | 본인 사용자/허용 기능/access/auth_epoch |
| POST /api/v1/auth/change-password | current_password/new_password/expected_auth_epoch, 원자 갱신 후204 및 재로그인 |
| POST /api/v1/auth/logout | CSRF 필수, 빈 JSON, 세션 폐기204 |

must_change_password 계정은 csrf/session/change-password/logout만 사용할 수 있고 health/미등록 경로/admin도403 PASSWORD_CHANGE_REQUIRED다. 다른 사용자 API는 이번 범위가 아니다. 익명 health는 liveness만 제공한다. director/lead는 업무 역할이며 기술 is_superuser와 독립이다. 익명 로그인에도 CSRF가 필요하고 APIView의 csrf_exempt로 우회하지 않는다.

임시 암호24시간, 제한 세션15분, 유휴30분, 절대8시간. 암호12~128자, 공통/숫자 전용/사용자정보 유사/현재 암호 재사용을 거부한다. 변경 시 이전 성공 결과/사용자 자료를 건드리지 않고 모든 이전 인증 세션을 epoch/hash로 무효화한다. 응답 유실은 rollback과 다르며 암호를 자동 재전송하지 않는다.

실패 제한은 DB의 HMAC IP/계정+IP bucket에15분 pair5/IP20. 원격 proxy 헤더를 신뢰하지 않는다. 실제 ingress 확정 시 trusted proxy와 제한 정책을 별도 검증해야 한다. 성공해도 IP 실패 횟수는 초기화하지 않는다. bucket 정리/장기 감사 보관은 운영 전 정책 확정이 필요하다.

보안 필드 수정은 User.save/행 잠금 서비스 경로를 사용한다. QuerySet.update, bulk_update, raw SQL로 암호/역할/활성/epoch를 수정하는 운영 코드를 추가하지 않는다. 향후 실제 결정/관리 API는 권한과 epoch를 변경 transaction 안에서 재대조해야 한다. 현재 A02는 합성 보호 endpoint 검증이다. 자동 계정 생성/고정 초기 암호/public signup/admin URL은 없다.

SQLite 합성 회귀:

```powershell
python server/manage.py test tests --settings=bid_server.settings.test --verbosity 0
python server/manage.py makemigrations --check --dry-run --settings=bid_server.settings.test
```

실제 PostgreSQL 잠금 검증은 저장소 밖 `SM03_TEST_DB_CONFIG_FILE`에 HOST=127.0.0.1, PORT, NAME=sm03_*와 USER/PASSWORD를 담아 격리 cluster를 지정하고 `--settings=bid_server.settings.test_postgres`로 실행한다. 암호를 명령줄에 직접 넣거나 파일을 Git에 추가하지 않는다. runner는 test_sm03_* DB를 생성/삭제한다. 실제 운영 DB를 지정하지 않는다. SQLite skip 결과는 PG 잠금 통과가 아니다.
