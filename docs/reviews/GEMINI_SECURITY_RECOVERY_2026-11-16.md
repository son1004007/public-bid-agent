# Gemini security recovery - 2026-11-16

## Evidence
- Branch fix/bid-security-20261116; commit e1eb57e; draft PR #5.
- Git ignores local data, backups and scratch; no local dumps staged.
- Restore rehearsal: reserved DB namespace, loopback host guard, SQL identifiers quoted, FORCE DROP removed.
- Backup output is outside Git; table count read errors fail; DB-only coverage explicit.
- Local Django secret stored under LOCALAPPDATA/PublicBidAgent/local; DEBUG false; no fixed startup login credentials.
- Windows isolated venv: 141 tests OK, 3 skipped; PostgreSQL synthetic checksum, table parity, FK and write/rollback passed. Storage artifacts zero, NOT proof of full recovery or zero data loss.
- Staged diff whitespace check passed.
- Isolated test-settings HTTP 127.0.0.1:18080 health 200; server stopped.
- On-demand Windows Task PublicBidAgentLocalWeb with no trigger, loopback local settings 127.0.0.1:8000: health 200, workspace 200 in separate session.
- No real DB migration or procurement submission.
- Development harness and Sprint 1 CI passed; Windows acceptance pending when written.

## Pending gates
- Independent review of the 86-file server foundation and remaining CI before merge.
- Unrelated preexisting modified docs preserved in working tree, not staged.
- No external/NAS/public deployment. This is a loopback development service, not a production release.
