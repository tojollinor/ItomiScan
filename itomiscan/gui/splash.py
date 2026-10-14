"""Scanner startup screen matching the Plymouth artwork at 1024x768."""
import tkinter as tk

from PIL import ImageTk

from itomiscan import branding
from itomiscan.gui.home import draw_logo, set_logo_busy

BG = branding.BG
PANEL = "#192738"
WHITE = branding.WHITE
MUTED = branding.MUTED
CYAN = branding.CYAN


class StartupSplash:
    def __init__(self, root, retry, exit_app):
        self.root = root
        self.retry = retry
        self.frame = tk.Frame(root, bg=BG)
        self.frame.place(x=0, y=0, relwidth=1, relheight=1)
        self.frame.lift()

        # Plymouth and Tk use the same icon, artwork and reference positions.
        self.logo = draw_logo(self.frame, branding.LOGO_SIZE)
        self.logo.place(relx=0.5, y=branding.LOGO_Y, anchor="n")
        set_logo_busy(self.logo, True)

        self.brand_photo = ImageTk.PhotoImage(
            branding._text_image((("Itomi", WHITE), ("Scan", CYAN)), 40))
        tk.Label(self.frame, image=self.brand_photo, bg=BG, bd=0,
                 highlightthickness=0).place(
                     relx=0.5, y=branding.BRAND_Y, anchor="n")
        self.subtitle_photo = ImageTk.PhotoImage(
            branding._text_image((("Dokumentenscanner", MUTED),), 17, False))
        tk.Label(self.frame, image=self.subtitle_photo, bg=BG, bd=0,
                 highlightthickness=0).place(
                     relx=0.5, y=branding.SUBTITLE_Y, anchor="n")

        self.title = tk.StringVar(value="Scanner wird vorbereitet")
        self.info = tk.StringVar(value="Systemstart …")
        tk.Label(self.frame, textvariable=self.title, bg=BG, fg=WHITE,
                 font=("DejaVu Sans", 19, "bold")).place(
                     relx=0.5, y=branding.STATUS_Y, anchor="n")
        tk.Label(self.frame, textvariable=self.info, bg=BG, fg=MUTED,
                 wraplength=720, font=("DejaVu Sans", 12)).place(
                     relx=0.5, y=branding.DETAIL_Y, anchor="n")

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
            self.buttons.place(relx=0.5, y=565, anchor="n")
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
            self.detail_label.place(relx=0.5, y=648, anchor="n")
        self.details_visible = not self.details_visible

    def destroy(self):
        # Invalidate any pending scan-line callbacks before destroying the frame.
        set_logo_busy(self.logo, False)
        self.frame.destroy()
