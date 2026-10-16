"""비신뢰 PDF/HWPX 구조 진단의 자식 프로세스 강제 메모리·시간 제한.
Windows Job Object의 PROCESS_MEMORY·KILL_ON_JOB_CLOSE, POSIX RLIMIT_AS/CPU.
안전한 입력 스트림 할당 전 Job 등록: subprocess는 stdin EOF 전에는 문서를 분석하지 않음.
오류/자원 한도 위반 시 호출자가 비식별 UNAVAILABLE로만 표시. 원문 stdout 로그 금지.
"""
import os
import subprocess

DEFAULT_MEMORY=512*1024*1024

def _windows_job(proc,bytes_limit):
    import ctypes
    from ctypes import wintypes

    class Basic(ctypes.Structure):
        _fields_=[
            ("PerProcessUserTimeLimit",ctypes.c_int64),
            ("PerJobUserTimeLimit",ctypes.c_int64),
            ("LimitFlags",wintypes.DWORD),
            ("MinimumWorkingSetSize",ctypes.c_size_t),
            ("MaximumWorkingSetSize",ctypes.c_size_t),
            ("ActiveProcessLimit",wintypes.DWORD),
            ("Affinity",ctypes.c_size_t),
            ("PriorityClass",wintypes.DWORD),
            ("SchedulingClass",wintypes.DWORD)]
    class Io(ctypes.Structure):
        _fields_=[
            ("ReadOperationCount",ctypes.c_uint64),
            ("WriteOperationCount",ctypes.c_uint64),
            ("OtherOperationCount",ctypes.c_uint64),
            ("ReadTransferCount",ctypes.c_uint64),
            ("WriteTransferCount",ctypes.c_uint64),
            ("OtherTransferCount",ctypes.c_uint64)]
    class Extended(ctypes.Structure):
        _fields_=[("BasicLimitInformation",Basic),("IoInfo",Io),
                  ("ProcessMemoryLimit",ctypes.c_size_t),
                  ("JobMemoryLimit",ctypes.c_size_t),
                  ("PeakProcessMemoryUsed",ctypes.c_size_t),
                  ("PeakJobMemoryUsed",ctypes.c_size_t)]
    k=ctypes.WinDLL("kernel32",use_last_error=True)
    k.CreateJobObjectW.argtypes=(ctypes.c_void_p,wintypes.LPCWSTR)
    k.CreateJobObjectW.restype=wintypes.HANDLE
    k.SetInformationJobObject.argtypes=(wintypes.HANDLE,ctypes.c_int,
                                          ctypes.c_void_p,wintypes.DWORD)
    k.SetInformationJobObject.restype=wintypes.BOOL
    k.AssignProcessToJobObject.argtypes=(wintypes.HANDLE,wintypes.HANDLE)
    k.AssignProcessToJobObject.restype=wintypes.BOOL
    k.CloseHandle.argtypes=(wintypes.HANDLE,)
    k.CloseHandle.restype=wintypes.BOOL
    job=k.CreateJobObjectW(None,None)
    if not job:raise OSError("문서 진단 작업 격리 생성 실패")
    try:
        info=Extended()
        info.BasicLimitInformation.LimitFlags=0x100|0x2000
        info.ProcessMemoryLimit=bytes_limit
        if not k.SetInformationJobObject(job,9,ctypes.byref(info),ctypes.sizeof(info)):
            raise OSError("문서 진단 메모리 제한 적용 실패")
        if not k.AssignProcessToJobObject(job,wintypes.HANDLE(int(proc._handle))):
            raise OSError("문서 진단 자식 프로세스 격리 실패")
        return k,job
    except Exception:
        k.CloseHandle(job)
        raise

def run_limited(command,raw,timeout=35,memory=DEFAULT_MEMORY):
    if not isinstance(command,list) or not command or not isinstance(raw,bytes):
        raise ValueError("진단 실행 형식 오류")
    if not 0<len(raw)<=8*1024*1024 or not 128*1024*1024<=memory<=1024*1024*1024:
        raise ValueError("진단 입력/메모리 범위 오류")
    env={k:v for k,v in os.environ.items() if k.upper() in
          ("PATH","SYSTEMROOT","WINDIR","TEMP","TMP","PYTHONIOENCODING","LANG","LC_ALL")}
    env["PYTHONIOENCODING"]="utf-8"
    kwargs={}
    if os.name=="posix":
        def restrict():
            import resource
            resource.setrlimit(resource.RLIMIT_AS,(memory,memory))
            resource.setrlimit(resource.RLIMIT_CPU,(30,35))
        kwargs["preexec_fn"]=restrict
    process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,env=env,**kwargs)
    job=None
    try:
        if os.name=="nt":
            job=_windows_job(process,memory)
        stdout,stderr=process.communicate(input=raw,timeout=timeout)
        if process.returncode!=0:
            raise ValueError("문서 진단 자원 제한 또는 실행 실패")
        if len(stdout)>50_000:
            raise ValueError("문서 진단 응답 크기 초과")
        return stdout
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()
        if job is not None:
            job[0].CloseHandle(job[1])
