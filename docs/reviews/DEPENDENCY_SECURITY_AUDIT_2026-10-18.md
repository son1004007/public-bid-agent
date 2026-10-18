# 2026-10-18 Python/npm 의존성·취약점 검사

## GitHub 독립 실행 검증

- 구현·문서 커밋 `d63adbbf4c6f8bcbbf7d7a2141f51c7a2fc95d0d` (개발 브랜치). Codex 최종 독립 재검수 **GO**, 첫 NO_GO 2건 보완.
- [GitHub Sprint 1 CI 39113379131](https://github.com/son1004007/public-bid-agent/actions/runs/39113379131): **SUCCESS**. Python 감사 7개 합성 회귀, 프런트엔드 정확한 잠금 설치, npm High 이상 차단, 타입 검사/빌드 포함.
- [GitHub Windows 합성 인수 39113379117](https://github.com/son1004007/public-bid-agent/actions/runs/39113379117): **SUCCESS**. localhost API 보안·복구/Chrome 합성 E2E.
- 본 공급망 작업으로 실제 `127.0.0.1:8765` 서비스 원본을 교체하지 않음. 최종 소스 P09 `f06a3fa`, 이전 P07 자동 재배포 작업 비활성화, 서비스 HTTP 200 재확인. 사용자 자료 변경 없음.

## 범위와 상태

- 독립 Codex 최신 읽기 전용 재검수 **VERDICT: GO**. 첫 NO_GO 2건(플랫폼 직접 marker/선택 extras 누락) 보완 후 실제 경계·순환 extras·잠금 파일 일치 재검증. Codex 자체의 패키지 설치/OSV/npm 재스캔은 NOT RUN이며, 아래 명시한 Windows 직접 실행 근거와 구분.
- 상태: **Python 직접 요구조건 10/10 충족**, pip check PASS; Python 51개 설치 목록과 의존 그래프 수집, OSV PyPI 48개 조회 결과 반환된 취약점 0건. **npm 21개 컴포넌트 CycloneDX 1.5 생성, npm audit 0건**, React Vite 7.3.7 빌드 PASS.
- 개발 브랜치: `feat/sprint1-search-demo`. `main` 병합과 공개 릴리스/서버 재배포는 수행하지 않음. Python 실행 서비스 코드·기존 로컬 운영 데이터 변경 없음.
- 개발 PC의 분석 결과는 `AgentRunner` 아래에만 저장하고 공개 저장소에는 스크립트·비식별 집계와 이 보고서만 보관한다.

## 원인과 조치

1. Python 가상환경에서 `local_app/requirements.txt`를 실제 배포 패키지 51개의 메타데이터와 비교. 직접 패키지 10개 설치·버전 범위 모두 충족, 48개는 직접·전이 경로로 연결, 3개는 환경 전용. `pip check` 의존성 모순 0.
2. `scripts/audit_python_environment.py`로 로컬 설치 패키지 이름·버전·직접/전이 구분·표준 `License-Expression` 또는 구형 라이선스 주장값을 재현 가능하게 수집. 명시된 버전 요구조건이 누락/불일치하거나 패키지 요구사항 메타데이터를 일부 파싱하지 못하면 exit 2, 이미 있는 결과 파일은 덮어쓰지 않음. 독립 Codex 최초 NO_GO 두 건(플랫폼 조건부 직접 요구사항과 extras 전이 누락)을 수정하고, 플랫폼/Python marker·직접 및 중첩 extras 경로 3건을 더한 총 7개 회귀를 통과함. `scripts/test_audit_python_environment.py`는 합성 입력으로 버전 불일치/누락·의존 그래프·경로 비노출 7건 회귀 PASS.
3. OSV `/v1/querybatch`에 Python **공개 배포 패키지 이름·버전만** 조회. 48개에 반환된 취약점 0. 공급망 보안·미공개 취약점·OSV 미수록 이슈까지 없는 것으로 주장하지 않음.
4. React 시안은 `frontend/package-lock.json`이 없었고, 최초 `npm audit`는 `Vite 7.1.12`에 높은 심각도의 권고를 보고. [파일 시스템 우회](https://github.com/advisories/GHSA-fx2h-pf6j-xcff), [WebSocket 파일 읽기](https://github.com/advisories/GHSA-p9ff-h696-f583) 등이 연관됨. 동일 7.x인 `vite 7.3.7`에 정확히 고정하고 잠금 파일 생성. 새 `npm audit --package-lock-only --json`: **0/0/0/0**(low/moderate/high/critical). `npm ci --ignore-scripts`와 `npm run build`: 성공.
5. `npm sbom --sbom-format cyclonedx`: CycloneDX 1.5, 컴포넌트 21개. 서드파티 공시 정합/스캔 범위는 npm 의존성만 해당. GitHub `Sprint 1 CI`는 `npm ci --ignore-scripts`로 고정 잠금 설치를 수행하고 `npm audit --package-lock-only --audit-level=high`으로 새 High 이상 보안 권고를 차단한다. Python 감사 도구의 합성 테스트는 개발 의존성 `packaging>=26,<27`과 함께 CI backend job에서 실행한다.
6. Tesseract 바이너리 `5.5.3.20260724`, kor/eng 언어팩 설치 확인. 실제 OCR·원본 PDF/HWP 정확도와 별개.

## 재현 절차 (Windows, 비공개 자료 읽기 없음)

프로젝트 루트의 PowerShell:

```powershell
$py = 'C:\Users\User\AppData\Local\PublicBidAgent\Lab\.venv\Scripts\python.exe'
& $py -m pip check
& $py scripts/audit_python_environment.py --requirements local_app/requirements.txt
$env:PYTHONPATH = 'scripts'
& $py -m unittest test_audit_python_environment -v
npm --prefix frontend audit --package-lock-only
npm --prefix frontend ci --ignore-scripts --no-audit --no-fund
npm --prefix frontend run build
npm --prefix frontend sbom --sbom-format cyclonedx
```

`--output` 옵션으로 Python 전체 설치 목록을 로컬 JSON에 저장한다. 공개 GitHub에 운영 폴더 경로·비공개 JSON·API 키·원본 문서를 올리지 않는다. OSV 대외 조회에는 패키지명과 버전만 사용했다.

## 남은 릴리스/검증 게이트

- Python 51개 중 **26개만 SPDX `License-Expression` 메타데이터 확인**; 나머지 25개의 구형 자유형 `License` 메타데이터는 재배포 조건 원문 확인·고지가 필요(예: certifi MPL-2.0, pypdfium2 PDFium/번들 라이브러리, OCR 실행 파일/언어팩). 이 수치는 위배 발견 건수가 아니다.
- 설치 가상환경의 목록은 **환경 인벤토리**, 해시 고정 재현성 lockfile이나 전체 SPDX/CycloneDX Python SBOM이 아니다. 개별 바이너리 LICENSE/NOTICE 포함·배포 대상 정확한 구성과 취약점 재검사는 출시 전 별도로 확인한다.
- `npm audit`와 OSV의 0건은 알려진 취약점 DB 검사 결과이지 배포/보안 승인이나 사용자 자료 검수가 아니다.
- 실제 RFP 원본 페이지·표/각주/누락 Recall 및 회사 면허·실적·원가·가용 인력, 사용자의 실제 UI 최종 인수는 **NOT VERIFIED**. 외부 비공개 AI 전송, 자동 입찰, `main`·공개 배포 금지.
- P11 과거 7일 수집 API 오류의 선제 진단은 D-10에 따라 계속 보류한다.
