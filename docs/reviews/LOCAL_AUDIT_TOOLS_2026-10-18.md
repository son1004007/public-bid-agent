# 2026-10-18 Local security audit tooling installation

## Verified current state

- A separate Windows `AgentRunner/audit-venv` was created with Python 3.12. It is **not** the `Lab/.venv` interpreter used by P09 localhost service.
- Installed: `jsonschema 4.26.0`, `packageurl-python 0.17.6`, `pip-audit 2.10.1`, `cyclonedx-python-lib 11.12.0`, `license-expression 30.4.4`. Their dependencies installed successfully and `pip check` PASS. Reproduction manifest: `scripts/requirements-audit-tools.txt`; install into a separate development-only virtual environment.
- Actual prior Python CycloneDX 1.5 SBOM: 48 components, official schema validation errors **0**, PURL canonicalization errors **0**, unresolved graph references **0**. 26 syntactically valid SPDX metadata expressions remain unverified legal claims; release approval is not implied.
- `pip-audit` scanned **47** of the 48 observed package versions and reported **0 known advisories**. `packaging 26.3` was absent from the audit result and was queried separately against OSV, which returned **no advisory records**. No false claim of 48/48 being scanned by pip-audit.
- Public package wheel reinspection for `et-xmlfile 2.0.0`, `langsmith 0.14.6`, `openpyxl 3.1.5`: none of the downloaded wheels exposed a readily identified LICENSE/NOTICE file under the inspected names. The public PyPI source archives were then downloaded with published SHA-256 digest verification: `et-xmlfile 2.0.0` includes `LICENCE.python` and `LICENCE.rst`; `openpyxl 3.1.5` includes `LICENCE.rst`; `langsmith 0.14.6` source archive supplied no matching named file. The project's official `langchain-ai/langsmith-sdk` repository MIT LICENSE was retrieved for local evidence, but an exact release-tag equivalence/legal notice still needs verification. All three packages were **already installed** in the application environment. The evidence is local and no user data were transmitted.
- Query data sent externally: only public package names and versions. Local RFP, employee/cost information, API keys and actual package file contents were not sent to an external AI or committed.

## Scope and remaining release gates

- Package scanners check published advisories, not all defects or misuse. The pins file is an observed version snapshot, not a fully hashed reproducible lock.
- Full license text/NOTICE verification for all redistributed wheels, Python/PDFium/Tesseract/kor-eng language packs, and npm dependencies is a separate approval gate. Missing wheel files are not proof of an invalid license.
- Production process, `main`, live RFP and existing protected JSON were not modified by this tooling installation. Real RFP TP/FP/FN and company eligibility are **NOT ESTIMABLE** without source-grounded independent labels/authorized company records.
- D-10 seven-day API failure investigation remains deferred.

## Safe reinstallation, Windows PowerShell

```powershell
$envRoot = Join-Path $env:LOCALAPPDATA 'PublicBidAgent/AgentRunner/audit-venv'
py -3.12 -m venv $envRoot
& (Join-Path $envRoot 'Scripts/python.exe') -m pip install -r scripts/requirements-audit-tools.txt
& (Join-Path $envRoot 'Scripts/python.exe') -m pip check
```

Execute the last two commands from the project root. Keep public dependency audit artifacts outside the Git tree and do not include user data.
