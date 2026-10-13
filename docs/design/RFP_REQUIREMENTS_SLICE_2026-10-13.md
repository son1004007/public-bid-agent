# RFP 요구사항 구조화 1단계 (2026-10-13)

## 목적과 범위

현재 확보된 조달청 RFP 문서에서 **실제 텍스트에 존재하는 요건 관련 표현 후보**를 근거와 함께 JSON으로 제공한다. 사용자에게 법적 참가 가능, 필수/선택, 수행 가능, 예상 수익성을 확정하지 않는다. 로컬 PC 127.0.0.1 전용이며 문서·비밀키·부서 인력정보를 외부 모델에 전송하지 않는다. 7일 자동수집 API 오류 분석 및 기존 데이터 대량 수정은 범위에서 제외한다.

### 입력·처리·출력

- 입력: `dashboard.json`의 공식 공고 1건과 공식 첨부의 `document_evidence`, 비공개 `rfp_fulltext` 캐시. SHA-256 source 및 공식 첨부 (URL, 이름) identity 를 검증한다.
- 구조화: 참가자격(participation), 업종·면허·인증(licenses), 수행실적(track_record), 과업범위(scope), 기술요건(technology), 인력·공수(staffing), 사업기간(duration), 예산·사업비(budget)의 정규식 기반 보수적 **표현 탐지**. 카테고리당 최대 5건, 문서당 44,000자 및 공고당 최대 2개 기록된 문서를 사용한다.
- 근거: 문서 이름, 원본 파일 SHA-256, 내부 fulltext 참조, 추출 텍스트 문자 시작/끝 위치, 실제 짧은 발췌 최대 220자, `page=null`, 위치 기준 `EXTRACTED_TEXT_OFFSET_NOT_PDF_PAGE` 또는 `STORED_EXCERPT_OFFSET_NOT_PDF_PAGE`. 원본 PDF/HWP 페이지, 필수/선택 단정, 표 셀의 읽기 순서는 추정하지 않는다.
- 신뢰성: 검증된 최대 44,000자 청크가 있으면 텍스트 SHA-256·청크 순서/시작 끝·raw source SHA를 대조하여 사용. 청크가 없는 과거 문서는 대시보드 발췌 결속 검증 후 최대 6,000자로 제한하며 `PARTIAL` 경고를 반환한다. 캐시 SHA 불일치는 HTTP 503.
- 안전: `notice_lifecycle` 취소/구차수/중복과 `rfp_review_status=STALE`은 원문 의미 검색 없이 `EXCLUDED_NOTICE`, `STALE_RFP` 반환. 문서에서 발견된 문구는 자연어 데이터로만 해석하며 프롬프트 주입, 명령 실행, 자동 적격 판정에 사용하지 않는다.
- 상태/쓰기: `GET /api/dashboard/rfp-requirements?id=G2B-...`는 **read-only**. 응답은 `{requirements:{schema_version,id,state,analysis_mode,requirements:[{category,label,count,items:[{status,evidence:{file,source_sha256,fulltext_ref,offset_start,offset_end,position_basis,source_mode,page,excerpt}}]}],requirement_count,sources_used,source_coverage,warnings,uncertainty,legal_eligibility,technical_fit,staffing_fit,profitability},storage}`. 원본 JSON과 RFP 청크를 수정하지 않는다.
- 프론트: `/decision-preview` → 해당 공고 `전체 상세보기` → `참가자격·과업 확인` 탭 → `RFP 요구사항·출처 근거 확인`. 사용자 클릭할 때만 API 요청, 화면 textContent 기반 표시, 오류·누락 경고.
- 사용자 실증: 현행·비보류·관심분야 CANDIDATE·마감 전·전체 텍스트 참조 보유 공고 66건 중 공고 ID 정렬로 고르게 20건 표본. 20건에서 총 561개 텍스트 표현 후보 탐지, 에러/0건 0, 그중 파서 일부 절단 또는 부분 발췌 4건. 개인 자료의 구체적 문장·주소·파일명은 공개 문서에 기록하지 않음. 표본 통계는 공고 가용성 및 저장 데이터 시점에 따라 달라짐.

## 완료 판정과 한계

- 구조화는 **규칙 기반 원문 표현 후보**, 현 단계의 AI 추론/RAG·LangGraph·회사 자격과 인력 비교는 미구현이다.
- 8개 분야별 단순 텍스트 매칭이라 법률상의 의무, 부정 표현/예외, 표/각주, 수치의 단위 해석에 대한 판단은 제공하지 않는다. 원문 페이지 ID를 알 수 없는 문서는 문자 위치로만 근거를 표시한다. 파서 절단/원문 누락 시 `PARTIAL` 또는 경고.
- API의 결과를 대외 제출·실제 Bid/No-Bid 판정으로 사용하기 전에는 사람의 원본 RFP 확인 필요.
- 8개 STALE 문서는 재추출을 자동으로 승인·해제하지 않으며 원본 보존/추천 제외를 유지.
- 검증: `python -m unittest discover -s local_app -p 'test_rfp_requirements.py' -v`, 전체 합성 테스트, 실제 Chrome read-only, 독립 Codex read-only 리뷰.


### Codex 독립 검수 지적에 따른 출처 결속·증거 순회 보완
- 공식 첨부 identity로 확인된 **실제 첨부 파일명만** 응답에 표시. 저장된 `document_evidence.name`이 공식 첨부명과 다르면 불일치 경고를 남기고 증거를 제외합니다.
- 증거 이력 최대 120개 항목을 살펴보고 **정상 SHA/파일명/본문 검증에 성공한 문서 2개**까지 선택합니다. 앞의 기록이 실패해도 이후 정상 기록을 탐지하고, 처리 상한·중복·충돌을 경고합니다. 같은 첨부 identity의 다른 원본 SHA가 있으면 둘 다 제외합니다.
- 요건 표현 후보는 필수 조건 여부와 원본 페이지가 미확인입니다. 캐시나 문서 이름의 불일치가 있으면 자동 분석 결과를 확정하지 않습니다. 이는 실제 문서 의미를 판단하는 AI 기능과 구분합니다.


### Codex 2차 지적: 공식 첨부 목록의 조용한 절단 보완
- 공식 첨부 목록은 **400건 이내에서 identity를 대조**합니다. 121번째의 정상 공식 첨부는 분석 대상에 포함됩니다. 400건을 초과하면 공식 첨부 탐색 상한을 `PARTIAL`과 명시적 경고로 표시하고 누락 원인을 감추지 않습니다.
- 합성 회귀 2건(121번째 정상 첨부 인식, 401번째 이후 탐색 상한 경고)을 추가했습니다. 앞의 Codex 개선 사항(출처 파일명 결속 및 최대 120개의 증거 이력에서 성공 2개 선정)은 유지합니다.
