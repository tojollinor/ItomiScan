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
        path = Path(self.temp.name) / "itomiscan.db"
        self.store = ProfileStore(path)
        with patch("app.ProfileStore", return_value=self.store), patch.object(
                ItomiScan, "refresh_ip", lambda _self: None):
            self.app = ItomiScan(
                self.root, initial_device="fujitsu:fi-6110dj:test",
                initial_options=OPTIONS)
        self.root.update_idletasks()

    def enable_pin(self, *, permissions=("scan",), profiles=("Foto",)):
        user_id = self.app.users.save_user(
            name="Testkonto", pin="2580", permissions=list(permissions),
            assigned_profiles=list(profiles), default_profile=profiles[0],
            active=True)
        self.app.users.configure(enabled=True, timeout_minutes=1)
        self.app.auth_tick()
        return user_id

    def unlock(self):
        for digit in "2580":
            self.app.pin_screen.press(digit)
        self.app.pin_screen.press("OK")

    def test_pin_blocks_scanning_before_login(self):
        calls = []
        self.app.start_scan = lambda: calls.append("scan")
        self.enable_pin()
        self.assertTrue(self.app.pin_screen.active)
        self.assertFalse(self.app.home.visible)
        self.assertEqual(
            self.app.on_front_scan_key(SimpleNamespace(widget=self.root)), "break")
        self.assertEqual(calls, [])
        self.unlock()
        self.assertFalse(self.app.pin_screen.active)
        self.assertTrue(self.app.home.visible)
        self.app.on_front_scan_key(SimpleNamespace(widget=self.root))
        self.assertEqual(calls, ["scan"])
        self.assertEqual(self.app.home.selected_var.get(), "Foto")

    def test_restricted_features_hidden_and_denied_by_backend(self):
        self.enable_pin(permissions=("copy",))
        self.unlock()
        self.assertEqual(self.app.home.tiles["scan"].winfo_manager(), "")
        self.assertEqual(self.app.home.tiles["paperless"].winfo_manager(), "")
        self.assertNotEqual(self.app.home.tiles["copy"].winfo_manager(), "")
        self.assertEqual(self.app.home.controls["shutdown"].winfo_manager(), "")
        self.assertEqual(self.app.home.controls["update"].winfo_manager(), "")
        with patch("app.messagebox.showwarning"):
            self.app.start_scan()
            self.app.show_scan()
            self.app.check_update()
            self.app.shutdown()
        self.assertFalse(self.app.busy)
        self.assertFalse(self.app.scan_view.winfo_manager())

    def test_personal_profile_and_logout_by_inactivity(self):
        self.enable_pin(permissions=("scan",), profiles=("Foto",))
        self.unlock()
        self.assertEqual(self.app.home.selected_var.get(), "Foto")
        self.assertEqual(self.app.format_var.get(), "Bild (PNG)")
        self.assertEqual(self.app.profile_store.db.list_profiles()[1], "Dokument")
        self.app.last_activity -= 85
        self.app.auth_tick()
        self.assertTrue(self.app.pin_screen.active)
        self.assertFalse(self.app.home.visible)
        self.assertIsNone(self.app.current_user)
        self.assertEqual(self.app.pages, [])

    def test_web_disabling_pin_login_shows_public_home(self):
        self.enable_pin()
        self.assertTrue(self.app.pin_screen.active)
        self.app.users.configure(enabled=False)
        self.app.auth_tick()
        self.assertFalse(self.app.pin_screen.active)
        self.assertTrue(self.app.home.visible)

    def test_network_target_enqueues_selected_delivery_intent(self):
        self.app.delivery_queue.db.save_target({
            "kind":"usb", "name":"ScanStick", "address":"usb://SCANUSB/Scans"})
        target = next(t for t in self.app.delivery_queue.db.list_targets()
                      if t["kind"]=="usb")
        calls = []
        def fake_scan():
            calls.append(self.app.pending_delivery)
            self.app.busy = True
        self.app.start_scan = fake_scan
        self.app.start_target_scan(target["id"])
        self.assertEqual(calls, [target["id"]])
        self.assertEqual(self.app._delivery_permission(), "usb")
        self.assertTrue(self.app.busy)

    def test_account_with_usb_right_cannot_start_local_scan(self):
        self.enable_pin(permissions=("usb",), profiles=("Dokument",))
        self.unlock()
        self.assertFalse(self.app._allowed("scan", silent=True))
        self.assertTrue(self.app._allowed("usb", silent=True))
        self.assertFalse(self.app.home.tiles["scan"].winfo_manager())
        self.assertTrue(self.app.home.controls["other"].winfo_manager())

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
