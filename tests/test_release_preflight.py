"""Read-only release preflight never claims hardware passed from CI."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from itomiscan.release_preflight import collect, main


class ReleasePreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        (self.home / ".config").mkdir()

    @patch("itomiscan.release_preflight.shutil.which",
           return_value="/usr/bin/fake")
    @patch("itomiscan.release_preflight.execute")
    def test_no_discovery_and_hardware_always_pending(self, execute, _):
        execute.return_value = SimpleNamespace(
            stdout="develop/1.0.0\n", returncode=0)
        result = collect(home=self.home, repo=self.home, discover=False)
        self.assertFalse(result["release_allowed"])
        self.assertTrue(result["physical_acceptance_pending"])
        checklist = {c["name"]: c for c in result["checks"]}
        self.assertFalse(checklist["physical_touch"]["passed"])
        self.assertFalse(checklist["physical_frontkey"]["passed"])
        self.assertFalse(checklist["printing"]["passed"])
        self.assertFalse(checklist["duplex_pdf"]["passed"])
        self.assertFalse(checklist["scanner"]["passed"])
        self.assertEqual(len(execute.call_args_list), 1)

    @patch("itomiscan.release_preflight.shutil.which", return_value=None)
    @patch("itomiscan.release_preflight.execute", return_value=None)
    def test_missing_scan_essentials_are_blocking(self, _run, _which):
        result = collect(home=self.home, repo=self.home, discover=False)
        self.assertIn("dependency_scanimage", result["blocking_errors"])
        self.assertIn("dependency_img2pdf", result["blocking_errors"])
        self.assertFalse(result["release_allowed"])

    def test_read_only_cli_json(self):
        with patch("itomiscan.release_preflight.collect",
                   return_value={"checks": [], "blocking_errors": [],
                                 "physical_acceptance_pending": True,
                                 "release_allowed": False}):
            self.assertEqual(main(["--json", "--no-scanner"]), 0)


if __name__ == "__main__":
    unittest.main()
