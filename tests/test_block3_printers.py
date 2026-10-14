"""Block 3 protocol validation regression checks (run with python -m unittest)."""
import unittest

from itomiscan.integrations.printing import PrintError, printer_uri


class PrinterProtocolTests(unittest.TestCase):
    def test_supported_protocols(self):
        for uri in (
            "ipp://printer.local/ipp/print",
            "ipps://printer.local/ipp/print",
            "socket://192.168.1.20:9100",
            "lpd://printer.local/queue",
            "usb://Brother/Printer",
        ):
            with self.subTest(uri=uri):
                self.assertEqual(printer_uri(uri), uri)

    def test_reject_credentials_and_unsupported_schemes(self):
        for uri in (
            "http://printer.local",
            "socket://user:password@printer.local:9100",
            "ipp://printer.local/print?token=secret",
            "file:///etc/passwd",
            "socket://printer.local:99999",
            "socket://printer.local/a b",
        ):
            with self.subTest(uri=uri):
                with self.assertRaises(PrintError):
                    printer_uri(uri)


if __name__ == "__main__":
    unittest.main()
