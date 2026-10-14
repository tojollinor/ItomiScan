"""Touch-friendly scanner error dialogs, no extra GUI dependencies."""
import tkinter as tk

BG = "#101927"
PANEL = "#24334a"
WHITE = "#f1f5fb"
CYAN = "#42bfea"
WARN = "#f5bd55"


def classify_scanner_error(raw):
    text = str(raw or "").lower()
    if "document feeder jammed" in text or "paper jam" in text or "paper jammed" in text:
        return ("Papierstau erkannt",
                "Bitte Dokumenteneinzug öffnen, gestautes Papier vorsichtig entfernen "
                "und anschließend erneut scannen.")
    if "document feeder out of documents" in text or "no documents" in text:
        return ("Kein Dokument eingelegt",
                "Bitte Papier in den Dokumenteneinzug legen und erneut scannen.")
    return ("Scannerfehler",
            "Der Scan konnte nicht abgeschlossen werden. Bitte Scanner und "
            "Dokumenteneinzug prüfen. Unter „Details“ findest du die Fehlermeldung.")


def show_scanner_error(root, raw):
    title, explanation = classify_scanner_error(raw)
    win = tk.Toplevel(root)
    win.title(title)
    win.configure(bg=BG, highlightbackground=WARN, highlightthickness=4)
    win.transient(root)
    win.geometry("760x460")
    win.grab_set()
    tk.Label(win, text=title, bg=BG, fg=WARN,
             font=("DejaVu Sans", 25, "bold")).pack(pady=(28, 18))
    tk.Label(win, text=explanation, bg=BG, fg=WHITE, wraplength=675,
             font=("DejaVu Sans", 17), justify="center").pack(padx=24, pady=12)
    details = tk.Label(win, text=str(raw)[-800:], bg=PANEL, fg=WHITE,
                       wraplength=675, font=("DejaVu Sans", 10), justify="left")
    def toggle():
        if details.winfo_manager():
            details.pack_forget()
        else:
            details.pack(fill="x", padx=20, pady=6)
    buttons = tk.Frame(win, bg=BG)
    buttons.pack(side="bottom", pady=25)
    for label, fn, color in (("Details", toggle, PANEL),
                             ("OK", win.destroy, CYAN)):
        tk.Button(buttons, text=label, command=fn,
                  bg=color, fg=BG if color == CYAN else WHITE,
                  font=("DejaVu Sans", 17, "bold"),
                  padx=30, pady=14, relief="flat").pack(side="left", padx=12)
    win.bind("<Return>", lambda _e: win.destroy())
    win.bind("<Escape>", lambda _e: win.destroy())
    root.wait_window(win)
