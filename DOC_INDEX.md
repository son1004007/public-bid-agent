# 문서 목차 | Public Bid Agent

상태와 진행률은 아래 정본을 확인합니다. 이 파일에는 상태를 복제하지 않습니다.

| 문서 | 목적 |
|---|---|
| [AGENTS.md](AGENTS.md) | AI 작업 규칙 및 필독 순서 |
| [DECISIONS.md](DECISIONS.md) | 사용자 결정 및 승인 범위 |
| [AI_CONTEXT.md](AI_CONTEXT.md) | 개발 배경 및 작업 인계 |
| [CURRENT_STATE.md](CURRENT_STATE.md) | 최신 구현·CI·실행 증거·차단 사유 |
| [TASKS.md](TASKS.md) | **MVP-FIRST 최신 실행 우선순위**·미완료 작업·재개 순서 |
| [서버 전환 설계 목차](docs/server-migration/README.md) | 서버 전환 상세 설계 |
| [사업부 집계 원가·공동 검토](docs/server-migration/09-aggregate-cost-and-shared-review.md) | 최신 업무 요구 및 승인 경계 |
| [Hybrid RAG 기술 설계](docs/server-migration/10-hybrid-rag-bid-decision.md) | 검색·SQL·판정·데이터/권한·검증 계약 |
| [전사 역량·부서 협업 및 전체 도식](docs/server-migration/12-enterprise-capability-hybrid-rag.md) | 법인/부서 모델, SQL+RAG, 지원 승인·가용성·시나리오 손익 |
| [GPT·Claude·Gemini 연동 후보](docs/server-migration/13-multi-llm-provider-routing.md) | 업체 중립 라우터·승인/비용/데이터 경계, 실제 연동 미구현 |
| [공개 입찰 MCP 연결·검증](docs/server-migration/14-bid-mcp-interface.md) | 읽기 전용 MCP 도구 구현·테스트·원격 연결 미완료 게이트 |
| [AGW-05 공식 공고 출처·원본 SHA 검증 및 공개 승인 구현](docs/implementation/ai-gateway/AGW-05-PUBLIC-PROVENANCE-2026-11-20.md) | 공고·첨부파일·추출기/Chunk 해시 체인, staff 승인형 공개 packet, 사전 재검증, 보안 차단·테스트 |
| [AGW-05/09 합성 RFP EvidenceSnapshot·분석 이력 구현/CI](docs/implementation/ai-gateway/AGW-05-09-IMPLEMENTATION-2026-11-20.md) | 공고·Chunk 출처 증빙 해시, 모델 JSON 검증, idempotent DB AnalysisRun/Revision, 77/378×3 검증 및 미완료 보안 과제 |
| [NAS Docker Codex 실제 Session Resume·AGW-02/04 개발/테스트 기록](docs/implementation/ai-gateway/AGW-NAS-SESSION-E2E-2026-11-20.md) | Synology `son1004007` Docker 실모델 2회/같은 session, DB lease/fence 및 Adapter 코드, 제한사항·다음 작업 |
| [AI Gateway P0 실제 Codex E2E·Adapter·Django DB/API 실행 기록](docs/implementation/ai-gateway/AGW-RUN-2026-11-20.md) | 실제 Windows 개인 CLI 추론/동일 세션 Resume, 소스/35+303×3 테스트, 서버 연결 남은 작업 |
| [AI Gateway 구현 작업 단위별 설계·계획 전체 목차 (AGW-00~15)](docs/implementation/ai-gateway/README.md) | **16개 상세 설계서**, 기술·DB/API·실행·오류·보안·테스트·선행조건, 다른 AI 작업 재개 진입점 |
| [사용자별 Codex·Claude 서버 로그인·Resume 및 독립 교차 검증](docs/server-migration/16-user-cli-session-and-blind-cross-check.md) | 최신 실행·세션 격리·근거 비교/이슈 공유·인수 기준 |
| [Codex·Claude 조건부 교차 검증 및 실행 정책](docs/server-migration/15-mcp-provider-executor-subscription-policy.md) | 0/1/2 프로필 가용 판정, 독립 분석, JSON 근거 비교·불일치 처리, CLI 구독 이용 경계 |
| [사업 담당자 안내](docs/server-migration/11-hybrid-rag-business-guide.md) | 쉬운 업무 흐름 및 가상 예시 |
| [서버 실행·검증 안내](server/README.md) | 격리 환경과 설정 계약 |
| [MVP-05 시범 운영 인계](docs/reviews/MVP05_PILOT_OPERATIONS_2026-11-19.md) | 실제 승인·환경 점검·운영자 명령 |
| [MVP-05 시범 배포 게이트](docs/reviews/MVP05_PILOT_GATE_2026-11-19.md) | 통합 인수 및 실제 배포 승인·복구 기준 |
| [운영·배포](docs/04-operation-and-deployment.md) | 운영 데이터 보존 및 배포 절차 |
| [PR #5 집중 보안 검토](docs/reviews/PR5_SECURITY_SEMANTIC_2026-11-17.md) | 발견 사항과 수정 이력 |
| [하네스 사용 안내](docs/implementation/HARNESS_USAGE.md) | 검증 실행 방법 |
| [AI 시작 안내](docs/implementation/AI_START_HERE.md) | 작업 재개 시 참조 순서 |

신규 문서 작성·이동·삭제 시 이 목차와 해당 하위 목차를 갱신합니다.
