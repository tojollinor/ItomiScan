#!/usr/bin/env python3
"""ItomiScan: lightweight local SANE touchscreen frontend (Debian 12/i386)."""
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from itomiscan.core.profiles import ProfileError, ProfileStore
from itomiscan.gui.keyboard import ask_touch
from itomiscan.gui.scanner_errors import show_scanner_error, classify_scanner_error
from itomiscan.gui.home import HomeScreen, draw_logo, set_logo_busy
from itomiscan.gui.copy import CopyScreen
from itomiscan.integrations.printing import list_queues, validate_copy_options, PrintError
from itomiscan.gui.pin import PinScreen
from itomiscan.gui.screensaver import IdleScreen
from itomiscan.storage.users import UserStore
from itomiscan.storage.queue import DeliveryQueue

from PIL import Image, ImageTk

DEVICE_PREFIX = "fujitsu:"
REPO = "https://github.com/tojollinor/ItomiScan.git"
BASE = "#101927"
PANEL = "#192738"
FG = "#f1f5fb"
MUTED = "#a8bacd"
BLUE = "#397edb"
GREEN = "#52c39b"
FONT = ("DejaVu Sans", 11)
LABELS = {
    "--source": "Einzug / Seiten", "--mode": "Farbmodus",
    "--resolution": "Auflösung (DPI)", "--page-width": "Papierbreite (mm)",
    "--page-height": "Papierhöhe (mm)", "-l": "Scanbereich links",
    "-t": "Scanbereich oben", "-x": "Scanbereich Breite",
    "-y": "Scanbereich Höhe", "--brightness": "Helligkeit",
    "--contrast": "Kontrast", "--threshold": "Schwellwert",
    "--rif": "Bild invertieren", "--ht-type": "Rastertyp",
    "--ht-pattern": "Rastermuster", "--emphasis": "Bildschärfung",
    "--variance": "SDTC-Varianz", "--ald": "Papier-Enderkennung",
    "--df-action": "Bei Doppeleinzug", "--df-skew": "Doppeleinzug: Schieflage",
    "--df-thickness": "Doppeleinzug: Stärke",
    "--df-length": "Doppeleinzug: Länge", "--df-diff": "Längendifferenz",
    "--dropoutcolor": "Farbunterdrückung", "--buffermode": "Interner Puffermodus",
    "--overscan": "Über den Rand scannen", "--sleeptimer": "Ruhemodus (Min.)",
    "--lowmemory": "Speichersparmodus", "--swdeskew": "Geraderücken",
    "--swdespeck": "Punkte entfernen", "--swcrop": "Rand entfernen",
    "--swskip": "Leere Seiten überspringen (%)",
}
SECTION_NAMES = {"Standard": "Grundfunktionen", "Geometry": "Papier & Scanbereich",
                 "Enhancement": "Bildoptimierung", "Advanced": "Erweitert",
                 "Sensors": "Sensoren"}


def shell(args, timeout=25, **kwargs):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, **kwargs)


def find_device(timeout=25):
    result = shell(["scanimage", "-L"], timeout=timeout)
    match = re.findall(r"device \x60([^\x27]+)\x27", result.stdout + result.stderr)
    return next((item for item in match if item.startswith(DEVICE_PREFIX)), None)


def read_options(device, timeout=25):
    result = shell(["scanimage", "-d", device, "--help"], timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip())
    section = None
    items = []
    pattern = re.compile(r"^\s{2,}(--[a-z][a-z0-9-]*|-[ltxy])(\[=\(yes\|no\)\])?\s*(.*)$")
    for line in result.stdout.splitlines():
        msec = re.match(r"^\s{2}([A-Za-z]+):\s*$", line)
        if msec:
            section = msec.group(1)
            continue
        if section not in SECTION_NAMES:
            continue
        match = pattern.match(line)
        if not match:
            continue
        flag, check, rest = match.groups()
        if flag not in LABELS:
            continue
        brackets = re.findall(r"\[([^\]]+)\]", rest)
        inactive = "inactive" in brackets
        defaults = [b for b in brackets if b not in ("inactive", "advanced")]
        default = defaults[0] if defaults else ""
        raw = rest.split("[", 1)[0].strip()
        if check:
            kind, choices = "bool", ["no", "yes"]
            default = default or "no"
        elif "|" in raw:
            kind, choices = "enum", [v.strip() for v in raw.split("|")]
        elif re.search(r"-?\d+(?:\.\d+)?\.\.-?\d+", raw):
            kind, choices = "number", []
        else:
            kind, choices = "text", []
        if flag == "--source" and "ADF Duplex" in choices and not inactive:
            value = "ADF Duplex"
        elif flag == "--mode" and "Color" in choices and not inactive:
            value = "Color"
        elif flag == "--resolution" and not inactive:
            value = "200"
        else:
            value = default or (choices[0] if choices else "")
        items.append({"flag": flag, "section": section, "inactive": inactive,
                      "kind": kind, "choices": choices, "default": default, "value": value})
    if not items:
        raise RuntimeError("Keine SANE-Geräteoptionen gefunden.")
    return items


class ItomiScan:
    def __init__(self, root, initial_device=None, initial_options=None):
        self.root = root
        self.root.title("ItomiScan")
        self.root.configure(bg=BASE)
        # Without a window manager Tk's -fullscreen hint may be ignored.
        # Size the kiosk window explicitly to the Xorg screen instead.
        self.root.overrideredirect(True)
        self.root.geometry(f"{self.root.winfo_screenwidth()}x{self.root.winfo_screenheight()}+0+0")
        self.root.bind("<Escape>", lambda e: None)
        self.busy = False
        self.device = initial_device
        self.options = list(initial_options or [])
        self.fields = []
        self.pending_delivery = None
        self.pending_export_path = None
        self.pending_print = None
        self.pages = []
        self.review_pending = False
        self.appending_pages = False
        self.batch_settings = None
        self.page_index = 0
        self.photo = None
        self.thumbnail_photos = []
        self.tempdir = None
        self.output_path = None
        self.preview_size = (570, 470)
        self.status_var = tk.StringVar(value="Scanner wird gesucht …")
        self.ip_var = tk.StringVar(value="IP wird ermittelt …")
        self.page_var = tk.StringVar(value="Keine Vorschau")
        self.format_var = tk.StringVar(value="PDF")
        self.profile_store = ProfileStore()
        self.users = UserStore(self.profile_store.path)
        self.delivery_queue = DeliveryQueue(self.profile_store.path)
        self.current_user = None
        self.session_profile = None
        self.last_activity = time.monotonic()
        self.pin_screen = None
        self.login_enabled = self.users.settings()["enabled"]
        if self.profile_store.warning:
            self.status_var.set(self.profile_store.warning)
        self.home = None
        self.idle_screen = None
        self.scan_view = tk.Frame(self.root, bg=BASE)
        self.scan_view.place(x=0, y=0, relwidth=1, relheight=1)
        self._style()
        self._layout()
        # The N1800 front-panel button is a separate USB HID keyboard.
        # Bind its likely Enter/KP-Enter key to the normal scan action.
        # Verify the actual keycode on the device before claiming support.
        self.root.bind_all("<Return>", self.on_front_scan_key, add="+")
        self.root.bind_all("<KP_Enter>", self.on_front_scan_key, add="+")
        # Without a window manager, give the kiosk keyboard focus explicitly.
        self.root.after(500, self.root.focus_force)
        if self.device and self.options:
            # Reuse SANE options from the splash's background readiness probe.
            self.render_options()
            self.apply_profile(self.profile_store.current())
            self.status_var.set("Bereit")
        else:
            # Preserve the original behavior for direct app.py invocations.
            self.root.after(200, self.load_scanner)
        self.home = HomeScreen(
            self.root, self.profile_store, self.select_profile,
            self.show_scan, self.quick_scan, self.unavailable,
            self.shutdown, self.check_update, self.exit, self.status_var,
            logout=self.logout, deliver=self.choose_destination,
            open_copy=self.show_copy,
        )
        self.copy_screen = CopyScreen(self.root, self.available_printers,
                                      self.start_copy, self.show_home)
        self.pin_screen = PinScreen(self.root, self.verify_pin)
        self.root.bind_all("<ButtonPress>", self.record_activity, add="+")
        self.root.bind_all("<KeyPress>", self.record_activity, add="+")
        idle_minutes = self.profile_store.db.get_settings().get("screensaver_minutes", 5) if self.profile_store.db else 5
        self.idle_screen = IdleScreen(
            self.root, lambda: self.busy or self.pin_screen.active,
            seconds=idle_minutes * 60)
        if self.login_enabled:
            self.show_login()
        elif self.device and self.options:
            self.show_home()
        self.root.after(250, self.refresh_ip)
        self.root.after(2000, self.auth_tick)
        self.root.after(6000, self.delivery_tick)
        self.root.after(300, self._refresh_busy_logos)

    def _refresh_busy_logos(self):
        """Small kiosk-safe status watcher; animates no frames while idle."""
        try:
            active = bool(self.busy)
            set_logo_busy(self.scan_logo, active)
            if self.home:
                set_logo_busy(self.home.logo, active)
            self.root.after(300, self._refresh_busy_logos)
        except tk.TclError:
            pass

    def _style(self):
        theme = ttk.Style(self.root)
        theme.theme_use("clam")
        theme.configure(".", font=FONT, background=PANEL, foreground=FG)
        theme.configure("TFrame", background=PANEL)
        theme.configure("TLabel", background=PANEL, foreground=FG, font=FONT)
        theme.configure("TCombobox", font=FONT, padding=8,
                        fieldbackground="#f8fafc", foreground="#142033")
        theme.configure("TEntry", padding=7, fieldbackground="#f8fafc", foreground="#142033")
        theme.configure("TScrollbar", background="#57718b", troughcolor=PANEL)
        theme.configure("TProgressbar", troughcolor=PANEL, background=BLUE)

    def _btn(self, parent, title, command, color=PANEL, width=None):
        return tk.Button(parent, text=title, command=command, font=("DejaVu Sans", 12, "bold"),
                         bg=color, fg=FG, activebackground=BLUE, activeforeground=FG,
                         relief="flat", bd=0, padx=15, pady=15,
                         cursor="hand2", width=width)

    def _layout(self):
        header = tk.Frame(self.scan_view, bg=BASE, height=62)
        header.pack(fill="x", padx=20, pady=(10, 4))
        self.scan_logo = draw_logo(header, 52)
        self.scan_logo.pack(side="left", padx=(0, 10))
        tk.Label(header, text="Itomi", bg=BASE, fg=FG,
                 font=("DejaVu Sans", 24, "bold")).pack(side="left")
        tk.Label(header, text="Scan", bg=BASE, fg="#42bfea",
                 font=("DejaVu Sans", 24, "bold")).pack(side="left")
        tk.Label(header, textvariable=self.ip_var, bg=BASE, fg=MUTED,
                 font=("DejaVu Sans", 13)).pack(side="right", padx=8)
        self.detail_shutdown = self._btn(header, "Ausschalten", self.shutdown)
        self.detail_shutdown.pack_forget()
        
        body = tk.Frame(self.scan_view, bg=BASE)
        body.pack(fill="both", expand=True, padx=16, pady=7)
        left = tk.Frame(body, bg=PANEL, width=405)
        left.pack(side="left", fill="y", padx=(0, 12))
        left.pack_propagate(False)
        tk.Label(left, text="SCAN-EINSTELLUNGEN", bg=PANEL, fg=FG,
                 font=("DejaVu Sans", 13, "bold")).pack(anchor="w", padx=17, pady=(15, 7))
        tk.Label(left, text="Erkannte Optionen des SANE-Treibers",
                 bg=PANEL, fg=MUTED, font=("DejaVu Sans", 9)).pack(anchor="w", padx=17)
        strip = tk.Frame(left, bg=PANEL)
        strip.pack(fill="x", padx=12, pady=11)
        tk.Label(strip, text="Ausgabe", bg=PANEL, fg=FG).pack(side="left", padx=5)
        ttk.Combobox(strip, textvariable=self.format_var,
                     values=["PDF", "Bild (PNG)"], state="readonly",
                     width=13).pack(side="right")
        holder = tk.Frame(left, bg=PANEL)
        holder.pack(fill="both", expand=True, padx=(9, 3), pady=(0, 10))
        self.canvas = tk.Canvas(holder, bg=PANEL, bd=0, highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb = tk.Scrollbar(holder, orient="vertical", command=self.canvas.yview,
                          width=34, bg="#42bfea", activebackground="#397edb",
                          troughcolor="#263b53", bd=0, highlightthickness=0)
        sb.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=sb.set)
        self.option_frame = tk.Frame(self.canvas, bg=PANEL)
        self.frame_id = self.canvas.create_window((0, 0), window=self.option_frame, anchor="nw")
        self.option_frame.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(
            self.frame_id, width=e.width))
        self.canvas.bind("<MouseWheel>", self._wheel)
        self.option_frame.bind("<MouseWheel>", self._wheel)
        for surface in (self.canvas, self.option_frame):
            surface.bind("<ButtonPress-1>", self._touch_scroll_start)
            surface.bind("<B1-Motion>", self._touch_scroll_move)

        right = tk.Frame(body, bg=PANEL)
        right.pack(side="left", fill="both", expand=True)
        top = tk.Frame(right, bg=PANEL)
        top.pack(fill="x", padx=20, pady=(15, 6))
        tk.Label(top, text="SCANVORSCHAU", bg=PANEL, fg=FG,
                 font=("DejaVu Sans", 13, "bold")).pack(side="left")
        tk.Label(top, textvariable=self.page_var, bg=PANEL, fg=MUTED,
                 font=("DejaVu Sans", 11)).pack(side="right")
        self.preview = tk.Label(right, text="Dokument einlegen\nund „Scannen“ drücken",
                                bg="#eef2f7", fg="#45566c",
                                font=("DejaVu Sans", 16), justify="center")
        self.preview.pack(fill="both", expand=True, padx=17, pady=8)
        self.thumbnail_strip = tk.Frame(right, bg=PANEL)
        self.thumbnail_strip.pack(fill="x", padx=17, pady=4)
        nav = tk.Frame(right, bg=PANEL)
        nav.pack(pady=8)
        self._btn(nav, "◀  Zurück", lambda: self.change_page(-1)).pack(side="left", padx=9)
        self._btn(nav, "Weiter  ▶", lambda: self.change_page(1)).pack(side="left", padx=9)
        edit = tk.Frame(right, bg=PANEL)
        edit.pack(fill="x", padx=14, pady=(0, 6))
        actions = (
            ("Erneut scannen", self.rescan_page),
            ("Drehen", self.rotate_page),
            ("Löschen", self.delete_page),
            ("Leere Seiten prüfen", self.remove_blank_pages),
            ("← Seite", lambda: self.move_page(-1)),
            ("Seite →", lambda: self.move_page(1)),
        )
        for index, (label, callback) in enumerate(actions):
            self._btn(edit, label, callback).grid(
                row=index // 3, column=index % 3, sticky="ew", padx=3, pady=3)
        for column in range(3):
            edit.grid_columnconfigure(column, weight=1)
        self.review_button = self._btn(right, "Fertig · Dokument übernehmen", self.finalize_scan, BLUE)
        self.review_button.pack(fill="x", padx=18, pady=(0, 8))
        self.review_button.pack_forget()
        self.append_button = self._btn(right, "Weitere Seiten scannen", self.append_pages, BLUE)
        self.path_label = tk.Label(right, text="Noch keine Datei", bg=PANEL, fg=MUTED,
                                   font=("DejaVu Sans", 9), wraplength=590)
        self.path_label.pack(pady=(3, 12))

        self.profile_save_button = self._btn(
            left, "Profil speichern", self.save_profile, width=16)
        self.profile_save_button.pack(fill="x", padx=13, pady=(0, 8))
        footer = tk.Frame(self.scan_view, bg=BASE)
        footer.pack(fill="x", padx=18, pady=(5, 13))
        self._btn(footer, "⌂", self.show_home, width=3).pack(side="left", padx=(0, 8))
        self.detail_exit = self._btn(footer, "Menü", self.show_device_menu)
        self.detail_exit.pack(side="left")
        self.detail_update = self._btn(footer, "Updates", self.check_update)
        self.progress = ttk.Progressbar(footer, mode="indeterminate", length=90)
        
        self.scan_button = self._btn(footer, "SCANNEN", self.start_scan, BLUE, width=15)
        self.scan_button.pack(side="right")
        tk.Label(footer, textvariable=self.status_var, bg=BASE, fg=MUTED,
                 font=("DejaVu Sans", 10), wraplength=360).pack(side="right", padx=16)

    def on_front_scan_key(self, event):
        if self.pin_screen and self.pin_screen.active:
            return "break"
        if self.idle_screen and self.idle_screen.active:
            self.idle_screen.wake()
            return "break"
        # Ignore other windows, e.g. confirmation or error dialogs.
        if event.widget.winfo_toplevel() is not self.root:
            return
        if self.root.grab_current() not in (None, self.root):
            return
        if self.busy or not self.device:
            return
        if self.copy_screen and self.copy_screen.visible:
            self.copy_screen.start()
        else:
            self.start_scan()
        return "break"

    def record_activity(self, _event=None):
        self.last_activity = time.monotonic()

    def _allowed(self, permission, *, silent=False):
        """Re-check database permissions before every restricted operation."""
        try:
            if not self.users.settings()["enabled"]:
                return True
            user_id = self.current_user["id"] if self.current_user else None
            allowed = self.users.authorized(user_id, permission)
            if not allowed and not silent:
                if self.current_user is None:
                    self.show_login()
                else:
                    messagebox.showwarning(
                        "Keine Berechtigung",
                        "Diese Funktion ist für den angemeldeten Benutzer nicht freigegeben.",
                        parent=self.root,
                    )
            return allowed
        except (OSError, ValueError) as exc:
            self.status_var.set("Berechtigungsprüfung fehlgeschlagen: " + str(exc))
            return False

    def _profile_record(self, name):
        self.profile_store.reload()
        return next((dict(p) for p in self.profile_store.profiles
                     if p["name"] == name), None)

    def show_login(self, message="Persönliche PIN mit 4 bis 6 Ziffern"):
        if self.busy:
            return
        self.current_user = None
        self.session_profile = None
        if self.home:
            self.home.hide()
        if self.copy_screen:
            self.copy_screen.hide()
        self.scan_view.place_forget()
        if self.idle_screen:
            self.idle_screen.wake()
        if self.pin_screen:
            self.pin_screen.show(message)
        self.record_activity()

    def verify_pin(self, pin):
        if self.busy:
            return
        try:
            if not self.users.settings()["enabled"]:
                self.pin_screen.hide()
                self.show_home()
                return
            identity = self.users.verify_pin(pin)
            if not identity:
                seconds = self.users.settings()["locked_seconds"]
                if seconds:
                    self.pin_screen.error(
                        "Zu viele Versuche. PIN-Eingabe für ca. "
                        + str(seconds) + " Sekunden gesperrt.")
                else:
                    self.pin_screen.error("PIN nicht erkannt. Bitte erneut versuchen.")
                return
            self.current_user = identity
            self.session_profile = identity["default_profile"]
            self.record_activity()
            self.pin_screen.hide()
            self.show_home()
        except (OSError, ValueError) as exc:
            self.pin_screen.error("Anmeldung derzeit nicht möglich: " + str(exc))

    def _clear_previous_scan(self):
        """Prevent next user from seeing previous user's scan preview."""
        self.pages = []
        self.review_pending = False
        self.review_button.pack_forget()
        self.page_index = 0
        self.photo = None
        self.output_path = None
        self.page_var.set("Keine Vorschau")
        self.path_label.configure(text="Noch keine Datei")
        self.preview.configure(image="", text="Dokument einlegen\nund „Scannen“ drücken")
        if self.tempdir:
            self.tempdir.cleanup()
            self.tempdir = None

    def logout(self):
        if self.busy:
            return
        self._clear_previous_scan()
        if self.users.settings()["enabled"]:
            self.show_login("Abgemeldet. Bitte persönliche PIN eingeben.")
        else:
            self.current_user = None
            self.session_profile = None
            self.show_home()

    def auth_tick(self):
        """Pick up web changes, expiration and account revocation without restart."""
        try:
            info = self.users.settings()
            enabled = info["enabled"]
            self.login_enabled = enabled
            if not self.busy:
                if not enabled:
                    if self.current_user or self.pin_screen.active:
                        self.current_user = None
                        self.session_profile = None
                        self.pin_screen.hide()
                        self.show_home()
                elif not self.current_user:
                    if not self.pin_screen.active:
                        self.show_login()
                else:
                    fresh = self.users.get_user(self.current_user["id"])
                    if not fresh or not fresh["active"]:
                        self.logout()
                    elif time.monotonic() - self.last_activity >= (
                            info["timeout_minutes"] * 60):
                        self.logout()
                    else:
                        changed = fresh != self.current_user
                        self.current_user = fresh
                        if changed and self.home.visible:
                            self.show_home()
        except (OSError, ValueError) as exc:
            # Access controls must fail closed if the database becomes unreadable.
            self.status_var.set("Benutzerverwaltung nicht erreichbar: " + str(exc))
            if not self.busy and self.login_enabled:
                self.show_login("Benutzerverwaltung nicht erreichbar.")
        finally:
            try:
                if self.root.winfo_exists():
                    self.root.after(2000, self.auth_tick)
            except tk.TclError:
                pass

    def _center_dialog(self, dialog, width=600, height=430):
        """Position touch dialogs relative to the physical kiosk screen."""
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        width = min(width, screen_w - 24)
        height = min(height, screen_h - 24)
        dialog.geometry(f"{width}x{height}+{(screen_w-width)//2}+{(screen_h-height)//2}")
        dialog.lift()
        dialog.focus_force()

    def confirm_discard_document(self):
        """Touch-friendly, centered confirmation for unfinished scan sessions."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Dokumentbearbeitung abbrechen?")
        dialog.configure(bg=BASE)
        dialog.transient(self.root)
        self._center_dialog(dialog, 660, 330)
        result = {"discard": False}
        tk.Label(dialog, text="Dokumentbearbeitung abbrechen?",
                 bg=BASE, fg=FG, font=("DejaVu Sans", 20, "bold"),
                 wraplength=600).pack(padx=20, pady=(24, 12))
        tk.Label(dialog,
                 text="Das Dokument ist noch nicht fertig. Die bereits gescannten "
                      "Originalseiten bleiben lokal gespeichert.",
                 bg=BASE, fg=MUTED, font=("DejaVu Sans", 12),
                 wraplength=570, justify="center").pack(padx=24, pady=(0, 18))
        buttons = tk.Frame(dialog, bg=BASE)
        buttons.pack(fill="x", side="bottom", padx=24, pady=24)

        def finish(discard):
            result["discard"] = discard
            dialog.destroy()

        self._btn(buttons, "Weiter bearbeiten", lambda: finish(False)).pack(
            side="left", fill="x", expand=True, padx=(0, 8))
        self._btn(buttons, "Verwerfen", lambda: finish(True)).pack(
            side="left", fill="x", expand=True, padx=(8, 0))
        dialog.protocol("WM_DELETE_WINDOW", lambda: finish(False))
        dialog.bind("<Escape>", lambda _event: finish(False))
        dialog.grab_set()
        self.root.wait_window(dialog)
        return result["discard"]

    def restart(self):
        if not self._allowed("shutdown") or self.busy:
            return
        if not messagebox.askyesno("Neustart", "ItomiScan jetzt neu starten?", parent=self.root):
            return
        try:
            result = shell(["sudo", "-n", "/usr/bin/systemctl", "reboot"], timeout=15)
            if result.returncode:
                raise RuntimeError(result.stderr or "Neustart fehlgeschlagen.")
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            messagebox.showerror("Neustart", str(exc), parent=self.root)

    def show_device_menu(self):
        if self.busy:
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Menü")
        dialog.configure(bg=BASE)
        dialog.transient(self.root)
        self._center_dialog(dialog)
        dialog.grab_set()
        tk.Label(dialog, text="Menü", bg=BASE, fg=FG,
                 font=("DejaVu Sans", 23, "bold")).pack(pady=18)
        actions = (
            ("Updates", "update", self.check_update),
            ("Ausschalten", "shutdown", self.shutdown),
            ("Beenden", "exit", self.exit),
        )
        for label, permission, fn in actions:
            if not self._allowed(permission, silent=True):
                continue
            def invoke(action=fn):
                dialog.destroy()
                action()
            self._btn(dialog, label, invoke).pack(fill="x", padx=32, pady=4)
        self._btn(dialog, "Schließen", dialog.destroy).pack(
            side="bottom", fill="x", padx=32, pady=14)

    def _detail_buttons(self):
        user = self.current_user if self.login_enabled else None
        access = set(user["permissions"]) if user else None
        # Shutdown belongs to the device menu, never the scan header.
        self.detail_shutdown.pack_forget()
        for permission, button, side in (
            ("exit", self.detail_exit, "left"),
        ):
            if access is None or permission in access:
                button.pack(side=side, padx=8)
            else:
                button.pack_forget()
        # Editing global profiles is restricted to the web administrator when
        # per-user access control is active.
        if user is None:
            self.profile_save_button.pack(fill="x", padx=13, pady=(0, 8))
        else:
            self.profile_save_button.pack_forget()

    def show_home(self):
        if self.busy or not self.home:
            return
        self.profile_store.reload()
        enabled = self.users.settings()["enabled"]
        if enabled and not self.current_user:
            self.show_login()
            return
        user = None
        if enabled:
            user = self.users.get_user(self.current_user["id"])
            if not user or not user["active"]:
                self.show_login("Benutzerkonto nicht mehr aktiv.")
                return
            self.current_user = user
        if self.review_pending and not self.confirm_discard_document():
            return
        if self.review_pending:
            self.review_pending = False
            self.appending_pages = False
            self.batch_settings = None
            self.pages = []
            self.review_button.pack_forget()
            self.append_button.pack_forget()
            self.thumbnail_strip.pack_forget()
            self.pending_delivery = None
            self.pending_print = None
        self.scan_view.place_forget()
        if self.copy_screen:
            self.copy_screen.hide()
        if self.pin_screen:
            self.pin_screen.hide()
        if user:
            names = [name for name in user["assigned_profiles"]
                     if self._profile_record(name)]
            if self.session_profile not in names:
                self.session_profile = user["default_profile"]
            if self.session_profile not in names:
                self.session_profile = names[0] if names else None
            current = self._profile_record(self.session_profile) if self.session_profile else None
            if current:
                self.apply_profile(current)
            self.home.set_access(user, profile_names=names,
                                 selected=self.session_profile or "")
        else:
            self.session_profile = None
            self.apply_profile(self.profile_store.current())
            self.home.set_access(None)
        self._detail_buttons()
        self.home.show()

    def show_scan(self):
        if not self._allowed(self._delivery_permission()):
            return
        if self.home:
            self.home.hide()
        self.scan_view.place(x=0, y=0, relwidth=1, relheight=1)
        self.scan_view.lift()

    def apply_profile(self, profile):
        """Apply supported preset options; never send unsupported SANE flags."""
        self.format_var.set(profile["output"])
        wanted = {"--mode": profile["mode"],
                  "--source": profile["source"],
                  "--resolution": str(profile["resolution"])}
        wanted.update(profile.get("settings", {}))
        for opt, variable in self.fields:
            value = wanted.get(opt["flag"])
            if value is None or opt["inactive"]:
                continue
            value = str(value)
            if opt["kind"] in ("enum", "bool") and value not in opt["choices"]:
                continue
            variable.set(value)

    def select_profile(self, name):
        if not self._allowed("scan"):
            return
        try:
            if self.users.settings()["enabled"]:
                user = self.users.get_user(self.current_user["id"])
                if not user or name not in user["assigned_profiles"]:
                    raise ProfileError("Dieses Profil ist nicht freigegeben.")
                profile = self._profile_record(name)
                if not profile:
                    raise ProfileError("Das Profil ist nicht mehr vorhanden.")
                self.session_profile = name
                self.apply_profile(profile)
            else:
                self.profile_store.select(name)
                self.apply_profile(self.profile_store.current())
            self.status_var.set("Profil ausgewählt: " + name)
        except (OSError, ProfileError) as exc:
            messagebox.showerror("Scanprofil", str(exc), parent=self.root)
            if self.home:
                self.home.refresh()

    def save_profile(self):
        if self.busy:
            return
        if self.users.settings()["enabled"]:
            messagebox.showinfo(
                "Scanprofil", "Gemeinsame Profile werden über die Webadministration verwaltet.",
                parent=self.root)
            return
        current = self.profile_store.selected
        name = ask_touch(self.root, "Scanprofil speichern", initial=current, max_length=32)
        if name is None:
            return
        flags = {opt["flag"]: variable.get().strip() for opt, variable in self.fields
                 if not opt["inactive"]}
        try:
            data = {"name": name, "mode": flags.get("--mode", "Color"),
                    "source": flags.get("--source", "ADF Duplex"),
                    "resolution": int(float(flags.get("--resolution", "200"))),
                    "output": self.format_var.get(),
                    "settings": flags}
            self.profile_store.save(data)
            if self.home:
                self.home.refresh()
            self.status_var.set("Profil gespeichert: " + name)
        except (ProfileError, ValueError, OSError) as exc:
            messagebox.showerror("Scanprofil", str(exc), parent=self.root)

    def quick_scan(self):
        if self.busy or not self._allowed("scan"):
            return
        if not self.device:
            messagebox.showwarning("Scanner", "Scanner ist noch nicht bereit.",
                                   parent=self.root)
            return
        if self.users.settings()["enabled"]:
            profile = self._profile_record(self.session_profile)
            if not profile:
                return
        else:
            profile = self.profile_store.current()
        self.apply_profile(profile)
        self.start_scan()

    def available_printers(self):
        """Only installed CUPS queues are considered ready for printing."""
        try:
            installed = set(list_queues())
        except PrintError:
            installed = set()
        return [
            {"id": entry["id"], "name": entry["name"],
             "ready": entry["name"] in installed}
            for entry in self.delivery_queue.db.list_targets()
            if entry["kind"] == "printer"
        ]

    def show_copy(self):
        if self.busy or not self._allowed("copy"):
            return
        if not self.device:
            messagebox.showwarning("Scanner", "Scanner noch nicht bereit.",
                                   parent=self.root)
            return
        if self.home:
            self.home.hide()
        self.scan_view.place_forget()
        self.copy_screen.show()

    def start_copy(self, printer_id, copies, sides, scan_source):
        if self.busy or not self._allowed("copy"):
            return
        try:
            validate_copy_options(copies, sides)
            if scan_source not in ("ADF Front", "ADF Duplex"):
                raise PrintError("Ungültiger Vorlageneinzug.", permanent=True)
            target = next((x for x in self.delivery_queue.db.list_targets()
                           if x["id"] == printer_id and x["kind"] == "printer"), None)
            if not target or target["name"] not in list_queues():
                raise PrintError("Drucker nicht in CUPS eingerichtet.", permanent=True)
            supported = next((
                opt["choices"] for opt in self.options
                if opt["flag"] == "--source" and not opt["inactive"]), ())
            if scan_source not in supported:
                raise PrintError("Der Scanner unterstützt diesen Einzug nicht.",
                                 permanent=True)
        except (PrintError, OSError) as exc:
            messagebox.showerror("Kopieren", str(exc), parent=self.root)
            return
        self.pending_print = {
            "target_id": printer_id, "copies": copies, "sides": sides,
            "scan_source": scan_source}
        self.copy_screen.hide()
        self.start_scan()
        if not self.busy:
            self.pending_print = None

    def _delivery_permission(self):
        if self.pending_print is not None:
            return "copy"
        if self.pending_delivery is None:
            return "scan"
        target = next((item for item in self.delivery_queue.db.list_targets()
                       if item["id"] == self.pending_delivery), None)
        return target["kind"] if target else "scan"

    def choose_destination(self, kind):
        if self.busy or self.pin_screen.active:
            return
        kinds = ("email", "usb") if kind == "other" else (kind,)
        targets = [item for item in self.delivery_queue.db.list_targets()
                   if item["kind"] in kinds and self._allowed(item["kind"], silent=True)]
        if not targets:
            messagebox.showinfo(
                "Dokumentenziele",
                "Noch kein freigegebenes Ziel vorhanden. "
                "Bitte über die Webadministration konfigurieren.",
                parent=self.root)
            return
        window = tk.Toplevel(self.root)
        window.title("Dokumentenziel wählen")
        window.configure(bg=BASE)
        window.transient(self.root)
        window.grab_set()
        window.geometry("650x" + str(min(650, max(260, 110 + len(targets) * 80))))
        tk.Label(window, text="Wohin soll der Scan?", bg=BASE, fg=FG,
                 font=("DejaVu Sans", 22, "bold")).pack(pady=(25, 14))
        def selected(target):
            window.destroy()
            self.start_target_scan(target["id"])
        for target in targets:
            self._btn(window, target["name"] + " · " + target["kind"],
                      lambda t=target: selected(t), BLUE).pack(
                          fill="x", padx=24, pady=5, ipady=11)
        self._btn(window, "Abbrechen", window.destroy).pack(pady=14)

    def start_target_scan(self, target_id):
        if self.busy:
            return
        target = next((item for item in self.delivery_queue.db.list_targets()
                       if item["id"] == target_id), None)
        if not target or target["kind"] not in ("paperless", "network", "email", "usb"):
            return
        if not self._allowed(target["kind"]):
            return
        self.pending_delivery = target_id
        self.pending_export_path = None
        self.start_scan()
        if not self.busy:
            self.pending_delivery = None
            self.pending_export_path = None

    def queue_export(self, path, target_id, copies=1, sides="one-sided"):
        try:
            job_id = self.delivery_queue.enqueue(
                path, target_id, copies=copies, sides=sides)
            self.dispatch(lambda: self.status_var.set(
                "Zustellung vorgemerkt · Auftrag " + job_id[:8]))
        except (OSError, ValueError) as exc:
            msg = str(exc)
            # The original scan stays in ~/Scans even if the spool fails.
            self.dispatch(lambda: messagebox.showerror(
                "Zustellung nicht vorgemerkt",
                "Die PDF ist lokal gespeichert, die Warteschlange konnte "
                "nicht angelegt werden. Bitte Datei sichern.\n\n" + msg,
                parent=self.root))

    def delivery_tick(self):
        try:
            counts = self.delivery_queue.summary()
            pending = sum(counts.get(k, 0)
                          for k in ("queued", "retry", "review", "failed"))
            if pending and not self.busy:
                self.status_var.set(str(pending) + " Zustellauftrag/-aufträge offen")
        except (OSError, ValueError):
            pass
        if self.root.winfo_exists():
            self.root.after(15000, self.delivery_tick)

    def unavailable(self, permission, name, block):
        if not self._allowed(permission):
            return
        messagebox.showinfo(
            name, name + " wird in Entwicklungsblock " + str(block) +
            "/8 ergänzt. Die Funktion ist aktuell noch nicht verfügbar.",
            parent=self.root)

    def _wheel(self, event):
        if event.delta:
            self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    def _touch_scroll_start(self, event):
        self.canvas.scan_mark(event.x_root - self.canvas.winfo_rootx(),
                              event.y_root - self.canvas.winfo_rooty())

    def _touch_scroll_move(self, event):
        self.canvas.scan_dragto(event.x_root - self.canvas.winfo_rootx(),
                                event.y_root - self.canvas.winfo_rooty(), gain=1)

    def refresh_ip(self):
        try:
            ips = shell(["hostname", "-I"], timeout=3).stdout.split()
            ip = next((p for p in ips if "." in p and not p.startswith("127.")), None)
        except (OSError, subprocess.TimeoutExpired):
            ip = None
        self.ip_var.set("IP: " + (ip or "nicht verbunden"))
        self.root.after(30000, self.refresh_ip)

    def load_scanner(self):
        try:
            self.device = find_device()
            if not self.device:
                raise RuntimeError("Kein Fujitsu-Scanner gefunden. USB-Verbindung prüfen.")
            self.options = read_options(self.device)
            self.render_options()
            self.apply_profile(self.profile_store.current())
            self.status_var.set("Bereit")
            if self.home:
                if self.users.settings()["enabled"]:
                    self.show_login()
                else:
                    self.show_home()
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            self.status_var.set("Scannerfehler")
            messagebox.showerror("Scanner", str(exc), parent=self.root)

    def render_options(self):
        for widget in self.option_frame.winfo_children():
            widget.destroy()
        self.fields = []
        last_section = None
        for opt in self.options:
            if opt["section"] != last_section:
                last_section = opt["section"]
                tk.Label(self.option_frame, text=SECTION_NAMES[last_section],
                         bg=PANEL, fg=GREEN, font=("DejaVu Sans", 12, "bold"),
                         anchor="w").pack(fill="x", padx=9, pady=(17, 7))
            row = tk.Frame(self.option_frame, bg=PANEL)
            row.pack(fill="x", padx=7, pady=5)
            caption = LABELS[opt["flag"]] + ("  (inaktiv)" if opt["inactive"] else "")
            tk.Label(row, text=caption, bg=PANEL,
                     fg=MUTED if opt["inactive"] else FG,
                     font=("DejaVu Sans", 10), anchor="w",
                     wraplength=350).pack(anchor="w", padx=3, pady=(0, 4))
            variable = tk.StringVar(value=opt["value"])
            if opt["kind"] in ("enum", "bool"):
                control = ttk.Combobox(row, textvariable=variable,
                                       values=opt["choices"], state="readonly",
                                       width=30)
            else:
                control = ttk.Entry(row, textvariable=variable, width=30)
                if not opt["inactive"]:
                    control.bind("<Button-1>",
                                 lambda _event, v=variable, o=opt: self._edit_touch_option(v, o))
            if opt["inactive"]:
                control.configure(state="disabled")
            control.pack(fill="x", padx=3)
            self.fields.append((opt, variable))
        if not self.fields:
            tk.Label(self.option_frame, text="Keine Optionen erkannt",
                     bg=PANEL, fg=FG).pack(pady=20)

    def _edit_touch_option(self, variable, option):
        if self.busy:
            return "break"
        name = LABELS.get(option["flag"], option["flag"])
        value = ask_touch(self.root, name, initial=variable.get(),
                          numeric=option["kind"] == "number", max_length=120)
        if value is not None:
            variable.set(value.replace(",", ".") if option["kind"] == "number" else value)
        return "break"

    def chosen_args(self):
        args = []
        for opt, variable in self.fields:
            if opt["inactive"]:
                continue
            value = variable.get().strip()
            if not value:
                continue
            if opt["kind"] == "enum" and value not in opt["choices"]:
                raise ValueError("Ungültiger Wert: " + LABELS[opt["flag"]])
            if opt["kind"] == "number":
                try:
                    float(value.replace(",", "."))
                except ValueError as exc:
                    raise ValueError("Zahl erwartet: " + LABELS[opt["flag"]]) from exc
                value = value.replace(",", ".")
            if opt["kind"] == "bool" and value not in ("yes", "no"):
                raise ValueError("Ungültige Auswahl: " + LABELS[opt["flag"]])
            if value != opt["default"]:
                args.append(opt["flag"] + "=" + value)
        return args

    def dispatch(self, fn):
        try:
            self.root.after(0, fn)
        except RuntimeError:
            pass

    def start_scan(self):
        if self.busy or not self.device:
            return
        if self.review_pending:
            messagebox.showinfo("Dokument prüfen",
                                "Bitte das vorherige Dokument erst mit Fertig abschließen.",
                                parent=self.root)
            return
        if not self._allowed(self._delivery_permission()):
            return
        if self.users.settings()["enabled"]:
            identity = self.users.get_user(self.current_user["id"])
            if not identity or not identity["active"]:
                self.show_login("Benutzerkonto nicht mehr aktiv.")
                return
            if self.session_profile not in identity["assigned_profiles"]:
                self.show_home()
                messagebox.showwarning("Scanprofil", "Dieses Profil ist nicht mehr freigegeben.", parent=self.root)
                return
            preset = self._profile_record(self.session_profile)
            if preset is None:
                self.show_home()
                return
            self.apply_profile(preset)
        if self.idle_screen and self.idle_screen.active:
            self.idle_screen.wake()
            return
        # Avoid partially scanned jobs when the SSD is critically full.
        # Existing documents and waiting jobs always remain untouched.
        try:
            scan_root = Path.home() / "Scans"
            scan_root.mkdir(parents=True, exist_ok=True)
            free_bytes = shutil.disk_usage(scan_root).free
            if free_bytes < 300 * 1024 * 1024:
                messagebox.showwarning(
                    "Speicher fast voll",
                    "Weniger als 300 MiB frei. Bitte zuerst Scans sichern "
                    "und Speicherplatz prüfen. Nichts wird automatisch gelöscht.",
                    parent=self.root)
                return
        except OSError as exc:
            messagebox.showerror("Speicher", "Speicherplatz nicht prüfbar: " + str(exc),
                                 parent=self.root)
            return
        if self.pending_print is not None:
            self.show_scan()
            # Always create a printable PDF, regardless of the user's PNG preset.
            self.format_var.set("PDF")
            for option, variable in self.fields:
                if option["flag"] == "--source" and not option["inactive"]:
                    variable.set(self.pending_print["scan_source"])
        elif self.home and self.home.visible:
            self.show_scan()
        try:
            settings = self.chosen_args()
        except ValueError as exc:
            messagebox.showerror("Scanoption", str(exc), parent=self.root)
            return
        self.busy = True
        self.scan_button.configure(state="disabled")
        self.progress.start(10)
        self.status_var.set("Scannen läuft …")
        if self.tempdir:
            self.tempdir.cleanup()
        self.tempdir = tempfile.TemporaryDirectory(prefix="itomiscan-")
        scan_mode = next((variable.get().strip() for opt, variable in self.fields
                          if opt["flag"] == "--mode" and not opt["inactive"]), "")
        self.batch_settings = (list(settings), scan_mode, self.format_var.get())
        threading.Thread(target=self.scan_worker,
                         args=(settings, self.format_var.get(), scan_mode),
                         daemon=True).start()

    def append_pages(self):
        if self.busy or not self.review_pending or not self.pages:
            return
        try:
            settings = self.chosen_args()
        except ValueError as exc:
            messagebox.showerror("Scanoption", str(exc), parent=self.root)
            return
        scan_mode = next((v.get().strip() for opt, v in self.fields
                          if opt["flag"] == "--mode" and not opt["inactive"]), "")
        if self.batch_settings is not None:
            settings, scan_mode, output_format = self.batch_settings
        else:
            output_format = self.format_var.get()
        self.appending_pages = True
        self.busy = True
        self.scan_button.configure(state="disabled")
        self.progress.start(10)
        self.status_var.set("Weitere Seiten werden gescannt …")
        if self.tempdir:
            self.tempdir.cleanup()
        self.tempdir = tempfile.TemporaryDirectory(prefix="itomiscan-append-")
        threading.Thread(target=self.scan_worker,
                         args=(settings, output_format, scan_mode),
                         daemon=True).start()

    def scan_worker(self, settings, output_format, scan_mode):
        folder = Path(self.tempdir.name)
        # For PDF color/gray pages, JPEG avoids expensive PNG compression on
        # the Atom N270 and img2pdf embeds the JPEG stream without re-encoding.
        # Keep lossless PNG for line art and for explicit PNG output.
        use_jpeg = output_format == "PDF" and scan_mode in ("Color", "Gray")
        image_format = "jpeg" if use_jpeg else "png"
        extension = "jpg" if use_jpeg else "png"
        cmd = ["scanimage", "-d", self.device, "--format=" + image_format,
               "--batch=page-%04d." + extension] + settings
        try:
            result = shell(cmd, timeout=600, cwd=str(folder))
            scans = sorted(folder.glob("page-*." + extension))
            if not scans:
                raise RuntimeError(result.stderr.strip() or "Kein Dokument eingezogen.")
            # Validate acquisition before committing review files.
            warning = result.stderr.strip() if result.returncode else ""
            if result.returncode != 0:
                title, _ = classify_scanner_error(warning)
                if title != "Kein Dokument eingelegt":
                    raise RuntimeError(warning or "Scan unvollständig.")
            if warning and classify_scanner_error(warning)[0] in (
                    "Scan unvollständig", "Möglicher Doppeleinzug", "Papierstau erkannt"):
                raise RuntimeError(warning)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            target = (self.output_path.parent if self.output_path.suffix.lower() == ".pdf"
                      else self.output_path) if self.appending_pages else (
                          Path.home() / "Scans" / ("ItomiScan_" + stamp))
            if not self.appending_pages:
                if target.exists():
                    target = Path.home() / "Scans" / ("ItomiScan_" + stamp + "_" + str(os.getpid()))
                target.mkdir(parents=True, exist_ok=False)
            elif not target.is_dir():
                raise RuntimeError("Dokumentordner nicht gefunden.")
            saved = []
            for number, scan in enumerate(scans, 1):
                permanent = target / (f"append-{time.time_ns()}-{number:04d}.{extension}" if self.appending_pages else f"page-{number:04d}.{extension}")
                shutil.copy2(scan, permanent)
                saved.append(permanent)
            # A PDF is generated only after the user approves page edits.
            path = self.output_path if self.appending_pages else (target / "Dokument.pdf" if output_format == "PDF" else target)
            # Do not prepare or enqueue any delivery before review approval.
            self.pending_export_path = None
            self.dispatch(lambda: self.scan_finished(saved, path, warning))
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            msg = str(exc)
            self.dispatch(lambda: self.scan_failed(msg))

    def scan_finished(self, images, path, warning):
        self.busy = False
        self.scan_button.configure(state="normal")
        self.progress.stop()
        was_appending = self.appending_pages
        self.appending_pages = False
        if was_appending:
            self.pages.extend(images)
            self.page_index = len(self.pages) - len(images)
        else:
            self.pages = list(images)
            self.page_index = 0
        self.review_pending = bool(self.pages)
        self.output_path = path
        self.path_label.configure(text="Gespeichert: " + str(path))
        self.show_page()
        self.status_var.set(str(len(self.pages)) + " Bildseite(n) erfasst · Bitte prüfen")
        if self.review_pending:
            self.append_button.pack(fill="x", padx=18, pady=(0, 8))
        if self.review_pending:
            self.review_button.pack(fill="x", padx=18, pady=(0, 8))
        if warning:
            title, _ = classify_scanner_error(warning)
            if title != "Kein Dokument eingelegt":
                show_scanner_error(self.root, warning)

    def scan_failed(self, msg):
        was_appending = self.appending_pages
        self.appending_pages = False
        if not was_appending:
            self.pending_delivery = None
            self.pending_export_path = None
            self.pending_print = None
        self.busy = False
        self.scan_button.configure(state="normal")
        self.progress.stop()
        self.status_var.set("Scan fehlgeschlagen")
        show_scanner_error(self.root, msg)

    def rescan_page(self):
        """Replace the selected image only after a successful single-page scan."""
        if self.busy or not self.review_pending or not self.pages:
            return
        if not messagebox.askyesno(
                "Seite erneut scannen",
                "Die ausgewählte Seite erneut einziehen und ersetzen? "
                "Die bisherige Seite bleibt bei einem Fehler erhalten.",
                parent=self.root):
            return
        try:
            settings = self.chosen_args()
        except ValueError as exc:
            messagebox.showerror("Scanoption", str(exc), parent=self.root)
            return
        self.busy = True
        self.scan_button.configure(state="disabled")
        self.progress.start(10)
        self.status_var.set("Ausgewählte Seite wird erneut gescannt …")
        index = self.page_index
        original = Path(self.pages[index])
        threading.Thread(target=self._rescan_page_worker,
                         args=(index, original, settings), daemon=True).start()

    def _rescan_page_worker(self, index, original, settings):
        try:
            with tempfile.TemporaryDirectory(prefix="itomiscan-rescan-") as folder:
                ext = original.suffix.lower().lstrip(".")
                fmt = "jpeg" if ext in ("jpg", "jpeg") else "png"
                command = ["scanimage", "-d", self.device, "--format=" + fmt,
                           "--batch=retry-%04d." + ext, "--batch-count=1"] + settings
                result = shell(command, timeout=180, cwd=folder)
                candidates = sorted(Path(folder).glob("retry-*." + ext))
                if result.returncode != 0:
                    raise RuntimeError(result.stderr.strip() or "Erneuter Scan fehlgeschlagen.")
                if len(candidates) != 1:
                    raise RuntimeError("Es wurde keine einzelne Bildseite erkannt. "
                                       "Bitte Einzug und Duplex-Einstellung prüfen.")
                with Image.open(candidates[0]) as img:
                    img.verify()
                # Replace atomically only when acquisition is complete.
                replacement = original.with_name(original.name + ".new")
                shutil.copy2(candidates[0], replacement)
                os.replace(replacement, original)
            self.dispatch(lambda: self._rescan_page_complete(index))
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            error = str(exc)
            self.dispatch(lambda: self._rescan_page_error(error))

    def _rescan_page_complete(self, index):
        self.busy = False
        self.scan_button.configure(state="normal")
        self.progress.stop()
        self.page_index = index
        self.show_page()
        self.status_var.set("Seite erneut gescannt · Bitte Dokument prüfen")

    def _rescan_page_error(self, error):
        self.busy = False
        self.scan_button.configure(state="normal")
        self.progress.stop()
        self.status_var.set("Erneuter Scan fehlgeschlagen · Alte Seite erhalten")
        show_scanner_error(self.root, error)

    def remove_blank_pages(self):
        """Suggest nearly blank pages; never remove them without confirmation."""
        if self.busy or not self.review_pending or not self.pages:
            return
        self.busy = True
        self.status_var.set("Leere Seiten werden geprüft …")
        threading.Thread(target=self._find_blank_pages_worker,
                         args=(list(self.pages),), daemon=True).start()

    def _find_blank_pages_worker(self, pages):
        candidates = []
        try:
            for index, filename in enumerate(pages):
                with Image.open(filename) as img:
                    gray = img.convert("L")
                    gray.thumbnail((160, 220), Image.Resampling.BILINEAR)
                    histogram = gray.histogram()
                    pixels = max(1, gray.width * gray.height)
                    # Conservative heuristic: at least 99.5% nearly white pixels.
                    white = sum(histogram[245:])
                    if white / pixels >= 0.995:
                        candidates.append(index)
            self.dispatch(lambda: self._confirm_blank_pages(pages, candidates))
        except (OSError, ValueError) as exc:
            error = str(exc)
            self.dispatch(lambda: self._blank_pages_error(error))

    def _blank_pages_error(self, error):
        self.busy = False
        self.status_var.set("Leerseitenerkennung fehlgeschlagen")
        show_scanner_error(self.root, error)

    def _confirm_blank_pages(self, snapshot, candidates):
        self.busy = False
        if not candidates:
            self.status_var.set("Keine eindeutig leeren Seiten erkannt")
            messagebox.showinfo("Leerseiten", "Keine eindeutig leeren Seiten gefunden.",
                                parent=self.root)
            return
        numbers = ", ".join(str(index + 1) for index in candidates)
        if not messagebox.askyesno(
                "Leerseiten entfernen",
                f"Diese Seiten wirken leer: {numbers}.\\n"
                "Sollen sie aus dem Dokument entfernt werden? "
                "Bei sehr hellen Vorlagen bitte vorher prüfen.",
                parent=self.root):
            return
        if self.pages != snapshot:
            return
        remove = set(candidates)
        if len(remove) == len(self.pages):
            messagebox.showwarning("Alle Seiten leer",
                                   "Es würden alle Dokumentseiten entfernt. Bitte Seiten einzeln prüfen.",
                                   parent=self.root)
            return
        self.pages = [page for index, page in enumerate(self.pages) if index not in remove]
        self.page_index = min(self.page_index, max(0, len(self.pages) - 1))
        if self.pages:
            self.show_page()
        else:
            self.photo = None
            self.preview.configure(image="", text="Keine Seiten mehr vorhanden")
            self.render_thumbnails()
            self.page_var.set("Keine Seiten")
        self.status_var.set(str(len(candidates)) + " Leerseite(n) entfernt")

    def rotate_page(self):
        if self.busy or not self.pages:
            return
        path = Path(self.pages[self.page_index])
        try:
            with Image.open(path) as source:
                rotated = source.rotate(-90, expand=True)
                temp = path.with_name(path.stem + "-rotated" + path.suffix)
                rotated.save(temp)
            os.replace(temp, path)
            self.show_page()
        except OSError as exc:
            show_scanner_error(self.root, str(exc))

    def delete_page(self):
        if self.busy or not self.pages:
            return
        if not messagebox.askyesno("Seite löschen", "Diese Seite aus dem Dokument entfernen?",
                                   parent=self.root):
            return
        self.pages.pop(self.page_index)
        self.page_index = min(self.page_index, max(0, len(self.pages) - 1))
        if self.pages:
            self.show_page()
        else:
            self.photo = None
            self.preview.configure(image="", text="Keine Seiten mehr vorhanden")
            self.page_var.set("Keine Seiten")
        self.status_var.set(str(len(self.pages)) + " Bildseite(n) verbleiben")

    def move_page(self, direction):
        if self.busy or not self.pages:
            return
        destination = self.page_index + direction
        if not 0 <= destination < len(self.pages):
            return
        self.pages[self.page_index], self.pages[destination] = (
            self.pages[destination], self.pages[self.page_index])
        self.page_index = destination
        self.show_page()

    def finalize_scan(self):
        if self.busy or not self.review_pending:
            return
        if not self.pages:
            messagebox.showwarning("Keine Seiten", "Bitte zunächst Dokumentseiten scannen.",
                                   parent=self.root)
            return
        self.busy = True
        self.status_var.set("Dokument wird abgeschlossen …")
        self.progress.start(10)
        threading.Thread(target=self._finalize_worker, args=(list(self.pages),),
                         daemon=True).start()

    def _finalize_worker(self, pages):
        try:
            output = self.output_path
            if output is None or not pages:
                raise RuntimeError("Keine Dokumentseiten zum Abschließen.")
            if output.suffix.lower() == ".pdf":
                target = output.with_name("Dokument-neu.pdf")
                converted = shell(["img2pdf", *map(str, pages), "-o", str(target)], timeout=180)
                if converted.returncode or not target.is_file() or target.stat().st_size == 0:
                    raise RuntimeError(converted.stderr or "PDF-Erstellung fehlgeschlagen.")
                os.replace(target, output)
                export_path = output
            else:
                ordered = output / "Fertiges-Dokument"
                if ordered.exists():
                    raise RuntimeError("Fertiges-Dokument existiert bereits; kein Überschreiben.")
                staging = output / "_Dokument-in-Arbeit"
                if staging.exists():
                    raise RuntimeError("Unvollständiger Export vorhanden; bitte prüfen.")
                staging.mkdir()
                for number, page in enumerate(pages, 1):
                    shutil.copy2(page, staging / f"Seite-{number:04d}{Path(page).suffix}")
                os.replace(staging, ordered)
                export_path = None
                if self.pending_delivery is not None or self.pending_print is not None:
                    pdf_path = output / "Dokument-fuer-Versand.pdf"
                    temp_pdf = output / "_Versand-in-Arbeit.pdf"
                    pdf = shell(["img2pdf", *map(str, pages), "-o", str(temp_pdf)], timeout=180)
                    if pdf.returncode or not temp_pdf.is_file() or temp_pdf.stat().st_size == 0:
                        raise RuntimeError(pdf.stderr or "Versand-PDF fehlgeschlagen.")
                    os.replace(temp_pdf, pdf_path)
                    export_path = pdf_path
            self.pending_export_path = export_path
            self.dispatch(self._finalize_complete)
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            error = str(exc)
            self.dispatch(lambda: self._finalize_error(error))
    def _finalize_error(self, error):
        self.busy = False
        self.progress.stop()
        self.status_var.set("Dokument konnte nicht abgeschlossen werden")
        show_scanner_error(self.root, error)

    def _finalize_complete(self):
        self.busy = False
        self.progress.stop()
        self.review_pending = False
        self.review_button.pack_forget()
        self.append_button.pack_forget()
        self.thumbnail_strip.pack_forget()
        self.batch_settings = None
        self.status_var.set("Dokument abgeschlossen · " + str(len(self.pages)) + " Bildseiten")
        export_path = self.pending_export_path or self.output_path
        self.pending_export_path = None
        if self.pending_delivery is not None:
            target_id = self.pending_delivery
            self.pending_delivery = None
            threading.Thread(target=self.queue_export,
                             args=(export_path, target_id), daemon=True).start()
        if self.pending_print is not None:
            details = self.pending_print
            self.pending_print = None
            threading.Thread(target=self.queue_export,
                             args=(export_path, details["target_id"],
                                   details["copies"], details["sides"]), daemon=True).start()

    def change_page(self, diff):
        if self.pages:
            self.page_index = max(0, min(len(self.pages) - 1, self.page_index + diff))
            self.show_page()

    def show_page(self):
        if not self.pages:
            return
        try:
            self.root.update_idletasks()
            width = max(240, self.preview.winfo_width() - 25)
            height = max(200, self.preview.winfo_height() - 25)
            with Image.open(self.pages[self.page_index]) as src:
                # Shrink in-place before RGB conversion to avoid an extra full
                # resolution colour buffer on the 1-GiB Atom scanner.
                if src.format == "JPEG":
                    src.draft("RGB", (width, height))
                src.thumbnail((width, height), Image.Resampling.BILINEAR)
                image = src.convert("RGB")
            self.photo = ImageTk.PhotoImage(image)
            self.preview.configure(image=self.photo, text="")
            self.page_var.set(f"Seite {self.page_index + 1} / {len(self.pages)}")
            self.render_thumbnails()
        except (OSError, ValueError) as exc:
            self.status_var.set("Vorschaufehler: " + str(exc))

    def render_thumbnails(self):
        """Only decode nearby thumbnails to keep memory use low."""
        for widget in self.thumbnail_strip.winfo_children():
            widget.destroy()
        self.thumbnail_photos = []
        if not self.review_pending or not self.pages:
            self.thumbnail_strip.pack_forget()
            return
        self.thumbnail_strip.pack(fill="x", padx=17, pady=4)
        start = max(0, min(self.page_index - 2, len(self.pages) - 5))
        for index in range(start, min(len(self.pages), start + 5)):
            try:
                with Image.open(self.pages[index]) as source:
                    if source.format == "JPEG":
                        source.draft("RGB", (80, 100))
                    source.thumbnail((70, 90), Image.Resampling.BILINEAR)
                    photo = ImageTk.PhotoImage(source.convert("RGB"))
                self.thumbnail_photos.append(photo)
                button = tk.Button(self.thumbnail_strip, image=photo,
                                   text=str(index + 1), compound="top",
                                   bg=BLUE if index == self.page_index else PANEL,
                                   fg=FG, command=lambda i=index: self.select_page(i))
            except (OSError, ValueError):
                button = self._btn(self.thumbnail_strip, str(index + 1),
                                   lambda i=index: self.select_page(i))
            button.pack(side="left", expand=True, padx=2)

    def select_page(self, index):
        if not self.busy and 0 <= index < len(self.pages):
            self.page_index = index
            self.show_page()

    def check_update(self):
        """Display update preferences; installation stays SSH-only for now."""
        if self.busy or not self._allowed("update"):
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Updates")
        dialog.configure(bg=BASE)
        dialog.transient(self.root)
        self._center_dialog(dialog, 620, 410)
        dialog.grab_set()
        tk.Label(dialog, text="ItomiScan Updates", bg=BASE, fg=FG,
                 font=("DejaVu Sans", 22, "bold")).pack(pady=(22, 10))
        installed = Path(__file__).resolve().parent / ".itomiscan-beta-commit"
        revision = installed.read_text().strip()[:10] if installed.exists() else "unbekannt"
        tk.Label(dialog, text="Installierter Stand: " + revision, bg=BASE, fg=MUTED,
                 font=("DejaVu Sans", 12)).pack(pady=4)
        include_beta = tk.BooleanVar(value=True)
        tk.Checkbutton(dialog, text="Beta-Releases einschließen",
                       variable=include_beta, bg=BASE, fg=FG,
                       selectcolor=PANEL, activebackground=BASE,
                       activeforeground=FG, font=("DejaVu Sans", 13),
                       padx=12, pady=12).pack(pady=8)
        result = tk.StringVar(value="Noch nicht geprüft.")
        tk.Label(dialog, textvariable=result, bg=BASE, fg=MUTED,
                 wraplength=530, justify="center",
                 font=("DejaVu Sans", 11)).pack(pady=8)
        def start_check():
            result.set("Suche nach Updates …")
            self.update_worker(include_beta.get(), result)
        self._btn(dialog, "Auf Updates prüfen", start_check, BLUE).pack(
            fill="x", padx=35, pady=7)
        self._btn(dialog, "Schließen", dialog.destroy).pack(
            side="bottom", fill="x", padx=35, pady=12)

    def update_worker(self, include_beta, result_var=None):
        """Read GitHub revision only; do not execute privileged installers in Tk."""
        def publish(message):
            def apply():
                if result_var is not None:
                    try:
                        result_var.set(message)
                    except tk.TclError:
                        pass
                self.status_var.set(message)
            self.dispatch(apply)

        def worker():
            import json
            import urllib.request
            try:
                if include_beta:
                    endpoint = ("https://api.github.com/repos/tojollinor/ItomiScan/"
                                "commits/develop/1.0.0")
                    request = urllib.request.Request(
                        endpoint, headers={"User-Agent": "ItomiScan-Beta-Updater",
                                           "Accept": "application/vnd.github+json"})
                    with urllib.request.urlopen(request, timeout=20) as response:
                        remote = json.load(response)["sha"]
                    installed = Path(__file__).resolve().parent / ".itomiscan-beta-commit"
                    local = installed.read_text().strip() if installed.exists() else ""
                    publish("Beta ist aktuell." if local == remote else
                            "Neue Beta verfügbar. Installation vorerst über SSH/curl.")
                else:
                    endpoint = ("https://api.github.com/repos/tojollinor/ItomiScan/"
                                "releases/latest")
                    request = urllib.request.Request(
                        endpoint, headers={"User-Agent": "ItomiScan-Updater",
                                           "Accept": "application/vnd.github+json"})
                    with urllib.request.urlopen(request, timeout=20) as response:
                        release = json.load(response)
                    publish("Stabile Version verfügbar: " + release.get("tag_name", "?") +
                            ". Installation vorerst über SSH/curl.")
            except Exception as exc:
                publish("Updateprüfung fehlgeschlagen: " + str(exc))
        threading.Thread(target=worker, daemon=True).start()

    def shutdown(self):
        if not self._allowed("shutdown"):
            return
        if self.busy:
            messagebox.showinfo("Scannen", "Bitte zuerst den Scan abschließen.", parent=self.root)
            return
        if not messagebox.askyesno(
            "ItomiScan ausschalten",
            "Scanner vollständig herunterfahren?\n\nDer Scanner wird ausgeschaltet.",
            icon="warning", parent=self.root,
        ):
            return
        self.status_var.set("Scanner wird heruntergefahren …")
        try:
            # Only this exact command is authorized in the installer sudoers rule.
            result = shell(["sudo", "-n", "/usr/bin/systemctl", "poweroff"], timeout=15)
            if result.returncode != 0:
                raise RuntimeError((result.stderr or result.stdout).strip()
                                   or "Systemberechtigung fehlt.")
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            self.status_var.set("Ausschalten fehlgeschlagen")
            messagebox.showerror(
                "Ausschalten fehlgeschlagen",
                "Die Berechtigung zum Herunterfahren fehlt oder der Befehl ist fehlgeschlagen.\n"
                "Einmalig setup-shutdown.sh als root ausführen.\n\n" + str(exc),
                parent=self.root,
            )

    def exit(self):
        if not self._allowed("exit"):
            return
        if self.busy:
            messagebox.showinfo("Scannen", "Bitte zuerst den Scan abschließen.", parent=self.root)
            return
        if self.tempdir:
            self.tempdir.cleanup()
        self.root.destroy()


if __name__ == "__main__":
    window = tk.Tk()
    ItomiScan(window)
    window.mainloop()
