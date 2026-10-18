"""현재 설치 Python 패키지 인벤토리 -> CycloneDX 1.5/관찰 버전 목록.

입력: audit_python_environment.py가 생성한 공개 패키지 메타데이터 JSON.
출력: 사용자가 지정한 신규 JSON SBOM 및 신규 pinned requirements 목록.
신뢰 경계: 비공개 파일·원문·키·설치 경로에 접근하지 않는다; 네트워크 호출 없음.
부작용: 새 출력 파일만 생성. 기존 파일 덮어쓰기/패키지 설치/복구 없음.
검증: 필요한 직접 의존성과 전이 의존성이 모두 설치됐는지 확인.
불변조건: 해시 잠금이 아닌 단일 OS/Python 설치 현황. 릴리스 승인이나 취약점 검사 아님.
관련: scripts/audit_python_environment.py, docs/reviews/DEPENDENCY_SECURITY_AUDIT_2026-10-18.md.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote
import json
import re

from packaging.utils import canonicalize_name
from packaging.version import Version, InvalidVersion

ROOT_REF = "application:public-bid-agent-local:installed-environment"


def refs_and_components(inventory):
    if inventory.get("direct_satisfied") is not True:
        raise ValueError("Direct requirements are not satisfied")
    if inventory.get("inventory_complete") is not True:
        raise ValueError("Inventory graph or metadata is incomplete")
    installed = {}
    for pkg in inventory["distributions"]:
        if pkg.get("dependency_scope") == "ENVIRONMENT_ONLY":
            continue
        name = canonicalize_name(pkg["name"])
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
            raise ValueError("Invalid PyPI distribution name")
        try:
            ver = str(Version(pkg["version"]))
        except InvalidVersion as exc:
            raise ValueError("Invalid installed package version") from exc
        if name in installed:
            raise ValueError("Duplicate Python package")
        installed[name] = (ver, pkg)
    if sum(pkg["dependency_scope"] == "DIRECT" for _, pkg in installed.values()) != inventory["direct_declared"]:
        raise ValueError("Direct distribution count differs from inventory")
    refs = {name: f"pkg:pypi/{name}@{quote(version, safe='.-_')}"
            for name, (version, _) in installed.items()}
    components = []
    for name, (version, pkg) in sorted(installed.items()):
        row = {"type": "library", "name": name, "version": version,
               "bom-ref": refs[name], "purl": refs[name],
               "scope": "required",
               "properties": [{"name": "public-bid-agent:source-scope",
                               "value": pkg["dependency_scope"]}]}
        spdx = pkg.get("spdx_expression")
        # Metadata can be malformed or non-SPDX; do not assert a legal license.
        if spdx:
            row["properties"].append({"name": "public-bid-agent:unverified-license-expression",
                                      "value": str(spdx)[:160]})
        legacy = pkg.get("legacy_license_metadata")
        if legacy:
            row["properties"].append({"name": "public-bid-agent:legacy-license-metadata",
                                      "value": str(legacy)[:160]})
        components.append(row)
    return refs, installed, components


def verified_graph(inventory):
    refs, installed, components = refs_and_components(inventory)
    edges = defaultdict(set)
    for source, target in inventory["transitive_edges"]:
        if source not in refs or target not in refs:
            raise ValueError("Installed dependency graph contains an unresolved package")
        edges[source].add(target)
    return refs, installed, components, edges


def to_cyclonedx(inventory):
    refs, installed, components, edges = verified_graph(inventory)
    direct = sorted(name for name, (_, pkg) in installed.items()
                    if pkg["dependency_scope"] == "DIRECT")
    relationships = [{"ref": ROOT_REF, "dependsOn": [refs[n] for n in direct]}]
    relationships.extend({"ref": refs[name], "dependsOn": [refs[n] for n in sorted(edges[name])]}
                         for name in sorted(refs))
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "timestamp": inventory["generated_at_utc"],
            "tools": {"components": [{"type": "application",
                                      "name": "public-bid-agent-python-inventory-exporter",
                                      "version": "1.0"}]},
            "component": {"type": "application", "name": "public-bid-agent-local",
                          "version": "installed-environment", "bom-ref": ROOT_REF},
            "properties": [
                {"name": "public-bid-agent:evidence", "value": "INSTALLED_METADATA_ONLY"},
                {"name": "public-bid-agent:hash-locked", "value": "false"},
                {"name": "public-bid-agent:external-binaries-covered", "value": "false"},
                {"name": "public-bid-agent:release-approved", "value": "false"}
            ]
        },
        "components": components,
        "dependencies": relationships
    }


def to_observed_pins(inventory):
    _, installed, _, _ = verified_graph(inventory)
    lines = [
        "# Observed Windows Python environment package versions (installed metadata).",
        "# NOT a hash-locked or cross-platform reproducible requirements lock.",
        "# Do not use as proof of license or security approval.",
        "# Does not include test-only/environment-only packages or OCR binaries.",
    ]
    lines.extend(f"{name}=={installed[name][0]}" for name in sorted(installed))
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inventory", type=Path, required=True)
    ap.add_argument("--sbom", type=Path, required=True)
    ap.add_argument("--pins", type=Path, required=True)
    args = ap.parse_args()
    if args.sbom.resolve() == args.pins.resolve():
        raise SystemExit("Output paths must differ")
    if args.sbom.exists() or args.pins.exists():
        raise SystemExit("Refusing to overwrite an output")
    report = json.loads(args.inventory.read_text(encoding="utf-8"))
    sbom = to_cyclonedx(report)
    pins = to_observed_pins(report)
    args.sbom.parent.mkdir(parents=True, exist_ok=True)
    args.pins.parent.mkdir(parents=True, exist_ok=True)
    with args.sbom.open("x", encoding="utf-8") as output:
        json.dump(sbom, output, ensure_ascii=True, indent=2)
        output.write("\n")
    with args.pins.open("x", encoding="utf-8") as output:
        output.write(pins)
    print(json.dumps({"sbom_spec":"CycloneDX 1.5",
       "python_components":len(sbom["components"]),
       "dependency_relationships":len(sbom["dependencies"]),
       "observed_pins":sum(line and not line.startswith("#") for line in pins.splitlines()),
       "hash_locked":False,"release_approved":False}))


if __name__=="__main__":
    main()
