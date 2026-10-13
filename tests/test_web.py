"""Isolated HTTP security and administration tests on 127.0.0.1 only."""
import http.client
import json
import re
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import urlencode

from itomiscan.storage.config import ConfigStore
from itomiscan.web.server import build_server


class WebAdminTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        path = Path(self.tmp.name) / "itomiscan.db"
        ConfigStore(path).set_password("VeryStrongExamplePassword_2026")
        self.server = build_server("127.0.0.1", 0, db_path=path)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.worker.join, 3)
        self.port = self.server.server_port
        self.cookie = ""
        self.csrf = ""

    def req(self, method, path, fields=None, *, headers=None, raw=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        defaults = {"Host": f"127.0.0.1:{self.port}"}
        if self.cookie:
            defaults["Cookie"] = self.cookie
        if headers:
            defaults.update(headers)
        if fields is not None:
            raw = urlencode(fields, encoding="utf-8")
            defaults["Content-Type"] = "application/x-www-form-urlencoded"
        connection.request(method, path, raw, defaults)
        response = connection.getresponse()
        result = (response.status, dict(response.getheaders()),
                  response.read().decode("utf-8", "replace"))
        connection.close()
        return result

    def login(self):
        code, headers, _ = self.req(
            "POST", "/login", {"password":"VeryStrongExamplePassword_2026"})
        self.assertEqual(code, 303)
        self.cookie = headers["Set-Cookie"].split(";", 1)[0]
        self.assertIn("HttpOnly", headers["Set-Cookie"])
        self.assertIn("SameSite=Strict", headers["Set-Cookie"])
        code, _, page = self.req("GET", "/profiles")
        self.assertEqual(code, 200)
        self.csrf = re.search(r'name="csrf" value="([^"]+)"', page).group(1)

    def test_password_only_login_and_auth_guard(self):
        self.assertEqual(self.req("GET", "/")[0], 303)
        self.assertEqual(self.req("GET", "/backup.json")[0], 303)
        self.assertEqual(self.req("POST", "/login", {"password":"wrong"})[0], 401)
        self.login()
        status, hdrs, body = self.req("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("Übersicht", body)
        self.assertIn("frame-ancestors", hdrs["Content-Security-Policy"])
        self.assertNotIn("VeryStrongExamplePassword_2026", body)

    def test_csrf_invalid_host_and_cross_origin_rejected(self):
        self.login()
        fields = {"csrf": "nope", "name": "Test"}
        self.assertEqual(self.req("POST", "/profiles/select", fields)[0], 403)
        self.assertEqual(self.req("GET", "/", headers={"Host":"strange.example"})[0], 421)
        self.assertEqual(self.req("POST", "/logout", {"csrf":self.csrf},
                                  headers={"Origin":"https://evil.invalid"})[0], 403)
        self.assertEqual(self.req("GET", "/")[0], 200)

    def test_profile_and_targets_saved_in_shared_database(self):
        self.login()
        fields = {"csrf":self.csrf,"name":"Steuerunterlagen",
                  "mode":"Gray","source":"ADF Duplex",
                  "resolution":"300","output":"PDF",
                  "advanced":'{"--brightness":"10"}'}
        self.assertEqual(self.req("POST", "/profiles/save", fields)[0], 303)
        self.assertEqual(ConfigStore(self.server.store.path).list_profiles()[1],
                         "Steuerunterlagen")
        target = {"csrf":self.csrf, "kind":"paperless", "name":"DMS",
                  "address":"https://dms.lan"}
        self.assertEqual(self.req("POST", "/targets/save", target)[0],303)
        self.assertEqual(len(ConfigStore(self.server.store.path).list_targets()),1)

    def test_target_html_escaped_and_secrets_not_exported(self):
        self.login()
        self.server.store.save_target({
            "kind":"paperless","name":'<img src=x onerror=alert(1)>',
            "address":"https://dms.lan"})
        code, _, html = self.req("GET", "/targets")
        self.assertEqual(code, 200)
        self.assertNotIn('<img src=x onerror=alert(1)>', html)
        self.assertIn("&lt;img", html)
        code, headers, backup = self.req("GET", "/backup.json")
        self.assertEqual(code,200)
        self.assertIn("attachment",headers["Content-Disposition"])
        self.assertNotIn("salt",backup)
        self.assertNotIn("hash",backup)
        self.assertNotIn("VeryStrongExamplePassword_2026",backup)
        self.assertEqual(json.loads(backup)["version"],1)

    def test_backup_restore_via_browser_upload(self):
        self.login()
        backup = json.dumps(self.server.store.backup()).encode("utf-8")
        self.server.store.save_target({
            "kind":"network","name":"Extra","address":"smb://nas/share"})
        boundary = "ITOMISCANtestboundary"
        chunks = []
        for name, value, filename in [
            ("csrf",self.csrf.encode("utf-8"),None),
            ("backup",backup,"backup.json"),
        ]:
            chunks.append(f"--{boundary}\r\n".encode())
            disp = f'Content-Disposition: form-data; name="{name}"'
            if filename:
                disp += f'; filename="{filename}"'
            chunks.append((disp + "\r\n\r\n").encode())
            chunks.append(value)
            chunks.append(b"\r\n")
        chunks.append(f"--{boundary}--\r\n".encode())
        status, _, _ = self.req("POST","/backups/restore",raw=b"".join(chunks),
                         headers={"Content-Type":f"multipart/form-data; boundary={boundary}"})
        self.assertEqual(status, 303)
        self.assertEqual(self.server.store.list_targets(), [])
        self.assertTrue(self.server.store.verify_password("VeryStrongExamplePassword_2026"))

    def test_network_bind_refuses_cleartext_and_wildcard(self):
        for ip in ("0.0.0.0", "192.168.2.3"):
            with self.subTest(ip=ip):
                with self.assertRaises(ValueError):
                    build_server(ip, 0, db_path=self.server.store.path)

    def test_logout_clears_session(self):
        self.login()
        code, hdrs, _ = self.req("POST","/logout",{"csrf":self.csrf})
        self.assertEqual(code,303)
        self.assertIn("Max-Age=0", hdrs["Set-Cookie"])
        self.assertEqual(self.req("GET","/")[0],303)


if __name__ == "__main__":
    unittest.main()
