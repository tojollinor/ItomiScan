"""Start splash first, then construct the existing scanner GUI when ready."""

import queue
import subprocess
import threading
import tkinter as tk

from itomiscan.core.startup import StartupFailure, wait_until_ready
from itomiscan.gui.splash import StartupSplash


def detect_scanner():
    from app import find_device
    try:
        return find_device(timeout=8)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("SANE-Geräteerkennung benötigt zu lange.") from exc


def detect_options(device):
    from app import read_options
    try:
        return read_options(device, timeout=12)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("SANE-Optionen konnten nicht rechtzeitig gelesen werden.") from exc


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
        self.root.after(160, self.retry)

    def retry(self):
        if self.active or not self.running:
            return
        self.attempt += 1
        attempt = self.attempt
        self.active = True
        self.splash.loading()
        thread = threading.Thread(target=self.worker, args=(attempt,), daemon=True)
        thread.start()

    def worker(self, attempt):
        try:
            result = wait_until_ready(
                detect_scanner, detect_options,
                lambda step, msg: self.events.put((attempt, "stage", step, msg)),
                timeout=45,
            )
        except StartupFailure as exc:
            self.events.put((attempt, "failure", str(exc), exc.detail))
        except Exception as exc:
            self.events.put((attempt, "failure", "Scannerstart fehlgeschlagen.",
                             str(exc)))
        else:
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
                    ItomiScan(self.root, initial_device=a, initial_options=b)
                    self.root.update_idletasks()
                    self.running = False
                    self.active = False
                    self.splash.destroy()
                    return
        except queue.Empty:
            pass
        self.root.after(120, self.poll)


def main():
    root = tk.Tk()
    KioskStartup(root)
    root.mainloop()


if __name__ == "__main__":
    main()
