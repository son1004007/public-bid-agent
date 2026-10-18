"""합성 메타데이터만 사용하는 Python 의존성 검사 회귀."""
import unittest
from audit_python_environment import inventory, parse_requirements


class FakeDistribution:
    def __init__(self, name, version, requires=(), license_expression=None):
        self.metadata = {"Name": name}
        if license_expression:
            self.metadata["License-Expression"] = license_expression
        self.version = version
        self.requires = list(requires)


class InventoryTests(unittest.TestCase):
    def test_complete_matching_direct_and_transitive(self):
        installed = [
            FakeDistribution("Alpha", "1.1", ("Bravo>=2,<3", "OptionalAddon; extra == 'unused'"), "MIT"),
            FakeDistribution("BRAVO", "2.5", license_expression="Apache-2.0"),
            FakeDistribution("other-tool", "7.0"),
        ]
        result = inventory(installed, parse_requirements("alpha>=1,<2\n# comment\n"))
        self.assertTrue(result["direct_satisfied"])
        self.assertEqual(result["direct_declared"], 1)
        self.assertEqual(result["distribution_count"], 3)
        self.assertEqual(result["reachable_distribution_count"], 2)
        self.assertEqual(result["transitive_edges"], [["alpha", "bravo"]])
        self.assertEqual(result["distributions"][0]["license_status"], "METADATA_ONLY")
        self.assertEqual(result["vulnerability_assessment"], "NOT_RUN")
        self.assertFalse(result["deployment_approved"])

    def test_missing_and_version_mismatch_block(self):
        result = inventory([FakeDistribution("alpha", "3.0")],
                           parse_requirements("alpha>=1,<2\nmissing>=1"))
        self.assertFalse(result["direct_satisfied"])
        self.assertEqual(result["missing"], ["missing"])
        self.assertEqual(result["mismatched"][0]["name"], "alpha")

    def test_reject_nonregistry_requirements(self):
        for text in ("-e .", "https://example.org/pkg.whl", "alpha @ https://example.org/pkg.whl"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_requirements(text)

    def test_inactive_platform_and_python_markers_are_not_missing(self):
        # The test must work on both Windows and Linux without hard-coded hosts.
        import sys
        inactive = "linux" if sys.platform == "win32" else "win32"
        requirements = parse_requirements(
            f'platform-only>=1; sys_platform == "{inactive}"' + "\n"
            + 'python2-only>=1; python_version < "2"')
        result = inventory([], requirements)
        self.assertTrue(result["direct_satisfied"])
        self.assertEqual(result["direct_declared"], 0)
        self.assertEqual(result["missing"], [])

    def test_direct_requested_extra_reaches_conditional_dependency(self):
        installed = [
            FakeDistribution("alpha", "1", ('bravo>=2; extra == "audit"',)),
            FakeDistribution("bravo", "2"),
        ]
        report = inventory(installed, parse_requirements("alpha[audit]>=1"))
        self.assertTrue(report["direct_satisfied"])
        self.assertEqual(report["reachable_distribution_count"], 2)
        self.assertEqual(report["transitive_edges"], [["alpha", "bravo"]])

    def test_nested_extra_revisits_package_and_recovers_deep_dependency(self):
        installed = [
            FakeDistribution("alpha", "1", ("bravo>=2",)),
            FakeDistribution("beta", "1", ("bravo[audit]>=2",)),
            FakeDistribution("bravo", "2", ('charlie; extra == "audit"',)),
            FakeDistribution("charlie", "1"),
        ]
        report = inventory(installed, parse_requirements("alpha==1\nbeta==1"))
        self.assertTrue(report["inventory_complete"])
        self.assertEqual(report["reachable_distribution_count"], 4)
        self.assertIn(["bravo", "charlie"], report["transitive_edges"])

    def test_no_credentials_or_local_paths_in_record(self):
        result = inventory([FakeDistribution("alpha", "1", license_expression="MIT")],
                           parse_requirements("alpha==1"))
        self.assertNotIn("files", result["distributions"][0])
        self.assertNotIn("path", result["distributions"][0])


if __name__ == "__main__":
    unittest.main()
