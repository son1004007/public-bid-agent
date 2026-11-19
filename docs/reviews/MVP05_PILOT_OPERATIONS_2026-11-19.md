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
