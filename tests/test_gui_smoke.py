"""Lightweight Tk touchscreen smoke checks under a virtual X display."""
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app import ItomiScan
from itomiscan.core.profiles import ProfileStore


OPTIONS = [
    {"flag": "--source", "section": "Standard", "inactive": False,
     "kind": "enum", "choices": ["ADF Front", "ADF Duplex"],
     "value": "ADF Duplex", "default": "ADF Duplex"},
    {"flag": "--mode", "section": "Standard", "inactive": False,
     "kind": "enum", "choices": ["Color", "Gray", "Lineart"],
     "value": "Color", "default": "Color"},
    {"flag": "--resolution", "section": "Standard", "inactive": False,
     "kind": "number", "choices": [], "value": "200", "default": "200"},
    {"flag": "--brightness", "section": "Enhancement", "inactive": False,
     "kind": "number", "choices": [], "value": "0", "default": "0"},
]


class TouchGuiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = tk.Tk()
        self.addCleanup(self.root.destroy)
        path = Path(self.temp.name) / "profiles.json"
        self.store = ProfileStore(path)
        with patch("app.ProfileStore", return_value=self.store), patch.object(
                ItomiScan, "refresh_ip", lambda _self: None):
            self.app = ItomiScan(
                self.root, initial_device="fujitsu:fi-6110dj:test",
                initial_options=OPTIONS)
        self.root.update_idletasks()

    def test_home_and_detail_toggle(self):
        self.assertTrue(self.app.home.visible)
        self.app.show_scan()
        self.assertFalse(self.app.home.visible)
        self.assertTrue(self.app.scan_view.winfo_manager())
        self.app.show_home()
        self.assertTrue(self.app.home.visible)

    def test_photo_preset_sets_png_and_adf_front(self):
        self.app.select_profile("Foto")
        flags = {opt["flag"]: variable.get() for opt, variable in self.app.fields}
        self.assertEqual(flags["--source"], "ADF Front")
        self.assertEqual(flags["--resolution"], "300")
        self.assertEqual(self.app.format_var.get(), "Bild (PNG)")

    def test_hardware_enter_uses_existing_scan(self):
        calls = []
        self.app.start_scan = lambda: calls.append("scan")
        self.assertEqual(
            self.app.on_front_scan_key(SimpleNamespace(widget=self.root)), "break")
        self.assertEqual(calls, ["scan"])
        self.app.idle_screen.active = True
        self.app.on_front_scan_key(SimpleNamespace(widget=self.root))
        self.assertEqual(calls, ["scan"])

    def test_quick_scan_reuses_profile(self):
        self.app.select_profile("Text")
        calls = []
        self.app.start_scan = lambda: calls.append(self.app.format_var.get())
        self.app.quick_scan()
        self.assertEqual(calls, ["PDF"])
        flags = {opt["flag"]: variable.get() for opt, variable in self.app.fields}
        self.assertEqual(flags["--mode"], "Gray")

    def test_saving_profile_keeps_advanced_settings(self):
        self.app.show_scan()
        flags = {opt["flag"]: variable for opt, variable in self.app.fields}
        flags["--brightness"].set("15")
        with patch("app.simpledialog.askstring", return_value="Rechnungen"):
            self.app.save_profile()
        saved = ProfileStore(self.store.path).current()
        self.assertEqual(saved["name"], "Rechnungen")
        self.assertEqual(saved["settings"]["--brightness"], "15")


if __name__ == "__main__":
    unittest.main()
