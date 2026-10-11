"""공식 공고 규격서 링크의 공개 문서 본문 추출 (사용자 요청 시에만).

입력: 서버가 API에서 저장한 고정 g2b 도메인 URL/파일명.
출력: 로컬 추출기 JSON에서 선택된 텍스트, 안전한 오류 상태.
부작용: 고정 공식 사이트 HTTPS 다운로드. 파일 원본 영구 보관/외부 AI 전송 없음.
경계: localhost 화면에서 사용자 클릭, 원격 URL 리다이렉트 거절, 최대 8MiB,
      확장자 whitelist, 한 번에 문서 하나, 서버의 별도 subprocess 추출 제한.
실패: 추출 불가를 적합/부적합으로 오인하지 않음.
"""
import urllib.parse
import urllib.request
import urllib.error
from pathlib import PurePath

SUPPORTED = {".pdf", ".hwpx", ".hwp", ".docx", ".txt", ".md"}
MAX_BYTES = 8 * 1024 * 1024


class DocumentFetchError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise DocumentFetchError("공식 첨부 주소가 다른 URL로 이동했습니다")


def official_url(url):
    if not isinstance(url, str) or len(url) > 1000:
        return False
    try:
        p = urllib.parse.urlsplit(url)
        return p.scheme == "https" and p.hostname in ("www.g2b.go.kr", "g2b.go.kr") and not (
            p.username or p.password or p.port not in (None, 443) or p.fragment
        )
    except ValueError:
        return False


def choose_attachment(notice):
    files = notice.get("attachments", [])
    valid = []
    for item in files[:10]:
        if not isinstance(item, dict):
            continue
        name, url = item.get("name", ""), item.get("url")
        if not isinstance(name, str) or not official_url(url):
            continue
        ext = PurePath(name.strip()).suffix.lower()
        if ext not in SUPPORTED:
            continue
        importance = max([v for phrase, v in (
            ("제안요청", 6), ("과업지시", 5), ("과업내용", 5), ("과업설명", 4),
            ("사업설명", 3), ("규격서", 2), ("공고문", 1)) if phrase in name] or [0])
        valid.append((importance, item, ext))
    valid.sort(key=lambda t: t[0], reverse=True)
    if not valid:
        raise DocumentFetchError("지원되는 공개 PDF/HWP/HWPX/DOCX/TXT 첨부 링크가 없습니다")
    return valid[0][1], valid[0][2]


def fetch_attachment(url, opener=None):
    if not official_url(url):
        raise DocumentFetchError("조달청 공식 HTTPS 첨부 URL만 허용합니다")
    opener = opener or urllib.request.build_opener(NoRedirect())
    try:
        request = urllib.request.Request(url, headers={"Accept": "application/octet-stream"})
        with opener.open(request, timeout=12) as response:
            if not official_url(response.geturl()):
                raise DocumentFetchError("공식 사이트가 아닌 응답")
            data = response.read(MAX_BYTES + 1)
    except (OSError, ValueError, urllib.error.URLError) as error:
        raise DocumentFetchError("공식 첨부 다운로드가 불가능합니다") from error
    if not data or len(data) > MAX_BYTES:
        raise DocumentFetchError("첨부파일 용량 한도 8MiB 초과 또는 비어 있음")
    return data


def extract(notice, extractor, opener=None):
    item, ext = choose_attachment(notice)
    data = fetch_attachment(item["url"], opener=opener)
    try:
        extracted = extractor(item["name"], data)
    except (ValueError, OSError) as error:
        raise DocumentFetchError("첨부 파일 텍스트 추출에 실패했습니다") from error
    if not isinstance(extracted, dict):
        raise DocumentFetchError("문서 추출 응답 형식 오류")
    text = extracted.get("text")
    if not isinstance(text, str) or not text.strip():
        raise DocumentFetchError("문서에서 추출 가능한 텍스트가 없습니다")
    return {"text": text[:12000], "source_name": item["name"][:200],
            "warnings": [str(x)[:90] for x in extracted.get("warnings", [])[:5]]}
