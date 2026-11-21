"""격리 Django 명령 진입점. 기본은 strict base 설정이며 기존 로컬 서버를 변경하지 않는다."""
import os
import sys
from django.core.management import execute_from_command_line

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bid_server.settings.base")
    execute_from_command_line(sys.argv)
