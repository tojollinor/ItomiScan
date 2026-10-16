"""Low-cost X11 touch feedback for the dedicated N1800 kiosk.

XFixes hides the pointer across Tk children and dialogs. An input-transparent
X11 window briefly paints a touch ring, without consuming click events.
The code falls back to Tk's hidden cursor if XFixes is unavailable.
"""
import ctypes
import ctypes.util
import tkinter as tk

from itomiscan import branding


class TouchFeedback:
    def __init__(self, root):
        self.root = root
        self.window = None
        self.canvas = None
        self.display = None
        self.x11 = None
        self.fixes = None
        self.generation = 0
        # Even on non-X11 test systems, the kiosk root hides its own cursor.
        root.configure(cursor="none")
        try:
            self._install_xfixes()
        except (OSError, ValueError, AttributeError, tk.TclError):
            self.close()
            return
        root.bind_all("<ButtonRelease-1>", self.on_touch, add="+")
        root.bind("<Destroy>", self._on_destroy, add="+")

    def _install_xfixes(self):
        self.x11 = ctypes.CDLL(ctypes.util.find_library("X11") or "libX11.so.6")
        self.fixes = ctypes.CDLL(
            ctypes.util.find_library("Xfixes") or "libXfixes.so.3")
        ptr = ctypes.c_void_p
        window_id = ctypes.c_ulong
        self.x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self.x11.XOpenDisplay.restype = ptr
        self.x11.XDefaultRootWindow.argtypes = [ptr]
        self.x11.XDefaultRootWindow.restype = window_id
        self.x11.XFlush.argtypes = [ptr]
        self.x11.XCloseDisplay.argtypes = [ptr]
        self.fixes.XFixesHideCursor.argtypes = [ptr, window_id]
        self.fixes.XFixesShowCursor.argtypes = [ptr, window_id]
        self.fixes.XFixesCreateRegion.argtypes = [ptr, ptr, ctypes.c_int]
        self.fixes.XFixesCreateRegion.restype = window_id
        self.fixes.XFixesSetWindowShapeRegion.argtypes = [
            ptr, window_id, ctypes.c_int, ctypes.c_int, ctypes.c_int, window_id]
        self.fixes.XFixesDestroyRegion.argtypes = [ptr, window_id]

        self.display = self.x11.XOpenDisplay(None)
        if not self.display:
            raise OSError("X11 display unavailable")
        xroot = self.x11.XDefaultRootWindow(self.display)

        self.window = tk.Toplevel(self.root)
        self.window.withdraw()
        self.window.overrideredirect(True)
        self.window.configure(bg=branding.BG, cursor="none", takefocus=False)
        self.canvas = tk.Canvas(self.window, width=58, height=58, bg=branding.BG,
                                highlightthickness=0, bd=0, cursor="none")
        self.canvas.pack()
        # Ensure Tk creates and flushes the X window before the separate
        # XFixes connection references its XID (otherwise BadWindow aborts).
        self.window.geometry("58x58+-200+-200")
        self.window.deiconify()
        self.window.update_idletasks()
        # X ShapeInput=2. Empty input shape means the ring never steals
        # a click, even if the user taps twice while the animation is visible.
        empty_region = self.fixes.XFixesCreateRegion(self.display, None, 0)
        if not empty_region:
            raise OSError("XFixes input region not available")
        try:
            self.fixes.XFixesSetWindowShapeRegion(
                self.display, window_id(self.window.winfo_id()), 2, 0, 0,
                empty_region)
        finally:
            self.fixes.XFixesDestroyRegion(self.display, empty_region)
        self.fixes.XFixesHideCursor(self.display, xroot)
        self.x11.XFlush(self.display)
        self.window.withdraw()

    def on_touch(self, event):
        if not self.window or not self.display:
            return
        if not (hasattr(event, "x_root") and hasattr(event, "y_root")):
            return
        self.generation += 1
        generation = self.generation
        self.window.geometry(f"58x58+{max(0, event.x_root - 29)}+"
                             f"{max(0, event.y_root - 29)}")
        try:
            bg = event.widget.cget("background")
            if not isinstance(bg, str) or not bg.startswith("#"):
                bg = branding.BG
        except (tk.TclError, AttributeError):
            bg = branding.BG
        self.canvas.configure(bg=bg)
        self.window.configure(bg=bg)
        self.window.deiconify()
        self.window.lift()
        self._pulse(generation, 0)

    def _pulse(self, generation, step):
        if generation != self.generation or not self.canvas:
            return
        if step >= 5:
            self.window.withdraw()
            return
        self.canvas.delete("pulse")
        radius = 7 + step * 5
        self.canvas.create_oval(29-radius, 29-radius, 29+radius, 29+radius,
                                outline=branding.CYAN, width=2, tags="pulse")
        self.root.after(55, self._pulse, generation, step + 1)

    def _on_destroy(self, event):
        if event.widget is self.root:
            self.close()

    def close(self):
        self.generation += 1
        if self.window is not None:
            try:
                self.window.destroy()
            except tk.TclError:
                pass
            self.window = None
            self.canvas = None
        if self.display:
            try:
                self.fixes.XFixesShowCursor(
                    self.display, self.x11.XDefaultRootWindow(self.display))
                self.x11.XCloseDisplay(self.display)
            except (OSError, AttributeError):
                pass
            self.display = None


def install_touch_feedback(root):
    """Attach to kiosk Tk root; never modifies Xorg configuration."""
    return TouchFeedback(root)
