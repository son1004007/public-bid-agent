# MVP 검증: 공개 공고 3건, 가상 업체 조건 4개 (2026-10-10)

## 검증 범위와 자료 등급

- 실제 공공입찰 공고번호: `R26BK01745574-000`, `R26BK01747372-000`, `R26BK01759604-001`.
- 수집 방식: 공개 입찰 정보 서비스의 공고문 전재·메타데이터 **수기 전사**. 실제 나라장터 원문 첨부 링크는 접근 시 403 또는 네트워크 오류로 다운로드하지 못했다.
- 공고 원문 정확성을 보장하지 않는다. 특히 R26BK01745574의 마감시간은 공개 재게시 자료 사이에 **10:00과 14:00이 충돌**하므로 원문 확인 전에는 더 이른 **10:00**을 기준으로만 표시한다.
- 업체 내부 조건: **전부 가상**이며 실제 사용자 재직회사나 팀의 인력·실적·법인 유형·나라장터 등록 현황을 뜻하지 않는다.
- 재현 데이터: `local_app/fixtures/public_tenders_2026_10_10.json`, `local_app/test_public_tenders.py`.
- 실모델/실로컬 처리: Windows Python 3.12, Codex CLI 0.154.0, `gpt-5.6-terra`, `--ephemeral --ignore-user-config --ignore-rules --sandbox read-only`. 사용자 명시적 지시 하에 4개 **공개 자료 + 가상 업체** 프롬프트만 외부 모델 전송.
- 앱 로컬 JSON: 회사 노트북의 `%LOCALAPPDATA%\\PublicBidAgent\\Lab\\public-notice-mvp-synthetic-data\\cases.json`에 전부 보관. 상용 데이터·실제 내부 정보는 사용하지 않음.

## 4개 사례 실제 Codex 모델 결과

| 사례(실제 공고 ID) | 가상 업체 조건 | AI 원문 권고 | AI 추출된 Fail Gate | 미확인 Gate 수 | 규칙 기반 위험분류 | 실제 사용자 Y2 | 시간 |
| --- | --- | --- | --- | ---: | --- | --- | ---: |
| 외식업 AI Agent R26BK01745574 | 소기업·벤처 요건 없는 가상 대기업 / 운영 SLA 비수용 | hold | eligibility, resources | 6 | REVIEW_NO_BID_PROVISIONAL | undecided | 18.7s |
| 과학 시뮬레이션 R26BK01747372 | AI 웹 개발 경험 있으나 과학교육 인력·파트너 미확보 | hold | resources | 5 | REVIEW_NO_BID_PROVISIONAL | undecided | 31.6s |
| 같은 시뮬레이션 공고 | 과학 콘텐츠 납품·인력 확보를 **가정**한 별도 가상 업체 | hold | 없음 | 7 | HOLD_UNVERIFIED | undecided | 27.0s |
| AI 클라우드 R26BK01759604-001 | 클라우드 개발역량 가정, RFP·자격·원가 미확인 | hold | 없음 | 8 | HOLD_UNVERIFIED | undecided | 21.4s |

- 4/4 모델 CLI 호출 성공. 4/4 응답 Gate 8개, Factor 12개로 구조화, Codex 원문 결과·미검증 초안·사람 결정이 로컬 JSON에 별도로 저장됨.
- **발견된 품질 문제:** AI는 4건 모두 `hold`를 추천하고 `reason` 필드의 내용을 빈 문자열로 반환했다. 따라서 raw AI Recommendation 한 가지만으로 결격 조건·수행능력 미확보와 자격확인 부족을 구분할 수 없다.
- **보완:** `decision_support.py`의 AI 실패/미확인/사용자 확인값 충돌 보수적 분류와 사유 미제공 경고를 추가. 원시 모델 응답을 위조·변경하지 않고 **별도 안전 경고**로 표시.
- 개정판 로컬 테스트: Python unittest **36개 PASS**, `node --check` 통과. GitHub CI [37997843667](https://github.com/son1004007/public-bid-agent/actions/runs/37997843667) **SUCCESS**.
- 개정판 실제 HTTP 서버 `127.0.0.1:8771`에서 기존 4건을 `/api/save`로 재분류, `NO_BID_PROVISIONAL 2건, HOLD_UNVERIFIED 2건` 상태 및 `undecided` 사용자 결정 불변 확인.
- 회사 노트북 사용자용 UI `http://127.0.0.1:8765/`에 `[검증 사례·실제공고/가상 업체]` 명칭으로 4건을 수기 이관하여 확인. 이동 전 사용자 업무 JSON이 빈 상태임을 검사하고 `cases.before_manual_public_notice_demo.json`에 백업. 직접 localhost 접속 확인, JSON 4건, 경고패널 4건, 사용자 결정 4건 모두 `undecided`.
- 위 결과는 **실제 수주 여부(Y3)의 정답이나 법적 적격증명**이 아니다. 부서 변수가 실제로 적절한지를 확정하려면 부서의 현실 자료 및 발주기관 원문이 필요하다.

## MVP 병합 게이트 및 독립 리뷰

- **기능 경로:** PASS — 수기 입력/코드 클리어→AI 분석→8+12 영향인자→보수적 위험 표시→사용자 결정/JSON 로컬 저장. 실제 공고 3건 기반 4개의 합성업체 사례로 완료.
- **공고 원문 신뢰:** PARTIAL — 공식 나라장터 RFP 첨부 직접 다운로드 불가(403), 재게시 메타데이터에 마감 시간 충돌 존재. UI는 이를 경고하며 실제 투찰정보로 사용 금지.
- **독립 의미/보안 검수:** BLOCKED — AGY Gemini 3.1 Pro High `plan --sandbox` headless가 소스 확인을 위한 `command` 권한을 요청하고 자동 거부. 인라인 전체코드 리뷰는 Win32 명령행 길이/인수문법 제한; 모델은 유효한 검수 결과를 반환하지 못함. Codex 5.6 Terra 독립 PR read-only diff 리뷰도 명령 실행권한 정책이 `git diff`/`Get-Content`를 거부하여 검토가 진행되지 않고 중단. **`--dangerously-skip-permissions` 등 권한 우회는 수행하지 않았다.**
- **Independent review provenance:** 리뷰 대상 SHA `751d75c8362b0fb01182ec482ccebef8dde29328`; AGY Gemini3.1 Pro High, 권한 제한에 의한 FAILED; 독립 Codex CLI 0.154.0 모델 gpt-5.6-terra, read-only diff 리뷰 FAILED(BLOCKED_BY_POLICY). 시도 로그는 사용자 PC Lab 로컬에만 존재; 회사 비공개 자료는 포함되지 않음.
- **최종 결론:** `IMPLEMENTED / TESTED`, `REVIEWED=NO`, `MAIN_MERGE=HOLD`. 전체 브랜치에는 이전부터 누적된 의미 있는 프런트/백엔드/보안 변경이 있으므로 테스트 통과만으로 독립 코드 리뷰를 생략하지 않는다.

## 후속 조치

1. 안전한 독립 리뷰 환경(회사 노트북의 읽기 전용 명령 권한만 승인, 또는 적절히 분리된 별도 개인 리뷰 장치)에서 AGY+Codex를 실제 실행하고 Findings를 기록.
2. BLOCKER/MAJOR가 있으면 수정 → 회귀 테스트/정확도 확인 → 범위에 맞춘 재검토.
3. 3개 공식 나라장터 공고 원문/RFP의 전문 확보 시 마감·자격·평가 배점 재검증. 공식 원문이 안 되면 정보 신뢰도를 미확인으로 표시한 로컬 MVP만 제한적으로 사용.
4. 기준 충족 후 Draft PR `#1`을 정상 리뷰 상태로 전환하고 `main`에 병합. 자동 공고 수집/실제 수주 데이터 연계는 **이후 별도 스프린트**.
