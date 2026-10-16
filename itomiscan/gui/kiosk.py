"""Start splash first, then construct the existing scanner GUI when ready."""

import logging
import queue
import sys
import time
import subprocess
import threading
import tkinter as tk

from itomiscan.core.startup import StartupFailure, wait_until_ready
from itomiscan.gui.splash import StartupSplash

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s itomiscan.kiosk: %(message)s", stream=sys.stderr)
LOG = logging.getLogger("itomiscan.kiosk")

def _boot_marker(stage):
    """Persist Linux uptime for comparing splash and UI readiness."""
    try:
        from pathlib import Path
        uptime = float(Path("/proc/uptime").read_text(encoding="ascii").split()[0])
        path = Path.home() / ".local" / "state" / "itomiscan" / "boot-timing.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as log:
            log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} uptime={uptime:.3f}s {stage}\n")
        LOG.info("Bootmessung: %s nach %.3fs", stage, uptime)
    except (OSError, ValueError) as exc:
        LOG.warning("Bootzeitmarke nicht verfuegbar: %s", exc)



def _timed_probe(label, callback, timeout):
    started = time.monotonic()
    LOG.info("%s gestartet (Timeout %ss)", label, timeout)
    try:
        result = callback()
    except subprocess.TimeoutExpired as exc:
        LOG.error("%s Timeout nach %.2fs: %s", label, time.monotonic() - started, exc)
        raise RuntimeError(f"{label}: Zeitlimit von {timeout}s überschritten.") from exc
    except Exception:
        LOG.exception("%s fehlgeschlagen nach %.2fs", label, time.monotonic() - started)
        raise
    LOG.info("%s erfolgreich nach %.2fs", label, time.monotonic() - started)
    return result


def detect_scanner():
    from app import find_device
    return _timed_probe("SANE-Geräteerkennung", lambda: find_device(timeout=30), 30)


def detect_options(device):
    from app import read_options
    return _timed_probe("SANE-Optionen", lambda: read_options(device, timeout=30), 30)


class KioskStartup:
    def __init__(self, root):
        self.root = root
        self.root.configure(bg="#101927")
        self.root.overrideredirect(True)
        self.root.geometry(f"{root.winfo_screenwidth()}x{root.winfo_screenheight()}+0+0")
        self.events = queue.Queue()
        self.running = True
        self.attempt = 0
        self.active = False
        self.splash = StartupSplash(root, retry=self.retry, exit_app=root.destroy)
        self.root.after(120, self.poll)
        self.root.after_idle(lambda: _boot_marker("splash_angezeigt"))
        self.root.after(160, self.retry)

    def retry(self):
        if self.active or not self.running:
            return
        self.attempt += 1
        attempt = self.attempt
        self.active = True
        self.splash.loading()
        LOG.info("Startversuch %s", attempt)
        thread = threading.Thread(target=self.worker, args=(attempt,), daemon=True)
        thread.start()

    def worker(self, attempt):
        try:
            result = wait_until_ready(
                detect_scanner, detect_options,
                lambda step, msg: self.events.put((attempt, "stage", step, msg)),
                timeout=90,
            )
        except StartupFailure as exc:
            LOG.error("Startversuch %s fehlgeschlagen: %s | %s", attempt, exc, exc.detail)
            self.events.put((attempt, "failure", str(exc), exc.detail))
        except Exception as exc:
            LOG.exception("Unerwarteter Fehler bei Startversuch %s", attempt)
            self.events.put((attempt, "failure", "Scannerstart fehlgeschlagen.",
                             str(exc)))
        else:
            LOG.info("Startversuch %s erfolgreich: %s, %s Optionen", attempt, result[0], len(result[1]))
            self.events.put((attempt, "ready", result[0], result[1]))

    def poll(self):
        if not self.running:
            return
        try:
            while True:
                attempt, kind, a, b = self.events.get_nowait()
                if attempt != self.attempt:
                    continue
                if kind == "stage":
                    self.splash.stage(a, b)
                elif kind == "failure":
                    self.active = False
                    self.splash.failure(a, b)
                elif kind == "ready":
                    from app import ItomiScan
                    # Build the complete interface behind the splash;
                    # remove the covering frame only once Tk has laid it out.
                    try:
                        ItomiScan(self.root, initial_device=a, initial_options=b)
                        # Keep the startup overlay above newly constructed views.
                        self.splash.frame.lift()
                        self.root.update_idletasks()
                    except Exception as exc:
                        LOG.exception("Hauptoberfläche konnte nicht aufgebaut werden")
                        self.active = False
                        self.splash.frame.lift()
                        self.splash.failure(
                            "Oberfläche konnte nicht gestartet werden.", str(exc))
                        continue
                    self.running = False
                    self.active = False
                    self.splash.destroy()
                    self.root.update_idletasks()
                    _boot_marker("oberflaeche_bereit")
                    return
        except queue.Empty:
            pass
        self.root.after(120, self.poll)


def main():
    _boot_marker("kiosk_start")
    root = tk.Tk()
    KioskStartup(root)
    root.mainloop()


if __name__ == "__main__":
    main()
