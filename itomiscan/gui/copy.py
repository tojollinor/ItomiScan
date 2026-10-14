"""Large simple copy screen for the original 1024x768 N1800 touch display.

No external assets, keyboard, printer drivers or CUPS API binding. This screen
only chooses a queue and options; all permissions and submission are checked
again in the application and delivery worker.
"""
import tkinter as tk

from itomiscan.gui.home import BASE, CARD, CYAN, FG, MUTED, BLUE, draw_logo
from itomiscan.integrations.printing import SIDES, MAX_COPIES


class CopyScreen:
    def __init__(self, root, printers, start_copy, back):
        self.root = root
        self.printers = printers
        self.start_copy = start_copy
        self.back = back
        self.frame = tk.Frame(root, bg=BASE)
        self.selected_id = None
        self.printer_page = 0
        self.copies = 1
        self.scan_source = "ADF Front"
        self.print_sides = "one-sided"
        self.display_printers = tk.Frame(self.frame, bg=BASE)
        self.message = tk.StringVar(value="")
        self.copies_var = tk.StringVar(value="1")
        self.scan_var = tk.StringVar(value="Vorderseiten")
        self.print_var = tk.StringVar(value="Einseitig")
        self._build()

    def _button(self, parent, label, fn, *, background=CARD, size=16, width=None):
        return tk.Button(parent, text=label, command=fn,
                         font=("DejaVu Sans", size, "bold"),
                         fg=FG, bg=background, activebackground="#28465f",
                         activeforeground=FG, relief="flat", bd=0,
                         padx=13, pady=12, width=width)

    def _build(self):
        # Pack the primary action first to reserve space on 1024x768.
        foot = tk.Frame(self.frame, bg=BASE)
        foot.pack(side="bottom", fill="x", padx=35, pady=(8, 12))
        tk.Label(foot, textvariable=self.message, bg=BASE, fg=MUTED,
                 font=("DejaVu Sans", 10), wraplength=490,
                 justify="left").pack(side="left")
        self.start_button = self._button(
            foot, "Scannen & drucken", self.start, background=BLUE, size=15)
        self.start_button.pack(side="right", ipady=3)
        bar = tk.Frame(self.frame, bg=BASE)
        bar.pack(fill="x", padx=29, pady=(19, 8))
        self._button(bar, "← Zurück", self.back, size=13).pack(side="left")
        draw_logo(bar, 48).pack(side="left", padx=(16, 0))
        tk.Label(bar, text="Kopieren", font=("DejaVu Sans", 27, "bold"),
                 bg=BASE, fg=FG).pack(side="left", padx=25)
        tk.Label(bar, text="ItomiScan", font=("DejaVu Sans", 15, "bold"),
                 bg=BASE, fg=CYAN).pack(side="right")
        subtitle = tk.Label(
            self.frame, text="Drucker wählen und Dokument einlegen",
            bg=BASE, fg=MUTED, font=("DejaVu Sans", 14))
        subtitle.pack(pady=(3, 14))
        self.display_printers.pack(fill="x", padx=32, pady=(0, 8))
        controls = tk.Frame(self.frame, bg=BASE)
        controls.pack(fill="both", expand=True, padx=32, pady=(6, 0))
        left = tk.Frame(controls, bg=CARD)
        right = tk.Frame(controls, bg=CARD)
        left.pack(side="left", fill="both", expand=True, padx=(0, 7))
        right.pack(side="left", fill="both", expand=True, padx=(7, 0))

        tk.Label(left, text="Anzahl Kopien", bg=CARD, fg=MUTED,
                 font=("DejaVu Sans", 14, "bold")).pack(pady=(16, 10))
        stepper = tk.Frame(left, bg=CARD)
        stepper.pack()
        self._button(stepper, "−", lambda: self._step(-1), size=24, width=3
                     ).pack(side="left", padx=7)
        tk.Label(stepper, textvariable=self.copies_var, bg=CARD, fg=FG,
                 font=("DejaVu Sans", 27, "bold"), width=3
                 ).pack(side="left", padx=9)
        self._button(stepper, "+", lambda: self._step(1), size=24, width=3
                     ).pack(side="left", padx=7)
        tk.Label(left, text="Vorlage einziehen", bg=CARD, fg=MUTED,
                 font=("DejaVu Sans", 13, "bold")).pack(pady=(20, 5))
        self._button(left, "1-seitig / 2-seitig", self._switch_source,
                     size=12).pack(fill="x", padx=14)
        tk.Label(left, textvariable=self.scan_var, bg=CARD, fg=CYAN,
                 font=("DejaVu Sans", 12)).pack(pady=(3, 8))

        tk.Label(right, text="Ausdruck", bg=CARD, fg=MUTED,
                 font=("DejaVu Sans", 14, "bold")).pack(pady=(16, 10))
        self._button(right, "Einseitig", lambda: self._print_sides("one-sided"),
                     size=14).pack(fill="x", padx=18, pady=4)
        self._button(right, "Duplex (lange Kante)",
                     lambda: self._print_sides("two-sided-long-edge"),
                     size=13).pack(fill="x", padx=18, pady=4)
        self._button(right, "Duplex (kurze Kante)",
                     lambda: self._print_sides("two-sided-short-edge"),
                     size=13).pack(fill="x", padx=18, pady=4)
        tk.Label(right, textvariable=self.print_var, bg=CARD, fg=CYAN,
                 font=("DejaVu Sans", 12)).pack(pady=5)


    def _step(self, amount):
        self.copies = max(1, min(MAX_COPIES, self.copies + amount))
        self.copies_var.set(str(self.copies))

    def _switch_source(self):
        self.scan_source = ("ADF Duplex" if self.scan_source == "ADF Front"
                            else "ADF Front")
        self.scan_var.set("Beidseitige Vorlage" if self.scan_source == "ADF Duplex"
                          else "Einseitige Vorlage")

    def _print_sides(self, value):
        if value in SIDES:
            self.print_sides = value
            self.print_var.set({
                "one-sided": "Einseitig",
                "two-sided-long-edge": "Duplex: lange Kante",
                "two-sided-short-edge": "Duplex: kurze Kante",
            }[value])

    def _select(self, target):
        if target["ready"]:
            self.selected_id = target["id"]
            self._render_printers(self._last_targets)

    def _render_printers(self, entries):
        for child in self.display_printers.winfo_children():
            child.destroy()
        self._last_targets = entries
        tk.Label(self.display_printers, text="Verfügbare Drucker",
                 bg=BASE, fg=FG, font=("DejaVu Sans", 16, "bold")
                 ).pack(anchor="w", pady=(0, 6))
        if not entries:
            tk.Label(self.display_printers,
                     text="Noch kein Drucker eingerichtet. Bitte in der Webadministration unter „Drucker hinzufügen“ einrichten.",
                     bg=CARD, fg=FG, font=("DejaVu Sans", 12),
                     pady=10, wraplength=820).pack(fill="x")
            return
        grid = tk.Frame(self.display_printers, bg=BASE)
        grid.pack(fill="x")
        for col in range(2):
            grid.grid_columnconfigure(col, weight=1, uniform="copyprinters")
        pages = max(1, (len(entries) + 3) // 4)
        self.printer_page = max(0, min(self.printer_page, pages - 1))
        start = self.printer_page * 4
        for i, target in enumerate(entries[start:start + 4]):
            state = "normal" if target["ready"] else "disabled"
            mark = "✓  " if self.selected_id == target["id"] else ""
            if target.get("default"):
                mark += "★  "
            note = "" if target["ready"] else " (nicht in CUPS)"
            button = self._button(
                grid, mark + target["name"] + note,
                lambda t=target: self._select(t),
                background=BLUE if self.selected_id == target["id"] else CARD,
                size=13)
            button.configure(state=state)
            button.grid(row=i//2, column=i%2, sticky="nsew",
                        padx=5, pady=4)
        if pages > 1:
            paging = tk.Frame(self.display_printers, bg=BASE)
            paging.pack(pady=3)
            self._button(paging, "◀", lambda: self._page_step(-1),
                         size=11).pack(side="left", padx=8)
            tk.Label(paging, text=f"Seite {self.printer_page + 1} / {pages}",
                     bg=BASE, fg=FG, font=("DejaVu Sans", 12)).pack(side="left")
            self._button(paging, "▶", lambda: self._page_step(1),
                         size=11).pack(side="left", padx=8)

    def _page_step(self, delta):
        self.printer_page += delta
        self._render_printers(self._last_targets)

    def show(self):
        try:
            targets = self.printers()
        except (OSError, ValueError):
            targets = []
        if self.selected_id not in [p["id"] for p in targets if p["ready"]]:
            self.selected_id = next((p["id"] for p in targets
                                     if p["ready"] and p.get("default")), None)
            if self.selected_id is None:
                self.selected_id = next((p["id"] for p in targets if p["ready"]), None)
        if self.selected_id is not None:
            self.printer_page = next(
                (i // 4 for i, p in enumerate(targets)
                 if p["id"] == self.selected_id), 0)
        self._render_printers(targets)
        self.message.set(
            "PDF wird lokal gesichert und über CUPS gedruckt. "
            "Ein erfolgreicher CUPS-Auftrag garantiert noch keinen Papierausdruck.")
        self.start_button.configure(state="normal" if self.selected_id else "disabled")
        self.frame.place(x=0, y=0, relwidth=1, relheight=1)
        self.frame.lift()

    def hide(self):
        self.frame.place_forget()

    def start(self):
        if self.visible and self.selected_id is not None:
            self.start_copy(self.selected_id, self.copies,
                            self.print_sides, self.scan_source)

    @property
    def visible(self):
        return bool(self.frame.winfo_manager())
