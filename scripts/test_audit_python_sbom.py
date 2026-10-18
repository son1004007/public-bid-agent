"""CycloneDX 1.5 installed-environment export: public synthetic fixtures only."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from export_python_sbom import ROOT_REF, to_cyclonedx, to_observed_pins


def fixture():
    return {
        "direct_satisfied": True, "inventory_complete": True,
        "direct_declared": 1,
        "generated_at_utc": "2026-10-18T10:00:00+00:00",
        "distributions": [
            {"name": "Alpha", "version": "1.0", "dependency_scope": "DIRECT",
             "spdx_expression": "MIT", "legacy_license_metadata": None},
            {"name": "BRAVO", "version": "2.5", "dependency_scope": "TRANSITIVE",
             "spdx_expression": None, "legacy_license_metadata": "BSD License"},
            {"name": "Private_Debug_Tool", "version": "0.1",
             "dependency_scope": "ENVIRONMENT_ONLY",
             "spdx_expression": None, "legacy_license_metadata": None}
        ],
        "transitive_edges": [["alpha", "bravo"]]
    }


class PythonSbomTests(unittest.TestCase):
    def test_cyclonedx_graph_and_public_metadata(self):
        bom = to_cyclonedx(fixture())
        self.assertEqual(bom["bomFormat"], "CycloneDX")
        self.assertEqual(bom["specVersion"], "1.5")
        self.assertEqual(bom["metadata"]["component"]["bom-ref"], ROOT_REF)
        self.assertEqual([x["name"] for x in bom["components"]], ["alpha", "bravo"])
        self.assertNotIn("licenses", bom["components"][0])
        self.assertIn({"name": "public-bid-agent:unverified-license-expression",
                       "value": "MIT"}, bom["components"][0]["properties"])
        self.assertNotIn("licenses", bom["components"][1])
        self.assertEqual(bom["dependencies"], [
            {"ref": ROOT_REF, "dependsOn": ["pkg:pypi/alpha@1.0"]},
            {"ref": "pkg:pypi/alpha@1.0", "dependsOn": ["pkg:pypi/bravo@2.5"]},
            {"ref": "pkg:pypi/bravo@2.5", "dependsOn": []}])
        self.assertNotIn("Private_Debug_Tool", json.dumps(bom))
        self.assertNotIn("license_approved", json.dumps(bom))

    def test_pins_are_versioned_but_not_hash_locked(self):
        pins = to_observed_pins(fixture())
        self.assertIn("alpha==1.0", pins)
        self.assertIn("bravo==2.5", pins)
        self.assertNotIn("private-debug-tool", pins.lower())
        self.assertIn("NOT a hash-locked", pins)

    def test_fail_closed_on_missing_dependency_or_unverified_graph(self):
        broken = fixture()
        broken["transitive_edges"] = [["alpha", "unknown"]]
        with self.assertRaisesRegex(ValueError, "unresolved"):
            to_cyclonedx(broken)
        broken = fixture()
        broken["inventory_complete"] = False
        with self.assertRaisesRegex(ValueError, "incomplete"):
            to_observed_pins(broken)
        broken = fixture()
        broken["direct_satisfied"] = False
        with self.assertRaisesRegex(ValueError, "not satisfied"):
            to_cyclonedx(broken)

    def test_special_versions_use_percent_encoded_purls(self):
        for version, expected in (("1!2.0", "1%212.0"), ("1.0+local.1", "1.0%2Blocal.1")):
            with self.subTest(version=version):
                report = fixture()
                report["distributions"][0]["version"] = version
                bom = to_cyclonedx(report)
                self.assertEqual(bom["components"][0]["purl"], "pkg:pypi/alpha@" + expected)
                self.assertEqual(bom["dependencies"][0]["dependsOn"], ["pkg:pypi/alpha@" + expected])

    def test_invalid_spdx_remains_unverified_metadata(self):
        report = fixture()
        report["distributions"][0]["spdx_expression"] = "BSD License"
        c = to_cyclonedx(report)["components"][0]
        self.assertNotIn("licenses", c)
        self.assertIn({"name": "public-bid-agent:unverified-license-expression",
                       "value": "BSD License"}, c["properties"])

    def test_pin_output_rejects_unresolved_dependency(self):
        report = fixture()
        report["transitive_edges"].append(["alpha", "missing"])
        with self.assertRaisesRegex(ValueError, "unresolved"):
            to_observed_pins(report)

    def test_cli_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "inventory.json"
            sbom = root / "sbom.json"
            pins = root / "pins.txt"
            source.write_text(json.dumps(fixture()), encoding="utf-8")
            script = Path(__file__).with_name("export_python_sbom.py")
            args = [sys.executable, str(script), "--inventory", str(source),
                    "--sbom", str(sbom), "--pins", str(pins)]
            first = subprocess.run(args, capture_output=True, text=True, timeout=15)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(len(json.loads(sbom.read_text(encoding="utf-8"))["components"]), 2)
            again = subprocess.run(args, capture_output=True, text=True, timeout=15)
            self.assertNotEqual(again.returncode, 0)
            self.assertIn("Refusing to overwrite", again.stderr + again.stdout)


if __name__ == "__main__":
    unittest.main()
