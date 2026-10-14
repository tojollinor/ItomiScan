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
from itomiscan.gui.home import HomeScreen
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
        self.page_index = 0
        self.photo = None
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
            self.status_var.set("Bereit · " + self.device)
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
        tk.Label(header, text="Itomi", bg=BASE, fg=FG,
                 font=("DejaVu Sans", 24, "bold")).pack(side="left")
        tk.Label(header, text="Scan", bg=BASE, fg="#42bfea",
                 font=("DejaVu Sans", 24, "bold")).pack(side="left")
        tk.Label(header, textvariable=self.ip_var, bg=BASE, fg=MUTED,
                 font=("DejaVu Sans", 13)).pack(side="right", padx=8)
        self.detail_shutdown = self._btn(header, "Ausschalten", self.shutdown)
        self.detail_shutdown.pack(side="right", padx=(0, 8))
        self._btn(header, "← Startseite", self.show_home, width=12).pack(
            side="right", padx=(0, 10))
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
        self.canvas.bind_all("<MouseWheel>", self._wheel)

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
        nav = tk.Frame(right, bg=PANEL)
        nav.pack(pady=8)
        self._btn(nav, "◀  Zurück", lambda: self.change_page(-1)).pack(side="left", padx=9)
        self._btn(nav, "Weiter  ▶", lambda: self.change_page(1)).pack(side="left", padx=9)
        edit = tk.Frame(right, bg=PANEL)
        edit.pack(fill="x", padx=14, pady=(0, 6))
        for label, callback in (
                ("Drehen", self.rotate_page),
                ("Löschen", self.delete_page),
                ("← Seite", lambda: self.move_page(-1)),
                ("Seite →", lambda: self.move_page(1))):
            self._btn(edit, label, callback).pack(side="left", expand=True, fill="x", padx=3)
        self.review_button = self._btn(right, "Fertig · Dokument übernehmen", self.finalize_scan, BLUE)
        self.review_button.pack(fill="x", padx=18, pady=(0, 8))
        self.review_button.pack_forget()
        self.path_label = tk.Label(right, text="Noch keine Datei", bg=PANEL, fg=MUTED,
                                   font=("DejaVu Sans", 9), wraplength=590)
        self.path_label.pack(pady=(3, 12))

        self.profile_save_button = self._btn(
            left, "Profil speichern", self.save_profile, width=16)
        self.profile_save_button.pack(fill="x", padx=13, pady=(0, 8))
        footer = tk.Frame(self.scan_view, bg=BASE)
        footer.pack(fill="x", padx=18, pady=(5, 13))
        self.detail_exit = self._btn(footer, "Menü", self.show_device_menu)
        self.detail_exit.pack(side="left")
        self.detail_update = self._btn(footer, "Updates", self.check_update)
        self.progress = ttk.Progressbar(footer, mode="indeterminate", length=90)
        self.progress.pack(side="left", padx=12)
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

    def show_device_menu(self):
        if self.busy:
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Menü")
        dialog.configure(bg=BASE)
        dialog.transient(self.root)
        dialog.geometry("600x430")
        dialog.grab_set()
        tk.Label(dialog, text="Menü", bg=BASE, fg=FG,
                 font=("DejaVu Sans", 23, "bold")).pack(pady=22)
        for label, permission, fn in (
                ("Updates", "update", self.check_update),
                ("Beenden", "exit", self.exit)):
            if not self._allowed(permission, silent=True):
                continue
            def invoke(action=fn):
                dialog.destroy()
                action()
            self._btn(dialog, label, invoke).pack(fill="x", padx=25, pady=8)
        self._btn(dialog, "Schließen", dialog.destroy).pack(pady=10)

    def _detail_buttons(self):
        user = self.current_user if self.login_enabled else None
        access = set(user["permissions"]) if user else None
        for permission, button, side in (
            ("shutdown", self.detail_shutdown, "right"),
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
        self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

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
            self.status_var.set("Bereit · " + self.device)
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
        threading.Thread(target=self.scan_worker,
                         args=(settings, self.format_var.get(), scan_mode),
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
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            target = Path.home() / "Scans" / ("ItomiScan_" + stamp)
            if target.exists():
                target = Path.home() / "Scans" / ("ItomiScan_" + stamp + "_" + str(os.getpid()))
            target.mkdir(parents=True, exist_ok=False)
            if output_format == "PDF":
                path = target / "Dokument.pdf"
                self.dispatch(lambda: self.status_var.set("PDF wird erstellt …"))
                pdf = shell(["img2pdf", *map(str, scans), "-o", str(path)], timeout=180)
                if pdf.returncode != 0:
                    raise RuntimeError("PDF-Erstellung: " + (pdf.stderr or pdf.stdout))
            else:
                for scan in scans:
                    shutil.copy2(scan, target / scan.name)
                path = target
            if self.pending_delivery:
                if output_format == "PDF":
                    self.pending_export_path = path
                else:
                    self.pending_export_path = target / "Dokument-fuer-Versand.pdf"
                    conversion = shell(
                        ["img2pdf", *map(str, scans), "-o", str(self.pending_export_path)],
                        timeout=180)
                    if conversion.returncode != 0:
                        raise RuntimeError("Versand-PDF: " + (conversion.stderr or conversion.stdout))
            warning = result.stderr.strip() if result.returncode else ""
            self.dispatch(lambda: self.scan_finished(scans, path, warning))
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            msg = str(exc)
            self.dispatch(lambda: self.scan_failed(msg))

    def scan_finished(self, images, path, warning):
        self.busy = False
        self.scan_button.configure(state="normal")
        self.progress.stop()
        self.pages = list(images)
        self.review_pending = bool(images)
        self.page_index = 0
        self.output_path = path
        self.path_label.configure(text="Gespeichert: " + str(path))
        self.show_page()
        self.status_var.set(str(len(images)) + " Bildseite(n) erfasst · Bitte prüfen")
        if self.review_pending:
            self.review_button.pack(fill="x", padx=18, pady=(0, 8))
        if warning:
            title, _ = classify_scanner_error(warning)
            if title == "Papierstau erkannt" or title == "Scannerfehler":
                show_scanner_error(self.root, warning)

    def scan_failed(self, msg):
        self.pending_delivery = None
        self.pending_export_path = None
        self.pending_print = None
        self.busy = False
        self.scan_button.configure(state="normal")
        self.progress.stop()
        self.status_var.set("Scan fehlgeschlagen")
        show_scanner_error(self.root, msg)

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
            if output is None:
                raise RuntimeError("Kein Speicherziel vorhanden.")
            if output.suffix.lower() == ".pdf":
                target = output.with_name("Dokument-neu.pdf")
                converted = shell(["img2pdf", *map(str, pages), "-o", str(target)],
                                  timeout=180)
                if converted.returncode:
                    raise RuntimeError(converted.stderr or "PDF-Erstellung fehlgeschlagen.")
                os.replace(target, output)
            else:
                ordered = output / "_geordnet"
                ordered.mkdir(exist_ok=True)
                for number, page in enumerate(pages, 1):
                    shutil.copy2(page, ordered / f"Seite-{number:04d}{Path(page).suffix}")
                for previous in output.glob("page-*"):
                    previous.unlink()
                for new_page in ordered.iterdir():
                    os.replace(new_page, output / new_page.name)
                ordered.rmdir()
            if output.suffix.lower() != ".pdf" and (self.pending_delivery or self.pending_print):
                pdf_path = output / "Dokument-fuer-Versand.pdf"
                pdf = shell(["img2pdf", *map(str, pages), "-o", str(pdf_path)], timeout=180)
                if pdf.returncode:
                    raise RuntimeError(pdf.stderr or "Versand-PDF fehlgeschlagen.")
                self.pending_export_path = pdf_path
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
        self.status_var.set("Dokument abgeschlossen · " + str(len(self.pages)) + " Bildseiten")
        if self.pending_delivery is not None:
            target_id = self.pending_delivery
            self.pending_delivery = None
            export_path = self.pending_export_path or self.output_path
            self.pending_export_path = None
            threading.Thread(target=self.queue_export,
                             args=(export_path, target_id), daemon=True).start()
        if self.pending_print is not None:
            details = self.pending_print
            self.pending_print = None
            export_path = self.pending_export_path or self.output_path
            self.pending_export_path = None
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
        except (OSError, ValueError) as exc:
            self.status_var.set("Vorschaufehler: " + str(exc))

    def check_update(self):
        if self.busy or not self._allowed("update"):
            return
        self.status_var.set("GitHub wird geprüft …")
        threading.Thread(target=self.update_worker, args=(False,), daemon=True).start()

    def update_worker(self, apply):
        folder = Path(__file__).resolve().parent
        try:
            if not (folder / ".git").exists():
                raise RuntimeError("Keine Git-Installation. Bitte aus dem Repository starten.")
            origin = shell(["git", "-C", str(folder), "remote", "get-url", "origin"])
            if origin.returncode or "tojollinor/ItomiScan" not in origin.stdout:
                raise RuntimeError("Unerwartetes Git-Repository. Update abgebrochen.")
            # Development checkouts must never update against stable main.
            branch_name = shell(["git", "-C", str(folder),
                                 "branch", "--show-current"])
            if branch_name.returncode or branch_name.stdout.strip() != "main":
                raise RuntimeError(
                    "Updates sind nur im stabilen main-Zweig erlaubt. "
                    "Entwicklungsfassungen über Git verwalten.")
            if apply:
                dirty = shell(["git", "-C", str(folder), "status", "--porcelain"])
                if dirty.stdout.strip():
                    raise RuntimeError("Lokale Änderungen vorhanden. Update abgebrochen.")
                result = shell(["git", "-C", str(folder), "merge", "--ff-only",
                                "origin/main"], timeout=90)
                if result.returncode:
                    raise RuntimeError(result.stderr.strip() or "Update fehlgeschlagen.")
                self.dispatch(self.update_applied)
                return
            fetch = shell(["git", "-C", str(folder), "fetch", "origin", "main"], timeout=90)
            if fetch.returncode:
                raise RuntimeError(fetch.stderr.strip() or "GitHub nicht erreichbar.")
            count = shell(["git", "-C", str(folder), "rev-list",
                           "--count", "HEAD..origin/main"])
            if count.returncode:
                raise RuntimeError(count.stderr.strip())
            new_count = int(count.stdout.strip())
            if new_count:
                self.dispatch(lambda: self.offer_update(new_count))
            else:
                self.dispatch(lambda: self.status_var.set("ItomiScan ist aktuell"))
        except (OSError, RuntimeError, subprocess.TimeoutExpired, ValueError) as exc:
            message = str(exc)
            self.dispatch(lambda: messagebox.showerror("GitHub-Update", message, parent=self.root))

    def offer_update(self, count):
        self.status_var.set(f"{count} neue(r) Commit(s) verfügbar")
        if messagebox.askyesno("ItomiScan Update",
                               f"{count} Änderung(en) verfügbar.\nJetzt installieren?",
                               parent=self.root):
            threading.Thread(target=self.update_worker, args=(True,), daemon=True).start()

    def update_applied(self):
        self.status_var.set("Aktualisiert")
        if messagebox.askyesno("Update installiert",
                               "ItomiScan wurde aktualisiert.\nOberfläche jetzt neu starten?",
                               parent=self.root):
            os.execv(sys.executable,
                     [sys.executable, "-m", "itomiscan.gui.kiosk"])

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
