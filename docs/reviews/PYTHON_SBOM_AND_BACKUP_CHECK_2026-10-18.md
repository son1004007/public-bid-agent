# Python SBOM 및 P09 백업 읽기 전용 검증 (2026-10-18)

## 실측 완료

- 공개 패키지 메타데이터만 이용해 `scripts/export_python_sbom.py`를 추가. 기존 `scripts/audit_python_environment.py`의 설치된 의존 그래프를 CycloneDX **1.5 JSON**과 Windows **관찰 버전 고정 목록**으로 변환한다. 현재 Windows 개발 Python 3.12 환경에서 **48개 Python 컴포넌트, 49개 루트 포함 dependency 관계, 48개 관찰 pin**이 생성됐다.
- `scripts/test_audit_python_sbom.py` 신규 4건을 포함해 `scripts/test_audit_*.py` 합성 회귀 **14 PASS**. 출력 경로 기존 파일 덮어쓰기 거부, 직접/전이 미충족·미완성 메타데이터 시 생성 차단, 버전·의존성 참조와 개인정보 경로 비포함 확인.
- Codex 초기 NO_GO에서 PURL 특수 버전 인코딩 및 SPDX 유효성 오인 2건 재현. 현재 코드는 percent-encoding과 검증 전 라이선스의 비공식 metadata 처리로 수정하고, 누락 의존성에 대한 pins 출력도 거부. 수정 후 독립 Codex **GO**, 로컬 합성 테스트 **14 PASS**. [6단계 종합 증거](FOLLOWUP_SIX_STAGE_2026-10-18.md).
- 공식 [CycloneDX 1.5 JSON Schema](https://github.com/CycloneDX/specification/blob/master/schema/bom-1.5.schema.json) 및 SPDX 참조 스키마를 Windows PC의 도구 전용 폴더에 확보하고 로컬 Python `jsonschema 4.20.0`로 생성된 실제 SBOM 스키마 검사: **0 errors / 48 components**. 검사 스크립트·결과물은 로컬 `AgentRunner`에만 보관.
- 운영 서버용 `last-local-release.json`의 P09 source `f06a3fa` 백업을 **읽기 전용**으로 조사. 릴리스 백업 파일 **318개 모두 읽기 성공**, 현재 보호 파일과 **318개 해시 일치**, 변경·현재 파일 누락·읽기 오류 0. 복원 명령, 기존 파일 삭제, 운영 상태 변경은 하지 않았다.
- 실제 운영 PC의 사업 데이터·RFP 본문·원가·신원·키·파일별 해시·상세 경로는 GitHub/외부 Codex에 전송하지 않았다. 원본 경로는 보고서에 저장하지 않고 집계만 기록한다.

## 정확한 검증 범위와 남은 게이트

- 이 버전 목록은 **observed pins**이며 **파일 SHA-256 해시가 고정된 cross-platform lockfile이 아니다**. 대상 플랫폼/파이썬 버전과 배포 wheel 아카이브 및 해시가 확인된 잠금/재현 설치 검증은 별개다.
- SBOM은 현재 개발 Windows 가상환경에서 직접·전이로 연결된 **Python 48개**만 포함한다. 환경 전용 3개, 프런트엔드 npm 21개 구성요소, Tesseract/kor/eng/PDFium, 운영체제 및 기타 외부 바이너리는 통합하지 않았다. 메타데이터 라이선스 정보는 법적 승인/NOTICE 고지의 증명이 아니다.
- 백업 **현재 동일성**은 확인했지만 실제 장애 상황에서 원자적 복원·전원 중단·다중 프로세스 쓰기 복구를 수행한 것은 아니다. 안전한 격리 공간에서의 복원 dry-run과 운영 시나리오 검증은 별도.
- 사용자 실제 RFP 문서의 독립 정답 라벨·페이지/표/각주/OCR recall, 회사 증빙, 사용자 UI 최종 승인도 미완료. `main`·외부 공개·실제 입찰 자동 실행은 별도 승인이 필요하며 D-10의 과거 7일 API 문제는 조사 보류.

## 재현 (비공개 데이터 사용 없이)

```powershell
$py = 'C:\Users\User\AppData\Local\PublicBidAgent\Lab\.venv\Scripts\python.exe'
$env:PYTHONPATH='scripts'
& $py -m unittest discover -s scripts -p 'test_audit_*.py' -v
& $py scripts/audit_python_environment.py --requirements local_app/requirements.txt --output <new-local-inventory-path>
& $py scripts/export_python_sbom.py --inventory <new-local-inventory-path> --sbom <new-local-sbom-path> --pins <new-local-pins-path>
```

`<...>`는 Windows PC의 안전한 신규 로컬 파일 경로로 지정한다. 생성 도구는 이미 존재하는 파일을 덮어쓰지 않는다. 원본 GitHub 저장소에는 산출 JSON을 강제로 커밋하거나 서드파티 배포 바이너리를 포함하지 않는다.
