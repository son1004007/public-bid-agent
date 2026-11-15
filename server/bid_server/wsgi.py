"""격리 WSGI 진입점. strict 설정 실패 시 시작하지 않으며 데이터 초기화 없음."""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bid_server.settings.base")
application = get_wsgi_application()
