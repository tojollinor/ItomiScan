"""Large touch-oriented 1024x768 home screen; only local scanning is live."""
import tkinter as tk
from tkinter import ttk

from itomiscan import branding

BASE = branding.BG
CARD = "#192738"
CARD_HOVER = "#24405b"
FG = "#f1f5fb"
MUTED = "#a8bacd"
CYAN = branding.CYAN
BLUE = "#397edb"


def draw_logo(parent, size=68):
    """Solid two-colour N1800-friendly rendition of the approved scan icon."""
    canvas = tk.Canvas(parent, width=size, height=size,
                       bg=BASE, bd=0, highlightthickness=0)
    factor = size / branding.LOGO_UNITS
    scaled = lambda coords: branding.scaled(coords, size)
    canvas.create_rectangle(*scaled((1, 1, 71, 71)),
                            fill=branding.BLUE, outline="")
    canvas.create_polygon(*scaled(branding.DOCUMENT),
                          fill="white", outline="")
    canvas.create_rectangle(
        *scaled((branding.LINE_LEFT, branding.LINE_START,
                 branding.LINE_RIGHT, branding.LINE_START + branding.LINE_HEIGHT)),
        fill=CYAN, outline="", tags="scanline")
    for x, y, dx, dy in branding.CORNERS:
        canvas.create_line(*scaled((x, y + dy, x, y, x + dx, y)),
                           fill=CYAN, width=max(3, round(4 * factor)))
    return canvas



def set_logo_busy(canvas, busy):
    """Animate only the existing scan bar, keeping the rest of the logo static."""
    if not canvas.winfo_exists():
        return
    current = bool(getattr(canvas, "_itomi_busy", False))
    if current == bool(busy):
        return
    canvas._itomi_busy = bool(busy)
    canvas._itomi_generation = getattr(canvas, "_itomi_generation", 0) + 1
    generation = canvas._itomi_generation
    original = canvas.coords("scanline")
    if not busy:
        if hasattr(canvas, "_itomi_original"):
            canvas.coords("scanline", *canvas._itomi_original)
        return
    canvas._itomi_original = original
    factor = float(canvas.cget("width")) / branding.LOGO_UNITS
    position = [float(branding.LINE_START)]
    direction = [1.0]

    def frame():
        if (not canvas.winfo_exists() or
                not getattr(canvas, "_itomi_busy", False) or
                canvas._itomi_generation != generation):
            return
        position[0] += direction[0] * 2.5
        if position[0] >= branding.LINE_MAX:
            position[0], direction[0] = branding.LINE_MAX, -1
        elif position[0] <= branding.LINE_MIN:
            position[0], direction[0] = branding.LINE_MIN, 1
        canvas.coords("scanline", branding.LINE_LEFT * factor,
                      position[0] * factor, branding.LINE_RIGHT * factor,
                      (position[0] + branding.LINE_HEIGHT) * factor)
        canvas.after(90, frame)

    frame()


class HomeScreen:
    """No remote actions here: unavailable destinations are explicitly labelled."""

    def __init__(self, root, profiles, select_profile, open_scan, quick_scan,
                 unavailable, shutdown, update, exit_app, status, logout=None,
                 deliver=None, open_copy=None, destination_status=None, restart=None):
        self.root = root
        self.profiles = profiles
        self.select_profile = select_profile
        self.open_scan = open_scan
        self.quick_scan = quick_scan
        self.unavailable = unavailable
        self.deliver = deliver or (lambda _kind: None)
        self.destination_status = destination_status or (lambda _kind: "Konfiguration prüfen")
        self.open_copy = open_copy or (lambda: self.unavailable('copy', 'Kopieren', 7))
        self.restart = restart
        self.logout = logout
        self.allowed = None
        self.tiles = {}
        self.controls = {}
        self.destination_page = None
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
        # Reserve the persistent bottom actions before the flexible content.
        bottom = tk.Frame(self.frame, bg=BASE)
        self.controls["footer"] = bottom
        bottom.pack(side="bottom", fill="x", padx=31, pady=(0, 18))
        header = tk.Frame(self.frame, bg=BASE)
        header.pack(fill="x", padx=28, pady=(18, 6))
        self.logo = draw_logo(header, 64)
        self.logo.pack(side="left", padx=(0, 16))
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

        # Compact primary actions; leave breathing room on the 1024x768 panel.
        tiles = tk.Frame(self.frame, bg=BASE)
        tiles.pack(fill="x", padx=100, pady=(22, 16))
        for i in range(2):
            tiles.grid_columnconfigure(i, weight=1, uniform="actions")
        actions = (
            ("scan", "Scannen", "Dokument digitalisieren", self.show_destinations),
            ("copy", "Kopieren", "Dokument ausdrucken", self.open_copy),
        )
        for index, (permission, title, subtitle, command) in enumerate(actions):
            card = tk.Frame(tiles, bg=CARD, bd=0)
            card.grid(row=0, column=index, padx=8, pady=8, sticky="ew")
            self.tiles[permission] = card
            self._button(card, title, command, bg=CARD, font=19,
                         pad_y=12).pack(fill="x", padx=10, pady=(8, 0))
            tk.Label(card, text=subtitle, bg=CARD, fg=MUTED,
                     font=("DejaVu Sans", 11)).pack(pady=(0, 12))

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

        self.controls["menu"] = self._button(
            bottom, "Menü", lambda: self.show_menu(shutdown, update, exit_app),
            font=13, pad_y=9)
        self.controls["menu"].pack(side="left", padx=4)
        self.controls["shutdown"] = self._button(bottom, "Ausschalten", shutdown,
                                                 font=11, pad_y=7)
        self.controls["shutdown"].pack_forget()
        self.controls["logout"] = self._button(
            bottom, "Benutzer wechseln", self.logout or (lambda: None), font=11,
            pad_y=7)
        self.controls["logout"].pack(side="right", padx=4)
        self.controls["logout"].pack_forget()

    def _modal(self, title):
        """Keep the menu fully visible and centred on the N1800 display."""
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.configure(bg=BASE)
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        width = min(600, max(320, screen_w - 40))
        height = min(550, max(320, screen_h - 40))
        dialog.geometry(
            f"{width}x{height}+{max(0, (screen_w-width)//2)}+"
            f"{max(0, (screen_h-height)//2)}")
        dialog.lift()
        dialog.grab_set()
        tk.Label(dialog, text=title, bg=BASE, fg=FG,
                 font=("DejaVu Sans", 23, "bold")).pack(pady=(24, 12))
        return dialog

    def show_destinations(self):
        """Show scan targets as a full-screen kiosk page."""
        if self.destination_page is not None:
            self.destination_page.destroy()
            self.destination_page = None
        page = tk.Frame(self.root, bg=BASE)
        self.destination_page = page
        page.place(x=0, y=0, relwidth=1, relheight=1)
        page.lift()
        # Back navigation must remain visible regardless of destination count.
        self._button(page, "← Zurück", self.close_destinations,
                     font=13).pack(side="bottom", anchor="w", padx=35, pady=16)
        header = tk.Frame(page, bg=BASE)
        header.pack(fill="x", padx=28, pady=18)
        draw_logo(header, 52).pack(side="left", padx=12)
        tk.Label(header, text="Scanziel wählen", bg=BASE, fg=FG,
                 font=("DejaVu Sans", 24, "bold")).pack(side="left")
        grid = tk.Frame(page, bg=BASE)
        grid.pack(fill="both", expand=True, padx=30, pady=12)
        for col in range(2):
            grid.grid_columnconfigure(col, weight=1)
        for row in range(3):
            grid.grid_rowconfigure(row, weight=1)
        choices = []
        if self.allowed is None or "scan" in self.allowed:
            choices.append(("Lokal speichern", self.open_scan, "scan"))
        for kind, title in (("paperless", "Paperless"),
                            ("network", "Netzwerkordner"),
                            ("email", "E-Mail"), ("usb", "USB")):
            if self.allowed is None or kind in self.allowed:
                choices.append((title, lambda k=kind: self.deliver(k), kind))
        for index, (title, action, kind) in enumerate(choices):
            def select(fn=action):
                page.destroy()
                self.destination_page = None
                fn()
            card = tk.Frame(grid, bg=CARD)
            card.grid(row=index // 2, column=index % 2, sticky="nsew",
                      padx=7, pady=7)
            self._button(card, title, select, bg=BLUE if kind == "scan" else CARD,
                         font=17, pad_y=13).pack(fill="both", expand=True, padx=4)
            state = ("Lokal verfügbar" if kind == "scan"
                     else self.destination_status(kind))
            tk.Label(card, text=state, bg=CARD, fg=MUTED,
                     font=("DejaVu Sans", 11)).pack(pady=(0, 10))

    def close_destinations(self):
        page = getattr(self, "destination_page", None)
        if page is not None:
            page.destroy()
            self.destination_page = None
        self.show()

    def show_menu(self, shutdown, update, exit_app):
        """Single device menu with power controls and Close always last."""
        dialog = self._modal("Menü")
        actions = (
            ("Updates", "update", update),
            ("Neustarten", "shutdown", self.restart),
            ("Ausschalten", "shutdown", shutdown),
            ("Beenden", "exit", exit_app),
        )
        for title, permission, action in actions:
            if action is None or (self.allowed is not None and permission not in self.allowed):
                continue
            def select(fn=action):
                dialog.destroy()
                fn()
            self._button(dialog, title, select, font=17, pad_y=13).pack(
                fill="x", padx=28, pady=5)
        self._button(dialog, "Schließen", dialog.destroy, font=15,
                     pad_y=13).pack(side="bottom", fill="x", padx=28, pady=12)

    def _selected(self, _event=None):
        self.select_profile(self.selected_var.get())

    def set_access(self, user, *, profile_names=None, selected=None):
        self.allowed = set(user["permissions"]) if user else None
        self.user_var.set(user["name"] if user else "")
        for permission, widget in self.tiles.items():
            if self.allowed is None or permission == "scan" and (
                    {"scan", "paperless", "network", "email", "usb"} & self.allowed
                    ) or permission in self.allowed:
                widget.grid()
            else:
                widget.grid_remove()
        self.controls["menu"].pack(side="left", padx=4)
        self.controls["shutdown"].pack_forget()
        if user:
            self.controls["logout"].pack(side="right", padx=4)
        else:
            self.controls["logout"].pack_forget()
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
        if self.destination_page is not None:
            self.destination_page.destroy()
            self.destination_page = None
        self.frame.place_forget()

    @property
    def visible(self):
        return bool(self.frame.winfo_manager())
