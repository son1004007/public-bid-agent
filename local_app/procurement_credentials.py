"""나라장터 API 인증키를 Windows 현재 사용자 DPAPI로 암호화하는 로컬 보관소.

입력: 대시보드에서 사용자가 명시적으로 입력한 공공데이터포털 키.
출력: 현재 설정 여부/저장 방식(키 값 제외), 내부 서버 수집 시에만 복호화된 키.
신뢰경계: loopback/Origin/CSRF는 server.py, 보관은 Windows 사용자 범위 DPAPI.
부작용: LOCALAPPDATA/PublicBidAgent/secrets 안에 암호문 파일만 원자 쓰기/삭제.
실패: Windows 이외 환경에서는 웹 등록 비활성화, 환경변수 방식만 허용.
보안: 저장된 값·부분 마스킹·해시·요청 URL/인증키 문자열을 로그나 응답으로 출력하지 않음.
"""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import unquote


class CredentialError(Exception):
    """인증키 관리 실패: 사용자에게 비밀 내용을 포함하지 않은 메시지만 전달."""


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def key_path() -> Path:
    if os.name != "nt" or not os.environ.get("LOCALAPPDATA"):
        raise CredentialError("웹 인증키 저장은 Windows 현재 사용자 PC에서만 지원합니다")
    return Path(os.environ["LOCALAPPDATA"]) / "PublicBidAgent" / "secrets" / "g2b_servicekey.dpapi"


def clean_key(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("인증키 문자열을 입력하세요")
    candidate = value.strip()
    if not (16 <= len(candidate) <= 600) or any(ord(ch) < 33 or ord(ch) > 126 for ch in candidate):
        raise ValueError("인증키는 공공데이터포털의 일반/인코딩 인증키 문자열이어야 합니다")
    if "%" in candidate:
        if re.search(r"%(?![0-9A-Fa-f]{2})", candidate):
            raise ValueError("URL 인코딩된 인증키 형식이 올바르지 않습니다")
        candidate = unquote(candidate)
    if not (16 <= len(candidate) <= 400) or any(ord(ch) < 33 or ord(ch) > 126 for ch in candidate):
        raise ValueError("입력한 인증키 형식을 확인하세요")
    return candidate


def _dpapi(data: bytes, *, decrypt: bool) -> bytes:
    if os.name != "nt":
        raise CredentialError("Windows 사용자 암호화가 지원되지 않습니다")
    input_buffer = ctypes.create_string_buffer(data)
    inp = _Blob(len(data), ctypes.cast(input_buffer, ctypes.POINTER(ctypes.c_ubyte)))
    out = _Blob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if decrypt:
        fn = crypt.CryptUnprotectData
        fn.argtypes = [ctypes.POINTER(_Blob), ctypes.c_void_p, ctypes.c_void_p,
                       ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_Blob)]
        fn.restype = wintypes.BOOL
        ok = fn(ctypes.byref(inp), None, None, None, None, 0x01, ctypes.byref(out))
    else:
        fn = crypt.CryptProtectData
        fn.argtypes = [ctypes.POINTER(_Blob), wintypes.LPCWSTR, ctypes.c_void_p,
                       ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_Blob)]
        fn.restype = wintypes.BOOL
        ok = fn(ctypes.byref(inp), "Public Bid Agent local procurement key",
                None, None, None, 0x01, ctypes.byref(out))
    if not ok:
        raise CredentialError("Windows 사용자 암호화 또는 복호화에 실패했습니다")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        kernel.LocalFree(ctypes.cast(out.pbData, ctypes.c_void_p))


def save_key(value: object) -> None:
    text = clean_key(value)
    path = key_path()
    encrypted = _dpapi(text.encode("utf-8"), decrypt=False)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".g2b-secret-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(encrypted)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def delete_key() -> bool:
    path = key_path()
    if not path.exists():
        return False
    path.unlink()
    return True


def status() -> dict:
    saved = False
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        saved = key_path().is_file()
    env = bool(os.environ.get("DATA_GO_KR_SERVICE_KEY"))
    return {
        "configured": saved or env,
        "source": "WINDOWS_DPAPI" if saved else ("ENVIRONMENT" if env else "NONE"),
        "can_save": os.name == "nt" and bool(os.environ.get("LOCALAPPDATA")),
        "can_delete": saved,
    }


def active_key() -> str | None:
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        path = key_path()
        if path.exists():
            try:
                # 보관소는 키 평문을 노출하는 API를 제공하지 않는다.
                return clean_key(_dpapi(path.read_bytes(), decrypt=True).decode("utf-8"))
            except (ValueError, UnicodeError, OSError, CredentialError) as exc:
                raise CredentialError("저장된 인증키를 읽을 수 없습니다. 다시 등록하세요") from exc
    candidate = os.environ.get("DATA_GO_KR_SERVICE_KEY")
    return clean_key(candidate) if candidate else None
