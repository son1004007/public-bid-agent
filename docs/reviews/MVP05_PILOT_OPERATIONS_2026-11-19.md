# 사내 MVP 시범 운영 인계 (후보, 배포 승인 아님)

## 범위
- 사업부 지정 구성원만 입찰 공고 검토, RFP 수동/자동 후보 확인, 집계 손익 및 공동 판단.
- 개인 급여·계정 비밀·회사 정책·실제 서버 주소/접속 자료는 공개 Git에 기록하지 않는다.
- 기존 업무 서버 또는 기존 localhost 앱을 교체하지 않는다. 자동 수집/외부 AI/입찰 제출은 비활성.

## 순서와 책임
| 단계 | 확인 및 증거 | 책임 |
|---|---|---|
| 1 | PR #5 정확 SHA 전체 CI, 별도 문맥 독립 검수 GO | 개발/검수 |
| 2 | 기존 보안 조치 완료, 시범 대상/기간/사용자/접근범위 승인 | 운영 책임자 |
| 3 | 사업부 소속·원가 게시·최종 결정 권한 별도 지정, 집계 기간/MM/최소인원/가공 단위 확정, 승인된 공고/RFP 입력 경로 | 업무 책임자 |
| 4 | 전용 서비스 계정/DB/미디어 경로, 사내 HTTPS 및 인증서, 포트 충돌·방화벽·ACL 점검, 운영 WSGI/ASGI 서버와 고정 의존성 검증 | 운영 |
| 5 | 승인된 원본 DB+파일 일관 세대 백업, 외부 보관한 manifest/dump 해시, 격리 복구 및 이전 버전 복귀/새 쓰기 보존 계획 | 운영/개발 |
| 6 | 설치 전 후보 설정 check --deploy, migration 계획 확인; 승인된 격리 DB에만 migration 및 구성원/원가 기준 발급; read-only preflight | 운영/개발 |
| 7 | 지정 계정 내부 접속, 로그인→공고→근거→손익→의견/결정→재조회, 다른 사업부·철회·CSRF 음성 확인; 제한 pilot 후 피드백 | 업무/운영 |

아래 명령은 준비된 격리 환경의 승인된 운영자가 실행하는 예시다. 현재 대화에서 운영 서버에 실행하지 않았다. 실제 secrets/config는 Git 밖의 승인 환경에서 제공하고 로그 공유 전에 민감정보를 제외한다.

```sh
python server/manage.py check --deploy --settings=bid_server.settings.base
python server/manage.py showmigrations --plan --settings=bid_server.settings.base
python server/manage.py pilot_preflight --approved-read-only --settings=bid_server.settings.base
```

- Django 5.2 공식 배포 체크리스트: https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/ . runserver는 운영용 아님. 실제 WSGI/ASGI 및 ingress 설정은 대상 환경에 맞춰 승인·검증한다. Proxy 헤더 신뢰는 실제 ingress가 외부 헤더를 삭제/덮어쓴다는 증거 없이 설정하지 않는다.
- preflight의 CHECKS_PASS는 일부 설정/권한/현재 데이터 존재만 검사한 상태이며 TLS 실제 연결, 경로 ACL 전체, 회사 정책 적합성·공식 RFP 진위·CI/독립 검수·백업/롤백 승인 증거를 대체하지 않는다. production 설정만 허용, PostgreSQL read-only transaction, no write. --synthetic은 Django test DB에 한정한다.
- 기존 사용자 조치 및 독립 검수 미완료. 실제 회사 대상/접속·정책이 승인되지 않았으므로 실제 설치·환경 변경·원가 입력은 금지. 현재 상태 RELEASE NO_GO.


## 최초 업무 구성 발급 (후보)
승인된 운영자가 기존 계정 UUID와 사업부 UUID, 권한, 단일 기간 집계값을 비공개 JSON에 준비한다. 파일은 Git 밖 정규 파일(Unix 0600, Windows 승인 ACL), 독립 승인 원장의 SHA-256을 입력한다. 최상위 키는 department_id, expected_revision, members, basis. members 각 항목은 user_id, can_manage_cost, can_decide. basis는 period_start, period_end, valid_until, labor_total_krw, allocation_mm, available_mm, headcount, minimum_headcount, rate_rounding_krw, capacity_rounding_mm, approved_by_id. MM은 Decimal 문자열, 금액/인원은 정수, 날짜 YYYY-MM-DD. 실제 값과 승인 원장은 공개 Git에 기록하지 않는다.

```sh
python server/manage.py pilot_provision --plan /private/approved-plan.json --trusted-plan-sha256 APPROVED_SHA256 --settings=bid_server.settings.base
```
기본은 검증만 한다. 실제 승인·독립 검수·환경 확인 후 운영자가 --apply 추가 및 대화형 확인으로 최초 발급한다. expected_revision=0은 신규 사업부만 허용; 이후 동일 membership과 정확한 최신 revision을 제시하면 이전 기준을 보존하고 새 기준을 등록한다. 기존 사용자 생성/비밀번호 변경/업무 권한 변경은 이 명령의 범위 밖이다. 승인 기록·원가 구성/배부방식·적용 시각은 회사 지정 비공개 원장에 보존해야 한다. 최소 인원·반올림 값은 정책 입력이며 코드가 회사 정책을 인증하지 않는다. 시범 운영 승인 전 실행하지 않는다.


## NAS 합성 검증용 미리보기 결과
- 사용자 요청에 따라 4853ab2 후보를 실제 NAS에 별도 합성 인스턴스로 설치했다. 운영 DB·회사 데이터·기존 서비스를 사용하지 않는다. 로컬 화면/health 및 인증 없는 공고 차단 확인. HTTPS 경로 추가는 권한 거부, 현행 설정 불변. 별도 경로 승인 및 실제 인증 검증 전 접속 가능하다고 판정하지 않는다. 임시 실행 환경은 재부팅 후 지속성을 검증하지 않았다. 상세 서버 위치·계정·비밀번호는 공개 Git에 기록하지 않는다.
