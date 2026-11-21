"""Validate the canonical live workspace without rewriting it.

The committed HTML is the source of truth; the historical generator embedded
a second divergent copy. Never write to a hard-coded workstation path.
"""
from pathlib import Path


def main():
    path = Path(__file__).resolve().parents[1] / "frontend/public/server-workspace-live.html"
    html = path.read_text(encoding="utf-8")
    for marker in ("loginForm", "passwordForm", "readBusiness", "escapeHtml"):
        if marker not in html:
            raise SystemExit("Workspace source contract missing")
    print("Canonical workspace source present; no files changed.")


if __name__ == "__main__":
    main()
