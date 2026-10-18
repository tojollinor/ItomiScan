"""Paperless connection diagnostics without contacting external servers."""
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode

from itomiscan.integrations.paperless_diagnostics import (
    diagnose_paperless, exchange_credentials, PaperlessDiagnosticError)
from itomiscan.storage.config import ConfigStore
from itomiscan.web.server import build_server


class DiagnosticTests(unittest.TestCase):
    def test_profile_and_document_read(self):
        def response(_address, method, suffix, **kwargs):
            self.assertEqual(method, "GET")
            self.assertEqual(kwargs["token"], "secret")
            if suffix == "/api/profile/":
                return 200, "application/json", b'{"username":"scanner"}'
            return 403, "application/json", b'{"detail":"forbidden"}'
        with patch("itomiscan.integrations.paperless_diagnostics._request",
                   side_effect=response):
            result = diagnose_paperless("https://paperless.example", "secret")
        self.assertTrue(result["ok"])
        self.assertIn("403", str(result["steps"]))
        self.assertNotIn("secret", str(result))
        self.assertTrue(any(s["ok"] is None for s in result["steps"]))
        
    def test_token_exchange_not_stored_password(self):
        with patch("itomiscan.integrations.paperless_diagnostics._request",
                   return_value=(200, "application/json", b'{"token":"tokenvalue"}')) as call:
            token = exchange_credentials("https://paperless.example", "user", "pass")
        self.assertEqual(token, "tokenvalue")
        self.assertEqual(call.call_args.kwargs["payload"],
                         {"username": "user", "password": "pass"})

    def test_403_and_bad_https(self):
        with patch("itomiscan.integrations.paperless_diagnostics._request",
                   return_value=(403, "application/json", b'')):
            result = diagnose_paperless("https://paperless.example", "secret")
        self.assertFalse(result["ok"])
        self.assertIn("403", str(result))
        with self.assertRaises(PaperlessDiagnosticError):
            exchange_credentials("http://insecure", "user", "pass")


class DiagnosticWebTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        db = Path(directory.name) / "itomiscan.db"
        store = ConfigStore(db)
        store.set_password("StrongExamplePassword123!")
        store.save_target({"kind":"paperless","name":"Archiv",
                           "address":"https://paperless.example"})
        self.target = store.list_targets()[0]
        server = build_server("127.0.0.1", 0, db_path=db)
        self.server = server
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(worker.join, 3)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.cookie = ""
        self.csrf = ""

    def req(self, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=4)
        headers = {"Host": "127.0.0.1:%d" % self.server.server_port}
        if self.cookie:
            headers["Cookie"] = self.cookie
        if body is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            body = urlencode(body)
        conn.request("POST" if body is not None else "GET", path, body, headers)
        response = conn.getresponse()
        result = response.status, dict(response.getheaders()), response.read().decode("utf-8", "replace")
        conn.close()
        return result

    def login(self):
        status, headers, _ = self.req("/login", {"password": "StrongExamplePassword123!"})
        self.assertEqual(status, 303)
        self.cookie = headers["Set-Cookie"].split(";", 1)[0]
        import re
        self.csrf = re.search(r'name="csrf" value="([^"]+)"',
                              self.req("/targets")[2]).group(1)

    def test_diagnostic_auth_csrf_and_page(self):
        self.assertEqual(self.req("/targets/paperless/test",
                                  {"csrf":"bad", "target_id": str(self.target["id"])})[0], 303)
        self.login()
        self.assertEqual(self.req("/targets/paperless/test",
                                  {"csrf":"bad", "target_id": str(self.target["id"])})[0], 403)
        self.server.secrets.update(self.target["id"], token="existing")
        with patch("itomiscan.web.server.diagnose_paperless",
                   return_value={"ok":False,"steps":[{"name":"Anmeldung","ok":False,
                       "http":403, "message":"Berechtigung prüfen"}]}) as test:
            status, _, html = self.req("/targets/paperless/test",
                {"csrf": self.csrf, "target_id": str(self.target["id"])})
        self.assertEqual(status, 200)
        self.assertIn("Berechtigung prüfen", html)
        self.assertNotIn("existing", html)
        test.assert_called_once()

    def test_password_login_stores_only_token(self):
        self.login()
        with patch("itomiscan.web.server.exchange_credentials",
                   return_value="generated") as exchange:
            status, _, _ = self.req("/targets/paperless/login", {
                "csrf":self.csrf,"target_id":str(self.target["id"]),
                "username":"user","password":"privatepw"})
        self.assertEqual(status, 303)
        exchange.assert_called_once()
        self.assertEqual(self.server.secrets.get(self.target["id"]), {"token":"generated"})
        self.assertNotIn("privatepw", str(self.server.store.backup()))


if __name__ == "__main__":
    unittest.main()
