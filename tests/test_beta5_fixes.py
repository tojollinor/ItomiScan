"""Regression tests for the beta 5 fixes (no scanner hardware required)."""
import unittest
from pathlib import Path
from unittest.mock import patch

from itomiscan.web import pages, server, vnc_bridge


class Beta5Regressions(unittest.TestCase):
    def test_disk_occupancy_is_not_rendered_twice(self):
        html = pages.overview(
            {"disk": "2 GiB / 57 GiB", "disk_free": "55 GiB"},
            {"profiles": 0, "targets": 0}, "csrf")
        self.assertEqual(html.count("<h2>Datenträgerbelegung</h2>"), 1)
        self.assertNotIn("<h2>Datenträger</h2>", html)
        self.assertNotIn("<h2>Freier Speicherplatz</h2>", html)
        self.assertIn("data-disk-progress", html)

    def test_partially_constructed_server_can_close_cleanly(self):
        instance = server.AdminServer.__new__(server.AdminServer)
        with patch.object(server.ThreadingHTTPServer, "server_close") as close:
            instance.server_close()
        close.assert_called_once()

    def test_x11_authentication_is_explicit_in_vnc_launch(self):
        bridge = vnc_bridge.VNCBridge.__new__(vnc_bridge.VNCBridge)
        import threading
        from unittest.mock import Mock
        bridge.live = Mock()
        bridge._lock = threading.RLock()
        bridge._process = None
        bridge._owner = None
        bridge._password = None
        bridge._private = None
        bridge._port = None
        process = Mock()
        process.poll.return_value = None
        with patch.object(bridge, "ready", return_value=True), \
             patch.object(vnc_bridge.shutil, "which", return_value="/usr/bin/x11vnc"), \
             patch.object(vnc_bridge.subprocess, "Popen", return_value=process) as popen, \
             patch.object(vnc_bridge.time, "sleep"):
            bridge.start("a" * 64)
            argv = popen.call_args.args[0]
            self.assertEqual(argv[argv.index("-auth") + 1],
                             str(Path.home() / ".Xauthority"))
            self.assertIn("-localhost", argv)
            bridge.stop("a" * 64)


if __name__ == "__main__":
    unittest.main()
