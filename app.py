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
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

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


def find_device():
    result = shell(["scanimage", "-L"])
    match = re.findall(r"device \x60([^\x27]+)\x27", result.stdout + result.stderr)
    return next((item for item in match if item.startswith(DEVICE_PREFIX)), None)


def read_options(device):
    result = shell(["scanimage", "-d", device, "--help"])
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
    def __init__(self, root):
        self.root = root
        self.root.title("ItomiScan")
        self.root.configure(bg=BASE)
        self.root.attributes("-fullscreen", True)
        self.root.bind("<Escape>", lambda e: None)
        self.busy = False
        self.device = None
        self.options = []
        self.fields = []
        self.pages = []
        self.page_index = 0
        self.photo = None
        self.tempdir = None
        self.output_path = None
        self.preview_size = (570, 470)
        self.status_var = tk.StringVar(value="Scanner wird gesucht …")
        self.ip_var = tk.StringVar(value="IP wird ermittelt …")
        self.page_var = tk.StringVar(value="Keine Vorschau")
        self.format_var = tk.StringVar(value="PDF")
        self._style()
        self._layout()
        self.root.after(200, self.load_scanner)
        self.refresh_ip()

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
        header = tk.Frame(self.root, bg=BASE, height=62)
        header.pack(fill="x", padx=20, pady=(10, 4))
        tk.Label(header, text="▣  ItomiScan", bg=BASE, fg=FG,
                 font=("DejaVu Sans", 24, "bold")).pack(side="left")
        tk.Label(header, textvariable=self.ip_var, bg=BASE, fg=MUTED,
                 font=("DejaVu Sans", 13)).pack(side="right", padx=8)
        body = tk.Frame(self.root, bg=BASE)
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
        sb = ttk.Scrollbar(holder, orient="vertical", command=self.canvas.yview)
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
        self.path_label = tk.Label(right, text="Noch keine Datei", bg=PANEL, fg=MUTED,
                                   font=("DejaVu Sans", 9), wraplength=590)
        self.path_label.pack(pady=(3, 12))

        footer = tk.Frame(self.root, bg=BASE)
        footer.pack(fill="x", padx=18, pady=(5, 13))
        self._btn(footer, "Beenden", self.exit).pack(side="left")
        self._btn(footer, "↻  Update", self.check_update).pack(side="left", padx=8)
        self.progress = ttk.Progressbar(footer, mode="indeterminate", length=90)
        self.progress.pack(side="left", padx=12)
        self.scan_button = self._btn(footer, "▣  SCANNEN", self.start_scan, BLUE, width=15)
        self.scan_button.pack(side="right")
        tk.Label(footer, textvariable=self.status_var, bg=BASE, fg=MUTED,
                 font=("DejaVu Sans", 10), wraplength=360).pack(side="right", padx=16)

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
            self.status_var.set("Bereit · " + self.device)
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
            if opt["inactive"]:
                control.configure(state="disabled")
            control.pack(fill="x", padx=3)
            self.fields.append((opt, variable))
        if not self.fields:
            tk.Label(self.option_frame, text="Keine Optionen erkannt",
                     bg=PANEL, fg=FG).pack(pady=20)

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
        threading.Thread(target=self.scan_worker, args=(settings, self.format_var.get()),
                         daemon=True).start()

    def scan_worker(self, settings, output_format):
        folder = Path(self.tempdir.name)
        cmd = ["scanimage", "-d", self.device, "--format=png",
               "--batch=page-%04d.png"] + settings
        try:
            result = shell(cmd, timeout=600, cwd=str(folder))
            scans = sorted(folder.glob("page-*.png"))
            if not scans:
                raise RuntimeError(result.stderr.strip() or "Kein Dokument eingezogen.")
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            target = Path.home() / "Scans" / ("ItomiScan_" + stamp)
            if target.exists():
                target = Path.home() / "Scans" / ("ItomiScan_" + stamp + "_" + str(os.getpid()))
            target.mkdir(parents=True, exist_ok=False)
            if output_format == "PDF":
                path = target / "Dokument.pdf"
                pdf = shell(["img2pdf", *map(str, scans), "-o", str(path)], timeout=180)
                if pdf.returncode != 0:
                    raise RuntimeError("PDF-Erstellung: " + (pdf.stderr or pdf.stdout))
            else:
                for scan in scans:
                    shutil.copy2(scan, target / scan.name)
                path = target
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
        self.page_index = 0
        self.output_path = path
        self.path_label.configure(text="Gespeichert: " + str(path))
        self.show_page()
        self.status_var.set(str(len(images)) + " Bildseite(n) gescannt")
        if warning:
            messagebox.showwarning("Scannerhinweis", warning[-600:], parent=self.root)

    def scan_failed(self, msg):
        self.busy = False
        self.scan_button.configure(state="normal")
        self.progress.stop()
        self.status_var.set("Scan fehlgeschlagen")
        messagebox.showerror("Scannerfehler", msg[-800:], parent=self.root)

    def change_page(self, diff):
        if self.pages:
            self.page_index = max(0, min(len(self.pages) - 1, self.page_index + diff))
            self.show_page()

    def show_page(self):
        if not self.pages:
            return
        try:
            with Image.open(self.pages[self.page_index]) as src:
                image = src.convert("RGB")
            self.root.update_idletasks()
            width = max(240, self.preview.winfo_width() - 25)
            height = max(200, self.preview.winfo_height() - 25)
            image.thumbnail((width, height), Image.Resampling.LANCZOS)
            self.photo = ImageTk.PhotoImage(image)
            self.preview.configure(image=self.photo, text="")
            self.page_var.set(f"Seite {self.page_index + 1} / {len(self.pages)}")
        except (OSError, ValueError) as exc:
            self.status_var.set("Vorschaufehler: " + str(exc))

    def check_update(self):
        if self.busy:
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
            os.execv(sys.executable, [sys.executable, str(Path(__file__).resolve())])

    def exit(self):
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
