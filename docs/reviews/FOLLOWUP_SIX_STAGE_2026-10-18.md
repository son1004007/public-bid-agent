# Public Bid Agent 2026-10-18 사용자 지시 1~6 검증 종합

## 단계별 실행 결과 (각 단계의 완료 기준 구분)

1. **SBOM 코드 오류 보완:** Python PURL 내 버전 `!`/`+` percent-encoding, 검증되지 않은 `License-Expression`은 SBOM 공식 `licenses.expression`이 아닌 `public-bid-agent:unverified-license-expression` 속성에만 유지. `to_observed_pins`도 연결되지 않은 dependency를 거부. **합성 Python 14 PASS**. 독립 Codex 최신 **VERDICT: GO**이며 Codex 자체 read-only 재현 13건 + 추가 경계 28건 PASS(파일 쓰기 수반 CLI 시험은 개발자 로컬 증거). Windows Python 48개 컴포넌트, 49 dependency, 48 관찰 pin. **공식 CycloneDX 1.5 JSON Schema 검증 0 errors**. `SBOM`은 관찰 메타데이터이지 배포 승인/해시 lock 아님.
2. **라이선스·의존성 실측:** 직접 Python 요구조건 10/10 버전 충족, 연결 패키지 48개, `pip check` PASS. 설치된 패키지에서 LICENSE/NOTICE 후보 파일 확인 **45/48**. 확인되지 않은 **3개: `et-xmlfile 2.0.0`, `langsmith 0.14.6`, `openpyxl 3.1.5`**. 이들은 위반 판정이 아니라 설치본에 명시적인 고지 파일을 찾지 못한 것이며, 공식 배포 원문/고지 묶음 검증이 필요. 이전 OSV Python 조회 48개 반환 0건, npm 감사 0건, React Vite 7.3.7·npm 잠금 파일·21개 npm CycloneDX 증거 유지. Tesseract/언어팩/PDFium 및 wheel 파일 해시 기반 lock, NOTICE의 법적 완성은 **NOT VERIFIED**.
3. **격리 복구 테스트:** P09 릴리스 백업에서 **318개/68,652,616바이트(약 68.7MB)**를 Windows 임시 복원 공간에 복사하고 모든 SHA-256 일치. JSON **305/305 파싱 성공**, 격리 복사본의 파일을 제거한 다음 백업으로 복구하는 조작 성공. 다음 단계로 **격리된 별도 localhost 포트에서 복구한 데이터로 P09 서버를 실행**하여 웹 화면 HTTP, RFP coverage/read-only review queue API 모두 200 응답·정상 계약 확인 후 시험 서버 종료. 기존 8765 포트·원본/백업/운영 PID는 변경하지 않음. 실제 운영 장애·전원 손실 시험은 별개.
4. **실제 RFP 현황과 24건 실데이터 준비도 read-only 검증:** 실운영 로컬 `/api/dashboard`의 공고 **5,691**, 전체 검토 후보 **347**, 활성 후보 **220**, 텍스트 추출 **87**, 공식 문서 확보 대기 **130**, 절단 품질 신호 **12**, 경고 신호 **21**. 실제 공고 24건의 `/api/dashboard/readiness?id=...` 호출 **24/24 HTTP·파싱 정상**. 사람의 결정 유지 **24/24**, 자동 참여 승인 없음 **24/24**. 요구사항 큐 220건이 계속 `human_review_required=true`로 반환. 실제 참가자격/평가기준/과업 범위 독립 문장 라벨과 TP/FP/FN/Recall은 **NOT ESTIMABLE**.
5. **실제 회사 자료 적격 검증:** 로컬 API의 근거 준비도 계약을 24개 실데이터에서 읽기 전용 확인. 실제 면허·실적증빙/검증된 인력 MM·원가·자격 요건의 실질 충족 여부에 필요한 사람이 확인한 증빙은 접근/승인·독립 대조가 없어 **NOT VERIFIED**. 현재 합성/메타데이터를 "적격 확정"으로 승격하지 않음.
6. **실제 로컬 UI 브라우저 확인:** Windows Chrome에서 운영 서비스 `127.0.0.1:8765` 대시보드 렌더·수집 내비게이션·추천 목록 갱신·추천 카드·공고 상세·요건 탭·RFP 근거 요청 및 상태 표시 확인, `SPRINT1_CHROME_UI_E2E=PASS`, 종료 0. 화면 실사용자의 정보 구조·가독성·법적 판단 확인 및 UI 최종 승인은 **NOT APPROVED**.

## 데이터 경계

- 비공개 RFP 본문·원문 파일·공고 식별번호·회사 내부 직원·원가·인증키·개별 해시는 GitHub/외부 Codex에 전달하지 않았음. 회사 데이터 대조와 실제 원문 전수 라벨링은 로컬 권한/사람 판단이 필요.
- 검사/복원 도구와 전체 인벤토리/SBOM/라이선스 파일 후보 결과는 개인 Windows PC의 `AgentRunner`에만 보관. 공개 소스에는 이 비식별 집계와 재현 가능한 exporter/합성 테스트만 반영.
- 변경 브랜치 `feat/sprint1-search-demo`. 로컬 운영은 이전 **P09 소스 `f06a3fa`** 유지. 공급망 도구/README를 운영 서비스에 자동 배포하지 않는다. `main` 병합·인터넷 공개·실제 입찰/서명·결제는 별도 승인.
- D-10 과거 7일 API 실패 진단은 계속 의도적으로 보류.

## 남은 검증과 완료 정의

- PURL/SPDX 코드 수정과 SBOM 합성 테스트는 **IMPLEMENTED/WINDOWS_TESTED/CODEX_GO**로 표기. 신규 커밋의 GitHub CI 성공 여부는 Actions 실제 완료 후 갱신.
- 라이선스 파일 누락 후보 3개 + 실제 OCR/PDFium 바이너리 및 npm 21개 패키지의 고지 파일은 공식 배포 원문 대조가 필요. 해시 고정 wheel/wheelhouse 설치 재현은 별도.
- 안전한 격리 서버 구동은 확인했지만 운영 기기 장애, 라이브 DB 동시 쓰기, 재해 복구 시간 목표의 충족은 별개.
- RFP의 독립 원문 FN/Recall과 사용자/회사 증빙 최종 승인, 모든 원본 최신성·정정·취소 판단은 사람과 승인된 실제 자료가 필요한 게이트.
