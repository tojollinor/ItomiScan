"""Isolated HTTP security and administration tests on 127.0.0.1 only."""
import http.client
import json
import re
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
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
        # unittest cleanups are LIFO: shutdown, close, then join.
        self.addCleanup(self.worker.join, 3)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
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
            raw = urlencode(fields, encoding="utf-8", doseq=True)
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

    def test_opaque_origin_user_creation_keeps_session_and_csrf_protection(self):
        self.login()
        payload = {
            "csrf": self.csrf, "name": "Testkonto", "pin": "2468",
            "active": "yes", "assigned_profiles": "Dokument",
            "default_profile": "Dokument", "perm_scan": "yes",
        }
        # An authenticated browser may send Origin:null on self-signed TLS.
        self.assertEqual(self.req(
            "POST", "/users/save", payload,
            headers={"Origin": "null"})[0], 303)
        self.assertEqual(self.server.users.list_users()[0]["name"], "Testkonto")
        payload["csrf"] = "invalid"
        self.assertEqual(self.req(
            "POST", "/users/save", payload,
            headers={"Origin": "null"})[0], 403)
        payload["csrf"] = self.csrf
        self.assertEqual(self.req(
            "POST", "/users/save", payload,
            headers={"Origin": "https://not-the-scanner.example"})[0], 403)
        self.assertEqual(len(self.server.users.list_users()), 1)

    def test_opaque_origin_login_still_needs_explicit_opt_in(self):
        self.assertEqual(self.req(
            "POST", "/login", {"password": "VeryStrongExamplePassword_2026"},
            headers={"Origin": "null"})[0], 403)
        with patch("itomiscan.web.server.Path.home",
                   return_value=Path(self.tmp.name)):
            flag = Path(self.tmp.name) / ".config" / "itomiscan" / "allow-null-origin"
            flag.parent.mkdir(parents=True, exist_ok=True)
            flag.write_text("")
            self.assertEqual(self.req(
                "POST", "/login",
                {"password": "VeryStrongExamplePassword_2026"},
                headers={"Origin": "null"})[0], 303)

    def test_branding_and_authenticated_live_status(self):
        self.assertEqual(self.req("GET", "/api/status")[0], 303)
        self.assertEqual(self.req("GET", "/assets/status.js")[0], 303)
        self.login()
        for route in ("/", "/system", "/users"):
            with self.subTest(route=route):
                code, _, page = self.req("GET", route)
                self.assertEqual(code, 200)
                self.assertIn('<svg class="brand-icon"', page)
                self.assertIn("Itomi<b>Scan</b>", page)
                if route in ("/", "/system"):
                    self.assertIn("data-status-key=\"disk", page)
                    self.assertIn("/assets/status.js", page)
                    self.assertIn('data-metric-chart="cpu"', page)
                    self.assertIn('data-metric-chart="ram"', page)
                    if route == "/":
                        self.assertNotIn('data-status-key="cpu"', page)
                        self.assertIn('data-ram-progress', page)
                    else:
                        self.assertIn('data-status-key="cpu"', page)
        code, headers, body = self.req("GET", "/api/status")
        self.assertEqual(code, 200)
        state = json.loads(body)
        for key in ("cpu", "ram", "ram_total", "ram_free", "disk_total",
                    "disk_used", "disk_free", "uptime", "web_service",
                    "delivery_service", "jobs_pending", "jobs_review"):
            self.assertIn(key, state)
        code, headers, script = self.req("GET", "/assets/status.js")
        self.assertEqual(code, 200)
        self.assertIn("javascript", headers["Content-Type"])
        self.assertIn("setInterval(refresh, 1000)", script)
        self.assertIn("/api/metrics", script)
        code, _, metrics = self.req("GET", "/api/metrics")
        self.assertEqual(code, 200)
        self.assertIn("ram_percent", json.loads(metrics))
        self.assertEqual(self.req("GET", "/assets/admin-dialogs.js")[0], 200)
        for route in ("/profiles", "/users", "/targets", "/printers"):
            code, _, html = self.req("GET", route)
            self.assertEqual(code, 200)
            self.assertIn('class="entry-list"', html)
        self.assertEqual(self.req("GET", "/api/metrics")[0], 200)
        self.assertIn("script-src 'self'", headers["Content-Security-Policy"])

    def test_lan_discovery_only_after_explicit_authenticated_search(self):
        with patch("itomiscan.web.server.discover_paperless",
                   return_value=["https://192.168.44.30:8443"]) as paperless, \
                patch("itomiscan.web.server.discover_printers",
                      return_value=["ipp://192.168.44.40/ipp/print"]) as cups, \
                patch("itomiscan.integrations.discovery.discover_ipp_printers",
                      return_value=["ipps://192.168.44.41:631/ipp/print"]) as dns:
            self.assertEqual(self.req("GET", "/targets?search=1")[0], 303)
            self.assertEqual(self.req("GET", "/printers?search=1")[0], 303)
            self.login()
            code, _, page = self.req("GET", "/targets")
            self.assertEqual(code, 200)
            self.assertIn("Paperless suchen", page)
            self.assertNotIn("data-select-paperless", page)
            paperless.assert_not_called()
            code, _, page = self.req("GET", "/targets?search=1")
            self.assertEqual(code, 200)
            self.assertIn('data-select-paperless="https://192.168.44.30:8443"', page)
            paperless.assert_called_once()
            self.assertEqual(self.req("GET", "/printers")[0], 200)
            cups.assert_not_called()
            dns.assert_not_called()
            code, _, page = self.req("GET", "/printers?search=1")
            self.assertEqual(code, 200)
            self.assertIn("data-select-printer", page)
            self.assertIn("ipps://192.168.44.41:631/ipp/print", page)
            cups.assert_called_once()
            dns.assert_called_once()

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

    def test_destination_specific_form_save_preserves_existing_store(self):
        self.login()
        cases = [
            ("paperless", {"paperless_url": "https://paperless.lan"},
             "https://paperless.lan"),
            ("network", {"network_host": "nas.lan", "network_share": "Scans",
                         "network_directory": "Eingang/2026"},
             "smb://nas.lan/Scans/Eingang/2026"),
            ("email", {"email_host": "smtp.lan", "email_security": "starttls",
                       "email_port": "", "email_recipient": "scan@example.org"},
             "smtp://smtp.lan:587/scan@example.org"),
            ("usb", {"usb_volume": "SCANSTICK", "usb_directory": "Dokumente"},
             "usb://SCANSTICK/Dokumente"),
        ]
        for index, (kind, fields, expected) in enumerate(cases):
            with self.subTest(kind=kind):
                code, _, _ = self.req("POST", "/targets/save", {
                    "csrf": self.csrf, "kind": kind, "name": "Ziel" + str(index),
                    **fields})
                self.assertEqual(code, 303)
                found = next(x for x in self.server.store.list_targets()
                             if x["name"] == "Ziel" + str(index))
                self.assertEqual(found["address"], expected)
        code, _, _ = self.req("POST", "/targets/save", {
            "csrf": self.csrf, "kind": "network", "name": "Bad",
            "network_host": "nas.lan", "network_share": ".."})
        self.assertEqual(code, 400)
        self.assertEqual(len(self.server.store.list_targets()), len(cases))

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

    def test_pin_user_administration_off_by_default(self):
        self.login()
        code, _, page = self.req("GET", "/users")
        self.assertEqual(code, 200)
        self.assertIn("PIN-Benutzerverwaltung", page)
        self.assertIn("Deaktiviert", page)
        payload = {
            "csrf":self.csrf, "name":"Anna", "pin":"4286", "active":"yes",
            "default_profile":"Foto",
            "assigned_profiles":["Foto","Dokument"],
            "perm_scan":"yes", "perm_copy":"yes",
        }
        self.assertEqual(self.req("POST", "/users/save", payload)[0], 303)
        self.assertEqual(self.req("GET", "/users")[0], 200)
        self.assertEqual(self.server.users.list_users()[0]["name"], "Anna")
        self.assertNotIn("4286", self.req("GET", "/users")[2])
        self.assertFalse(self.server.users.settings()["enabled"])
        self.assertEqual(self.req("POST", "/users/config", {
            "csrf":self.csrf, "enabled":"yes", "timeout_minutes":"3"})[0], 303)
        self.assertTrue(self.server.users.settings()["enabled"])
        self.assertEqual(self.server.users.settings()["timeout_minutes"], 3)
        self.assertTrue(self.server.users.verify_pin("4286"))
        self.assertEqual(self.req("GET", "/backup.json")[0], 200)
        self.assertNotIn("4286", self.req("GET", "/backup.json")[2])

    def test_pin_user_endpoint_requires_csrf_and_web_login(self):
        code, _, _ = self.req("GET", "/users")
        self.assertEqual(code, 303)
        self.login()
        data = {"name":"Test","pin":"6789","assigned_profiles":"Dokument",
                "default_profile":"Dokument"}
        self.assertEqual(self.req("POST", "/users/save", data)[0], 403)
        self.assertEqual(self.server.users.list_users(), [])
        data["csrf"] = self.csrf
        self.assertEqual(self.req("POST", "/users/save", data)[0], 303)
        uid = self.server.users.list_users()[0]["id"]
        self.assertEqual(self.req("POST", "/users/config", {
            "csrf":self.csrf, "enabled":"yes", "timeout_minutes":"1"})[0], 400)
        # Creating an inactive account does not authorize enabling a PIN gate.
        self.assertFalse(self.server.users.settings()["enabled"])
        self.assertEqual(self.req("POST", "/users/delete",
                                  {"csrf":self.csrf,"user_id":str(uid)})[0], 303)

    def test_last_active_pin_user_cannot_be_removed(self):
        self.login()
        self.assertEqual(self.req("POST", "/users/save", {
            "csrf":self.csrf, "name":"Scanner", "pin":"234567",
            "active":"yes", "assigned_profiles":"Dokument",
            "default_profile":"Dokument", "perm_scan":"yes"})[0], 303)
        self.assertEqual(self.req("POST", "/users/config", {
            "csrf":self.csrf,"enabled":"yes","timeout_minutes":"1"})[0], 303)
        uid = self.server.users.list_users()[0]["id"]
        self.assertEqual(self.req("POST", "/users/delete",
                                 {"csrf":self.csrf,"user_id":str(uid)})[0], 400)
        self.assertTrue(self.server.users.settings()["enabled"])

    def test_document_targets_credentials_and_queue_management(self):
        self.login()
        self.assertEqual(self.req("POST", "/targets/save", {
            "csrf":self.csrf,"kind":"usb","name":"OfficeStick",
            "address":"usb://SCANUSB/Scans"})[0], 303)
        self.assertEqual(self.req("POST", "/targets/save", {
            "csrf":self.csrf,"kind":"paperless","name":"Archiv",
            "address":"https://paperless.example.org"})[0], 303)
        paperless = next(x for x in self.server.store.list_targets()
                         if x["kind"] == "paperless")
        secrets = {"csrf":self.csrf,"target_id":str(paperless["id"]),
                   "token":"top-private-api-token"}
        self.assertEqual(self.req("POST", "/targets/secrets", secrets)[0],303)
        self.assertEqual(self.server.secrets.get(paperless["id"])["token"],
                         "top-private-api-token")
        self.assertNotIn("top-private-api-token", self.req("GET", "/targets")[2])
        self.assertNotIn("top-private-api-token", self.req("GET", "/backup.json")[2])
        scan = Path(self.tmp.name) / "source.pdf"
        scan.write_bytes(b"%PDF-1.4\n" + b"example")
        job_id = self.server.queue.enqueue(scan, paperless["id"])
        code, _, html = self.req("GET", "/jobs")
        self.assertEqual(code, 200)
        self.assertIn(job_id[:10], html)
        self.assertIn("Wartend", html)
        claimed = self.server.queue.claim()
        self.server.queue.outcome(claimed["id"],"review",error="Unklar")
        self.assertEqual(self.req("POST", "/jobs/retry", {
            "csrf":self.csrf,"job_id":job_id})[0],400)
        self.assertEqual(self.req("POST", "/jobs/retry", {
            "csrf":self.csrf,"job_id":job_id,"reviewed":"yes"})[0],303)
        self.assertEqual(self.server.queue.all()[0]["status"], "retry")

    def test_delivery_endpoints_require_auth_and_csrf(self):
        self.assertEqual(self.req("GET", "/jobs")[0],303)
        self.login()
        self.assertEqual(self.req("POST","/targets/secrets",{
            "target_id":"1", "token":"evil"})[0],403)
        self.assertEqual(self.req("POST","/jobs/retry",{
            "job_id":"a"*32})[0],403)
        self.assertEqual(self.req("GET", "/jobs")[0],200)

    def test_printer_page_and_safe_web_registration(self):
        self.login()
        with patch("itomiscan.web.server.list_queues", return_value=[]):
            status, _, page = self.req("GET", "/printers")
        self.assertEqual(status, 200)
        self.assertIn("Netzwerkdrucker", page)
        self.assertEqual(self.req("POST", "/printers/save", {
            "csrf": self.csrf, "name": "OfficeLaser",
            "address": "ipps://printer.lan/ipp/print"})[0], 303)
        printer = next(x for x in self.server.store.list_targets()
                       if x["kind"] == "printer")
        body = {"csrf": self.csrf, "target_id": str(printer["id"])}
        with patch("itomiscan.web.server.install_queue", return_value="OfficeLaser") as install:
            self.assertEqual(self.req("POST", "/printers/install", body)[0], 303)
            install.assert_called_once_with("OfficeLaser", "ipps://printer.lan/ipp/print")
        with patch("itomiscan.web.server.test_page", return_value="Accepted") as testing:
            self.assertEqual(self.req("POST", "/printers/test", body)[0], 303)
            testing.assert_called_once_with("OfficeLaser")
        with patch("itomiscan.web.server.uninstall_queue", return_value="OfficeLaser") as remove:
            self.assertEqual(self.req("POST", "/printers/uninstall", body)[0], 303)
            remove.assert_called_once_with("OfficeLaser")

    def test_printer_admin_authorization_invalid_uri_and_errors(self):
        self.assertEqual(self.req("GET", "/printers")[0], 303)
        self.assertEqual(self.req("POST", "/printers/save", {
            "name": "OfficeLaser", "address": "ipps://printer.lan/ipp/print"})[0], 303)
        self.login()
        self.assertEqual(self.req("POST", "/printers/save", {
            "csrf": "bad", "name": "OfficeLaser",
            "address": "ipps://printer.lan/ipp/print"})[0], 403)
        self.assertEqual(self.req("POST", "/printers/save", {
            "csrf": self.csrf, "name": "OfficeLaser",
            "address": "http://printer.lan/"} )[0], 400)
        self.assertEqual(self.req("POST", "/printers/save", {
            "csrf": self.csrf, "name": "OfficeLaser",
            "address": "ipps://printer.lan/ipp/print"})[0], 303)
        printer = next(x for x in self.server.store.list_targets()
                       if x["kind"] == "printer")
        from itomiscan.integrations.printing import PrintError
        with patch("itomiscan.web.server.install_queue",
                   side_effect=PrintError("CUPS verweigert Zugang")):
            status, _, html = self.req("POST", "/printers/install", {
                "csrf": self.csrf, "target_id": str(printer["id"])})
        self.assertEqual(status, 400)
        self.assertIn("CUPS verweigert", html)
        self.assertEqual(self.req("POST", "/printers/test", {
            "csrf": self.csrf, "target_id": "99999"})[0], 400)

    def test_printer_manual_ip_setup_and_address_edit(self):
        self.login()
        self.assertEqual(self.req("POST", "/printers/save", {
            "csrf": self.csrf, "name": "LaserTest", "protocol": "socket",
            "host": "192.168.1.22", "address": ""})[0], 303)
        rows = [x for x in self.server.store.list_targets()
                if x["kind"] == "printer" and x["name"] == "LaserTest"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["address"], "socket://192.168.1.22:9100")
        target_id = rows[0]["id"]
        self.assertEqual(self.req("POST", "/printers/edit", {
            "csrf": self.csrf, "target_id": str(target_id),
            "address": "ipps://laser.lan/ipp/print"})[0], 303)
        rows = [x for x in self.server.store.list_targets()
                if x["kind"] == "printer" and x["name"] == "LaserTest"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], target_id)
        self.assertEqual(rows[0]["address"], "ipps://laser.lan/ipp/print")
        self.assertEqual(self.req("POST", "/printers/edit", {
            "csrf": self.csrf, "target_id": "999999",
            "address": "ipp://laser.lan/ipp/print"})[0], 400)

    def test_configured_printer_must_be_uninstalled_before_delete(self):
        self.login()
        self.assertEqual(self.req("POST", "/printers/save", {
            "csrf": self.csrf, "name": "OfficePrinter",
            "address": "ipps://printer.lan/ipp/print"})[0], 303)
        target = next(x for x in self.server.store.list_targets()
                      if x["kind"] == "printer" and x["name"] == "OfficePrinter")
        with patch("itomiscan.web.server.list_queues", return_value=["OfficePrinter"]):
            code, _, _ = self.req("POST", "/targets/delete", {
                "csrf": self.csrf, "id": str(target["id"])})
        self.assertEqual(code, 400)
        self.assertTrue(any(x["id"] == target["id"]
                            for x in self.server.store.list_targets()))

    def test_live_desktop_requires_login_csrf_and_exclusive_browser(self):
        self.assertEqual(self.req("GET", "/api/remote-frame")[0], 303)
        self.assertEqual(self.req("POST", "/remote/live/start", {"csrf": "bad"})[0], 303)
        self.login()
        code, _, html = self.req("GET", "/remote")
        self.assertEqual(code, 200)
        self.assertIn("Liveansicht starten", html)
        self.assertEqual(self.req("POST", "/remote/live/start",
                          {"csrf": "bad"})[0], 403)
        self.assertEqual(self.req("POST", "/remote/live/start",
                          {"csrf": self.csrf})[0], 303)
        self.assertEqual(self.req("GET", "/remote")[0], 200)
        self.assertIn("remote-live-frame", self.req("GET", "/remote")[2])
        # Image response is refused until the physical kiosk has written a fresh frame.
        self.assertEqual(self.req("GET", "/api/remote-frame")[0], 503)
        self.assertEqual(self.req("POST", "/remote/live/input",
                          {"csrf": self.csrf, "kind": "click",
                           "x": "501", "y": "250"})[0], 200)
        self.assertEqual(self.server.remote_live.take()["kind"], "click")
        self.assertEqual(self.req("POST", "/remote/live/input",
                          {"csrf": self.csrf, "kind": "key",
                           "key_name": "Control_L"})[0], 400)
        self.assertEqual(self.req("POST", "/remote/live/ping",
                          {"csrf": self.csrf})[0], 200)
        self.assertEqual(self.req("POST", "/remote/live/stop",
                          {"csrf": self.csrf})[0], 303)
        self.assertEqual(self.req("GET", "/api/remote-frame")[0], 403)
        self.assertEqual(self.req("POST", "/remote/live/input",
                          {"csrf": self.csrf, "kind": "key",
                           "key_name": "Return"})[0], 400)

    def test_authenticated_remote_actions_and_csrf(self):
        self.assertEqual(self.req("GET", "/remote")[0], 303)
        self.assertEqual(self.req("GET", "/api/remote-status")[0], 303)
        self.login()
        code, _, html = self.req("GET", "/remote")
        self.assertEqual(code, 200)
        self.assertIn("Scanner fernsteuern", html)
        self.assertIn('action="/remote/profile"', html)
        self.assertEqual(self.req("POST", "/remote/profile",
                         {"csrf": "invalid", "name": "Dokument"})[0], 403)
        self.assertEqual(self.req("POST", "/remote/profile",
                         {"csrf": self.csrf, "name": "Dokument"})[0], 303)
        self.assertIn("csrf", html)
        self.assertIn("/assets/remote.js", html)
        code, _, script = self.req("GET", "/assets/remote.js")
        self.assertEqual(code, 200)
        self.assertIn("confirm(", script)
        self.assertEqual(self.req("POST", "/remote/command",
                         {"csrf": "wrong", "action": "scan"})[0], 403)
        self.assertEqual(self.req("POST", "/remote/command",
                         {"csrf": self.csrf, "action": "systemctl"})[0], 400)
        self.assertEqual(self.req("POST", "/remote/command",
                         {"csrf": self.csrf, "action": "restart"})[0], 400)
        self.assertEqual(self.req("POST", "/remote/command",
                         {"csrf": self.csrf, "action": "home"})[0], 303)
        self.assertEqual(self.server.remote_commands.latest()["action"], "home")
        self.assertEqual(self.req("POST", "/remote/command",
                         {"csrf": self.csrf, "action": "scan"})[0], 400)
        code, _, body = self.req("GET", "/api/remote-status")
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)["status"], "pending")

    def test_profile_printer_assignment(self):
        self.login()
        self.server.store.save_target({
            "kind": "printer", "name": "OfficePrinter",
            "address": "ipp://192.168.2.20/ipp/print"})
        printer = next(t for t in self.server.store.list_targets()
                       if t["name"] == "OfficePrinter")
        profile = self.server.store.list_profiles()[0][0]["name"]
        code, _, html = self.req("GET", "/profiles")
        self.assertEqual(code, 200)
        self.assertIn("Bevorzugter Drucker", html)
        self.assertEqual(self.req("POST", "/profiles/printer", {
            "csrf": self.csrf, "name": profile,
            "target_id": str(printer["id"])})[0], 303)
        self.assertEqual(self.server.store.get_profile_printer(profile),
                         printer["id"])
        backup = self.server.store.backup()
        self.assertEqual(backup["profile_printers"][profile], "OfficePrinter")
        self.server.store.restore(backup)
        self.assertIsNotNone(self.server.store.get_profile_printer(profile))

    def test_logout_clears_session(self):
        self.login()
        code, hdrs, _ = self.req("POST","/logout",{"csrf":self.csrf})
        self.assertEqual(code,303)
        self.assertIn("Max-Age=0", hdrs["Set-Cookie"])
        self.assertEqual(self.req("GET","/")[0],303)


if __name__ == "__main__":
    unittest.main()
