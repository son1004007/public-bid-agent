# 제3자 라이브러리·바이너리 라이선스 검토

## BID-05 (2026-10-19)

새 패키지·바이너리·외부 API/AI 의존성 없음. 기존 stdlib/URL whitelist/fulltext 검증/캡처를 재사용하며 문서 조회는 다운로드/파서 실행을 하지 않는다. 기존 Python3.12.x·Node22/Chrome 검증 환경과 라이선스 고지는 유지한다.

## 2026-10-19 BID-04

추가 패키지·바이너리·버전 변경 없음. CPython 3.12.x 표준 라이브러리로만 집계하며 SQLite release intent는 제한된 바이트를 메모리 DB에 deserialize하여 읽습니다. 기존 의존성·OCR/라이선스 잔여 게이트를 변경하지 않습니다.

## 2026-10-18 추가 설치 및 공개 소스 LICENSE 검증

- 운영 Python과 별도 감사 전용 가상환경에서 jsonschema, packageurl-python, pip-audit, license-expression, cyclonedx-python-lib 설치. `pip check` PASS; 실제 48개 SBOM 스키마·PURL·dependency 참조 오류 0; pip-audit 응답 47개 0 advisories + 누락 `packaging 26.3` OSV 0.
- 배포 wheel에서 LICENSE 파일을 발견하지 못한 3개 패키지 중 `et-xmlfile 2.0.0`, `openpyxl 3.1.5`은 SHA-256이 PyPI 게시 digest와 같은 공식 sdist에서 `LICENCE` 원문 발견. `langsmith 0.14.6`은 sdist에 후보가 없어 공식 저장소 MIT LICENSE 별도 확보. 정확한 버전의 고지 텍스트와 외부 바이너리 NOTICE 법적 충족은 별도 확인. [근거](reviews/LOCAL_AUDIT_TOOLS_2026-10-18.md).


## 2026-10-18 Python SBOM 추가 증거

- 현재 Windows Python 연결 패키지 48개 설치 메타데이터에서 CycloneDX 1.5/49개 의존 관계/48개 버전 관찰 pin 생성, 공식 스키마 오류 0. npm/외부 OCR·언어팩/PDFium/OS는 **별도**. SHA hash pin과 재현 가능한 wheel 집합·각 라이선스 원문 고지는 미완료. [검증 보고](reviews/PYTHON_SBOM_AND_BACKUP_CHECK_2026-10-18.md).

## 2026-10-18 현재 Windows 가상환경 검사 (기존 10월 9일 스냅샷과 구분)

- 직접 선언 `local_app/requirements.txt` 10개 모두 버전 범위 충족, 설치 51개/전이 경로 48개 및 `pip check` PASS. 이전 10월 18일 P09 테스트 환경에서 기록한 `Pillow 10.3.0`·`python-docx 1.1.2` 미달은 **현재 이 별도 개발 가상환경에서 재현되지 않음**.
- 51개 패키지 중 SPDX `License-Expression` 메타데이터 26개, 구형 자유형 표기 25개. 후자는 자동 `LICENSE/NOTICE` 적합 판정이 아니라 공식 배포 조건 검토 대기.
- 공개 패키지명·버전만 OSV에 질의한 Python 48개 반환 취약점 0. React 시안 `Vite 7.1.12` npm High 조치로 `7.3.7` 고정, npm 감사 0, `frontend/package-lock.json` 및 21개 컴포넌트 CycloneDX 1.5 작성·검증.
- Tesseract 5.5.3.20260724 + kor/eng 설치 확인, 배포 대상 OCR 모델/Leptonica/PDFium의 LICENSE·NOTICE는 실제 배포 전 원문 조사 필요. [실행 증거/범위](reviews/DEPENDENCY_SECURITY_AUDIT_2026-10-18.md).



- 점검 기준일: 2026-10-09
- 본 프로젝트 코드 라이선스: Apache-2.0
- 판정 범위: 직접 의존성의 공개된 업스트림 라이선스, 저장소에 포함된 의존성 명세; **배포 바이너리의 모든 전이 의존성 자동 법무 확인을 뜻하지 않음**.

## Python 직접 의존성

| 패키지 | 라이선스 | 판단/조건 | 공식 확인처 |
| --- | --- | --- | --- |
| pypdf | BSD-3-Clause | 사용 가능, 배포 시 고지 | https://github.com/py-pdf/pypdf/blob/main/LICENSE |
| python-docx | MIT | 사용 가능, 고지 | https://pypi.org/project/python-docx/ |
| openpyxl | MIT | 사용 가능, 고지 | https://pypi.org/project/openpyxl/ |
| xlrd | BSD | 사용 가능, 고지 | https://pypi.org/project/xlrd/ |
| pypdfium2 | Apache-2.0 OR BSD-3-Clause | **조건부 사용 가능:** PDFium 및 포함 라이브러리 라이선스 고지·파일을 함께 배포 | https://github.com/pypdfium2-team/pypdfium2/blob/main/README.md#licensing |
| Pillow | PIL 계열 MIT-CMU | 사용 가능, 원문 LICENSE 고지 | https://github.com/python-pillow/Pillow/blob/main/LICENSE |
| pytesseract | Apache-2.0 | 사용 가능, 고지 | https://pypi.org/project/pytesseract/ |
| python-hwpx | Apache-2.0 | 사용 가능, NOTICE 고지. HWP 5.0 파싱 기능의 버전 의존성 주의 | https://pypi.org/project/python-hwpx/6.8.0/ |
| langgraph | MIT | 사용 가능, 고지. 실행 시 하위 의존성 확인 | https://pypi.org/project/langgraph/1.2.14/ |
| langchain-core | MIT | 사용 가능, 고지 | https://github.com/langchain-ai/langchain/tree/master/libs/core |
| reportlab (테스트 전용) | BSD | 사용 가능, 고지 | https://pypi.org/project/reportlab/ |
| xlwt (테스트 전용) | BSD | 사용 가능, 고지 | https://pypi.org/project/xlwt/ |
| fastapi (별도 웹 시안) | MIT | 사용 가능, 고지 | https://github.com/fastapi/fastapi |
| uvicorn (별도 웹 시안) | BSD-3-Clause | 사용 가능, 고지 | https://github.com/Kludex/uvicorn/blob/main/pyproject.toml |
| pytest/httpx (테스트 전용) | MIT/BSD-3-Clause (버전·각각 고지 확인) | CI 환경에서 별도 시험 의존성 | 각 배포판 메타데이터 |

## OCR 및 프런트엔드

- **Tesseract OCR 실행 파일** Apache-2.0, Leptonica는 BSD 계열; `kor/eng` 모델은 Tesseract 공식 tessdata 라이선스 경로로 확인. `https://github.com/tesseract-ocr/tesseract`, `https://github.com/tesseract-ocr/tessdata`.
- React / React DOM: MIT. TypeScript: Apache-2.0. Vite: MIT 및 번들된 하위 의존 라이선스가 있음. `https://github.com/facebook/react`, `https://github.com/microsoft/TypeScript`, `https://github.com/vitejs/vite/blob/main/packages/vite/LICENSE.md`.
- HWP 및 HWPX **파일 규격 자체·고객 문서의 재이용 권한**은 파서의 Apache-2.0 라이선스와 다른 문제. 공고/RFP 원문은 별도 사용조건 확인.

## 재배포 체크리스트

### 2026-10-18 P09 검증 도구 경계

- 신규 합성 테스트는 CPython 3.12 표준 라이브러리, Node 22 내장 모듈 및 별도 설치된 Chrome을 사용한다. 새 pip/npm 의존성이나 Chrome/드라이버/OCR 바이너리를 저장소에 추가·재배포하지 않는다.
- 합성 API/TXT 테스트에 선택 의존성이 필요 없다는 사실은 전체 앱 의존성 충족/라이선스 승인이 아니다. 현재 환경은 python-docx 1.1.2·Pillow 10.3.0이 선언 최소 버전 미달이며 xlrd/pytesseract/python-hwpx/langgraph/langchain-core 미설치. 자동 설치·업그레이드는 하지 않았다.
- **릴리스 게이트 유지:** 정확한 배포 후보의 고정 버전 목록, 전이 의존성 SBOM, 실제 배포 파일의 LICENSE/NOTICE, PDFium/Tesseract/언어팩 고지 및 해당 후보의 취약점 검증이 없으면 재배포 준비 완료로 판정하지 않는다. 이 작업에서 그 검증은 NOT RUN이다. [실행·인계](reviews/P09_SYNTHETIC_ACCEPTANCE_2026-10-18.md).

- [x] 직접 의존성 공식 라이선스 유형 조사 (라이선스 관점에서 Apache-2.0 프로젝트에 사용 가능)
- [x] pyhwp(AGPL)를 새 기본 의존성으로 넣지 않음
- [x] 개발용 사용자 PC 로컬 설치: 앱이 third-party 실행 파일/모델을 직접 배포하지 않는 구조
- [ ] 릴리스 빌드마다 `pip freeze`/lockfile + 설치된 모든 **transitive** Python dependency 및 npm 패키지 SPDX SBOM 생성/확인
- [ ] 배포하는 wheel/PDFium/Tesseract/언어팩/React 번들에 대해 해당 버전의 LICENSE/NOTICE를 묶어서 전달
- [ ] 보안 취약점 및 사용 라이선스 점검, 상용 재판매/Claude Code·Codex CLI 외부 프로그램 사용 계약 검증

**판단:** 직접 의존성을 개발에 사용해도 Apache-2.0 프로젝트의 코드 라이선스를 유지할 수 있습니다. 이 검토는 재배포 전 모든 제3자 구성요소에 대한 별도 고지·실제 버전 감사 의무를 없애지 않습니다.
