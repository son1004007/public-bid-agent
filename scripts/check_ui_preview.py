"""정적 퍼블리싱 HTML의 최소 파일/JS 문법 게이트.

목적/책임: 외부 의존성 없이 데모 HTML의 필수 면책 표시 및 JavaScript 구문을 확인한다.
입력/출력: frontend/public/ui-review.html -> 검사 실패 시 예외/비영 종료.
신뢰 경계/권한: 사용자 화면이나 브라우저 검증·독립 리뷰를 대체하지 않는다.
상태 변경/부작용: 임시 파일만 사용, 저장소 파일 미수정.
실패/타임아웃/재시도: Node 실행 오류는 테스트 실패.
핵심 불변조건: 실제 API/LLM이 동작하는 것으로 오인하게 하는 문구를 두지 않는다.
관련 요구사항/테스트/설계 문서: docs/ui/SCREEN_REVIEW_GUIDE.md.
"""

from html.parser import HTMLParser
from pathlib import Path
import subprocess
import tempfile


class PreviewParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_script = False
        self.scripts = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.in_script = True
        if tag in {"script", "link", "iframe"}:
            self.links += [(tag, dict(attrs))]

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_script = False

    def handle_data(self, text):
        if self.in_script:
            self.scripts.append(text)


html_path = Path(__file__).resolve().parents[1] / "frontend/public/ui-review.html"
source = html_path.read_text(encoding="utf-8")
parser = PreviewParser()
parser.feed(source)
assert len(parser.scripts) == 1, "expected one inline, offline JS script"
assert not any(attrs.get("src") or attrs.get("href") for _, attrs in parser.links), "unexpected external asset"
for marker in ["합성", "UI", "접수", "검토", "공고", "id=\"results\"", "id=\"scenario\""]:
    assert marker in source, f"missing required marker {marker}"

with tempfile.TemporaryDirectory() as directory:
    js = Path(directory) / "ui-review.js"
    js.write_text(parser.scripts[0], encoding="utf-8")
    subprocess.run(["node", "--check", str(js)], check=True, timeout=20)

print("UI publishing static/syntax check: PASS")


# 두 번째 세부 페이지는 실제 입찰 제출·점수 기록이 아닌 브라우저 목업이다.
detail_path = Path(__file__).resolve().parents[1] / "frontend/public/bid-detail-review.html"
detail_source = detail_path.read_text(encoding="utf-8")
detail_parser = PreviewParser()
detail_parser.feed(detail_source)
assert len(detail_parser.scripts) == 1, "detail page must have one inline script"
assert not any(attrs.get("src") or attrs.get("href") for _, attrs in detail_parser.links), "detail page external asset"
for marker in ["제출", "점수", "미확인", "합성", "id=\"content\"", "id=\"tabs\""]:
    assert marker in detail_source, f"detail page missing {marker}"
with tempfile.TemporaryDirectory() as directory:
    script = Path(directory) / "detail.js"
    script.write_text(detail_parser.scripts[0], encoding="utf-8")
    subprocess.run(["node", "--check", str(script)], check=True, timeout=20)
print("Bid detail publishing static/syntax check: PASS")


# 2026-10-09 실제 UI 우선 검증: 입찰 참여/제출물 분리/낙찰·계약/평가/회고 시안.
workflow_path = Path(__file__).resolve().parents[1] / "frontend/public/bid-management-preview.html"
workflow_source = workflow_path.read_text(encoding="utf-8")
workflow_parser = PreviewParser()
workflow_parser.feed(workflow_source)
assert len(workflow_parser.scripts) == 1, "workflow preview must have one inline JS"
assert not any(attrs.get("src") or attrs.get("href") for _, attrs in workflow_parser.links), "workflow preview has external assets"
for marker in ["Bid / No-Bid", "가격입찰서", "기술제안서", "접수증", "미확인", "계약", "점수", "회고", "id=\"boardRows\"", "id=\"detailBody\""]:
    assert marker in workflow_source, f"workflow UI marker missing: {marker}"
script_text = workflow_parser.scripts[0]
for prohibited in ["localStorage", "sessionStorage", "document.cookie", "fetch(", "XMLHttpRequest", "sendBeacon", "innerHTML"]:
    assert prohibited not in script_text, f"workflow mock has prohibited I/O: {prohibited}"
with tempfile.TemporaryDirectory() as directory:
    script_path = Path(directory) / "workflow.js"
    script_path.write_text(script_text, encoding="utf-8")
    subprocess.run(["node", "--check", str(script_path)], check=True, timeout=20)

print("Bid management UI publishing static/syntax check: PASS")


# 내 ChatGPT/Codex 계정 선택 UI는 OAuth나 실제 로그인으로 오인하지 않는 별도 목업.
account_page = Path(__file__).resolve().parents[1] / "frontend/public/ai-account-preview.html"
account_html = account_page.read_text(encoding="utf-8")
account_parser = PreviewParser()
account_parser.feed(account_html)
assert len(account_parser.scripts) == 1, "AI account preview must have exactly one inline JS"
assert not any(a.get("src") or a.get("href") for _, a in account_parser.links), "unexpected script/link/iframe asset URL"
for keyword in ["실제 로그인 미연결", "가상 계정", "사용 권한", "id=\"accounts\"", "id=\"connect\"", "disabled", "PKCE"]:
    assert keyword in account_html, f"AI account screen missing {keyword}"
for forbidden in ["localStorage", "sessionStorage", "document.cookie", "fetch(", "XMLHttpRequest", "sendBeacon", "innerHTML"]:
    assert forbidden not in account_parser.scripts[0], f"AI account mock unexpected network/persistence: {forbidden}"
with tempfile.TemporaryDirectory() as directory:
    script = Path(directory) / "account.js"
    script.write_text(account_parser.scripts[0], encoding="utf-8")
    subprocess.run(["node", "--check", str(script)], check=True, timeout=20)

print("Personal Codex account preview syntax/security-static check: PASS")
