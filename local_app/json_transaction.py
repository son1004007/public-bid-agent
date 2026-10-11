"""대시보드·RFP 상태 파일의 프로세스 간 쓰기 트랜잭션 계약.

목적/책임: read → validate/merge → os.replace 간 단일 작성자 보장.
입력/출력: 사용자 데이터 디렉터리 Path, 공통 잠금 컨텍스트.
신뢰 경계: 로컬 프로세스만 접근; 잠금 파일에는 사용자 데이터 미기록.
부작용: 사용자 데이터 디렉터리에 고정 .dashboard-rfp.lock 파일 생성(삭제하지 않음).
실패: 최대 10초 대기 후 TimeoutError; 원본 JSON 미변경.
불변조건: 모든 dashboard.json/rfp_batch.json read-modify-write는 같은 잠금을 사용.
잠금 수명: 예외 또는 작업자 종료 시 파일·스레드 잠금을 해제하고, 다음 요청이 다시 획득한다.
검증: test_json_transaction.py, test_rfp_batch.py, docs/design/RFP_RESUMABLE_BATCH_2026-10-11.md.
"""
import os
import time
import threading
from contextlib import contextmanager
from pathlib import Path

_LOCK_FILE = ".dashboard-rfp.lock"
_PROCESS_LOCKS = {}
_PROCESS_LOCKS_MUTEX = threading.Lock()


@contextmanager
def _local_lock(path: Path, timeout: float):
    """Windows 동일 프로세스의 별도 파일 핸들 잠금 재획득까지 직렬화한다."""
    key = os.path.normcase(os.path.abspath(str(path)))
    with _PROCESS_LOCKS_MUTEX:
        lock = _PROCESS_LOCKS.setdefault(key, threading.Lock())
    if not lock.acquire(timeout=timeout):
        raise TimeoutError("동일 프로세스 RFP/대시보드 잠금 시간 초과: 원본 미변경")
    try:
        yield
    finally:
        # worker lease는 start 스레드에서 획득해 worker 스레드에서 해제한다.
        lock.release()


@contextmanager
def transaction(root: Path, timeout: float = 10.0, *, name: str = _LOCK_FILE):
    """프로세스 경계의 변경 트랜잭션; POSIX flock / Windows msvcrt byte lock."""
    if timeout < 0 or name not in (_LOCK_FILE, ".rfp-batch-worker.lock"):
        raise ValueError("잠금 설정 오류")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = root / name
    # 로컬 스레드 대기와 OS 파일 잠금을 하나의 전체 deadline으로 제한한다.
    deadline = time.monotonic() + timeout
    with _local_lock(path, max(0.0, deadline - time.monotonic())), path.open("a+b") as handle:
        if os.name == "posix":
            os.chmod(path, 0o600)
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        if os.name == "nt":
            import msvcrt
            handle.seek(0)
            def acquire():
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            def release():
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            def acquire():
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            def release():
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        while True:
            try:
                acquire()
                break
            except (OSError, BlockingIOError) as exc:
                if time.monotonic() >= deadline:
                    raise TimeoutError("RFP/대시보드 저장 잠금 시간 초과: 원본 미변경") from exc
                time.sleep(min(0.05, max(0.001, deadline - time.monotonic())))
        try:
            yield
        finally:
            release()
