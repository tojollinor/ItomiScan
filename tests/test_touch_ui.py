"""Targeted N1800 touch layout and navigation checks under virtual X11."""
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from app import ItomiScan
from itomiscan.core.profiles import ProfileStore
from itomiscan.gui.keyboard import ask_touch


OPTIONS = [
    {"flag": "--source", "section": "Standard", "inactive": False,
     "kind": "enum", "choices": ["ADF Front", "ADF Duplex"],
     "value": "ADF Duplex", "default": "ADF Duplex"},
    {"flag": "--mode", "section": "Standard", "inactive": False,
     "kind": "enum", "choices": ["Color", "Gray"], "value": "Color",
     "default": "Color"},
    {"flag": "--resolution", "section": "Standard", "inactive": False,
     "kind": "number", "choices": [], "value": "200", "default": "200"},
]


class TouchLayoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = tk.Tk()
        self.root.geometry("1024x768+0+0")
        self.addCleanup(self.root.destroy)
        store = ProfileStore(Path(self.temp.name) / "scan.db")
        with patch("app.ProfileStore", return_value=store), patch.object(
                ItomiScan, "refresh_ip", lambda self: None):
            self.app = ItomiScan(
                self.root, initial_device="fujitsu:fi-6110dj:test",
                initial_options=OPTIONS)
        self.root.update_idletasks()

    def test_primary_buttons_match_destination_grid_and_home_symbol_is_large(self):
        home = self.app.home
        self.assertEqual(str(self.root["cursor"]), "none")
        self.assertEqual(len(home.tiles), 2)
        self.assertGreaterEqual(home.tiles["scan"].winfo_height(), 160)
        self.assertGreaterEqual(home.tiles["copy"].winfo_height(), 160)
        self.assertGreaterEqual(int(self.app.home_button["font"].split()[-2]), 24)

    def test_menu_is_a_page_from_both_views_and_saver_can_be_previewed(self):
        self.app.home.controls["menu"].invoke()
        self.assertTrue(self.app.device_menu.visible)
        self.assertIn("Bildschirmschoner anzeigen",
                      self.app.device_menu.buttons)
        self.app.device_menu.buttons["Bildschirmschoner anzeigen"].invoke()
        self.assertFalse(self.app.device_menu.visible)
        self.assertTrue(self.app.idle_screen.active)
        self.app.idle_screen.wake()
        self.app.show_scan()
        self.app.show_device_menu()
        self.assertTrue(self.app.device_menu.visible)
        self.app.device_menu.hide()
        self.assertTrue(self.app.scan_view.winfo_manager())

    def test_screensaver_manual_activation_is_blocked_while_scanning(self):
        self.app.busy = True
        self.assertFalse(self.app.idle_screen.show_now())
        self.assertFalse(self.app.idle_screen.active)

    def test_pin_keypad_sits_below_midline(self):
        pin = self.app.pin_screen
        pin.show()
        self.root.update_idletasks()
        keypad = pin.frame.grid_slaves(row=3, column=0)[0]
        self.assertGreaterEqual(
            keypad.winfo_rooty(),
            self.root.winfo_rooty() + self.root.winfo_height() // 2)
        pin.hide()

    def test_keyboard_windows_fit_bottom_half(self):
        for numeric in (False, True):
            dimensions = []

            def inspect_and_close():
                windows = [w for w in self.root.winfo_children()
                           if isinstance(w, tk.Toplevel)]
                if windows:
                    win = windows[-1]
                    dimensions.append((win.winfo_y(), win.winfo_height()))
                    win.destroy()
            self.root.after(60, inspect_and_close)
            with self.subTest(numeric=numeric):
                ask_touch(self.root, "Eingabe", numeric=numeric)
                self.assertTrue(dimensions)
                y, height = dimensions[0]
                self.assertLessEqual(height, self.root.winfo_screenheight() // 2)
                self.assertGreaterEqual(y, self.root.winfo_screenheight() // 2)


if __name__ == "__main__":
    unittest.main()
