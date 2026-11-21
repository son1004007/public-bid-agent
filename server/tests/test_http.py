"""실제 loopback WSGI health smoke. 임시 포트와 합성 test 설정, DB 연결 없음."""
import json
import threading
from urllib.request import urlopen
from wsgiref.simple_server import make_server, WSGIRequestHandler
from django.core.wsgi import get_wsgi_application
from django.test import SimpleTestCase


class QuietHandler(WSGIRequestHandler):
    def log_message(self, format, *args):
        pass


class LocalHttpTests(SimpleTestCase):
    def test_loopback_process_liveness(self):
        with make_server("127.0.0.1", 0, get_wsgi_application(), handler_class=QuietHandler) as server:
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                with urlopen(f"http://127.0.0.1:{server.server_port}/api/v1/health", timeout=3) as response:
                    body = json.load(response)
                    self.assertEqual(response.status, 200)
                    self.assertEqual(body["data"], {"status": "ok", "scope": "process"})
                    self.assertEqual(response.headers["X-Request-ID"], body["request_id"])
            finally:
                server.shutdown()
                worker.join(timeout=3)
                self.assertFalse(worker.is_alive())
