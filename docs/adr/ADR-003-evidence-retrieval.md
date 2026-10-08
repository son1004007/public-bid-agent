# ADR-003 원문 근거 추적 및 검색·임베딩

- 상태: **근거 계약 채택 / 임베딩 공급자 결정 보류**
- 관련 지적: DSR-006, DSR-010
- 목표: 결과의 각 판단을 **어느 시점의 어떤 원문 구간**에서 가져왔는지 재검증 가능하게 한다.

## 최소 데이터 계약

- `SourceDocumentVersion`: `document_id`, 공식 출처 URL, `source_notice_revision_id`, 바이트 해시, 관측 시각, 취득 권한/조건 및 저장 정책.
- `ParsedArtifact`: 해당 원문 버전의 `parser_name/version`, `extractor_configuration_hash`, 추출 성공/실패, 출력 checksum과 **추출 완전성·범위**를 별도 기록.
- `Passage`: `passage_id`, `parsed_artifact_id`, 페이지/섹션/문자 오프셋(지원되는 범위), 내용 해시. 오프셋 미지원 시 위치 정확도를 `UNKNOWN`으로 남긴다.
- `ExtractedRequirement`: 인용 가능 근거 ID, 요구 조건의 원시 표현·정규화 형태·필수/권장 구분·추출 신뢰상태.
- `Claim`: 결과로 제시할 주장, 그 주장의 근거 상태, 공고 버전, 분석 시점.
- `EvidenceLink`: `claim_id`, 유효한 `passage_id`, `SUPPORTS`/`CONTRADICTS`/`INSUFFICIENT` 관계, `verification_status` 및 검증 주체·버전·시각.

## 결정

1. Citation은 LLM이 작성한 문자열 URL을 그대로 믿지 않는다. 백엔드가 허용한 passage ID에만 연결하며 ID 존재·소유권·원문 버전을 검증한다. **이 구조적 유효성만으로 passage가 주장 내용을 의미상 지지한다고 단정하지 않는다.**
2. 검색 실패와 '해당 내용이 없다'는 주장을 구분한다. 검색 실패 시 `NEEDS_REVIEW` 등 명시적 불확실 상태를 유지한다.
3. 정정·재파싱 이후에도 이전 분석 결과는 당시 `SourceDocumentVersion`과 `ParsedArtifact`를 참조한다. 원문을 보관하지 않는다면 **재현 불가 위험을 기록**하고 현재 원문 링크로 자동 대체하지 않는다.
4. 초기 검색 기준은 정확 키워드·섹션 분할·전문 검색 등 결정적 baseline이다. pgVector는 실제 평가에서 근거 검색 품질 개선이 확인되면 추가한다.
5. 임베딩은 LLM 추론 인증과 별도 공급자/모델/차원/비용/데이터 국외 전송을 평가하는 승인 게이트가 있다. 공식 API 또는 사용권 검증 없이 Codex가 임베딩을 제공한다고 가정하지 않는다.
6. 계약 또는 라이선스상 원문 저장·임베딩이 허용되지 않으면 외부 원문 링크/허용된 최소 메타데이터만 사용하고 벡터화를 비활성화한다.
7. 사용자별 기업 프로필은 공개 원문 corpus에 섞지 않는다. tenant별 검색·분석 범위는 서버 ownership을 검증한다.

## 평가 절차

공개 출처/라이선스 확인된 원문에서 표본을 선정하고 출처·수집 버전·파서 버전을 기록한다. AI/SW 관련성, 요건 추출(특히 필수조건 누락), 검색 passage 적중, claim-evidence 검증, 결과 상태 판정을 **각각** 측정한다. 정상·모호·정정·문서누락·상충 요건을 포함하고 어노테이션 기준 및 불일치 조정 절차를 기록한다. 데이터가 적으면 통계적으로 검증됐다고 주장하지 않는다.

릴리스 품질 기준은 실제 baseline을 먼저 측정해 결정한다. 측정 전 수치를 임의로 약속하지 않으며, **근거가 없는 확정적인 참가자격 판정은 허용하지 않는다**는 안전 불변조건은 수치와 독립적으로 적용한다.

## 의미상 근거 타당성 검증 — R2-004

- 근거 연결 상태: `PROPOSED`(모델 제안), `STRUCTURALLY_VALIDATED`(존재·출처·버전·소유권·위치 검증), `SEMANTICALLY_REVIEWED`(해당 주장과 문맥에서 실제 지지/반박 여부 검토), `REJECTED`(잘못되거나 무관한 근거). 각 상태 변화는 검증 방법(`DETERMINISTIC/AUTHORIZED_HUMAN/UNVERIFIED_MODEL`)·검증자/도구 버전·시각을 함께 기록한다.
- 모델이 같은 문서의 **실제 passage ID**를 선택해도 문맥상 무관하거나 반대 의미일 수 있다. 구조 검증 통과는 의미 검증 통과와 다르다.
- `SEMANTICALLY_REVIEWED`는 사람이 문맥을 점검했거나, 제한된 구조적 사실을 재현 가능한 결정적 규칙으로 검증한 경우 등 검증 방법과 범위가 명시된 상태만 허용한다. 모델 자신의 self-check만으로 이 상태를 부여하지 않는다.
- 중요한 필수 참가요건의 결론을 확정하려면 해당 판단의 관계(`SUPPORTS/CONTRADICTS/INSUFFICIENT`)가 문맥상 뒷받침되어야 한다. 그렇지 않다면 결과는 `NEEDS_REVIEW`이며 UI에서 해당 문장을 '모델 제안 근거/미검증'으로 표시한다.
- UI는 최소한 passage 발췌, 공식 링크, 문서 버전·위치 정확도, 검증 상태 및 반대/부족 근거를 구분한다. 민감한 제3자 정보는 별도 마스킹·인용 최소화 규칙(ADR-008)에 따른다.
- 모델의 인용은 서버가 제공한 후보 집합으로 제한하고, 허위 ID·잘못된 문서·다른 사용자/버전은 서버에서 거부한다.
- 테스트는 존재하지만 무관한 passage, 정반대 의미, 일부 조건만 표현한 passage, 조건의 부정/예외, 다른 문서/버전 인용을 포함한다. 이 사례들이 `SEMANTICALLY_REVIEWED`로 자동 승격되면 실패다.

## PDF 추출 완전성 및 필수요건 포괄성 — R3-002

- `extraction_completeness`: `COMPLETE`, `PARTIAL`, `UNREADABLE`, `UNKNOWN`. parser 실행 성공(`parse_status=SUCCESS`)과 **판정에 필요한 내용 추출 성공**은 서로 다른 축이다.
- 원문 페이지 총수, 실제 처리 페이지 수, 텍스트 없는 페이지 수, 이미지 전용 페이지, 표 추출 여부, 처리 중단 사유와 허용 문자/분량 초과를 기록한다.
- 모든 페이지를 처리했다는 사실만으로 `COMPLETE`로 자동 승격하지 않는다. 표/스캔/특수 폰트/텍스트 누락 위험 검사가 통과하고 추출 가능한 범위가 확인될 때만 제한적인 `COMPLETE`를 부여한다.
- 스캔 PDF에 대한 OCR은 초기 MVP에서 자동 수행하지 않는다. 이미지 전용 PDF, 심한 텍스트 깨짐, 과도한 페이지, 표 추출 실패, 일부 페이지만 추출한 경우에는 `PARTIAL/UNREADABLE/UNKNOWN`을 설정하고 **필수 참가요건을 모두 검토했다고 주장하지 않는다**.
- `SUITABLE`은 문서 내용 범위와 필수요건 추출의 포괄성이 확인되고, 중요한 근거가 의미 검증된 경우에만 가능하다. 그렇지 않으면 `NEEDS_REVIEW`. 추출본이 완전해도 법적 적격성을 보장하지 않는다.
- 테스트: 합성 이미지 PDF, 텍스트 없는 페이지, 표 안의 필수조항, 특수 글꼴, 암호화·손상, 페이지 제한 및 partial extraction. 이러한 사례가 `SUITABLE`이 되면 출시 실패.

## 검증 상태·주체·관계의 단일 스키마 — R3-Q01 / R4-001

`EvidenceLink`는 아래 **서로 다른 필드**를 갖는다.

| 필드 | 허용값 | 의미 |
|---|---|---|
| `verification_status` | `PROPOSED / STRUCTURALLY_VALIDATED / SEMANTICALLY_REVIEWED / REJECTED` | 근거 연결 자체의 검증 단계 |
| `review_source` | `NONE / DETERMINISTIC / AUTHORIZED_HUMAN` | 의미 검증을 수행한 권한 있는 경로 |
| `semantic_relation` | `SUPPORTS / CONTRADICTS / INSUFFICIENT` | 정확히 어떤 주장에 대한 관계인지 |
| `validator_ref` | 버전이 있는 `rule_id` 또는 권한 있는 `service_reviewer_id`, 없으면 null | 검증 책임과 재현 근거 |
| `user_acknowledged_at` | 시간 또는 null | 일반 사용자가 출처를 읽었다는 행위. 검증 상태를 변경하지 않음 |
| `source_document_version_id` | 존재·소유권·범위를 확인한 버전 ID | 근거가 참조하는 원문 |

**DETERMINISTICALLY_VERIFIED, SERVICE_REVIEWED, USER_ACKNOWLEDGED는 별도의 verification_status enum 값이 아니다.** 설명상의 검토 방법·사용자 행위를 뜻하며 코드·DB·API에는 위 표의 정확한 값만 사용한다.

전이 및 권한:

1. 모델은 `PROPOSED` 제안만 가능하다. `review_source`·`verification_status`를 모델 입력값으로 신뢰하지 않는다.
2. 서버는 허용된 passage ID·버전·소유권·범위를 검증한 뒤 `STRUCTURALLY_VALIDATED`로만 승격할 수 있다.
3. `SEMANTICALLY_REVIEWED`는 좁은 범위의 재현 가능한 결정적 규칙(`review_source=DETERMINISTIC`, 유효한 rule id/version) 또는 별도 승인된 서비스 운영 검토자(`AUTHORIZED_HUMAN`, 실제 reviewer id)의 확인 뒤에만 가능하다.
4. 일반 사용자는 자신의 자료를 `user_acknowledged_at`으로 표시할 수 있지만 서비스 의미 검증을 승인할 수 없다. 타 사용자의 자료에는 이 행위도 금지한다.
5. 현재 포트폴리오 MVP에는 서비스 전담 검토자가 없으므로 `AUTHORIZED_HUMAN` 승격 UI/권한을 구현하지 않는다. 규칙으로 검증할 수 없는 해석적 자격 판단은 `NEEDS_REVIEW`.
6. `SUPPORTS`인 의미 검증만 충족 근거로 쓰고, `CONTRADICTS`는 충돌 근거로 표시한다. `INSUFFICIENT` 또는 검증 상태 미완성 시 SUITABLE 승격 금지.
7. 재파싱/공고 정정은 기존 링크의 값을 조용히 변경하지 않고 새 원문·분석 버전으로 별도 검증한다.

검증: 모델/일반 사용자/다른 사용자의 의미 승격 거부, rule version 누락, reviewer id·권한 누락, 지원 관계 상충, DB/API/도메인의 enum 계약 불일치, 사용자 확인만으로 SUITABLE 변경되는지 확인.
