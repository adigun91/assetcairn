from threading import Thread
from urllib.error import HTTPError
from urllib.request import urlopen

from django.http import HttpResponse
from django.test import SimpleTestCase
from waitress import create_server

from backend.middleware import RemoveServerHeadersMiddleware


class ResponseHeaderTests(SimpleTestCase):
    def test_removes_existing_identifying_headers(self):
        response = HttpResponse(headers={"Server": "Example/1.2", "X-Powered-By": "Example framework",
                                         "X-AspNet-Version": "1.2", "X-AspNetMvc-Version": "3.4"})
        hardened = RemoveServerHeadersMiddleware(lambda request: response)(None)
        self.assertEqual(hardened["Server"], "")
        for name in ("X-Powered-By", "X-AspNet-Version", "X-AspNetMvc-Version"):
            self.assertNotIn(name, hardened)

    def test_application_success_and_error_headers(self):
        for path in ("/api/health", "/api/does-not-exist"):
            response = self.client.get(path)
            self.assertFalse(response.headers.get("Server"))
            self.assertNotIn("X-Powered-By", response)
            self.assertIn("X-Content-Type-Options", response)

    def test_waitress_network_headers_for_application_and_server_errors(self):
        def application(environ, start_response):
            if environ["PATH_INFO"] == "/error":
                raise RuntimeError("Intentional test failure")
            start_response("200 OK", [("Content-Type", "text/plain"), ("Server", "")])
            return [b"ok"]

        server = create_server(application, host="127.0.0.1", port=0, ident="", threads=1)
        thread = Thread(target=server.run, daemon=True)
        thread.start()
        try:
            for path in ("/", "/error"):
                try:
                    response = urlopen(f"http://127.0.0.1:{server.effective_port}{path}", timeout=5)
                except HTTPError as error:
                    response = error
                with response:
                    self.assertFalse(response.headers.get("Server"))
                    self.assertIsNone(response.headers.get("X-Powered-By"))
        finally:
            server.close()
            thread.join(timeout=3)