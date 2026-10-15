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
        self.assertNotEqual(self.app.home.tiles["copy"].winfo_manager(), "")
        self.assertEqual(self.app.home.controls["shutdown"].winfo_manager(), "")
        self.app.show_device_menu()
        self.assertNotIn("Updates", self.app.device_menu.buttons)
        self.assertNotIn("Neustarten", self.app.device_menu.buttons)
        self.assertNotIn("Ausschalten", self.app.device_menu.buttons)
        self.app.device_menu.hide()
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
        # The single scan entry opens the destination chooser, where USB
        # appears even without the permission for direct local scanning.
        self.assertTrue(self.app.home.tiles["scan"].winfo_manager())
        self.app.home.show_destinations()
        self.assertTrue(self.app.home.destination_page.winfo_manager())
        self.app.home.close_destinations()

    def add_printer(self):
        self.app.delivery_queue.db.save_target({
            "kind": "printer", "name": "OfficeLaser",
            "address": "ipps://printer.lan/ipp/print"})
        return next(x for x in self.app.delivery_queue.db.list_targets()
                    if x["kind"] == "printer")

    def test_copy_screen_large_touch_controls(self):
        target = self.add_printer()
        with patch("app.list_queues", return_value=["OfficeLaser"]):
            self.app.show_copy()
        self.assertTrue(self.app.copy_screen.visible)
        self.assertEqual(self.app.copy_screen.selected_id, target["id"])
        self.app.copy_screen._step(2)
        self.app.copy_screen._print_sides("two-sided-long-edge")
        self.app.copy_screen._switch_source()
        self.assertEqual(self.app.copy_screen.copies, 3)
        self.assertEqual(self.app.copy_screen.print_sides, "two-sided-long-edge")
        self.assertEqual(self.app.copy_screen.scan_source, "ADF Duplex")
        started = []
        def scan_started():
            started.append(dict(self.app.pending_print))
            self.app.busy = True
        with patch.object(self.app, "start_scan", side_effect=scan_started), \
             patch("app.list_queues", return_value=["OfficeLaser"]):
            self.app.copy_screen.start()
        self.assertEqual(started[0]["target_id"], target["id"])
        self.assertEqual(started[0]["copies"], 3)
        self.assertEqual(started[0]["scan_source"], "ADF Duplex")
        self.assertEqual(self.app._delivery_permission(), "copy")
        self.assertFalse(self.app.copy_screen.visible)

    def test_front_panel_key_uses_selected_copy_mode(self):
        self.add_printer()
        with patch("app.list_queues", return_value=["OfficeLaser"]):
            self.app.show_copy()
        with patch.object(self.app.copy_screen, "start") as copier:
            self.assertEqual(
                self.app.on_front_scan_key(SimpleNamespace(widget=self.root)),
                "break")
        copier.assert_called_once()

    def test_copy_without_cups_queue_is_not_started(self):
        self.add_printer()
        with patch("app.list_queues", return_value=[]):
            self.app.show_copy()
        self.assertIsNone(self.app.copy_screen.selected_id)
        self.assertEqual(str(self.app.copy_screen.start_button["state"]),
                         "disabled")
        self.assertFalse(self.app.busy)

    def test_copy_only_pin_user_has_access_without_scan_privilege(self):
        target = self.add_printer()
        self.enable_pin(permissions=("copy",), profiles=("Foto",))
        self.unlock()
        self.assertFalse(self.app._allowed("scan", silent=True))
        self.assertTrue(self.app._allowed("copy", silent=True))
        with patch("app.list_queues", return_value=["OfficeLaser"]):
            self.app.show_copy()
        self.assertTrue(self.app.copy_screen.visible)
        def fake_thread():
            return SimpleNamespace(start=lambda: None)
        with patch("app.list_queues", return_value=["OfficeLaser"]), \
             patch("app.threading.Thread", return_value=fake_thread()):
            self.app.start_copy(target["id"], 2, "one-sided", "ADF Front")
        self.assertTrue(self.app.busy)
        self.assertEqual(self.app._delivery_permission(), "copy")
        self.assertEqual(self.app.format_var.get(), "PDF")
        self.assertEqual(next(var.get() for opt, var in self.app.fields
                              if opt["flag"] == "--source"), "ADF Front")
        if self.app.tempdir:
            self.app.tempdir.cleanup()
            self.app.tempdir = None

    def test_low_disk_blocks_scan(self):
        from types import SimpleNamespace
        with patch("app.shutil.disk_usage",
                   return_value=SimpleNamespace(free=1000000)):
            with patch("app.messagebox.showwarning") as warning:
                self.app.start_scan()
        self.assertFalse(self.app.busy)
        warning.assert_called_once()

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
