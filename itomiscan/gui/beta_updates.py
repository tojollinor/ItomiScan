"""ItomiScan beta update UI. No privileged operations in this module."""
import json
from pathlib import Path
import re
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from urllib.request import Request, urlopen

from itomiscan.gui.home import BASE, PANEL, FG, MUTED, BLUE

HELPER = "/usr/local/libexec/itomiscan-beta-updater"
API = "https://api.github.com/repos/tojollinor/ItomiScan/"
TAG = re.compile(r"^v[0-9]+\.[0-9]+\.[0-9]+-beta\.[0-9]+$")
SHA = re.compile(r"^[0-9a-f]{40}$")


def api_json(endpoint, opener=urlopen):
    request = Request(API + endpoint, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "ItomiScan-Beta-Checker"})
    with opener(request, timeout=25) as response:
        return json.load(response)


def beta_number(tag):
    return tuple(map(int, tag[1:].replace("-beta.", ".").split(".")))


def latest_published_beta(opener=urlopen):
    rows = api_json("releases?per_page=30", opener)
    if not isinstance(rows, list):
        raise ValueError("Ungültige Release-Liste.")
    candidates = []
    for row in rows:
        tag = row.get("tag_name", "")
        if (isinstance(tag, str) and TAG.fullmatch(tag)
                and row.get("prerelease") and not row.get("draft")):
            candidates.append((beta_number(tag), tag))
    if not candidates:
        raise ValueError("Kein veröffentlichtes Beta-Release gefunden.")
    tag = max(candidates)[1]
    sha = api_json("commits/" + tag, opener).get("sha")
    if not isinstance(sha, str) or not SHA.fullmatch(sha):
        raise ValueError("GitHub-Commit ungültig.")
    return tag, sha


def installed_version(project):
    project = Path(project)
    commit = project / ".itomiscan-beta-commit"
    tag = project / ".itomiscan-beta-tag"
    return (commit.read_text(encoding="ascii").strip() if commit.is_file() else "",
            tag.read_text(encoding="ascii").strip() if tag.is_file() else "")


class BetaUpdateDialog:
    def __init__(self, app):
        self.app = app
        self.project = Path(__file__).resolve().parents[2]
        self.dialog = tk.Toplevel(app.root)
        self.dialog.title("Updates")
        self.dialog.configure(bg=BASE)
        self.dialog.transient(app.root)
        app._center_dialog(self.dialog, 620, 480)
        self.dialog.grab_set()
        self.working = False
        self.candidate = None
        tk.Label(self.dialog, text="ItomiScan Updates", bg=BASE, fg=FG,
                 font=("DejaVu Sans", 22, "bold")).pack(pady=(17, 7))
        sha, tag = installed_version(self.project)
        tk.Label(self.dialog,
                 text="Installiert: " + (tag or sha[:10] or "unbekannt"),
                 bg=BASE, fg=MUTED, font=("DejaVu Sans", 12)).pack(pady=3)
        self.beta = tk.BooleanVar(value=True)
        self.channel = tk.Checkbutton(
            self.dialog, text="Beta-Releases einschließen", variable=self.beta,
            command=self.change_channel, bg=BASE, fg=FG, selectcolor=PANEL,
            activebackground=BASE, activeforeground=FG,
            font=("DejaVu Sans", 13), padx=12, pady=8)
        self.channel.pack()
        self.notice = tk.StringVar(value="Bitte nach Updates suchen.")
        tk.Label(self.dialog, textvariable=self.notice, bg=BASE, fg=MUTED,
                 wraplength=530, height=3, justify="center",
                 font=("DejaVu Sans", 11)).pack(pady=4)
        self.percentage = tk.IntVar(value=0)
        ttk.Progressbar(self.dialog, orient="horizontal", maximum=100,
                        variable=self.percentage).pack(fill="x", padx=35, pady=6)
        self.check_button = app._btn(
            self.dialog, "Auf Updates prüfen", self.start_check, BLUE)
        self.install_button = app._btn(
            self.dialog, "Beta installieren", self.install, BLUE)
        self.rollback_button = app._btn(
            self.dialog, "Letztes Update rückgängig machen", self.rollback)
        self.restart_button = app._btn(
            self.dialog, "Jetzt neu starten", self.app.restart)
        self.close_button = app._btn(self.dialog, "Schließen", self.close)
        for button in (self.check_button, self.install_button,
                       self.rollback_button, self.restart_button):
            button.pack(fill="x", padx=35, pady=3)
        self.close_button.pack(side="bottom", fill="x", padx=35, pady=8)
        self.install_button.configure(state=tk.DISABLED)
        self.restart_button.configure(state=tk.DISABLED)
        self.rollback_button.configure(state=tk.NORMAL if Path(HELPER).is_file()
                                       else tk.DISABLED)
        self.dialog.protocol("WM_DELETE_WINDOW", self.close)

    def close(self):
        if self.working:
            self.notice.set("Bitte die laufende Installation abschließen lassen.")
        else:
            self.dialog.destroy()

    def change_channel(self):
        self.candidate = None
        self.percentage.set(0)
        self.install_button.configure(state=tk.DISABLED)
        self.notice.set("Bitte nach Updates suchen." if self.beta.get() else
                        "Stable-Releases werden nur angezeigt, nicht automatisch installiert.")

    def publish(self, message, percent=None):
        def update():
            if not self.dialog.winfo_exists():
                return
            self.notice.set(str(message)[:340])
            self.app.status_var.set(str(message)[:180])
            if percent is not None:
                self.percentage.set(max(0, min(100, int(percent))))
        self.app.dispatch(update)

    def start_check(self):
        if self.working or not self.app._allowed("update"):
            return
        beta = self.beta.get()
        self.candidate = None
        self.install_button.configure(state=tk.DISABLED)
        self.check_button.configure(state=tk.DISABLED)
        self.notice.set("Suche nach veröffentlichten Updates …")

        def worker():
            candidate = None
            try:
                if beta:
                    tag, sha = latest_published_beta()
                    local_sha, local_tag = installed_version(self.project)
                    newer = (local_sha != sha and not (
                        TAG.fullmatch(local_tag) and
                        beta_number(local_tag) >= beta_number(tag)))
                    if not newer:
                        message = "Beta ist aktuell (" + tag + ")."
                    elif not Path(HELPER).is_file():
                        message = ("Neue Beta " + tag + " verfügbar. "
                                   "Installationshilfe fehlt: einmalig neuen "
                                   "Beta-Installer per SSH ausführen.")
                    else:
                        message = "Neue Beta verfügbar: " + tag + " (" + sha[:10] + ")."
                        candidate = (tag, sha)
                else:
                    release = api_json("releases/latest")
                    message = ("Stable: " + release.get("tag_name", "?") +
                               ". Stable-Installation bleibt separat.")
            except Exception as exc:
                message = "Updateprüfung fehlgeschlagen: " + str(exc)

            def finish():
                if self.dialog.winfo_exists():
                    self.candidate = candidate
                    self.notice.set(message[:340])
                    self.check_button.configure(state=tk.NORMAL)
                    self.install_button.configure(
                        state=tk.NORMAL if candidate else tk.DISABLED)
            self.app.dispatch(finish)
        threading.Thread(target=worker, daemon=True, name="itomiscan-beta-check").start()

    def install(self):
        if self.working or not self.candidate or not self.app._allowed("update"):
            return
        tag = self.candidate[0]
        if messagebox.askyesno(
            "Beta installieren",
            "Neueste veröffentlichte Beta installieren?\n\n"
            "Angezeigt: " + tag + "\n"
            "Der Update-Dienst ermittelt vor dem Start erneut das neueste Release.\n"
            "Bisherige Installation wird gesichert; danach ist ein Neustart nötig.\n"
            "Währenddessen bitte keinen Scan starten.",
            icon="warning", parent=self.dialog):
            self.run_helper("install")

    def rollback(self):
        if self.working or not self.app._allowed("update"):
            return
        if messagebox.askyesno(
            "Letztes Update rückgängig machen",
            "Letzte gesicherte Programmversion wiederherstellen?\n"
            "Scans, Einstellungen und Zustellaufträge bleiben erhalten.\n"
            "Anschließend ist ein Neustart erforderlich.",
            icon="warning", parent=self.dialog):
            self.run_helper("rollback")

    def run_helper(self, operation):
        if self.working or operation not in ("install", "rollback"):
            return
        if not Path(HELPER).is_file():
            self.notice.set("Installationshilfe fehlt. Einmalig über SSH einrichten.")
            return
        self.working = True
        self.app.busy = True
        self.percentage.set(0)
        self.notice.set("Update wird vorbereitet …")
        for button in (self.check_button, self.install_button,
                       self.rollback_button, self.restart_button, self.close_button):
            button.configure(state=tk.DISABLED)
        self.channel.configure(state=tk.DISABLED)

        def worker():
            last = ""
            success = False
            try:
                proc = subprocess.Popen(
                    ["sudo", "-n", HELPER, operation],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace", bufsize=1)
                for raw in proc.stdout:
                    line = raw.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        last = str(data["message"])
                        success = data.get("state") == "success"
                        self.publish(last, data.get("percent"))
                    except (ValueError, KeyError, TypeError):
                        last = line[-340:]
                        self.publish(last)
                code = proc.wait()
                if code != 0:
                    success = False
                    if not last:
                        last = "Updater beendet mit Fehlercode " + str(code)
            except OSError as exc:
                last = "Updater nicht ausführbar: " + str(exc)

            def finish():
                self.working = False
                self.app.busy = False
                if not self.dialog.winfo_exists():
                    return
                self.channel.configure(state=tk.NORMAL)
                self.check_button.configure(state=tk.NORMAL)
                self.close_button.configure(state=tk.NORMAL)
                self.rollback_button.configure(state=tk.NORMAL)
                if success:
                    self.candidate = None
                    self.install_button.configure(state=tk.DISABLED)
                    self.restart_button.configure(
                        state=tk.NORMAL if self.app._allowed("shutdown", silent=True)
                        else tk.DISABLED)
                    self.notice.set(last or "Update abgeschlossen. Neustart erforderlich.")
                else:
                    self.install_button.configure(
                        state=tk.NORMAL if self.candidate else tk.DISABLED)
                    self.notice.set(last or "Update fehlgeschlagen. Installation unverändert.")
            self.app.dispatch(finish)
        threading.Thread(target=worker, daemon=True, name="itomiscan-beta-install").start()
