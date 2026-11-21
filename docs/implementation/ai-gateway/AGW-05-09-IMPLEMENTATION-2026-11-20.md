# AGW-05/09 실행 기록 — RFP 근거 스냅샷·분석 JSON 검증/불변 이력

- 기준: 2026-11-20 KST
- 저장소: `son1004007/public-bid-agent`, 개발 브랜치 `fix/bid-security-20261116`, Draft PR #5
- 범위: **코드 구현 + 합성 테스트**. NAS 런타임 및 제한된 모델 호출을 이전에 검증했지만 **본 변경은 모델 실호출/데이터 반출/운영 DB migration 없이 합성 RFP에 한정한다.**
- 결정: 사용자 최신 지시인 정확도 우선/유료 호출 허용을 적용하되, 모델 응답이 법적 참가자격·원가·회사 실적의 권위 있는 사실을 생성할 수 없도록 fail-closed.

## 실제 구현 파일

| 단위 | 구현 | 동작 및 검증 |
| --- | --- | --- |
| AGW-05 코어 | [`ai_gateway_core/snapshot.py`](../../../server/ai_gateway_core/snapshot.py) | `AnalysisRequestV1`에 대응하는 `run_id/notice_version/corpus_snapshot/prompt_version/요구사항/근거` 패킷 생성. 데이터 분류는 `PUBLIC` 또는 `SYNTHETIC`으로 제한; 현재 Django는 **SYNTHETIC만** 작성. 문서 ID 허용목록·source_version/span·extract 상태·근거별 requirement 링크·길이/건수 상한, canonical JSON SHA-256 및 재검증. 모델·네트워크 I/O 없음 |
| AGW-09 코어 | [`ai_gateway_core/result_contract.py`](../../../server/ai_gateway_core/result_contract.py) | 원문 JSON 중복 key/NaN/과다 크기, 잘못된 run/provider/version/hash, 누락/중복 requirement, 존재하지 않거나 다른 요구사항의 evidence ID, 스키마 외 필드, 근거 없는 자격 판정 거부. **RFP 증거만 있을 때 MET과 NOT_MET을 모두 금지**, `UNKNOWN`에는 missing reason 요구. 초기 리스크/시나리오/unknowns 배열은 **빈 배열만 허용**하는 의도적 축소 계약 |
| AGW-05 Django | [`analysis_service.py`](../../../server/bid_server/ai_gateway/analysis_service.py) | `create_synthetic_analysis_run`: `Notice.source=SYNTHETIC_FIXTURE`에서만 최신 NoticeVersion, DocumentVersion+owner/shared ACL, `ExtractionRun.PARSED`, `DocumentFreshness.CURRENT`, 실제 `Chunk`를 DB 조회. 입력 Chunk 본문은 1.8KB로 제한, SHA-256과 출처를 고정하여 `AnalysisRun` 저장. 문서의 직원급여·실제 회사기밀은 넣지 않음. 동일 user+notice+request_key 재요청은 input_digest 동일할 때만 기존 run 반환. 회사 부서별 예산/원가 SQL, PUBLIC 실제 공고 전송은 이 API에서 **제공하지 않음** |
| AGW-09 Django | [`models.py`](../../../server/bid_server/ai_gateway/models.py), [`0002_analysis_results.py`](../../../server/bid_server/ai_gateway/migrations/0002_analysis_results.py) | `AnalysisRun`에 원본 패킷/hash, 작성자, 공고 버전, 입력 멱등키; `AnalysisRevision`에 공급자/차수/검증된 JSON/digest 저장. model.save/delete 및 기본 QuerySet.update/delete 차단; FK PROTECT 및 고유 제약. `append_validated_result`은 원본 Chunk 본문/소유권/문서 상태/공고 버전을 DB에서 **다시 검증** 후 정형 결과만 append. 같은 digest 재도착 시 같은 revision, 다른 결과를 신규 revision으로 저장하려면 `authorize_additional_revision=True` 필요 |
| 테스트 | [`test_ai_gateway_snapshot.py`](../../../server/tests/test_ai_gateway_snapshot.py), [`test_ai_gateway_analysis.py`](../../../server/tests/test_ai_gateway_analysis.py) | 중복 JSON key, 허위 근거, 외부 문서 참조, 누락 요건, 오염/변경된 Chunk, ACL 철회, 요청키 충돌, 멱등 반복, 수정 이력/불변 ORM, 잘못된 자격 MET/NOT_MET 차단. **합성 데이터·테스트 DB만 사용** |

## 구체적 정상 경로

1. Django 신뢰된 서비스가 해당 사용자에게 접근 가능한 SYNTHETIC_FIXTURE 최신 공고와 PARSED 문서 Chunk를 조회한다.
2. 고정한 스냅샷의 canonical SHA-256을 계산하고, 이 작업의 run UUID/요청 멱등키와 함께 `AnalysisRun` INSERT.
3. **이 단계에서는 실제 Codex/Claude로 전달하거나 예약 실행하지 않는다.** 사용자가 제공한 회사 실적이 확인되지 않았으므로 RFP 요건에 대한 판단은 UNKNOWN 및 누락 이유 유지.
4. 나중에 승인된 모델 adapter가 만든 strict `bid_analysis_v1` 원문 JSON을 `append_validated_result`로 전달. 서버는 작성자·공고 차수·원문 출처/분류·조회 권한·근거 hash·결과 스키마 검증 후 `AnalysisRevision` INSERT.
5. 동일 result digest면 멱등 재전송; 다른 결과는 기존 결과를 덮어쓰지 않고 **명시 허용된 새로운 revision**. 공급자 2개가 같은 run을 참조할 수 있으나 독립 실행/상충 비교는 아직 미연결.

## 아직 미구현 — 다음 우선순위

- **P0 AGW-05** 공개 실제 공고의 공식 원문 메타·접근범위·추출 품질을 검증하여 provider 별 transmission 승인, RFP 단위 허용 증거/회사 FACT 합산 projection 및 explicit 회사 반출 승인. 현재 합성-only는 회사 보안 우회가 아님.
- **P0 AGW-08** `JobAttempt/Outbox`와 `SessionBinding` lease/fence, NAS Docker `0.171.0 / gpt-6.2-sol / medium` runner를 실제 연결하는 명시적인 사용자 요청 E2E. 중복 모델 호출/토큰 이중과금 주의.
- **P0 AGW-09/13 운영 강화**: 현재 ORM은 Update/Delete를 막지만, **직접 privileged SQL, `_base_manager`, 관리 명령으로는 DB 행 변경 가능**. PostgreSQL 운영 역할 권한·불변 trigger/WORM·민감 패킷 암호화 및 백업 정책 완료 전에는 법적 감사급 불변성이라고 주장하지 않는다. Job/Outbox와 원자 commit은 후속 단계이다.
- **P0 AGW-10** SQL/Decimal 기반 법적 자격·자원 MM·합계 원가 hard gate, 모델 2개 독립 판단의 일치가 사실 증명이라는 오해 방지.
- **P1** Claude 공식 사용자별 로그인/상업 이용, 이슈 재분석/UI/실제 RFP 금본 평가, 회사 data1은 승인 전 HOLD.

## 인수 증거·한계

- 최신 CI 증거: [AI Gateway core](https://github.com/son1004007/public-bid-agent/actions/runs/44676123480) **77 단위테스트 PASS**(snapshot/result 계약 포함). [Django server foundation](https://github.com/son1004007/public-bid-agent/actions/runs/44676123557) Windows/Linux/PostgreSQL 합성 회귀 및 migration check의 **개별 job 상태와 최종 conclusion**을 확인해야 한다. 실측 상태는 `CURRENT_STATE.md`에 완료 후 정본으로 유지한다.
- 현재 사용자 인터페이스에 새 endpoint/분석 실행 버튼은 만들지 않았다. 마이그레이션은 **GitHub-hosted CI 테스트 DB**에서만 진행하며 NAS/prod DB에는 적용하지 않는다. 회사 데이터·인증/토큰·실제 provider thread ID는 공개 Git이나 stdout에 저장하지 않는다.
- 테스트/공식 자료 결과는 Source of Truth인 GitHub Actions 로그와 NAS device-control 런타임 기록으로 판단한다.
