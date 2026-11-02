"""Work 큐의 START 대기 bridge. Windows Job 결속 전 후보/하네스 실행 금지.
고정 runtime의 H01 CLI만 호출하며 자유 명령·모델·운영 데이터 경로를 받지 않는다.
시간/출력/자식 종료는 부모의 기존 process.execute가 담당한다.
"""
from pathlib import Path
import subprocess
import sys

if __name__ == '__main__':
    if sys.stdin.readline().strip() != 'START':
        sys.exit(3)
    repo, trusted, candidate, run = sys.argv[1:]
    sys.exit(subprocess.call([sys.executable, '-B', str(Path(repo) / 'scripts/task_harness.py'),
                             'run', '--task', 'A01', '--trusted-ref', trusted,
                             '--candidate-ref', candidate, '--run-dir', run], cwd=repo))
