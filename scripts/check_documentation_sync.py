"""코드 변경 커밋 시 루트·로컬 README 동반 갱신을 강제하는 CI 검사."""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REQUIRED={"README.md", "local_app/README.md"}
SOURCE_PREFIXES=("local_app/", "frontend/src/", "backend/")
SOURCE_EXACT={"frontend/package.json", "frontend/package-lock.json", "local_app/requirements.txt"}
SOURCE_EXT={".py", ".js", ".ts", ".tsx", ".html", ".css", ".txt"}

def run() -> int:
    for f in [*REQUIRED, "docs/DEPENDENCIES_AND_LICENSES.md", "docs/02-architecture.md"]:
        if not (ROOT/f).is_file():
            print("DOC FAIL required file missing:",f)
            return 1
    try:
        diff=subprocess.run(["git","diff","--name-only","HEAD^","HEAD"],cwd=ROOT,
                             capture_output=True,text=True,check=True).stdout.splitlines()
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("DOC SKIP: cannot inspect parent commit (initial/shallow checkout)")
        return 0
    changed=set(diff)
    sources={x for x in changed if x in SOURCE_EXACT or
             (x.startswith(SOURCE_PREFIXES) and Path(x).suffix in SOURCE_EXT
              and not Path(x).name.startswith("test_"))}
    if sources:
        missing=REQUIRED-changed
        if missing:
            print("DOC FAIL: source changes",sorted(sources),"require same-commit updates",sorted(missing))
            return 1
        print("DOC PASS: implementation and both README files updated in this commit")
    else: print("DOC PASS: no application source change in this commit")
    return 0

if __name__=="__main__":sys.exit(run())