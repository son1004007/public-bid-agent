# AGW-05 / P0-03 — RFP 추출 Chunk 원문 보존과 구조 완전성 보류

- 기준일: 2026-11-21 KST
- 작업 원장: [TASKS.md 최상단 P0-03](../../../TASKS.md)
- 상태: CODE_IMPLEMENTED / SYNTHETIC_CI_PASS_SHA_80ef1409 / NAS_REAL_5_RFP_READ_ONLY_SOURCE_SPLIT_PASS / NAS_REEXTRACTION_DB_WRITE_NOT_RUN / PUBLIC_COMPLETE_OFF
- 선행: [P0-01 실원본 5건 보전](AGW-05-P0-01-LIVE-NAS-VERIFY-2026-11-20.md), [P0-02 공식 raw vs canonical DB source mapping](AGW-05-P0-02-OFFICIAL-SOURCE-RECONCILIATION-2026-11-21.md) (운영 DB migration/real link 아직 NOT_APPLIED).

## 1. 문제

기존 extractor_service.py는 파서가 반환한 본문/표 셀을 통째로 Chunk.text에 저장하며 UTF-8 1,800 bytes를 넘길 수 있었습니다. 기존 AI Gateway는 이런 Chunk를 조용히 자르는 대신 거부하므로, RFP 자격요건이 후반에 있는 경우 사용할 수 없는 출처가 됩니다. 길이 5 이하 표 셀은 아예 건너뛰어 점수/필수요건 표 토큰을 누락했습니다. 각주는 구조 객체에만 저장하고 Chunk에는 넣지 않았습니다. 기존 HWPX fallback 4건은 텍스트만 추출하며 표 격자/각주 anchor의 복원 근거가 없고, 추출한 5건 모두 ExtractionRun.coverage.complete 키가 존재하지 않았습니다.

## 2. 변경

- [source_chunking.py](../../../server/bid_server/procurement/source_chunking.py): Unicode codepoint 사이에서만 UTF-8 최대 1,800 bytes 단위로 분할. 공백/개행/조합 문자/한글/emoji 포함 본문을 무손실 재연결. 각 span에 char_start/end, utf8_start/end, extracted source text SHA-256, span SHA-256 부여. 출처는 EXTRACTED_BLOCK_TEXT: **원본 HWPX ZIP 내 XML byte offset이 아니라 파서로 추출한 단일 블록/셀 텍스트 내 오프셋**입니다.
- [extractor_service.py](../../../server/bid_server/procurement/extractor_service.py): 원본 DocumentVersion size+SHA/미디어/ACL 이중 대조 뒤, 모든 본문·비어 있지 않은 표 셀(1글자 포함)·실제 각주 텍스트의 span을 사전 계산. 빈 각주를 나타내는 구 버전 생성 문구는 진짜 원문으로 저장하지 않습니다. 각 Chunk에 원본 문서 SHA, 추출 텍스트 hash/segment hash 및 block/cell/footnote ref를 함께 저장. 30,000 chunks/run 및 2,048 spans/block 한도 초과, UTF-8 오류, 원본 SHA 불일치 시 트랜잭션 저장 차단.
- 기존 ExtractionRun/DocumentStructure.coverage JSON에는 chunk_count, chunk_utf8_bytes, max_chunk_utf8_bytes, source_text_lossless_segmentation, offset_origin, source_document_sha256 기록. **complete=False, status=PARTIAL, structure_fidelity=UNVERIFIED**를 모든 새 추출에 보수적으로 명시. 텍스트 파싱 성공을 뜻하는 ExtractionRun.state=PARSED와 표·각주까지 완전함을 뜻하는 coverage.complete는 의도적으로 구분. fallback에는 TEXT_ONLY_LAYOUT_AND_FOOTNOTES_UNVERIFIED, 구조화 파서에도 STRUCTURAL_COVERAGE_NOT_VERIFIED 경고를 남겨 모델/직원 PUBLIC packet 생성 금지.
- 기존 DB 스키마의 Chunk.locator/refs, ExtractionRun.coverage/warnings JSON을 재사용합니다. 신규 migration 없음. **기존 5건 ExtractionRun 또는 Chunk는 삭제/수정/재처리하지 않았습니다.**

## 3. 실제 개인 NAS 5건의 비변경 검증

- 증거: Gateway 개인 NAS read-only job `job_01M7XD0K8Z00PV044MDX3RXN6K` 성공(exit 0). `--network none`, 기존 DB socket/secret/media volume 모두 readonly, PostgreSQL SET TRANSACTION READ ONLY, 비승격 UID. 새 파서·분할 함수는 일회성 프로세스 메모리에만 주입. 기존 NAS 배포 컨테이너를 교체/재시작하거나 실제 원문/DB를 변경하지 않았습니다.
- 원본 SHA 및 DB Notice/DocumentVersion·owner/공유 OFF/current/freshness: 5/5 PASS. 1건 구조화 파싱, 4건 text-only. 추출된 모든 블록·셀 텍스트의 재결합 일치, UTF-8 <=1800 바이트 PASS.

| 기존 문서 SHA 접두 | 처리 형태 | 블록 | 새 로직 예상 Chunk | 표 셀 추출 | 5자 이하 짧은 표 셀 |
| --- | --- | ---: | ---: | ---: | ---: |
| d18a9208 | text-only | 5,073 | 5,073 | 0 | 0 |
| d72eba52 | 구조화 | 763 | 1,028 | 298 | **149** |
| b1d34223 | text-only | 2,573 | 2,573 | 0 | 0 |
| f59c44f8 | text-only | 3,622 | 3,622 | 0 | 0 |
| 0c74c8fa | text-only | 2,447 | 2,447 | 0 | 0 |
| **합계** | | | **14,743** | **298** | **149** |

- 기존 최신 Chunk 총량 **14,594** 대비 새 로직의 예상 14,743개는 기존 5글자 이하 표 셀 149개를 포함하기 때문입니다. 단, **14,743개를 NAS DB에 저장했다는 뜻이 아닙니다.** 실제 5건의 기존 coverage.complete는 모두 미설정이었습니다. 실제 5건에서 구조화된 각주는 0건이고, 각주 Chunk 로직은 합성 테스트로만 검증했습니다.
- 전체 인수 경계: 출처 text span의 SHA/위치는 재구성할 수 있으나, HWPX의 실제 표 병합 좌표, 본문 내 anchor, 그림/OCR, nested 문단의 중복 여부가 완전하게 검증된 것은 아닙니다. 따라서 parsed != complete이고 문서 전체 전송/업무 자격 자동충족 판정은 허용하지 않습니다.

## 4. 테스트

- [test_source_chunking_p003.py](../../../server/tests/test_source_chunking_p003.py): Unicode(한글, emoji, 결합문자, 개행), 바이트 경계, zero/NULL/미완성 surrogate, 모든 span의 SHA·byte/char offsets·연결 무손실, 1글자 table cell, footnote chunks, fallback warning/partial coverage, 원본 불일치 및 chunk budget rollback.
- 최신 코드 SHA `80ef1409750de4c8672f877802249d7ece64d6dc`: [core 94 PASS](https://github.com/son1004007/public-bid-agent/actions/runs/44818921068), [Django Windows/Linux/PostgreSQL 각각 437 tests PASS](https://github.com/son1004007/public-bid-agent/actions/runs/44818921064); 해당 SHA에서 migrate check도 PASS. 별도 [Windows synthetic local acceptance](https://github.com/son1004007/public-bid-agent/actions/runs/44818463585) 등 이전 코드 SHA 기준 워크플로도 PASS. 기존 테스트의 오류 타입을 정확히 검증하도록 수정한 상태까지 재검증했습니다.

## 5. 다음 단계 / 승인 경계

- P0-02 기존 NAS 운영 PostgreSQL mapping migration+real record는 여전히 미적용. 승인된 백업/복구·릴리스 게이트 통과 후 실행할 것.
- P0-03 실제 NAS DB 재추출(write)은 미수행. 데이터 버전·권한/구성 독립 검증과 승인된 운영 프로세스 없이는 기존 원본/Chunk 또는 reviewer 결정을 덮어쓰거나 삭제하지 말 것.
- P0-04 실제 staff PUBLIC attestation/AI provider export는 별도 인수. 현재 public_source.py의 metadata digest == raw bytes SHA 비교는 실공고에는 맞지 않으므로 OfficialSourceLink 별도 재검증 계약으로 수정 필요. complete가 False인 동안 PUBLIC snapshot은 fail-closed.
- 기타 HOLD: 회사 data1 배포, 직원 비밀 원가/개인자료 반출, AGY/Gemini 위임 재개, 기존 스케줄 임의 변경, Draft PR #5 merge/release blocker bypass.
