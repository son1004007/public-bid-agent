# Public Bid Agent 로컬 RFP 배포 4건 수정 및 Codex 독립 재검수

- 날짜: 2026-10-13
- 개발 브랜치: feat/sprint1-search-demo
- 수정: d8b7007, 4077ff5
- 검토 범위: Windows 단일 사용자 개인 PC의 127.0.0.1 오프라인 배포/복구
- 사용자 운영 자료, 계정 인증정보 및 실제 RFP 원문은 외부 모델 입력·GitHub에 전송하지 않음

## 수정된 네 가지 결함

1. **서버 quiescence / 실행 중 승격 거부**: 서버가 `.rfp-server-lease.lock`을 서비스 수명 동안 독점 점유하며, 승격·롤백·복구 도구가 동일 잠금 획득에 실패하면 변경을 중단. GET/POST는 SQLite 미완료 배포 의도 발견 시 503으로 실패.
2. **Windows crash recovery**: `.rfp-release-intent.sqlite3`에 `synchronous=FULL`, DELETE 저널로 PREPARED/COMPLETED 기록. 기존 JSON 배포 저널도 유지. Windows `MoveFileExW` WRITE_THROUGH 및 POSIX 디렉터리 fsync, SHA-256 검증, JSON 두 파일 세대 불일치 복구 경로. 텍스트 저널이 유실되더라도 PREPARED SQLite 기록으로 기동 차단·명시적 복구.
3. **Junction/reparse/TOCTOU 경계**: 경로 컴포넌트 symlink·junction·reparse 거부, 읽기 전후 파일 ID 확인. Windows `CreateFileW(GENERIC_READ)`로 상위·대상 디렉터리 핸들을 잡고 FILE_SHARE_DELETE를 허용하지 않아 배포 동안 디렉터리 교체를 차단. 백업 및 RFP 캐시가 생성된 뒤에도 새 경로를 핀.
4. **중단된 백업 준비 복구**: `.backup-intent.json`으로 이전 live JSON SHA 고정, 모호한 파일·변조·완료된 백업 거부, 원본 상태가 일치하는 부분 백업만 안전하게 이어 복사.

## 실제 실행 증거

- 사용자 PC Windows Python 3.12 기존 + 신규 전체 테스트: 최초 수정 **226 PASS / 186.726초**, 경로 핀 보완 후 **227 PASS / 175.163초**.
- 실제 Windows 디렉터리 핀 아래 stage 디렉터리 이름 변경을 시도하고 OS 거부를 확인하는 테스트 PASS.
- GitHub Actions: [d8b7007 CI](https://github.com/son1004007/public-bid-agent/actions/runs/38347863332)와 [4077ff5 CI](https://github.com/son1004007/public-bid-agent/actions/runs/38348472312) 모두 success.
- 독립 Codex 1차: NO_GO — `reject_reparse` 확인과 실제 파일 조작 사이 경로 교체 위험.
- 독립 Codex 2차: **GO (localhost-only, trusted-single-user, offline release)** — `CreateFileW` 디렉터리 핀과 실제 Windows rename-denial 테스트를 코드 검토로 확인. 재검수 Codex는 소스만 읽었으며 테스트 자체는 실행하지 않았음.
- 물리적인 전원 차단·디스크 제어기 캐시 오동작은 실증하지 않았음. SQLite 내구성은 운영체제와 스토리지의 FlushFileBuffers/fsync 계약에 의존.
- 악의적인 동일 사용자 권한의 로컬 프로세스가 자식 파일을 변경하는 모든 위협까지 막는 보안 경계는 범위 밖이며, 현재 사용자 혼자 실행하는 개인 로컬 시연 범위로 한정.

## 운영/병합 경계

- 코드는 개발 브랜치에 반영. `main` 병합 및 외부 공개 배포는 이번 작업의 범위가 아님.
- 기존 TD-kiseok 8765 서버/실사용 원본은 새 코드로 교체하지 않음. 이미 반영된 RFP 70건은 불필요하게 재승격하지 않음.
- 새 코드로 오프라인 로컬 업데이트하려면 기존 서버를 종료하고, 최신 개발 브랜치를 로컬 앱 실행 경로에 적용한 뒤 개인 PC 데이터 폴더를 백업·검증하고 실제 Chrome GET 및 UI 확인을 별도 진행.
