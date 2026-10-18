"""Minimal low-power N1800 idle screen with manual preview control."""
import time
import tkinter as tk

from itomiscan import branding
from itomiscan.gui.home import draw_logo

BG = "#060c14"
WHITE = branding.WHITE
MUTED = branding.MUTED
CYAN = branding.CYAN


class IdleScreen:
    def __init__(self, root, busy, seconds=300, on_timeout=None, logout_delay=30):
        self.root = root
        self.busy = busy
        self.seconds = seconds
        self.on_timeout = on_timeout
        self.logout_delay = logout_delay
        self.started_at = None
        self.logout_done = False
        self.last = time.monotonic()
        self.active = False
        self.frame = tk.Frame(root, bg=BG)
        self.clock = tk.StringVar(value="")

        draw_logo(self.frame, 110, background=BG).pack(pady=(142, 15))
        brand = tk.Frame(self.frame, bg=BG)
        brand.pack(pady=(0, 19))
        tk.Label(brand, text="Itomi", fg=WHITE, bg=BG,
                 font=("DejaVu Sans", 30, "bold")).pack(side="left")
        tk.Label(brand, text="Scan", fg=CYAN, bg=BG,
                 font=("DejaVu Sans", 30, "bold")).pack(side="left")
        tk.Label(self.frame, textvariable=self.clock, fg=WHITE, bg=BG,
                 font=("DejaVu Sans", 26)).pack()
        tk.Label(self.frame, text="Zum Aktivieren den Bildschirm berühren",
                 fg=MUTED, bg=BG, font=("DejaVu Sans", 12)).pack(pady=30)
        self.frame.bind("<ButtonPress>", self.wake_event)
        self.frame.bind("<KeyPress>", self.wake_event)
        for child in self.frame.winfo_children():
            child.bind("<ButtonPress>", self.wake_event)
            for grandchild in child.winfo_children():
                grandchild.bind("<ButtonPress>", self.wake_event)
        self.root.bind_all("<ButtonPress>", self.activity, add="+")
        self.root.bind_all("<KeyPress>", self.activity, add="+")
        self.root.after(1000, self.tick)

    def activity(self, _event=None):
        self.last = time.monotonic()

    def wake_event(self, _event=None):
        self.wake()
        return "break"

    def wake(self):
        self.last = time.monotonic()
        if self.active:
            self.active = False
            self.started_at = None
            self.logout_done = False
            self.frame.place_forget()

    def _show(self):
        if self.active:
            return
        self.started_at = time.monotonic()
        self.logout_done = False
        self.active = True
        self.clock.set(time.strftime("%H:%M"))
        self.frame.place(x=0, y=0, relwidth=1, relheight=1)
        self.frame.lift()

    def show_now(self):
        """Manual preview; protect active scan operations."""
        if self.busy():
            return False
        self.last = time.monotonic()
        self._show()
        return True

    def tick(self):
        try:
            if not self.root.winfo_exists():
                return
            if self.active:
                self.clock.set(time.strftime("%H:%M"))
                if (not self.logout_done and self.on_timeout is not None
                        and self.started_at is not None
                        and time.monotonic() - self.started_at >= self.logout_delay
                        and not self.busy()):
                    if self.on_timeout():
                        self.logout_done = True
                    self.frame.lift()
            elif not self.busy() and time.monotonic() - self.last >= self.seconds:
                self._show()
            self.root.after(1000, self.tick)
        except tk.TclError:
            pass
