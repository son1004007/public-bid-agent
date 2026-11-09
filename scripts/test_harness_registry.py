"""기존 모듈에 추가된 검사가 고정 하네스 목록에서 빠지지 않는지 확인한다."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'local_app'))


def test_ids(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from test_ids(test)
        else:
            yield test.id()


class RegistryTests(unittest.TestCase):
    def test_registered_modules_have_no_omitted_or_extra_cases(self):
        registry = json.loads((ROOT / 'harness/commands.json').read_text())['commands']
        for check, modules in [('a01_deadline', ['test_procurement_filter']),
                               ('audit_regression', ['test_audit_python_environment', 'test_audit_python_sbom']),
                               ('local_regression', [p.stem for p in sorted((ROOT / 'local_app').glob('test_*.py'))])]:
            with self.subTest(check=check):
                suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
                actual = list(test_ids(suite))
                self.assertTrue(actual)
                self.assertFalse(any('_FailedTest' in name for name in actual))
                self.assertEqual(actual, registry[check]['tests'])


if __name__ == '__main__':
    unittest.main()
