"""Regression tests for explicit on-demand discovery in beta 2."""
import unittest
from unittest.mock import Mock, patch

from itomiscan.integrations.discovery import discover_ipp_printers, discover_paperless
from itomiscan.web.delivery_pages import targets_page
from itomiscan.web.printing_pages import printers_page


class DiscoveryTests(unittest.TestCase):
    def test_ipp_discovery_uses_bounded_dns_sd_and_filters_nonlocal(self):
        output = (
            '=;eth0;IPv4;Office printer;_ipps._tcp;local;printer.local;192.168.44.30;631;"rp=ipp/print"\n'
            '=;eth0;IPv4;Loopback;_ipps._tcp;local;local;127.0.0.1;631;"rp=ipp/print"\n'
            '=;eth0;IPv4;Outside;_ipps._tcp;local;outside;8.8.8.8;631;"rp=ipp/print"\n'
            '=;eth0;IPv4;Malicious;_ipps._tcp;local;bad;192.168.44.44;631;"rp=../../admin"\n'
        )
        with patch("itomiscan.integrations.discovery.shutil.which", return_value="/usr/bin/avahi-browse"), \
                patch("itomiscan.integrations.discovery.subprocess.run",
                      side_effect=[Mock(stdout=output), Mock(stdout="")]) as runner:
            found = discover_ipp_printers()
        self.assertIn("ipps://192.168.44.30:631/ipp/print", found)
        self.assertNotIn("ipps://127.0.0.1:631/ipp/print", found)
        self.assertFalse(any("8.8.8.8" in item or "../" in item for item in found))
        self.assertEqual(runner.call_count, 2)
        self.assertTrue(all(call.kwargs["timeout"] == 4 for call in runner.call_args_list))

    def test_missing_avahi_degrades_to_manual_input(self):
        with patch("itomiscan.integrations.discovery.shutil.which", return_value=None):
            self.assertEqual(discover_ipp_printers(), [])
            self.assertEqual(discover_paperless(), [])

    def test_paperless_selection_is_escaped_and_is_not_automatic_save(self):
        html = targets_page([], "csrf-token", {}, discovered=[
            'https://192.168.1.3:8443', 'https://malicious.example/"onmouseover="x'],
            searched=True)
        self.assertIn("Paperless suchen", html)
        self.assertIn("data-select-paperless", html)
        self.assertIn("&quot;onmouseover=&quot;", html)
        self.assertIn('action="/targets/save"', html)
        self.assertIn("Suchtreffer sind nur Vorschläge", html)
        self.assertNotIn('data-select-paperless="https://malicious.example/"onmouseover', html)

    def test_printer_search_results_and_no_results(self):
        html = printers_page([], [], "csrf-token", searched=True,
                             discovered=["ipps://192.168.44.20:631/ipp/print"])
        self.assertIn("Drucker suchen", html)
        self.assertIn("data-select-printer", html)
        self.assertIn("Keine", printers_page([], [], "csrf-token", searched=True,
                                            discovered=[]))
        self.assertIn('action="/printers/save"', html)


if __name__ == "__main__":
    unittest.main()
