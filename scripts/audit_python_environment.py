"""로컬 Python 의존성 증거 수집 (읽기 전용).

목적/책임: 실제 설치 패키지/직접 요구 버전/전이 의존성 메타데이터를 요약한다.
입력/출력: requirements.txt 및 현재 Python 환경 -> 비밀 경로 없는 JSON.
신뢰 경계: 소스코드·비공개 JSON/RFP·인증정보를 읽지 않으며 네트워크 호출 없음.
상태 변경: --output 지정 시 결과 파일만 생성. 기존 운영 자료는 변경하지 않음.
실패: 선언한 직접 요구조건 미충족 또는 요구 문자열 오류 시 종료 코드 2.
불변조건: 메타데이터 라이선스는 법적 승인 아님. 보안 취약점 검사는 NOT_RUN.
관련: docs/DEPENDENCIES_AND_LICENSES.md, P09, D-06/D-13.
"""
from __future__ import annotations

import argparse
from collections import deque
from datetime import datetime, timezone
import importlib.metadata as metadata
import json
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


def parse_requirements(raw: str):
    result = []
    for line in raw.splitlines():
        stripped = line.split("#", 1)[0].strip()
        if not stripped:
            continue
        if stripped.startswith(("-", "git+", "http:", "https:", ".")):
            raise ValueError("Only versioned public distribution requirements are supported")
        item = Requirement(stripped)
        if item.url:
            raise ValueError("Direct URL dependencies are not supported")
        result.append(item)
    return result


def marker_applies(requirement, extras):
    """Evaluate platform/python markers and each explicitly selected parent extra."""
    if requirement.marker is None:
        return True
    return any(requirement.marker.evaluate({"extra": extra})
               for extra in sorted(set(extras) | {""}))


def inventory(installed, requirements):
    dist_map = {}
    for dist in installed:
        name = dist.metadata.get("Name")
        if name:
            dist_map[canonicalize_name(name)] = dist
    missing, mismatched, direct = [], [], []
    roots = []
    for req in requirements:
        if not marker_applies(req, set()):
            continue  # An inactive platform-specific direct requirement is not missing.
        name = canonicalize_name(req.name)
        direct.append(name)
        roots.append((name, frozenset(req.extras)))
        dist = dist_map.get(name)
        if dist is None:
            missing.append(name)
        elif dist.version not in req.specifier:
            mismatched.append({"name": name, "required": str(req.specifier),
                               "installed": dist.version})
    encountered = set()
    enabled_extras = {}
    pending = deque(roots)
    edges = set()
    skipped_markers = []
    while pending:
        name, requested_extras = pending.popleft()
        before = enabled_extras.get(name, set())
        if name in encountered and set(requested_extras).issubset(before):
            continue
        encountered.add(name)
        active_extras = before | set(requested_extras)
        enabled_extras[name] = active_extras
        dist = dist_map.get(name)
        if dist is None:
            continue
        for expr in dist.requires or []:
            try:
                requirement = Requirement(expr)
                if not marker_applies(requirement, active_extras):
                    continue
                child = canonicalize_name(requirement.name)
                edges.add((name, child))
                pending.append((child, frozenset(requirement.extras)))
            except (ValueError, KeyError, TypeError):
                skipped_markers.append(name)
    items = []
    for name, dist in sorted(dist_map.items()):
        meta = dist.metadata
        expression = (meta.get("License-Expression") or "").strip()
        # The older License field is freeform and does not prove SPDX compliance.
        declared = (meta.get("License") or "").strip().replace("\n", " ")
        items.append({"name": name, "version": dist.version,
                      "dependency_scope": "DIRECT" if name in direct
                          else "TRANSITIVE" if name in encountered else "ENVIRONMENT_ONLY",
                      "spdx_expression": expression or None,
                      "legacy_license_metadata": declared[:160] or None,
                      "license_status": "METADATA_ONLY" if expression else "NEEDS_REVIEW"})
    return {
        "schema_version": 1,
        "direct_declared": len(direct),
        "direct_satisfied": not missing and not mismatched,
        "missing": sorted(set(missing)),
        "mismatched": mismatched,
        "distribution_count": len(items),
        "reachable_distribution_count": sum(x["dependency_scope"] != "ENVIRONMENT_ONLY" for x in items),
        "transitive_edges": [list(pair) for pair in sorted(edges)],
        "unparsed_metadata_dependencies": sorted(set(skipped_markers)),
        "inventory_complete": not skipped_markers,
        "distributions": items,
        "vulnerability_assessment": "NOT_RUN",
        "license_assessment": "METADATA_INVENTORY_ONLY",
        "external_binaries_and_frontend": "NOT_INCLUDED",
        "deployment_approved": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--requirements", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    declared = parse_requirements(args.requirements.read_text(encoding="utf-8"))
    report = inventory(metadata.distributions(), declared)
    report["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    data = json.dumps(report, ensure_ascii=True, indent=2) + "\n"
    if args.output:
        if args.output.exists():
            raise SystemExit("Refusing to overwrite an existing report")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(data, encoding="utf-8")
    print(json.dumps({k: report[k] for k in (
        "direct_declared", "direct_satisfied", "missing", "mismatched",
        "distribution_count", "reachable_distribution_count",
        "unparsed_metadata_dependencies", "inventory_complete", "vulnerability_assessment",
        "license_assessment", "external_binaries_and_frontend")}, ensure_ascii=True))
    raise SystemExit(0 if report["direct_satisfied"] and report["inventory_complete"] else 2)


if __name__ == "__main__":
    main()
