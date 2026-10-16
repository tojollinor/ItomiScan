"""Remote command queue and optional LAN discovery regression tests."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

from itomiscan.storage.remote_commands import RemoteCommands
from itomiscan.integrations.discovery import discover_paperless


class RemoteCommandsTests(unittest.TestCase):
    def test_one_pending_command_consumed_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            commands = RemoteCommands(Path(tmp) / "itomiscan.db")
            ident = commands.request("scan")
            self.assertEqual(commands.latest()["status"], "pending")
            with self.assertRaises(ValueError):
                commands.request("home")
            item = commands.take()
            self.assertEqual(item["id"], ident)
            self.assertIsNone(commands.take())
            commands.finish(ident, "done", "Kiosk hat Befehl übernommen.")
            self.assertEqual(commands.latest()["status"], "done")
            self.assertEqual(commands.request("home"), ident + 1)

    def test_stale_command_and_unknown_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            now = [100.]
            commands = RemoteCommands(Path(tmp) / "db.sqlite", clock=lambda: now[0])
            with self.assertRaises(ValueError):
                commands.request("shell")
            commands.request("restart")
            now[0] += 31
            self.assertIsNone(commands.take())
            self.assertEqual(commands.latest()["status"], "expired")
            commands.request("home")


class DiscoveryTests(unittest.TestCase):
    @patch("itomiscan.integrations.discovery.shutil.which", return_value=None)
    def test_optional_tool_unavailable(self, _which):
        self.assertEqual(discover_paperless(), [])

    @patch("itomiscan.integrations.discovery.shutil.which", return_value="/usr/bin/avahi-browse")
    @patch("itomiscan.integrations.discovery.subprocess.run")
    def test_only_private_named_https_candidates(self, run, _which):
        run.return_value = Mock(stdout=(
            "=;eth0;IPv4;Paperless Office;_https._tcp;local;paperless.local;192.168.2.8;443;\n"
            "=;eth0;IPv4;Other Web;_https._tcp;local;other.local;192.168.2.9;443;\n"
            "=;eth0;IPv4;Paperless Public;_https._tcp;local;public.local;8.8.8.8;443;\n"
        ))
        self.assertEqual(discover_paperless(), ["https://192.168.2.8"])


if __name__ == "__main__":
    unittest.main()
