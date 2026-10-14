"""Lightweight German touch keyboard for the N1800 (no X11 keyboard daemon)."""
import tkinter as tk

BG = "#101927"
PANEL = "#192738"
FG = "#f1f5fb"
CYAN = "#42bfea"
BLUE = "#397edb"


def ask_touch(root, title, initial="", *, numeric=False, secret=False, max_length=120):
    """Modal, touch-sized QWERTZ keyboard. Return text or None on cancel."""
    result = {"value": None}
    win = tk.Toplevel(root)
    win.title(title)
    win.configure(bg=BG)
    # The kiosk root uses overrideredirect(True) and no window manager.
    # A transient child can be hidden or leave the screen apparently blank.
    # Keep this keyboard as a normal, explicitly raised top-level window.
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    width = min(1000, max(320, screen_w - 24))
    height = min(690, max(260, screen_h - 24))
    win.geometry(f"{width}x{height}+{(screen_w-width)//2}+{(screen_h-height)//2}")
    # Build and map the complete keyboard before requesting a grab.
    # Grabbing an unmapped Toplevel can fail on X11/Tk.
    value = tk.StringVar(value=str(initial))
    shifted = tk.BooleanVar(value=False)

    tk.Label(win, text=title, bg=BG, fg=FG,
             font=("DejaVu Sans", 21, "bold")).pack(pady=(14, 7))
    entry = tk.Entry(win, textvariable=value, show="*" if secret else "",
                     font=("DejaVu Sans", 23), justify="center",
                     bg="#ffffff", fg="#101927", insertbackground="#101927")
    entry.pack(fill="x", padx=24, pady=(0, 12), ipady=8)
    board = tk.Frame(win, bg=BG)
    # The board is packed after the bottom action bar.

    def put(char):
        pos = entry.index(tk.INSERT)
        text = value.get()
        try:
            start = entry.index(tk.SEL_FIRST)
            end = entry.index(tk.SEL_LAST)
        except tk.TclError:
            start = end = pos
        if len(text) - (end - start) + len(char) > max_length:
            return
        if end > start:
            entry.delete(start, end)
            pos = start
        entry.insert(pos, char)
        entry.icursor(pos + len(char))

    # Enforce the same length limit for a connected physical keyboard.
    def limit_input(*_args):
        current = value.get()
        if len(current) > max_length:
            value.set(current[:max_length])
    value.trace_add("write", limit_input)

    def erase():
        try:
            entry.delete(tk.SEL_FIRST, tk.SEL_LAST)
        except tk.TclError:
            pos = entry.index(tk.INSERT)
            if pos:
                entry.delete(pos - 1, pos)

    def confirm():
        result["value"] = value.get()
        win.destroy()

    def cancel():
        win.destroy()

    # Reserve the confirmation bar before expanding the keyboard rows.
    # The N1800 panel is 1024x768: no keyboard action may be clipped.
    compact = width < 900 or height < 620
    footer = tk.Frame(win, bg=BG)
    footer.pack(side="bottom", fill="x", padx=20, pady=(4, 12))
    board.pack(fill="both", expand=True, padx=12, pady=(0, 3))

    def key(parent, label, command, width=5, color=PANEL):
        return tk.Button(parent, text=label, command=command,
                         font=("DejaVu Sans", 13 if compact else 16, "bold"),
                         bg=color, fg=FG, activebackground=BLUE,
                         activeforeground=FG, relief="flat", bd=0,
                         width=width, padx=2, pady=4 if compact else 7,
                         takefocus=False)

    def render():
        for widget in board.winfo_children():
            widget.destroy()
        if numeric:
            rows = ("789", "456", "123", ",0.")
        else:
            rows = ("qwertzuiopü", "asdfghjklöä", "yxcvbnmß")
        for line in rows:
            row = tk.Frame(board, bg=BG)
            row.pack(fill="both", expand=True, pady=2)
            for ch in line:
                label = ch.upper() if shifted.get() else ch
                key(row, label, lambda c=label: put(c),
                    width=2 if not numeric else 3).pack(
                        side="left", fill="both", expand=True, padx=1)
        if not numeric:
            # Network paths, URLs, e-mail addresses and passwords require
            # punctuation without a physical keyboard.
            symbols = tk.Frame(board, bg=BG)
            symbols.pack(fill="both", expand=True, pady=2)
            for symbol in ("@", ".", "/", ":", "_", "?", "&", "=", "+", "#", "%"):
                key(symbols, symbol, lambda s=symbol: put(s), width=2).pack(
                    side="left", fill="both", expand=True, padx=1)
        tools = tk.Frame(board, bg=BG)
        tools.pack(fill="x", pady=3)
        if not numeric:
            def toggle():
                shifted.set(not shifted.get())
                render()
                entry.focus_set()
            key(tools, "⇧ Shift", toggle, width=8).pack(side="left", padx=2)
            key(tools, "Leerzeichen", lambda: put(" "), width=12).pack(
                side="left", fill="x", expand=True, padx=2)
            key(tools, "-", lambda: put("-"), width=3).pack(side="left", padx=2)
        key(tools, "⌫ Löschen", erase, width=10).pack(side="right", padx=2)

    render()
    key(footer, "Abbrechen", cancel, width=11).pack(side="left")
    key(footer, "Übernehmen", confirm, width=12, color=BLUE).pack(side="right")
    win.protocol("WM_DELETE_WINDOW", cancel)
    win.bind("<Return>", lambda _e: confirm())
    win.bind("<Escape>", lambda _e: cancel())
    win.update_idletasks()
    win.wait_visibility()
    win.lift()
    try:
        win.grab_set()
    except tk.TclError:
        # Never leave a blank kiosk if the X server rejects the grab.
        win.lift()
    entry.focus_set()
    root.wait_window(win)
    return result["value"]
