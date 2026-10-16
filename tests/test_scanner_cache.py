"""Offline cache safety and asynchronous kiosk scanner readiness tests."""
import json
import tempfile
import unittest
from pathlib import Path

from itomiscan.core.scanner_cache import read_cache, write_cache


OPTIONS = [{"flag": "--resolution", "section": "Standard",
            "inactive": False, "kind": "number", "choices": [],
            "value": "200", "default": "200"}]


class ScannerCacheTests(unittest.TestCase):
    def test_round_trip_is_capabilities_only(self):
        with tempfile.TemporaryDirectory() as root:
            cache = Path(root) / "options.json"
            self.assertTrue(write_cache("fujitsu:fi-6110dj:test", OPTIONS, cache))
            self.assertEqual(read_cache(cache),
                             ("fujitsu:fi-6110dj:test", OPTIONS))
            raw = json.loads(cache.read_text())
            self.assertNotIn("ready", raw)
            self.assertEqual(raw["version"], 1)

    def test_invalid_device_and_malformed_cache_are_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            cache = Path(root) / "options.json"
            self.assertFalse(write_cache("other:usb", OPTIONS, cache))
            self.assertIsNone(read_cache(cache))
            cache.write_text('{"version":1,"device":"fujitsu:fake",'
                             '"options":[{"flag":"--foo"}]}')
            self.assertIsNone(read_cache(cache))

    def test_oversized_cache_is_ignored(self):
        with tempfile.TemporaryDirectory() as root:
            cache = Path(root) / "options.json"
            cache.write_bytes(b"x" * (97 * 1024))
            self.assertIsNone(read_cache(cache))


if __name__ == "__main__":
    unittest.main()
