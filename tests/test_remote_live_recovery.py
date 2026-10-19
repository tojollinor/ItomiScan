"""Regression tests for browser live-session recovery and security guards."""
import re
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import urlencode
import http.client

from itomiscan.storage.config import ConfigStore
from itomiscan.storage.remote_live import viewer_id
from itomiscan.web.server import build_server


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        db = Path(self.tmp.name) / "itomiscan.db"
        ConfigStore(db).set_password("StrongTestPassword_2026!")
        self.server = build_server("127.0.0.1", 0, db_path=db)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.thread.join, 3)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.server.vnc.start = lambda owner: "test-vnc-password"
        self.server.vnc.password = lambda owner: (
            "test-vnc-password" if self.server.remote_live.authorized(owner) else None)
        self.cookie = ""
        self.csrf = ""

    def request(self, method, path, fields=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        headers = {"Host": "127.0.0.1:%s" % self.server.server_port}
        if self.cookie:
            headers["Cookie"] = self.cookie
        body = None
        if fields is not None:
            body = urlencode(fields)
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        conn.request(method, path, body=body, headers=headers)
        resp = conn.getresponse()
        result = resp.status, dict(resp.getheaders()), resp.read().decode("utf-8", "replace")
        conn.close()
        return result

    def login(self):
        status, headers, _ = self.request("POST", "/login",
                                          {"password": "StrongTestPassword_2026!"})
        self.assertEqual(status, 303)
        self.cookie = headers["Set-Cookie"].split(";", 1)[0]
        html = self.request("GET", "/remote")[2]
        self.csrf = re.search(r'name="csrf" value="([^"]+)"', html).group(1)

    def test_recovery_requires_web_session_and_csrf(self):
        self.assertEqual(self.request("POST", "/remote/live/reconnect",
                                      {"csrf": "x"})[0], 303)
        self.login()
        self.assertEqual(self.request("POST", "/remote/live/reconnect",
                                      {"csrf": "wrong"})[0], 403)
        self.assertEqual(self.request("POST", "/remote/live/reconnect",
                                      {"csrf": self.csrf})[0], 200)
        self.assertIn("Wiederherstellen", self.request("GET", "/remote")[2])
        self.assertIn("remote-live-placeholder", self.request("GET", "/remote")[2])

    def test_recovery_exclusive_lease_and_refresh(self):
        self.login()
        owner = viewer_id(self.cookie.split("=", 1)[1])
        state = self.server.remote_live
        state.start(owner)
        with state._db() as db:
            db.execute("UPDATE remote_live SET until_time=0")
        self.assertFalse(state.authorized(owner))
        self.assertEqual(self.request("POST", "/remote/live/reconnect",
                                      {"csrf": self.csrf})[0], 200)
        self.assertTrue(state.authorized(owner))
        other = viewer_id("another-browser")
        with state._db() as db:
            db.execute("UPDATE remote_live SET owner=?", (other,))
        status, _, text = self.request("POST", "/remote/live/reconnect",
                                       {"csrf": self.csrf})
        self.assertEqual(status, 409)
        self.assertIn("anderen Browser", text)
        self.assertTrue(state.authorized(other))

    def test_recovery_script_includes_states(self):
        self.login()
        status, _, script = self.request("GET", "/assets/vnc.js")
        self.assertEqual(status, 200)
        for snippet in ("'/remote/live/reconnect'", "'/remote/vnc/ws'",
                        "Wiederherstellen", "response.redirected",
                        "rfb.disconnect()", "keepAlive"):
            self.assertIn(snippet, script)


if __name__ == "__main__":
    unittest.main()
