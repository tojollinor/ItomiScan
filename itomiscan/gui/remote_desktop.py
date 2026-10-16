"""Low-frame-rate X11 desktop capture and explicitly whitelisted XTest input.

Kiosk runs this as the ordinary scanner user under its own X11 authority.
No listening socket, shell invocation or privileged subprocess is added.
"""
import ctypes
import ctypes.util
import io
import logging
import os
import threading
import time

LOG = logging.getLogger("itomiscan.remote")


def _xtest_input(event, width, height):
    lib = ctypes.util.find_library("Xtst")
    if not lib:
        raise OSError("XTest ist nicht installiert.")
    x = ctypes.CDLL(ctypes.util.find_library("X11") or "libX11.so.6")
    xt = ctypes.CDLL(lib)
    P = ctypes.c_void_p
    x.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x.XOpenDisplay.restype = P
    x.XCloseDisplay.argtypes = [P]
    x.XFlush.argtypes = [P]
    x.XStringToKeysym.argtypes = [ctypes.c_char_p]
    x.XStringToKeysym.restype = ctypes.c_ulong
    x.XKeysymToKeycode.argtypes = [P, ctypes.c_ulong]
    x.XKeysymToKeycode.restype = ctypes.c_uint
    xt.XTestFakeMotionEvent.argtypes = [P, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                        ctypes.c_ulong]
    xt.XTestFakeButtonEvent.argtypes = [P, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
    xt.XTestFakeKeyEvent.argtypes = [P, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
    display = x.XOpenDisplay(None)
    if not display:
        raise OSError("X11-Display des Kiosks nicht erreichbar.")
    try:
        if event["kind"] == "click":
            px = min(width - 1, max(0, round(event["x"] * (width - 1) / 1000)))
            py = min(height - 1, max(0, round(event["y"] * (height - 1) / 1000)))
            xt.XTestFakeMotionEvent(display, -1, px, py, 0)
            xt.XTestFakeButtonEvent(display, 1, 1, 0)
            xt.XTestFakeButtonEvent(display, 1, 0, 0)
        else:
            name = event["key_name"]
            shift = len(name) == 1 and name.isupper()
            name = name.lower() if shift else name
            keysym = x.XStringToKeysym(name.encode("ascii"))
            code = x.XKeysymToKeycode(display, keysym) if keysym else 0
            if not code:
                raise ValueError("Tastenbelegung nicht verfügbar.")
            shift_code = x.XKeysymToKeycode(display, x.XStringToKeysym(b"Shift_L"))
            if shift and shift_code:
                xt.XTestFakeKeyEvent(display, shift_code, 1, 0)
            xt.XTestFakeKeyEvent(display, code, 1, 0)
            xt.XTestFakeKeyEvent(display, code, 0, 0)
            if shift and shift_code:
                xt.XTestFakeKeyEvent(display, shift_code, 0, 0)
        x.XFlush(display)
    finally:
        x.XCloseDisplay(display)


class RemoteDesktop:
    def __init__(self, root, live):
        self.root = root
        self.live = live
        self.last_capture = 0.
        self.capturing = False
        self.root.after(300, self._poll)

    def _poll(self):
        try:
            if self.live.active():
                event = self.live.take()
                if event:
                    _xtest_input(event, self.root.winfo_screenwidth(),
                                 self.root.winfo_screenheight())
                now = time.monotonic()
                if not self.capturing and now - self.last_capture >= 1.5:
                    self.last_capture = now
                    self.capturing = True
                    threading.Thread(target=self._capture, daemon=True).start()
        except (OSError, ValueError) as exc:
            LOG.warning("Fernsteuerung nicht verfügbar: %s", exc)
        finally:
            if self.root.winfo_exists():
                self.root.after(200, self._poll)

    def _capture(self):
        try:
            from PIL import Image, ImageGrab
            image = ImageGrab.grab()
            image.thumbnail((768, 576), Image.Resampling.BILINEAR)
            with io.BytesIO() as stream:
                image.convert("RGB").save(stream, format="JPEG", quality=48, optimize=False)
                blob = stream.getvalue()
            if len(blob) > 512 * 1024:
                raise ValueError("Bildgröße überschreitet Sicherheitslimit.")
            path = self.live.frame_path
            temporary = path.with_suffix(".jpg.tmp")
            fd = os.open(str(temporary), os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "wb") as output:
                output.write(blob)
            if self.live.active():
                os.replace(temporary, path)
            else:
                os.unlink(temporary)
        except (OSError, ValueError, ImportError) as exc:
            LOG.warning("Fernbild nicht verfügbar: %s", exc)
        finally:
            self.capturing = False
