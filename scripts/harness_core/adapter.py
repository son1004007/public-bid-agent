"""신뢰된 unittest 결과 어댑터.
입력: 부모가 전달한 실행 identity/정확한 test ID. 출력: 구조화 결과.
부작용: 합성 테스트와 전용 결과 파일만. stdin 시작 신호 전 후보 import 금지.
테스트 자체는 소유자가 신뢰하는 코드이며 OS 보안 sandbox를 대체하지 않는다.
"""
import json
import os
from pathlib import Path
import sys
import unittest


def main():
    if sys.stdin.readline().strip() != 'START':
        return 3
    config = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    sys.path.insert(0, str(Path(config['snapshot']) / config['import_dir']))
    class Result(unittest.TestResult):
        def __init__(self):
            super().__init__()
            self.ids = []
        def startTest(self, test):
            self.ids.append(test.id())
            super().startTest(test)
    result = Result()
    unittest.defaultTestLoader.loadTestsFromNames(config['tests']).run(result)
    report = {k: config[k] for k in ('run_id', 'check_id', 'source_digest', 'adapter_digest')}
    report.update(tests_run=result.testsRun, test_ids=result.ids,
                  failures=len(result.failures), errors=len(result.errors),
                  skipped=len(result.skipped), expected_failures=len(result.expectedFailures),
                  unexpected_successes=len(result.unexpectedSuccesses))
    target = Path(config['report'])
    temp = target.with_suffix('.tmp')
    temp.write_text(json.dumps(report, sort_keys=True), encoding='utf-8')
    os.replace(temp, target)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
