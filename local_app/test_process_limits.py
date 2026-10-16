"""Windows Job Object/POSIX rlimit 기반 비신뢰 자식 프로세스 진단 보호 검증."""
import sys
import unittest
from process_limits import run_limited

class ProcessLimitsTests(unittest.TestCase):
    def test_normal_child_and_memory_hard_limit(self):
        command=[sys.executable,"-c",
             "import sys; b=sys.stdin.buffer.read(); sys.stdout.buffer.write(str(len(b)).encode())"]
        self.assertEqual(run_limited(command,b"synthetic",timeout=10,memory=256*1024*1024),b"9")
        costly=[sys.executable,"-c",
             "import sys; sys.stdin.buffer.read(); x=bytearray(300*1024*1024); print('INVALID_MEMORY_SUCCESS')"]
        with self.assertRaises(ValueError):
            run_limited(costly,b"a",timeout=12,memory=128*1024*1024)
    def test_zero_and_oversized_rejected_before_process(self):
        cmd=[sys.executable,"-c","print('NO')"]
        for raw in (b"",b"x"*(8*1024*1024+1)):
            with self.assertRaises(ValueError):
                run_limited(cmd,raw,timeout=3)

if __name__=="__main__":unittest.main()
