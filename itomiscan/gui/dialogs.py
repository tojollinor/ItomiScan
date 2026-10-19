"""Shared touch dialogs. Questions always default to cancellation."""
import tkinter as tk

BG = "#101927"
PANEL = "#24334a"
FG = "#f1f5fb"


def close_transients(root):
    """Remove keyboards and dialogs before displaying an authentication gate."""
    for child in list(root.winfo_children()):
        if isinstance(child, tk.Toplevel):
            child.destroy()


def _dialog(title, message, *, parent, question=False):
    root = parent.winfo_toplevel()
    active = getattr(root, "_itomiscan_dialog", None)
    if active is not None and active.winfo_exists():
        active.lift()
        return False
    win = tk.Toplevel(root)
    root._itomiscan_dialog = win
    win.title(title or "ItomiScan")
    win.configure(bg=BG, cursor="none")
    win.overrideredirect(True)
    width = min(720, root.winfo_screenwidth() - 32)
    height = min(430, root.winfo_screenheight() - 32)
    win.geometry(f"{width}x{height}+{(root.winfo_screenwidth()-width)//2}"
                 f"+{(root.winfo_screenheight()-height)//2}")
    result = [False]

    def finish(value=False):
        result[0] = value
        win.destroy()

    footer = tk.Frame(win, bg=BG)
    footer.pack(side="bottom", fill="x", padx=24, pady=24)
    cancel = tk.Button(footer, text="Abbrechen" if question else "Schließen",
                       command=finish, bg=PANEL, fg=FG, relief="flat", bd=0,
                       font=("DejaVu Sans", 17, "bold"), pady=18, cursor="none")
    cancel.pack(side="left", fill="x", expand=True, padx=6)
    if question:
        tk.Button(footer, text="Bestätigen", command=lambda: finish(True),
                  bg="#397edb", fg=FG, relief="flat", bd=0, cursor="none",
                  font=("DejaVu Sans", 17, "bold"), pady=18).pack(
                      side="left", fill="x", expand=True, padx=6)
    tk.Label(win, text=title or "ItomiScan", bg=BG, fg=FG,
             font=("DejaVu Sans", 22, "bold"), wraplength=width-60).pack(padx=24, pady=(30, 16))
    body = tk.Text(win, bg=BG, fg=FG, font=("DejaVu Sans", 15),
                   wrap="word", bd=0, highlightthickness=0, height=5)
    body.insert("1.0", str(message or ""))
    body.configure(state="disabled")
    body.pack(fill="both", expand=True, padx=32, pady=8)
    win.bind("<Escape>", lambda event: finish())
    win.bind("<Return>", lambda event: finish())
    win.protocol("WM_DELETE_WINDOW", finish)
    win.lift()
    win.grab_set()
    cancel.focus_set()
    try:
        root.wait_window(win)
    finally:
        root._itomiscan_dialog = None
    return result[0]


def askyesno(title=None, message=None, **kwargs):
    return _dialog(title, message, parent=kwargs["parent"], question=True)


askokcancel = askyesno


def showinfo(title=None, message=None, **kwargs):
    _dialog(title, message, parent=kwargs["parent"])


showwarning = showinfo
showerror = showinfo
