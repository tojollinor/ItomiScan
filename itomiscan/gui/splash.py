"""Small Tk-only startup screen, sized for the N1800 1024x768 display."""

import tkinter as tk

from itomiscan.gui.home import draw_logo

BG = "#101927"
PANEL = "#192738"
WHITE = "#f1f5fb"
MUTED = "#a8bacd"
CYAN = "#42bfea"


class StartupSplash:
    def __init__(self, root, retry, exit_app):
        self.root = root
        self.retry = retry
        self.frame = tk.Frame(root, bg=BG)
        self.frame.place(x=0, y=0, relwidth=1, relheight=1)
        self.frame.lift()

        # Exact reference coordinates shared with the Plymouth theme (1024x768).
        # Keep the content visible during the switch to the main kiosk.
        draw_logo(self.frame, 84).place(relx=0.5, y=29, anchor="n")
        brand = tk.Frame(self.frame, bg=BG)
        brand.place(relx=0.5, y=126, anchor="n")
        tk.Label(brand, text="Itomi", font=("DejaVu Sans", 30, "bold"),
                 bg=BG, fg=WHITE).pack(side="left")
        tk.Label(brand, text="Scan", font=("DejaVu Sans", 30, "bold"),
                 bg=BG, fg=CYAN).pack(side="left")
        tk.Label(self.frame, text="Dokumentenscanner", font=("DejaVu Sans", 13),
                 bg=BG, fg=MUTED).place(relx=0.5, y=177, anchor="n")
        self.canvas = tk.Canvas(self.frame, width=150, height=150,
                                bg=BG, bd=0, highlightthickness=0)
        self.canvas.place(relx=0.5, y=228, anchor="n")
        self.canvas.create_oval(21, 21, 129, 129, outline="#34475e", width=11)
        self.arc = self.canvas.create_arc(21, 21, 129, 129, start=90, extent=85,
                                          style=tk.ARC, outline=CYAN, width=11)
        self.angle = 90
        self.running = True
        self.title = tk.StringVar(value="Scanner wird vorbereitet")
        self.info = tk.StringVar(value="Systemstart …")
        tk.Label(self.frame, textvariable=self.title, bg=BG, fg=WHITE,
                 font=("DejaVu Sans", 19, "bold")).place(relx=0.5, y=410, anchor="n")
        tk.Label(self.frame, textvariable=self.info, bg=BG, fg=MUTED,
                 wraplength=720, font=("DejaVu Sans", 12)).place(relx=0.5, y=457, anchor="n")
        self.buttons = tk.Frame(self.frame, bg=BG)
        self.detail_text = tk.StringVar(value="")
        self.details_visible = False
        self.detail_label = tk.Label(self.frame, textvariable=self.detail_text,
                                     bg=PANEL, fg=WHITE, font=("DejaVu Sans", 10),
                                     justify="left", wraplength=760, padx=20, pady=13)
        self.retry_btn = tk.Button(self.buttons, text="Erneut versuchen", command=retry,
                                    bg=CYAN, fg=BG, font=("DejaVu Sans", 13, "bold"),
                                    padx=20, pady=12)
        self.detail_btn = tk.Button(self.buttons, text="Diagnose", command=self.toggle_details,
                                     bg=PANEL, fg=WHITE, font=("DejaVu Sans", 13),
                                     padx=20, pady=12)
        self.exit_btn = tk.Button(self.buttons, text="Beenden", command=exit_app,
                                   bg=PANEL, fg=WHITE, font=("DejaVu Sans", 13),
                                   padx=20, pady=12)
        self._animate()

    def _animate(self):
        if not self.running:
            return
        self.angle = (self.angle + 12) % 360
        self.canvas.itemconfigure(self.arc, start=self.angle)
        self.root.after(80, self._animate)

    def stage(self, step, message):
        self.title.set("Scanner wird vorbereitet")
        self.info.set(message)
        if step == "ready":
            self.title.set("Scanner bereit")

    def failure(self, message, detail):
        self.title.set("Start nicht abgeschlossen")
        self.info.set(message)
        self.detail_text.set((detail or "Keine weiteren Diagnosedaten.")[:600])
        if not self.buttons.winfo_manager():
            self.buttons.place(relx=0.5, y=520, anchor="n")
            self.retry_btn.pack(side="left", padx=8)
            self.detail_btn.pack(side="left", padx=8)
            self.exit_btn.pack(side="left", padx=8)

    def loading(self):
        self.title.set("Scanner wird vorbereitet")
        self.info.set("Erneuter Versuch …")
        self.buttons.place_forget()
        self.detail_label.place_forget()
        self.details_visible = False

    def toggle_details(self):
        if self.details_visible:
            self.detail_label.place_forget()
        else:
            self.detail_label.place(relx=0.5, y=615, anchor="n")
        self.details_visible = not self.details_visible

    def destroy(self):
        self.running = False
        self.frame.destroy()
