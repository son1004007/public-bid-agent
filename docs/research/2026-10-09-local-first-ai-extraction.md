# 공공입찰 AI 의사결정: 영향인자 충족성 조사와 로컬-first 데이터 설계

- 조사일: 2026-10-09
- 기준: APMP 수주 프로세스 / 조달청 공공 입찰 계약 구분 / OpenAI·Anthropic 공식 개발자 문서
- 상태: 조사 기반 초기 구현, 변수 가중치·계약 방식·모델 결과 정확도는 여전히 가설

## 현재 6+8 인자에서 빠진 항목

기존 Gate 6개와 비교인자 8개는 **가장 기본적인 형태**는 갖췄으나 다음 항목이 불명확하게 묶여 있었다.

1. 입찰의 실재성, 예산/사업계획의 확실성, 취소 가능성: 기회 평가와 본질적으로 구분
2. 고객의 핵심 요구와 선정기준·평가구조/기술·가격 배점: 실제 공고 문서 확인
3. 경쟁사와 incumbent(기존 수행 업체), 차별화/가격 경쟁 전략
4. 실질적인 제안서 작성 비용(인력시간·제안비)과 비참여 시 다른 기회에 투입할 수 있는 자원
5. 계약 조건별 보험·보증·지체상금·책임/현금흐름 위험
6. 공동수급·협력사 확약 여부와 실제 확보된 핵심 인력의 일정
7. 기존 발주처 성과/고객 이해와 전략적 후속 사업 가치 (불법적인 접촉·우대가 아닌 합법적 근거에 한정)
8. P(win)과 구매자가 실제 계약을 추진할 P(go) 구별. 과거 실제 입찰 이력 없이는 수주확률 수치화 금지

APMP의 Go/No-Go 안내는 적합도·예상 계약규모·제안서 준비 인시/비용·구현비용과 수익성을 보고하라고 제시한다. APMP Winning Business Ecosystem은 고객 요구, 시장 조사, 기존 수행사업자, 경쟁 전략, ROI, 위험과 팀을 나눠 검토한다.

조달청은 물품·용역 입찰 방식에 따라 평가 기준이 다르고 협상에 의한 계약은 기술·가격 평가 비중을 조정할 수 있다고 설명한다. 따라서 본 프로젝트의 Gate/점수는 공고별 제약과 실제 배점으로 보정되기 전엔 '법적 적격'/'낙찰확률'이라고 표시하지 않는다.

## 초기 변수 스키마

- \`gates\` 8개: 입찰 등록·업종, 면허·인증·보험·보증, 필수 유사실적, 필수 인력·재무, 공동수급·지역·하도급, 제출기한·서류, 보안·수행 장소, 계약 필수/배제 조건.
- \`factors\` 12개: 기술·솔루션(15), 수행 자원(10), 유사 실적(10), 고객 요구(10), 기존 사업자/경쟁(10), 차별성·가격경쟁(10), 경제성(10), 투찰 준비 비용(5), 과거 고객평가·관계 이해(5), 전략적 가치(5), 제안 준비도(5), 계약·수행 위험(5). 가중치 합 100. 모두 **검증되지 않은 시연용**으로 고정.
- 각 항목: 값, 원문 근거 또는 입력자의 수기 이유, \`verified\` (기본 false). 모델이 제시한 '충족'은 실제 회사 등록/자격을 검증한 게 아니므로 \`verified=false\`.
- \`ai_reports.codex\`, \`ai_reports.claude\`, \`ai_draft\`: provider별 응답 상태/초안. 사용자의 검증된 값을 자동 덮어쓰지 않음.
- \`decision\`: 사람이 별도 확정하는 \`undecided | bid | hold | no_bid\` + 시점/메모.
- 가중지표는 모든 Gate·항목을 사람이 근거 확인한 때에만 산출. Gate 미충족이면 지표 미산출. **가중합은 수주 확률이 아님.**

향후 2차 변수 후보로는 실제 발주 예산/확정 여부, 유사기관 계약이력, 입찰자 수·낙찰 방식, 연속 계약/경쟁제한, 실제 투입인월/납기와 변동, 수행 원가·제안비용·프로젝트 예상 이익률, 계약상 보증금·손해배상, 협력사 계약확약, 원문 조항 ID 및 정정 이력을 수집해야 한다. 초기에 회사별 내부 데이터를 강제하지 않고 근거 없으면 UNKNOWN.

## 로컬 PC 실행 구조

Browser(local origin) -> Python localhost HTTP -> \`~/.public-bid-agent-local/cases.json\`.

1. 사용자가 자유 프롬프트나 파일을 선택. TXT/MD/CSV/JSON 문자열, PDF(pypdf), DOCX(python-docx)를 PC에서 텍스트로 추출.
2. 업로드된 바이너리는 보존하지 않고 추출 텍스트를 로컬 JSON에 기록. 원본도 보관하려면 별도 승인된 안전한 오프라인 자료 관리 구현이 필요.
3. 사용자가 Codex/Claude를 선택하고 명시적으로 외부 전송 동의한 경우에만 로컬 CLI 서브프로세스가 텍스트를 AI 제공자에게 보낸다.
4. AI는 JSON형식 영향인자 초안을 출력. Python이 JSON 필드·값을 검증하고 \`verified=false\`로 별도 보관. 사람이 '초안 적용'한 뒤 수정·검증.
5. 사람이 참여/보류/미참여를 별도로 결정하고 JSON에 결과를 저장. 실제 제출/낙찰정보는 공고 출처와 별도 연결 필요.

보안 범위: 127.0.0.1과 Host·Origin·CSRF 검사, 다운로드 없는 로컬 JSON 기록, POSIX 0600/0700. PDF/DOCX는 메모리에서 파싱하므로 **완전한 공격 코드 격리 아님**. 파서 subprocess 격리/자원 제한 및 멀티유저 접근제어, 실제 데이터 보안·백업은 별도 후속 검증 필요.

중요한 개인정보/회사 기밀: 모델을 호출하면 정보는 실제 OpenAI·Anthropic 시스템으로 전송된다. CLI 자신이 별도의 캐시·인증·진행기록을 쓸 수 있으므로 'JSON만 저장'은 앱이 관리하는 업무기록 범위로 한정된다. 완전한 로컬 추론/통신금지 조건을 만족하는 시스템이 아니다.

## 실제 Codex/Claude 실행 자격

- Codex CLI \`codex exec\`: 제한 샌드박스와 자동화/JSON 출력 예제를 공식 문서가 제공. 현재 앱은 텍스트 JSON 재시도 미지원·서브프로세스 제한 모드로 최소 실행.
- Claude Code CLI: \`claude -p --tools ""\`를 통한 비대화형 응답은 공식 문서에 있으나 외부 프로그램 연동 및 구독/사용권한은 현행 약관과 해당 사용자 구독조건에 따라 따로 검증한다.
- 개발용 로컬 CLI 인증과 공개 타인 대상 계정 중계는 다르다. 로컬 앱은 타인의 CLI 로그인을 받지 않는다.
- LangGraph는 향후 수집→각 모델 독립 분석→근거/이견 교차검토→사용자 결정/재실행 단계에 도입하되, 실제 CLI 사용 자격·상태입출력과 실패 흐름 검증 후 의존성을 추가한다.

## 출처

- APMP Winning Business Ecosystem: https://members.apmp.org/Web/Web/About-Us/Winning-Business-Ecosystem.aspx?hkey=78f94982-b424-49fe-b276-f890f0ab744c
- APMP-NCA Go/No-Go Decisions 101: https://apmpnca.org/blog/go-no-go-decisions-101/
- APMP India 의사결정 경험: https://apmpindia.org/2023/03/02/decision-making-principles-in-bid-management/
- 조달청 총액계약/협상에 의한 계약: https://www.pps.go.kr/kor/content.do?key=00726
- 조달청 입찰 계약방식 및 평가비중: https://www.pps.go.kr/kor/content.do?key=00178
- OpenAI Codex CLI 자동화: https://developers.openai.com/cookbook/examples/codex/build_iterative_repair_loops_with_codex
- OpenAI SIWC 로컬 OSS 사용권한: https://developers.openai.com/siwc/token-sharing-open-source
- Claude Code CLI reference: https://docs.anthropic.com/en/docs/claude-code/cli-usage

## 미구현

- 실제 AI CLI 인증이 가능한 사용자 PC에서 두 provider 출력의 성공률 검증.
- Codex·Claude 상호 반론/랭그래프 HUMAN_IN_THE_LOOP 상태 저장.
- 파일 업로드 안전 파서 프로세스 격리와 HWP/HWPX/OCR.
- 실제 평가점수·수주 결과 정답 데이터 수집 및 지표/가중치 검증.
