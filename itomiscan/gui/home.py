"""Large touch-oriented 1024x768 home screen; only local scanning is live."""
import tkinter as tk
from tkinter import ttk

BASE = "#101927"
CARD = "#192738"
CARD_HOVER = "#24405b"
FG = "#f1f5fb"
MUTED = "#a8bacd"
CYAN = "#42bfea"
BLUE = "#397edb"


def draw_logo(parent, size=68):
    """Solid two-colour N1800-friendly rendition of the approved scan icon."""
    canvas = tk.Canvas(parent, width=size, height=size,
                       bg=BASE, bd=0, highlightthickness=0)
    factor = size / 72
    def scaled(coords):
        return tuple(round(v * factor) for v in coords)
    canvas.create_rectangle(*scaled((1, 1, 71, 71)), fill="#073d81",
                            outline="")
    canvas.create_polygon(*scaled((23, 15, 44, 15, 52, 23, 52, 58, 23, 58)),
                          fill="white", outline="")
    canvas.create_rectangle(*scaled((15, 36, 57, 40)), fill=CYAN, outline="")
    for x, y, dx, dy in ((13, 13, 8, 8), (59, 13, -8, 8),
                         (13, 59, 8, -8), (59, 59, -8, -8)):
        canvas.create_line(*scaled((x, y + dy, x, y, x + dx, y)),
                           fill=CYAN, width=max(3, round(4 * factor)))
    return canvas


class HomeScreen:
    """No remote actions here: unavailable destinations are explicitly labelled."""

    def __init__(self, root, profiles, select_profile, open_scan, quick_scan,
                 unavailable, shutdown, update, exit_app, status, logout=None,
                 deliver=None):
        self.root = root
        self.profiles = profiles
        self.select_profile = select_profile
        self.open_scan = open_scan
        self.quick_scan = quick_scan
        self.unavailable = unavailable
        self.deliver = deliver or (lambda _kind: None)
        self.logout = logout
        self.allowed = None
        self.tiles = {}
        self.controls = {}
        self.frame = tk.Frame(root, bg=BASE)
        self.selected_var = tk.StringVar(value=profiles.selected)
        self._build(shutdown, update, exit_app, status)

    def _button(self, parent, text, command, bg=CARD, font=14,
                pad_y=12, width=None):
        return tk.Button(parent, text=text, command=command,
                         font=("DejaVu Sans", font, "bold"),
                         bg=bg, fg=FG, activebackground=CARD_HOVER,
                         activeforeground=FG, relief="flat", bd=0,
                         padx=12, pady=pad_y, cursor="hand2", width=width)

    def _build(self, shutdown, update, exit_app, status):
        header = tk.Frame(self.frame, bg=BASE)
        header.pack(fill="x", padx=28, pady=(18, 6))
        draw_logo(header, 64).pack(side="left", padx=(0, 16))
        brand = tk.Frame(header, bg=BASE)
        brand.pack(side="left", anchor="w")
        title = tk.Frame(brand, bg=BASE)
        title.pack(anchor="w")
        tk.Label(title, text="Itomi", bg=BASE, fg=FG,
                 font=("DejaVu Sans", 28, "bold")).pack(side="left")
        tk.Label(title, text="Scan", bg=BASE, fg=CYAN,
                 font=("DejaVu Sans", 28, "bold")).pack(side="left")
        tk.Label(brand, text="Dokumentenscanner", bg=BASE, fg=MUTED,
                 font=("DejaVu Sans", 11)).pack(anchor="w")
        self.user_var = tk.StringVar(value="")
        tk.Label(header, textvariable=self.user_var, bg=BASE, fg=CYAN,
                 font=("DejaVu Sans", 13, "bold")).pack(side="right", padx=10)
        tk.Label(header, textvariable=status, bg=BASE, fg="#90d9ba",
                 font=("DejaVu Sans", 10), wraplength=285,
                 justify="right").pack(side="right", anchor="n", padx=6)

        tiles = tk.Frame(self.frame, bg=BASE)
        tiles.pack(fill="both", expand=True, padx=30, pady=(12, 8))
        for i in range(2):
            tiles.grid_columnconfigure(i, weight=1, uniform="actions")
            tiles.grid_rowconfigure(i, weight=1, uniform="actions")
        actions = (
            ("scan", "SCAN", "Scannen", "PDF oder Bild speichern", True, self.open_scan),
            ("paperless", "ARCHIV", "Paperless", "PDF an Archiv senden", True,
             lambda: self.deliver("paperless")),
            ("copy", "KOPIE", "Kopieren", "In Vorbereitung", False,
             lambda: self.unavailable("copy", "Kopieren", 7)),
            ("network", "NETZ", "Netzwerkordner", "PDF ins Netzwerk", True,
             lambda: self.deliver("network")),
        )
        for index, (permission, short, title, subtitle, enabled, command) in enumerate(actions):
            row, column = divmod(index, 2)
            card = tk.Frame(tiles, bg=CARD, bd=0)
            card.grid(row=row, column=column, padx=8, pady=8, sticky="nsew")
            self.tiles[permission] = card
            tk.Label(card, text=short, bg=CARD,
                     fg=CYAN if enabled else MUTED,
                     font=("DejaVu Sans", 10, "bold")).pack(pady=(12, 0))
            self._button(card, title, command, bg=CARD, font=21,
                         pad_y=19).pack(fill="both", expand=True, padx=10)
            tk.Label(card, text=subtitle, bg=CARD, fg=MUTED,
                     font=("DejaVu Sans", 11)).pack(pady=(0, 17))

        profiles = tk.Frame(self.frame, bg=CARD)
        profiles.pack(fill="x", padx=37, pady=(2, 12))
        self.controls["profile_bar"] = profiles
        tk.Label(profiles, text="Scanprofil", bg=CARD, fg=FG,
                 font=("DejaVu Sans", 13, "bold")).pack(side="left", padx=(18, 10))
        self.profile_select = ttk.Combobox(profiles, textvariable=self.selected_var,
                                           values=self.profiles.names(),
                                           state="readonly", width=15,
                                           font=("DejaVu Sans", 13))
        self.profile_select.pack(side="left", padx=5, pady=12)
        self.profile_select.bind("<<ComboboxSelected>>", self._selected)
        self._button(profiles, "Jetzt scannen", self.quick_scan,
                     bg=BLUE, font=15, pad_y=12).pack(side="right", padx=12, pady=5)

        bottom = tk.Frame(self.frame, bg=BASE)
        self.controls["footer"] = bottom
        bottom.pack(fill="x", padx=31, pady=(0, 18))
        self.controls["other"] = self._button(
            bottom, "E-Mail / USB", lambda: self.deliver("other"), font=11, pad_y=7)
        self.controls["other"].pack(side="left", padx=4)
        self.controls["exit"] = self._button(bottom, "Beenden", exit_app, font=11,
                                             pad_y=7)
        self.controls["exit"].pack(side="left", padx=4)
        self.controls["update"] = self._button(bottom, "Update", update, font=11,
                                               pad_y=7)
        self.controls["update"].pack(side="left", padx=4)
        self.controls["shutdown"] = self._button(bottom, "Ausschalten", shutdown,
                                                 font=11, pad_y=7)
        self.controls["shutdown"].pack(side="right", padx=4)
        self.controls["logout"] = self._button(
            bottom, "Benutzer wechseln", self.logout or (lambda: None), font=11,
            pad_y=7)
        self.controls["logout"].pack(side="right", padx=4)
        self.controls["logout"].pack_forget()

    def _selected(self, _event=None):
        self.select_profile(self.selected_var.get())

    def set_access(self, user, *, profile_names=None, selected=None):
        self.allowed = set(user["permissions"]) if user else None
        self.user_var.set(user["name"] if user else "")
        for permission, widget in self.tiles.items():
            if self.allowed is None or permission in self.allowed:
                widget.grid()
            else:
                widget.grid_remove()
        for permission in ("exit", "update", "shutdown"):
            widget = self.controls[permission]
            if self.allowed is None or permission in self.allowed:
                widget.pack(side="right" if permission == "shutdown" else "left",
                            padx=4)
            else:
                widget.pack_forget()
        if user:
            self.controls["logout"].pack(side="right", padx=4)
        else:
            self.controls["logout"].pack_forget()
        if self.allowed is not None and not ({"email", "usb"} & self.allowed):
            self.controls["other"].pack_forget()
        else:
            self.controls["other"].pack(side="left", padx=4)
        if self.allowed is not None and not ({"scan", "paperless", "network", "email", "usb"} & self.allowed):
            self.controls["profile_bar"].pack_forget()
        else:
            self.controls["profile_bar"].pack(fill="x", padx=37, pady=(2, 12),
                                              before=self.controls["footer"])
        self.refresh(names=profile_names, selected=selected)

    def refresh(self, *, names=None, selected=None):
        self.profile_select.configure(values=names if names is not None
                                      else self.profiles.names())
        self.selected_var.set(selected if selected is not None else self.profiles.selected)

    def show(self):
        self.frame.place(x=0, y=0, relwidth=1, relheight=1)
        self.frame.lift()

    def hide(self):
        self.frame.place_forget()

    @property
    def visible(self):
        return bool(self.frame.winfo_manager())
