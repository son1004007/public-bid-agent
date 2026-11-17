# PR #5 security semantic review — 2026-11-17

Status: REVIEW_IN_PROGRESS / NO_GO_FOR_MERGE. Source HEAD at review: `7c1381dffed042063e85c1ff200576163b3bc747`. This is a focused code review finding, not a completed 105-file independent review.

## Confirmed code finding: synthetic RFP body silently persisted (P1 data integrity)

`server/bid_server/procurement/views.py::DocumentExtractAPIView.post` accepts POST for any authenticated user with the document UUID. It calls `request.body` and, if the payload is absent or shorter than four bytes, substitutes the hard-coded Korean text "과업지시서 및 제안요청서 본문 내용입니다." with the document logical key, then passes this fabricated source into `ExtractionService.extract_and_persist`. This produces a 201 extraction response and persistent extraction artifacts from content that was never supplied by the caller or official source. A valid empty or short request therefore may create a misleading evidence record. The authenticated user is not restricted to a document ownership/tenant scope in this view; the current model is not confirmed multi-tenant, so this requires explicit policy validation before shared company deployment.

Reproduction from source: authenticated POST to `/api/v1/documents/<existing-document-version-uuid>/extract` with empty body reaches fallback and `extract_and_persist`; code path confirmed by reading source. HTTP reproduction NOT RUN; do not claim exploitation against live data.

Required minimum correction before GO: reject missing/short body with a deterministic 4xx response and no DB writes; require explicit content-type/size validation; use the actual approved source bytes or a verified stored source, not generated placeholders. Add a synthetic DB test asserting no ExtractionRun/DocumentStructure created for empty/short payload, plus successful extraction of a valid fixture. Review authorized document scope for authenticated users and add cross-user/cross-scope negative test once tenancy contract is fixed. Do not modify existing document records to reproduce.

## Other verified evidence

- PR #5 HEAD `7c1381dffed042063e85c1ff200576163b3bc747` is draft, not merged. Four GitHub Actions workflows at that SHA succeeded: Server foundation CI #44042255613, Development harness #44042255560, Sprint 1 CI #44042255486, Windows synthetic #44042255518. CI success does not close the semantic finding.
- Gateway Windows non-elevated read-only inspection succeeded: `C:\Users\User\source\public-bid-agent-bid03` exists, HEAD `1994a2ff3aa6ad6ceaf9abe8495122d1c9093a24`, at least 12 tracked modified files and 34 untracked files, 127.0.0.1:8000 listening (PID 15924). Existing workspace must not be reset/cleaned/checked out. No deployment or HTTP/data SHA verification performed.
- New 2026-11-17 aggregate-cost design is documented but NOT_IMPLEMENTED. It must not be misrepresented as working role isolation.

## Next gate

Keep draft and main unchanged. Implement minimal fix with tests in a separate clean workspace or isolated GitHub branch; rerun same-HEAD CI and independent review. Continue full authn/authz, CSRF, secret, restore, concurrency, dependency and CI trust-boundary review. Check secrets/PII committed and original protected data hashes before deployment. Windows localhost test must use a non-conflicting port and a clean SHA-matched checkout.

## 2026-11-17 follow-up fix (pending CI)

On PR head 86c25c9872d4f657aa50acf9bb035095d01ba994, removed the synthetic text fallback in `DocumentExtractAPIView`. Empty/short payloads now return 400, unsupported media type 415, and payloads above 10 MiB 413 before persistence. Added 3 isolated HTTP integrity tests covering empty/short, unsupported and valid synthetic plain-text input. Code change committed only to PR branch, not main; local test execution and same-head Actions verification pending. The endpoint deliberately does not claim support for binary document uploads; content-type/file-format and document source provenance/tenant authorization still need independent review before shared deployment. This change does not solve the separate object-scope finding.


## 2026-11-17 19:48 KST — P1 source binding follow-up

- Rechecked PR #5 head `782cde6a6b89b50c0ebb60599b9174d6ab91a37b`: same-head four workflow families SUCCESS (Server foundation 44060277740/44060269123, Sprint 1 44060277621, Harness 44060277841, Windows synthetic 44060277758). These results predate this follow-up and cannot verify the new HEAD.
- P1 found: `DocumentExtractAPIView` accepted any nonempty text/plain body and persisted `ExtractionRun` under an existing `DocumentVersion` without comparing bytes to immutable `sha256` and `size_bytes`. A caller could attach unrelated text to an RFP version; provenance and downstream evidence would be false.
- Changed `server/bid_server/procurement/views.py` to reject mismatched size or SHA-256 with HTTP 409 before extraction writes. Changed `server/tests/test_document_parser_def03.py` synthetic fixture to use real digest/size and added same-size wrong-digest and wrong-size negative cases asserting zero persisted runs/structures.
- Commits `af36ca33c0d80c8e9c40393f225dea2234f34237`, `a277fd8425c9358bb6753f7a827c6a5fc5ae83e2`. Explicit file allowlist only; no local/Windows workspace writes.
- **UNVERIFIED**: same-head CI, independent review, source object access authorization, uploaded body limit at middleware, parser format/media-type consistency, legacy direct service callers, whole-PR security, Windows isolated HTTP, protected data SHA. Keep PR draft and main merge NO_GO until all gates.
