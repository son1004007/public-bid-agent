"""Work 큐 최소 계약 회귀: 중복, ID/SHA, 잠금, 중단, 실행 결과 구분."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import work_queue as q


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.value = q.request('job-1', 'a'*40, 'b'*40)

    def tearDown(self):
        self.temp.cleanup()

    def test_submit_idempotence_and_conflict(self):
        self.assertEqual(q.submit(self.root, self.value), 'QUEUED')
        self.assertEqual(q.submit(self.root, self.value), 'EXISTING')
        with self.assertRaises(ValueError):
            q.submit(self.root, dict(self.value, candidate='c'*40))
        self.assertEqual(len(q.status(self.root)), 1)

    def test_bad_identity(self):
        for value in ('../x', 'x/y', '', '.hidden'):
            with self.assertRaises(ValueError):
                q.request(value, 'a'*40, 'b'*40)
        with self.assertRaises(ValueError):
            q.request('ok', 'main', 'b'*40)

    def test_repository_queue_rejected(self):
        with self.assertRaises(ValueError):
            q.queue_root(self.root / 'queue', self.root)

    def test_process_lock(self):
        code = 'from pathlib import Path; import work_queue as q;\nwith q.locked(Path(__import__("sys").argv[1]), ".worker.lock"): print("acquired")'
        with q.locked(self.root, '.worker.lock'):
            run = subprocess.run([sys.executable, '-c', code, str(self.root)],
                                 cwd=Path(q.__file__).parent, capture_output=True, timeout=10)
        self.assertNotEqual(run.returncode, 0)
        with q.locked(self.root, '.worker.lock'):
            pass

    @patch.object(q, 'verify_runtime')
    def test_interrupted_blocks_following_job(self, runtime):
        q.submit(self.root, self.value)
        q.h.write_json(self.root/'job-1/running.json', {'state':'RUNNING'})
        q.submit(self.root, q.request('job-2', 'a'*40, 'b'*40))
        with patch.object(q, 'execute') as execute:
            self.assertEqual(q.worker(self.root, self.root, 'a'*40), 'BLOCKED_INTERRUPTED')
            self.assertEqual(q.worker(self.root, self.root, 'a'*40), 'BLOCKED_INTERRUPTED')
            execute.assert_not_called()

    @patch.object(q, 'verify_runtime')
    def test_missing_report_cannot_succeed(self, runtime):
        q.submit(self.root, self.value)
        outcome = dict(exit_code=0, cleanup=True, timed_out=False, output_exceeded=False)
        with patch.object(q, 'execute', return_value=outcome):
            self.assertEqual(q.worker(self.root, self.root, 'a'*40), 'FAILED')
        self.assertFalse(q.status(self.root)[0]['result']['task_complete'])

    @patch.object(q, 'verify_runtime')
    def test_cleanup_failure_blocks_queue(self, runtime):
        q.submit(self.root, self.value)
        outcome = dict(exit_code=0, cleanup=False, timed_out=False, output_exceeded=False)
        with patch.object(q, 'execute', return_value=outcome):
            self.assertEqual(q.worker(self.root, self.root, 'a'*40), 'BLOCKED_ENVIRONMENT')
            self.assertEqual(q.worker(self.root, self.root, 'a'*40), 'BLOCKED_INTERRUPTED')

    @patch.object(q, 'verify_runtime')
    def test_other_runtime_rejected(self, runtime):
        q.submit(self.root, self.value)
        with self.assertRaises(ValueError):
            q.worker(self.root, self.root, 'c'*40)


if __name__ == '__main__':
    unittest.main()
