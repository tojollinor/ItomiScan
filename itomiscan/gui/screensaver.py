"""Minimal idle dim-screen for low-powered N1800 display.

Never activates during a scan or modal dialog; wakes on tap or key.
"""
import time
import tkinter as tk

BG = "#060c14"
WHITE = "#f1f5fb"
MUTED = "#a8bacd"


class IdleScreen:
    def __init__(self, root, busy, seconds=300):
        self.root = root
        self.busy = busy
        self.seconds = seconds
        self.last = time.monotonic()
        self.active = False
        self.frame = tk.Frame(root, bg=BG)
        self.clock = tk.StringVar(value="")
        tk.Label(self.frame, text="ItomiScan", fg=WHITE, bg=BG,
                 font=("DejaVu Sans", 30, "bold")).pack(pady=(220, 26))
        tk.Label(self.frame, textvariable=self.clock, fg=WHITE, bg=BG,
                 font=("DejaVu Sans", 26)).pack()
        tk.Label(self.frame, text="Zum Aktivieren den Bildschirm berühren",
                 fg=MUTED, bg=BG, font=("DejaVu Sans", 12)).pack(pady=30)
        self.frame.bind("<ButtonPress>", self.wake_event)
        self.frame.bind("<KeyPress>", self.wake_event)
        for child in self.frame.winfo_children():
            child.bind("<ButtonPress>", self.wake_event)
        self.root.bind_all("<ButtonPress>", self.activity, add="+")
        self.root.bind_all("<KeyPress>", self.activity, add="+")
        self.root.after(10000, self.tick)

    def activity(self, _event=None):
        self.last = time.monotonic()
        # On the cover the child's own binding handles dismissal and stops
        # that first tap from activating something underneath.

    def wake_event(self, _event=None):
        self.wake()
        return "break"

    def wake(self):
        self.last = time.monotonic()
        if self.active:
            self.active = False
            self.frame.place_forget()

    def tick(self):
        try:
            if not self.root.winfo_exists():
                return
            if self.active:
                self.clock.set(time.strftime("%H:%M"))
            elif (not self.busy() and not self.root.grab_current()
                  and time.monotonic() - self.last >= self.seconds):
                self.active = True
                self.clock.set(time.strftime("%H:%M"))
                self.frame.place(x=0, y=0, relwidth=1, relheight=1)
                self.frame.lift()
            self.root.after(10000, self.tick)
        except tk.TclError:
            pass
