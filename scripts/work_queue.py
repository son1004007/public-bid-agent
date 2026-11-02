"""Work 비동기 작업 큐 계약.

목적: Work가 구현/판단하고 노트북은 고정 H01 검사를 연결과 독립적으로 실행한다.
입력: 소유자가 제출한 job ID, trusted/candidate 40자리 SHA. 자유 명령은 받지 않는다.
출력: 요청/heartbeat/result JSON과 기존 H01 원시 결과. 제품 DONE 판정은 하지 않는다.
경계: 단일 소유자 trusted 코드 전용. OS sandbox나 악의적 같은 사용자 방어가 아니다.
부작용: 저장소 밖 큐만 쓰며 git fetch/reset/운영 자료 변경/모델 호출을 하지 않는다.
실패: 실행 중 OS 잠금 유지. 죽은 RUNNING은 INTERRUPTED로 차단하며 자동 재시도하지 않는다.
관련: WORK_ASYNC_RUNBOOK.md, test_work_queue.py. Python 3.12 표준 라이브러리만 사용.
"""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import sys
import threading
import time

import task_harness as h
from harness_core.process import execute

RUNTIME = (*h.TRUSTED, 'scripts/work_queue.py', 'scripts/work_queue_child.py')
ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z')


def queue_root(path, repo):
    root = Path(path).absolute()
    h.no_links(root)
    if root == repo or repo in root.parents or root in repo.parents:
        raise ValueError('queue must be outside repository')
    root.mkdir(parents=True, exist_ok=True)
    return root


@contextmanager
def locked(root, name):
    path = root / name
    h.no_links(path)
    with path.open('a+b') as lock:
        lock.seek(0)
        if os.name == 'nt':
            import msvcrt
            if path.stat().st_size == 0:
                lock.write(b'0'); lock.flush(); lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            lock.seek(0)
            if os.name == 'nt':
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock, fcntl.LOCK_UN)


def request(job_id, trusted, candidate):
    if not ID.fullmatch(job_id):
        raise ValueError('invalid job id')
    for sha in (trusted, candidate):
        if not re.fullmatch('[0-9a-f]{40}', sha):
            raise ValueError('full SHA required')
    return dict(schema_version=1, job_id=job_id, check='A01', trusted=trusted, candidate=candidate)


def submit(root, value):
    with locked(root, '.submit.lock'):
        folder = root / value['job_id']
        h.no_links(folder)
        if folder.exists():
            if h.read_json(folder / 'request.json') != value:
                raise ValueError('job ID payload conflict')
            return 'EXISTING'
        # Publish only after request has been written; worker ignores staging directories.
        staging = root / ('.pending-' + value['job_id'])
        staging.mkdir()
        h.write_json(staging / 'request.json', value)
        staging.rename(folder)
        return 'QUEUED'


def jobs(root):
    for folder in sorted(root.iterdir()):
        if ID.fullmatch(folder.name) and folder.is_dir():
            h.no_links(folder)
            yield folder


def status(root):
    out = []
    for folder in jobs(root):
        value = h.read_json(folder / 'request.json')
        result = folder / 'result.json'
        running = folder / 'running.json'
        out.append(dict(request=value, result=h.read_json(result) if result.exists() else None,
                        running=h.read_json(running) if running.exists() else None))
    return out


def verify_runtime(repo, trusted):
    h.commit(repo, trusted)
    for name in RUNTIME:
        h.no_links(repo / name)
        if (repo / name).read_bytes() != h.blob(repo, trusted, name):
            raise ValueError('runtime does not match trusted SHA')


def worker(root, repo, trusted):
    verify_runtime(repo, trusted)
    with locked(root, '.worker.lock'):
        pending = list(jobs(root))
        for folder in pending:
            # Never clear this automatically: controller must reconcile any orphan descendants.
            if (folder / 'running.json').exists() and not (folder / 'result.json').exists():
                h.write_json(folder / 'result.json', dict(state='INTERRUPTED', task_complete=False,
                             reason='previous worker lost; reconcile processes before new queue'))
                return 'BLOCKED_INTERRUPTED'
            if (folder / 'result.json').exists():
                previous = h.read_json(folder / 'result.json')
                if previous['state'] in ('INTERRUPTED', 'BLOCKED_ENVIRONMENT'):
                    return 'BLOCKED_INTERRUPTED'
        for folder in pending:
            if (folder / 'result.json').exists():
                continue
            value = h.read_json(folder / 'request.json')
            if value != request(value['job_id'], value['trusted'], value['candidate']) or value['job_id'] != folder.name:
                raise ValueError('invalid request')
            if value['trusted'] != trusted:
                raise ValueError('request uses different trusted runtime')
            record = dict(**value, state='RUNNING', started_at=h.stamp(), heartbeat=h.stamp(), pid=os.getpid())
            h.write_json(folder / 'running.json', record)
            stopped = threading.Event()
            def heartbeat():
                while not stopped.wait(5):
                    record['heartbeat'] = h.stamp()
                    h.write_json(folder / 'running.json', record)
            beat = threading.Thread(target=heartbeat, daemon=True)
            beat.start()
            result = dict(**value, state='BLOCKED_ENVIRONMENT', task_complete=False)
            try:
                argv = [sys.executable, '-B', str(repo / 'scripts/work_queue_child.py'),
                        str(repo), trusted, value['candidate'], str(folder / 'harness-run')]
                env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1')
                outcome = execute(argv, repo, env, 600, 2_000_000, folder)
                result['process'] = outcome
                run = folder / 'harness-run/run.json'
                result['report_present'] = run.exists()
                if not outcome['cleanup']:
                    result['state'] = 'BLOCKED_ENVIRONMENT'
                elif outcome['timed_out']:
                    result['state'] = 'TIMED_OUT'
                elif outcome['exit_code'] != 0 or outcome['output_exceeded'] or not run.exists():
                    result['state'] = 'FAILED'
                else:
                    # H01 remains the sole detailed verifier; queue success is not product DONE.
                    report = h.read_json(run)
                    if report['trusted_commit'] != trusted or report['candidate_commit'] != value['candidate'] or report['task_id'] != 'A01':
                        raise ValueError('report identity mismatch')
                    verified = h.verify(folder / 'harness-run')
                    result['verification'] = verified
                    result['state'] = 'SUCCEEDED' if verified['state'] == 'LOCAL_VERIFIED' else 'FAILED'
            except Exception as exc:
                result['error_type'] = type(exc).__name__
            finally:
                stopped.set(); beat.join()
                result['finished_at'] = h.stamp()
                h.write_json(folder / 'result.json', result)
            return result['state']
        return 'IDLE'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--queue', required=True)
    parser.add_argument('--repo', default=str(Path(__file__).resolve().parents[1]))
    sub = parser.add_subparsers(dest='action', required=True)
    add = sub.add_parser('submit')
    add.add_argument('--id', required=True)
    add.add_argument('--trusted', required=True)
    add.add_argument('--candidate', required=True)
    run = sub.add_parser('worker')
    run.add_argument('--trusted', required=True)
    sub.add_parser('status')
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    if repo != Path(__file__).resolve().parents[1]:
        raise ValueError('run worker from its fixed repository')
    root = queue_root(args.queue, repo)
    if args.action == 'submit':
        result = submit(root, request(args.id, args.trusted, args.candidate))
    elif args.action == 'worker':
        result = worker(root, repo, args.trusted)
    else:
        result = status(root)
    print(json.dumps(result, ensure_ascii=True))
    return 1 if args.action == 'worker' and result not in ('SUCCEEDED', 'IDLE') else 0


if __name__ == '__main__':
    sys.exit(main())
