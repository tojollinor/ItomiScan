"""Frontend regression contracts and optional JavaScript parser checks."""
import shutil
import subprocess
import unittest

from itomiscan.web import pages


class FrontendContracts(unittest.TestCase):
    def test_vnc_reconnect_ignores_events_from_obsolete_client(self):
        source = pages.VNC_JS
        self.assertIn("const previous = rfb;", source)
        self.assertIn("client === rfb", source)
        self.assertIn("new RFB(screen, url", source)
        self.assertIn("'/remote/vnc/ws'", source)
        self.assertNotIn("URL.createObjectURL", source)

    def test_chart_reloads_history_after_background_and_shows_gaps(self):
        script = pages.STATUS_JS
        self.assertIn("'/api/metrics/history'", script)
        self.assertIn("visibilitychange", script)
        self.assertIn("loadHistory().then(refresh)", script)
        self.assertIn("samples.length = 0", script)
        self.assertIn("'L' : 'M'", script)
        self.assertIn("data-monitor-line", script)

    def test_no_external_script_or_metrics_persistence_in_frontend(self):
        scripts = pages.VNC_JS + pages.STATUS_JS
        self.assertNotIn("localStorage", scripts)
        self.assertNotIn("sessionStorage", scripts)
        self.assertNotIn("indexedDB", scripts)
        self.assertIn("'/novnc/core/rfb.js'", pages.VNC_JS)
        self.assertIn("credentials:'same-origin'", pages.VNC_JS)
        self.assertIn("credentials:'same-origin'", pages.STATUS_JS)

    @unittest.skipUnless(shutil.which("node"), "Node.js JavaScript parser unavailable")
    def test_critical_browser_scripts_parse_as_modules(self):
        for name, script in (
            ("remote_vnc", pages.VNC_JS),
            ("metrics", pages.STATUS_JS),
            ("old_remote_compat", pages.REMOTE_JS),
        ):
            with self.subTest(asset=name):
                result = subprocess.run(
                    ["node", "--input-type=module", "--check"],
                    input=script, text=True, capture_output=True, timeout=15,
                    check=False)
                self.assertEqual(
                    result.returncode, 0,
                    name + " is not valid JavaScript: " + result.stderr[-1200:])


if __name__ == "__main__":
    unittest.main()
