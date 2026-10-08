# 현재 개발 상태

- 기준일: 2026-10-08
- 단계: Codex 재검수 R2·R3 지적사항에 대한 설계 수정 완료 / R4 독립 검수 대기
- 저장소: 공개
- 라이선스: Apache-2.0
- 서비스 구현: 미착수
- 테스트: 미실행
- 배포: 미실행
- 독립 설계 리뷰: Codex 초기 검수(13건) → R2(주요 7건) → R3(주요 6건). 지적된 설계 계약을 수정했으며 R4 검증 전까지 `HOLD` 유지

## 확인된 사항

- `son1004007/public-bid-agent` 저장소가 존재합니다.
- 프로젝트 작성 코드와 문서는 Apache-2.0을 적용합니다.
- 제3자 공고/RFP의 이용조건은 별도로 유지합니다.
- 목표는 공공 AI/SW 입찰 탐색 및 원문 근거 기반 적합성 분석입니다.
- 공공데이터포털에서 조달청 나라장터 입찰공고정보서비스를 제공하고 있습니다.

## 구현 전 확인 사항

1. [ADR 설계 8개](docs/adr/README.md)에 Codex R2/R3의 최신 공고 projection, PDF 추출 완전성, 기존 SSE 권한 철회, React 출력 안전, 질문·답변 최소수집, 영속 사용량 장부를 반영했다. 아직 R4 재검수와 주요 finding 판정 정리가 필요하다.
2. 나라장터 API의 실제 작업/필드/첨부 수집 방법 검증
3. Google OAuth 운영 설정과 redirect/origin 정책 검증
4. 오픈소스 ChatGPT 플랜 연동(SIWC)과 원격 호스팅 앱의 별도 승인/등록 요건을 구분하여 공식 지원 여부 검증
5. 운영비, 비밀정보 보관, 배포 대상 결정

## 리뷰 실행 자료

- [Gemini 1차 리뷰](docs/reviews/2026-10-08-agy-gemini-raw.md)
- [Codex 1차 독립 리뷰](docs/reviews/2026-10-08-codex-raw.md)
- [검토 결과 조정](docs/reviews/2026-10-08-review-reconciliation.md)
- [Codex R2 원문](docs/reviews/2026-10-08-codex-r2-raw.md)
- [Codex R3 원문](docs/reviews/2026-10-08-codex-r3-raw.md)
- [한글 설계 결정](docs/adr/README.md)
