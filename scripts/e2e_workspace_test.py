"""Run the existing synthetic procurement HTTP regression in isolation.

Never read workstation settings, log session/CSRF tokens, or authenticate as a
real account. This is API integration, not browser or operational acceptance.
"""
from pathlib import Path
import subprocess
import sys


def main():
    server = Path(__file__).resolve().parents[1] / "server"
    result = subprocess.run(
        [sys.executable, str(server / "manage.py"), "test",
         "tests.test_procurement_api", "--settings=bid_server.settings.test", "--verbosity=1"],
        cwd=server, timeout=180,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
