"""Single full-screen, touch-friendly device menu for the N1800.

Both home and scan-detail screens use this page instead of separate dialogs.
The previous screen remains behind the page and is restored on Back.
"""
import tkinter as tk

from itomiscan.gui.home import BASE, CARD, BLUE, FG, MUTED, draw_logo


class DeviceMenu:
    def __init__(self, root):
        self.root = root
        self.frame = None
        self.buttons = {}

    @property
    def visible(self):
        return bool(self.frame and self.frame.winfo_exists())

    def hide(self):
        if self.visible:
            self.frame.destroy()
        self.frame = None
        self.buttons = {}

    def show(self, actions):
        """Show already-authorized (label, callback) pairs as full-screen tiles."""
        self.hide()
        page = tk.Frame(self.root, bg=BASE)
        self.frame = page
        page.place(x=0, y=0, relwidth=1, relheight=1)
        page.lift()

        back = tk.Button(
            page, text="← Zurück", command=self.hide,
            font=("DejaVu Sans", 13, "bold"), bg=CARD, fg=FG,
            activebackground=BLUE, relief="flat", bd=0, cursor="none",
            padx=18, pady=10)
        back.pack(side="bottom", anchor="w", padx=35, pady=16)
        header = tk.Frame(page, bg=BASE)
        header.pack(fill="x", padx=28, pady=18)
        draw_logo(header, 52).pack(side="left", padx=12)
        tk.Label(header, text="Menü", bg=BASE, fg=FG,
                 font=("DejaVu Sans", 24, "bold")).pack(side="left")

        grid = tk.Frame(page, bg=BASE)
        grid.pack(fill="both", expand=True, padx=30, pady=12)
        for col in range(2):
            grid.grid_columnconfigure(col, weight=1, uniform="menu")
        for row in range(3):
            grid.grid_rowconfigure(row, weight=1, minsize=182)
        for index, (label, fn) in enumerate(actions[:6]):
            def activate(callback=fn):
                self.hide()
                callback()

            card = tk.Frame(grid, bg=CARD)
            card.grid(row=index // 2, column=index % 2, sticky="nsew",
                      padx=7, pady=7)
            button = tk.Button(
                card, text=label, command=activate,
                font=("DejaVu Sans", 17, "bold"), bg=CARD, fg=FG,
                activebackground=BLUE, activeforeground=FG,
                relief="flat", bd=0, cursor="none", padx=12, pady=13)
            button.pack(fill="both", expand=True, padx=4, pady=4)
            self.buttons[label] = button
        return page
