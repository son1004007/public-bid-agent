# 현재 개발 상태

- 기준일: 2026-10-09
- 대상: son1004007/public-bid-agent
- 개발 브랜치: feat/sprint1-search-demo / Draft PR #1
- 사용자 우선순위: **설계 → UI 퍼블리싱 → 사용자 화면 검증 → 프런트엔드 수정 → 백엔드 세부 구현**
- 현재 단계: **공고 목록 + 상세 하위 화면 + 제출·낙찰·평가점수 시안 보완 / 사용자 피드백 대기 (UI_PROPOSED)**
- backend: 초기 합성 공고 API와 테스트 11개 기존 구현을 유지. 더 이상 백엔드 확장하지 않음.
- frontend: 기존 React+FastAPI 연동 코드 보존 + `frontend/public/ui-review.html` 공고 목록에서 `bid-detail-review.html` 공고별 상세·제출·낙찰·점수 화면으로 이동하는 독립 퍼블리싱 추가.
- 신규 시안은 브라우저 메모리 수기 상태만 다루며 서버 저장·공식 조회·개별 업체 입찰내역 조회가 아니다.
- 실공고 연동, Google 로그인, RAG/LLM, 실제 행정자격 판정, 외부 서비스 배포: 미구현/비활성.
- 공통 UI 퍼블리싱 우선 정책: personal-engineering-handbook의 Draft PR #1, **아직 검수/승인 전**.

## 사용자가 확인할 퍼블리싱 범위

- 공고 탐색 / 상세 검토 / 임시 검토 보관함 / 화면 검증 메뉴
- **공고별 상세 화면**: 기본정보, 행정 참가자격, 제안서·평가배점, 제출 수기 기록, 낙찰·기술/가격 점수, 수주 이력 표
- 제출/점수 수기 입력의 값 검증, 모든 자료의 합성·미확인 표기
- 합성 공고 8건, 검색어 및 AI/SW/DATA 필터
- 선택한 공고의 기술·사업 요건 예시
- 0건/오류 화면 시뮬레이션
- 데스크톱·모바일 반응형 레이아웃, 키보드 동작 기본 확인
- 화면 검증 체크리스트

설계 자료는 **합성 fixture**이며 실제 공공 입찰 정보가 아니다. 브라우저 밖으로 데이터를 전송하거나 서버·DB에 보존하지 않는다.

## 실행 및 검증 상태

- 최초 Sprint 1 백엔드: 로컬 pytest 11 PASS (2026-10-09).
- 최초 Sprint 1 PR CI: Python 및 TypeScript/Vite 빌드 PASS (GitHub Actions 37885735328).
- GitHub Actions push [37894035152](https://github.com/son1004007/public-bid-agent/actions/runs/37894035152) 및 PR [37894040200](https://github.com/son1004007/public-bid-agent/actions/runs/37894040200): **PASS**. Python 백엔드 테스트, TypeScript/Vite 빌드, 독립 UI 정적 HTML JavaScript 구문·안내문·외부 자원 참조 검사, 번들 내 퍼블리싱 파일 포함 여부를 확인했다. 사용자 화면 적합성 승인/브라우저 E2E를 대체하지 않는다.
- 사용자 검증용 시안과 일치하는 별도 정적 데모는 로컬 브라우저에서 화면/상호작용을 사전 점검했으나, GitHub 파일의 정식 시각 검수 및 사용자 승인은 여전히 미완료.
- 별도 AGY/Gemini 의미 검수: **NOT RUN (REVIEW_DEBT)**. Draft PR 유지 및 main 병합/릴리스 금지.
- 기존 R1~R4 설계 검수 및 정정 ADR은 삭제하지 않음.

## 다음 작업

1. 사용자가 [UI 화면 검증 가이드](docs/ui/SCREEN_REVIEW_GUIDE.md)와 공고별 [상세·제출·결과 시안](frontend/public/bid-detail-review.html)을 직접 확인하도록 안내.
2. 페이지/탐색/상세/보관함/모바일/빈 결과·오류에 대한 사용성 피드백 수집.
3. 사용자 결정에 따라 화면과 API 응답 데이터 계약 수정.
4. UI 검증 뒤 해당 화면의 필요 기능부터 백엔드 구현을 이어감.
5. 변경 단위 독립 검수·실제 테스트 및 필요 시 별도 사용자 승인 후 main 통합을 판단.

## 근거 문서

- [화면 검증 가이드](docs/ui/SCREEN_REVIEW_GUIDE.md)
- [독립 HTML 퍼블리싱 시안](frontend/public/ui-review.html)
- [애자일 개발 절차](docs/07-agile-development-workflow.md)
- [기존 Sprint 1 실행 기록](docs/implementation/SPRINT1_RUNBOOK.md)
- [다른 채팅/AI용 인수인계](docs/implementation/CONTINUE_IMPLEMENTATION_PROMPT_2026-10-09.md)
- [보안·독립 검수 정책](https://github.com/son1004007/personal-engineering-handbook/blob/main/REVIEW_POLICY.md)

## 2026-10-09 상세 퍼블리싱 추가

- 목록에서 `전체 상세·제출·낙찰 관리` 링크로 이동.
- 상세 페이지 6개 화면: 기본정보/참가자격/제안서·평가/제출 관리/낙찰·평가점수/진행 이력.
- 제출 기록은 `미확인/미제출/제출했다고 기록/접수증을 사람이 확인했다고 기록`로 구분하며 공식 접수 확인을 주장하지 않음.
- 평가점수는 입력값과 만점의 유효성을 검사하며 미공개·미입력 점수를 0으로 환산하지 않음.
- 공식 조사: `docs/research/2026-10-09-bid-lifecycle-management.md`. 공식 공공 API는 개찰·낙찰·계약을 제공하지만, 내 기업이 제출했다는 사실과 개별 기술점수는 별도의 증빙/공개 조건이 필요.
- 새 HTML 상세 퍼블리싱의 GitHub Actions push run [37900354978](https://github.com/son1004007/public-bid-agent/actions/runs/37900354978) 및 PR run [37900360576](https://github.com/son1004007/public-bid-agent/actions/runs/37900360576): PASS. 백엔드 tests, frontend Vite typecheck/build, 정적 JS 및 독립 HTML 파일 포함 검증을 통과. 독립 최종 검수 및 실제 GitHub 버전의 브라우저 E2E는 NOT RUN.
