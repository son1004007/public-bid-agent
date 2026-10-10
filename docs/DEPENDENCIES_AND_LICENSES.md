# 제3자 라이브러리·바이너리 라이선스 검토

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

- [x] 직접 의존성 공식 라이선스 유형 조사 (라이선스 관점에서 Apache-2.0 프로젝트에 사용 가능)
- [x] pyhwp(AGPL)를 새 기본 의존성으로 넣지 않음
- [x] 개발용 사용자 PC 로컬 설치: 앱이 third-party 실행 파일/모델을 직접 배포하지 않는 구조
- [ ] 릴리스 빌드마다 `pip freeze`/lockfile + 설치된 모든 **transitive** Python dependency 및 npm 패키지 SPDX SBOM 생성/확인
- [ ] 배포하는 wheel/PDFium/Tesseract/언어팩/React 번들에 대해 해당 버전의 LICENSE/NOTICE를 묶어서 전달
- [ ] 보안 취약점 및 사용 라이선스 점검, 상용 재판매/Claude Code·Codex CLI 외부 프로그램 사용 계약 검증

**판단:** 직접 의존성을 개발에 사용해도 Apache-2.0 프로젝트의 코드 라이선스를 유지할 수 있습니다. 이 검토는 재배포 전 모든 제3자 구성요소에 대한 별도 고지·실제 버전 감사 의무를 없애지 않습니다.