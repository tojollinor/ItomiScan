"""Single-purpose, touch-friendly PIN gate for 1024x768 N1800 kiosk."""
import tkinter as tk

from itomiscan.gui.home import BASE, CARD, CYAN, FG, MUTED, draw_logo


class PinScreen:
    def __init__(self, root, verify):
        self.root = root
        self.verify = verify
        self.digits = ""
        self.active = False
        self.frame = tk.Frame(root, bg=BASE)
        self.frame.columnconfigure(0, weight=1)
        # Grow the information row, keeping the actual keypad in the
        # lower half of the 1024x768 touchscreen.
        self.frame.rowconfigure(2, weight=1)
        self.frame.rowconfigure(3, minsize=420)
        top = tk.Frame(self.frame, bg=BASE)
        top.grid(row=0, column=0, pady=(28, 5))
        draw_logo(top, 56).pack(side="left", padx=13)
        tk.Label(top, text="ItomiScan", bg=BASE, fg=FG,
                 font=("DejaVu Sans", 27, "bold")).pack(side="left")
        tk.Label(self.frame, text="Bitte PIN eingeben", bg=BASE, fg=FG,
                 font=("DejaVu Sans", 21, "bold")).grid(row=1, column=0, pady=8)
        middle = tk.Frame(self.frame, bg=BASE)
        middle.grid(row=2, column=0, sticky="n")
        self.mask = tk.StringVar(value="○  ○  ○  ○  ○  ○")
        tk.Label(middle, textvariable=self.mask, bg=BASE, fg=CYAN,
                 font=("DejaVu Sans", 26, "bold")).pack(pady=(7, 5))
        self.notice = tk.StringVar(value="Persönliche PIN mit 4 bis 6 Ziffern")
        tk.Label(middle, textvariable=self.notice, bg=BASE, fg=MUTED,
                 font=("DejaVu Sans", 12), wraplength=700).pack(pady=(0, 12))
        keypad = tk.Frame(self.frame, bg=BASE)
        keypad.grid(row=3, column=0, sticky="n", pady=(0, 12))
        keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "C", "0", "OK"]
        for i, key in enumerate(keys):
            row, column = divmod(i, 3)
            button = tk.Button(
                keypad, text=key, command=lambda digit=key: self.press(digit),
                font=("DejaVu Sans", 25, "bold"), bg=CYAN if key == "OK" else CARD,
                fg=BASE if key == "OK" else FG,
                activebackground="#54d5fa", relief="flat", borderwidth=0,
                width=6, height=1, pady=12, cursor="none",
            )
            button.grid(row=row, column=column, padx=9, pady=5, sticky="nsew")
        self.frame.bind_all("<BackSpace>", self.backspace, add="+")

    def backspace(self, _event=None):
        if self.active:
            self.digits = self.digits[:-1]
            self._mask()
            return "break"

    def press(self, digit):
        if not self.active:
            return
        if digit == "C":
            self.digits = ""
        elif digit == "OK":
            if not 4 <= len(self.digits) <= 6:
                self.notice.set("Bitte 4 bis 6 Ziffern eingeben.")
                return
            candidate = self.digits
            self.digits = ""
            self._mask()
            self.notice.set("PIN wird geprüft …")
            self.root.update_idletasks()
            self.verify(candidate)
            return
        elif digit.isdigit() and len(self.digits) < 6:
            self.digits += digit
        self._mask()

    def _mask(self):
        self.mask.set("  ".join("●" if index < len(self.digits) else "○"
                                for index in range(6)))

    def show(self, message="Persönliche PIN mit 4 bis 6 Ziffern"):
        self.digits = ""
        self._mask()
        self.notice.set(message)
        self.active = True
        self.frame.place(x=0, y=0, relwidth=1, relheight=1)
        self.frame.lift()

    def hide(self):
        self.digits = ""
        self._mask()
        self.active = False
        self.frame.place_forget()

    def error(self, message="PIN nicht erkannt. Bitte erneut versuchen."):
        self.digits = ""
        self._mask()
        self.notice.set(message)
