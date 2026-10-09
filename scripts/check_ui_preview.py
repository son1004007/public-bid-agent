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
