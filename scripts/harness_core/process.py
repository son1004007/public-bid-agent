"""합성 검사 자식의 시간·출력·수명 제한.
stdin 시작 신호 전 Job/프로세스 그룹 결속. 부모가 소유한 트리만 종료한다.
Windows Job의 active process=0 확인 실패는 성공이 아닌 환경 차단이다.
출력은 stream별 상한을 넘겨 저장하지 않는다. 재시도 없음.
"""
import os
from pathlib import Path
import signal
import subprocess
import threading
import time


class WindowsJob:
    def __init__(self, process):
        import ctypes as c
        from ctypes import wintypes as w
        class Basic(c.Structure):
            _fields_ = [('user', c.c_int64), ('kernel', c.c_int64), ('flags', w.DWORD),
                        ('min', c.c_size_t), ('max', c.c_size_t), ('active', w.DWORD),
                        ('affinity', c.c_size_t), ('priority', w.DWORD), ('scheduling', w.DWORD)]
        class Extended(c.Structure):
            _fields_ = [('basic', Basic), ('io', c.c_uint64 * 6),
                        ('memory', c.c_size_t), ('jobmemory', c.c_size_t),
                        ('peak', c.c_size_t), ('jobpeak', c.c_size_t)]
        class Accounting(c.Structure):
            _fields_ = [('times', c.c_int64 * 4), ('faults', w.DWORD),
                        ('total', w.DWORD), ('active', w.DWORD), ('terminated', w.DWORD)]
        self.c, self.Accounting = c, Accounting
        self.k = k = c.WinDLL('kernel32', use_last_error=True)
        for name, args, restype in [
            ('CreateJobObjectW', [c.c_void_p, w.LPCWSTR], w.HANDLE),
            ('SetInformationJobObject', [w.HANDLE, c.c_int, c.c_void_p, w.DWORD], w.BOOL),
            ('AssignProcessToJobObject', [w.HANDLE, w.HANDLE], w.BOOL),
            ('TerminateJobObject', [w.HANDLE, w.UINT], w.BOOL),
            ('QueryInformationJobObject', [w.HANDLE, c.c_int, c.c_void_p, w.DWORD, c.c_void_p], w.BOOL),
            ('CloseHandle', [w.HANDLE], w.BOOL)]:
            f = getattr(k, name); f.argtypes = args; f.restype = restype
        self.handle = k.CreateJobObjectW(None, None)
        if not self.handle:
            raise OSError('Job creation failed')
        info = Extended(); info.basic.flags = 0x2000  # KILL_ON_JOB_CLOSE
        if not k.SetInformationJobObject(self.handle, 9, c.byref(info), c.sizeof(info)) or not k.AssignProcessToJobObject(self.handle, w.HANDLE(int(process._handle))):
            k.CloseHandle(self.handle)
            raise OSError('Job assignment failed')

    def stop(self):
        k, c = self.k, self.c
        try:
            if not k.TerminateJobObject(self.handle, 1):
                raise OSError('Job termination failed')
            until = time.monotonic() + 3
            while time.monotonic() < until:
                info = self.Accounting()
                if not k.QueryInformationJobObject(self.handle, 1, c.byref(info), c.sizeof(info), None):
                    raise OSError('Job query failed')
                if info.active == 0:
                    return
                time.sleep(.02)
            raise OSError('Job descendants remain')
        finally:
            k.CloseHandle(self.handle)


def execute(argv, cwd, env, timeout, limit, directory):
    process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               start_new_session=os.name == 'posix')
    job = None
    overflow = threading.Event()
    threads = []
    def capture(stream, filename):
        count = 0
        with open(Path(directory) / filename, 'wb') as out:
            while True:
                block = stream.read(4096)
                if not block:
                    break
                out.write(block[:max(0, limit-count)])
                count += len(block)
                if count > limit:
                    overflow.set()
        stream.close()
    timed_out = False
    cleanup = True
    exit_code = None
    try:
        if os.name == 'nt':
            job = WindowsJob(process)
        elif os.name != 'posix':
            raise OSError('unsupported process adapter')
        for stream, filename in [(process.stdout, 'stdout.log'), (process.stderr, 'stderr.log')]:
            thread = threading.Thread(target=capture, args=(stream, filename), daemon=True)
            thread.start(); threads.append(thread)
        process.stdin.write(b'START\n'); process.stdin.close()
        deadline = time.monotonic() + timeout
        while process.poll() is None and not overflow.is_set():
            if time.monotonic() >= deadline:
                timed_out = True; break
            time.sleep(.01)
        exit_code = process.poll()
    finally:
        try:
            if job:
                job.stop()
            elif os.name == 'posix':
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            elif process.poll() is None:
                process.kill()
            process.wait(timeout=3)
        except (OSError, subprocess.TimeoutExpired):
            cleanup = False
        for thread in threads:
            thread.join(3)
            cleanup = cleanup and not thread.is_alive()
    return dict(exit_code=exit_code, timed_out=timed_out, output_exceeded=overflow.is_set(), cleanup=cleanup)
