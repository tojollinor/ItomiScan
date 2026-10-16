"""Hide the X11 pointer without displaying visual feedback for touch events.

The previous XFixes ring overlay was removed at the user's request.
Keep the public install_touch_feedback interface for existing kiosk callers.
"""
import ctypes
import ctypes.util
import tkinter as tk


def park_pointer():
    """Place the invisible X11 pointer away from PIN keys before rendering.

    This only changes pointer location. It must not synthesize a press/touch
    event or require root privileges. Failure is nonfatal on headless tests.
    """
    display = None
    x11 = None
    try:
        x11 = ctypes.CDLL(ctypes.util.find_library("X11") or "libX11.so.6")
        pointer = ctypes.c_void_p
        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x11.XOpenDisplay.restype = pointer
        x11.XDefaultRootWindow.argtypes = [pointer]
        x11.XDefaultRootWindow.restype = ctypes.c_ulong
        x11.XWarpPointer.argtypes = [
            pointer, ctypes.c_ulong, ctypes.c_ulong,
            ctypes.c_int, ctypes.c_int, ctypes.c_uint, ctypes.c_uint,
            ctypes.c_int, ctypes.c_int,
        ]
        x11.XFlush.argtypes = [pointer]
        x11.XCloseDisplay.argtypes = [pointer]
        display = x11.XOpenDisplay(None)
        if display:
            root_window = x11.XDefaultRootWindow(display)
            x11.XWarpPointer(display, 0, root_window, 0, 0, 0, 0, 1, 1)
            x11.XFlush(display)
            return True
    except (OSError, ValueError, AttributeError):
        pass
    finally:
        if display and x11 is not None:
            x11.XCloseDisplay(display)
    return False


class TouchFeedback:
    def __init__(self, root):
        self.root = root
        self.display = None
        self.x11 = None
        self.fixes = None
        root.configure(cursor="none")
        try:
            self._hide_x11_cursor()
        except (OSError, ValueError, AttributeError, tk.TclError):
            self.close()
        root.bind("<Destroy>", self._on_destroy, add="+")

    def _hide_x11_cursor(self):
        self.x11 = ctypes.CDLL(ctypes.util.find_library("X11") or "libX11.so.6")
        self.fixes = ctypes.CDLL(
            ctypes.util.find_library("Xfixes") or "libXfixes.so.3")
        pointer = ctypes.c_void_p
        window_id = ctypes.c_ulong
        self.x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self.x11.XOpenDisplay.restype = pointer
        self.x11.XDefaultRootWindow.argtypes = [pointer]
        self.x11.XDefaultRootWindow.restype = window_id
        self.x11.XFlush.argtypes = [pointer]
        self.x11.XCloseDisplay.argtypes = [pointer]
        self.fixes.XFixesHideCursor.argtypes = [pointer, window_id]
        self.fixes.XFixesShowCursor.argtypes = [pointer, window_id]
        self.display = self.x11.XOpenDisplay(None)
        if not self.display:
            raise OSError("X11 display unavailable")
        self.fixes.XFixesHideCursor(
            self.display, self.x11.XDefaultRootWindow(self.display))
        self.x11.XFlush(self.display)

    def _on_destroy(self, event):
        if event.widget is self.root:
            self.close()

    def close(self):
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
