"""AGW-05 공식 RFP 원문 수집 계약.

목적/책임: 공공데이터포털 상세 JSON/나라장터 HWPX의 *응답 바이트*를 원형 보관한다.
입력/출력: 공식 공고번호·차수, 검증된 첨부 URL, 인증키(출력 금지), 원본 해시와 비공개 저장 키.
신뢰 경계: 외부 HTTP·JSON·ZIP은 무신뢰. 공식 고정 HTTPS, 무프록시/무리다이렉트,
    URL-공고번호/차수 결속, 응답 크기·인코딩·중복 JSON key를 검증한다.
상태 변경: capture는 GET만, persist는 저장소 외부 private 파일만 O_EXCL로 생성한다.
실패/재시도: 코드형 오류, 기존 저장 파일 수정/삭제 없음. DB 원본 digest를 임의 대체하지 않는다.
불변조건: 담당자 attestation·문서 ACL·ExtractionRun coverage·유료 모델 실행은 별도 단계.
관련: docs/implementation/ai-gateway/AGW-05-PUBLIC-PROVENANCE-2026-11-20.md.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
import zipfile


API_URL = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService02/getBidPblancListInfoServc02"
ATTACHMENT_PATH = "/pn/pnp/pnpe/UntyAtchFile/downloadFile.do"
MAX_BYTES = 8 * 1024 * 1024
CAPTURE_DIR = "official-g2b-capture"


class CaptureError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise CaptureError("REDIRECT_DENIED")


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _identity(number, revision):
    if (type(number) is not str or type(revision) is not str
            or not re.fullmatch(r"[A-Za-z0-9-]{4,32}", number)
            or number.startswith("SYNTHETIC-")
            or not re.fullmatch(r"[0-9]{1,5}", revision)):
        raise CaptureError("INVALID_NOTICE_ID")


def _normalized_service_key(service_key):
    """공공데이터포털의 일반 인증키와 1회 URL 인코딩된 인증키를 안전하게 동일하게 처리."""
    if (type(service_key) is not str or not 1 <= len(service_key) <= 1024
            or any(ord(ch) < 33 for ch in service_key)):
        raise CaptureError("MISSING_SERVICE_KEY")
    if "%" in service_key:
        if re.search(r"%(?![0-9a-fA-F]{2})", service_key):
            raise CaptureError("MISSING_SERVICE_KEY")
        service_key = unquote(service_key)
        if not service_key or len(service_key) > 1024 or any(ord(ch) < 33 for ch in service_key):
            raise CaptureError("MISSING_SERVICE_KEY")
    return service_key


def _no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CaptureError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _official_response(raw, number, revision):
    try:
        data = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_no_duplicate_keys)
        header = data["response"]["header"]
        if str(header["resultCode"]) not in ("00", "0"):
            raise CaptureError("OFFICIAL_API_ERROR")
        items = data["response"]["body"]["items"]
        items = items.get("item", []) if isinstance(items, dict) else items
        items = [items] if isinstance(items, dict) else items
        if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict):
            raise CaptureError("AMBIGUOUS_NOTICE")
        row = items[0]
        observed_rev = str(row.get("bidNtceOrd", ""))
        if (row.get("bidNtceNo") != number or not observed_rev.isdecimal()
                or int(observed_rev) != int(revision)):
            raise CaptureError("NOTICE_IDENTITY_MISMATCH")
        title = row.get("bidNtceNm")
        if type(title) is not str or not title.strip() or len(title) > 500:
            raise CaptureError("NOTICE_TITLE_MISSING")
        return title.strip()
    except CaptureError:
        raise
    except (ValueError, TypeError, KeyError, UnicodeError, AttributeError, IndexError):
        raise CaptureError("INVALID_API_RESPONSE") from None


def _official_attachment(url, number, revision):
    if type(url) is not str or len(url) > 1000 or any(ord(c) < 33 or c == "\\" for c in url):
        return False
    try:
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.hostname != "www.g2b.go.kr"
                or parsed.username is not None or parsed.password is not None
                or parsed.port not in (None, 443) or parsed.fragment
                or parsed.path != ATTACHMENT_PATH
                or not re.fullmatch(r"[A-Za-z0-9_=-]+(?:&[A-Za-z0-9_=-]+){4}", parsed.query)):
            return False
        pairs = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True, max_num_fields=5)
        args = dict(pairs)
        return (len(args) == len(pairs) == 5
                and set(args) == {"bidPbancNo", "bidPbancOrd", "fileSeq", "prcmBsneSeCd", "fileType"}
                and args["bidPbancNo"] == number
                and args["bidPbancOrd"].isdecimal()
                and int(args["bidPbancOrd"]) == int(revision)
                and re.fullmatch(r"[1-9][0-9]{0,3}", args["fileSeq"]) is not None
                and args["prcmBsneSeCd"] in ("03", "05") and args["fileType"] == "")
    except (ValueError, TypeError):
        return False


def _fetch(url, hostname, opener):
    try:
        parts = urlsplit(url)
        if (parts.scheme != "https" or parts.hostname != hostname
                or parts.username is not None or parts.password is not None
                or parts.port not in (None, 443) or parts.fragment):
            raise CaptureError("URL_DENIED")
        request = Request(url, headers={
            "Accept-Encoding": "identity", "User-Agent": "PublicBidAgent-OfficialCapture/1",
        })
        with opener.open(request, timeout=15) as response:
            if response.geturl() != url or getattr(response, "status", 200) != 200:
                raise CaptureError("REDIRECT_DENIED")
            if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                raise CaptureError("ENCODING_DENIED")
            raw = response.read(MAX_BYTES + 1)
        if not raw or len(raw) > MAX_BYTES:
            raise CaptureError("SOURCE_SIZE_REJECTED")
        return raw
    except CaptureError:
        raise
    except (HTTPError, URLError, OSError, ValueError, TypeError):
        raise CaptureError("OFFICIAL_FETCH_FAILED") from None


@dataclass(frozen=True)
class OfficialCapture:
    notice_number: str
    source_revision: str
    title: str
    attachment_url: str
    attachment_name: str
    raw_notice: bytes
    raw_document: bytes

    def summary(self):
        return {
            "status": "UNATTESTED_RAW_CAPTURE",
            "notice_number": self.notice_number,
            "source_revision": self.source_revision,
            "notice_sha256": _sha(self.raw_notice),
            "notice_size_bytes": len(self.raw_notice),
            "document_sha256": _sha(self.raw_document),
            "document_size_bytes": len(self.raw_document),
            "document_type": "HWPX",
            "official_api_operation": "getBidPblancListInfoServc02",
        }


def capture(*, notice_number, source_revision, attachment_url, attachment_name, service_key, opener=None):
    """고정 공식 URL에서 GET만 수행한다. 공고 metadata/attachment URL 간 신뢰 결속은 부분 검증."""
    _identity(notice_number, source_revision)
    service_key = _normalized_service_key(service_key)
    if (type(attachment_name) is not str or not 1 <= len(attachment_name) <= 180
            or not attachment_name.lower().endswith(".hwpx")
            or any(ord(ch) < 32 or ch in "/\\" for ch in attachment_name)):
        raise CaptureError("INVALID_ATTACHMENT_NAME")
    if not _official_attachment(attachment_url, notice_number, source_revision):
        raise CaptureError("ATTACHMENT_URL_DENIED")
    opener = opener or build_opener(ProxyHandler({}), _NoRedirect())
    query = urlencode({
        "serviceKey": service_key, "pageNo": "1", "numOfRows": "10",
        "type": "json", "inqryDiv": "2", "bidNtceNo": notice_number,
        "bidNtceOrd": source_revision,
    })
    raw_notice = _fetch(API_URL + "?" + query, "apis.data.go.kr", opener)
    title = _official_response(raw_notice, notice_number, source_revision)
    raw_doc = _fetch(attachment_url, "www.g2b.go.kr", opener)
    if not zipfile.is_zipfile(io.BytesIO(raw_doc)):
        raise CaptureError("INVALID_HWPX_ARCHIVE")
    return OfficialCapture(notice_number, source_revision, title, attachment_url,
                           attachment_name, raw_notice, raw_doc)


def _write_once(folder, name, raw):
    target = folder / name
    try:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    except FileExistsError:
        try:
            if target.is_symlink() or not stat.S_ISREG(target.stat().st_mode):
                raise CaptureError("STORAGE_CONFLICT")
            with target.open("rb") as stream:
                if stream.read(len(raw) + 1) != raw:
                    raise CaptureError("STORAGE_CONFLICT")
        except OSError:
            raise CaptureError("STORAGE_CONFLICT") from None
    else:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())


def persist(result: OfficialCapture, private_root):
    """private root 외·저장소 내부 금지. 생성 후 원본은 덮어쓰기/삭제하지 않는다."""
    if type(result) is not OfficialCapture:
        raise CaptureError("INVALID_CAPTURE")
    # Windows ACL 검증을 구현하지 않았으므로 POSIX 파일 권한 보장 없이 원본을 저장하지 않는다.
    if os.name == "nt":
        raise CaptureError("STORAGE_PLATFORM_UNVERIFIED")
    root = Path(private_root) if isinstance(private_root, (str, os.PathLike)) else None
    try:
        if root is None or not root.is_absolute() or root.is_symlink():
            raise CaptureError("STORAGE_ROOT_DENIED")
        root = root.resolve(strict=True)
        repository_root = Path(__file__).resolve().parents[2]
        if not root.is_dir() or root.is_relative_to(repository_root) or (root.stat().st_mode & 0o022):
            raise CaptureError("STORAGE_ROOT_DENIED")
        folder = root / CAPTURE_DIR
        folder.mkdir(mode=0o700, exist_ok=True)
        if folder.is_symlink() or not folder.is_dir() or stat.S_IMODE(folder.stat().st_mode) != 0o700:
            raise CaptureError("STORAGE_ROOT_DENIED")
        summary = result.summary()
        capture_id = _sha((":".join([
            summary["notice_sha256"], summary["document_sha256"],
            result.notice_number, result.source_revision,
        ])).encode())
        base = CAPTURE_DIR + "/" + capture_id
        notice_key = base + ".notice.raw.json"
        doc_key = base + ".document.hwpx"
        manifest_key = base + ".manifest.json"
        _write_once(folder, capture_id + ".notice.raw.json", result.raw_notice)
        _write_once(folder, capture_id + ".document.hwpx", result.raw_document)
        manifest = {
            **summary, "capture_id": capture_id,
            "notice_storage_key": notice_key, "document_storage_key": doc_key,
            "attestation_state": "UNREVIEWED",
        }
        raw = (json.dumps(manifest, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":")) + "\n").encode()
        _write_once(folder, capture_id + ".manifest.json", raw)
        return {**summary, "capture_id": capture_id, "manifest_key": manifest_key}
    except CaptureError:
        raise
    except (OSError, TypeError, ValueError):
        raise CaptureError("STORAGE_FAILED") from None
