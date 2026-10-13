"""Bounded, headless startup checks for the N1800 kiosk.

All I/O runs in a background thread; callbacks contain no Tk operations.
The USB check proves enumeration, not that every physical tap works.
"""

import re
import subprocess
import time
from pathlib import Path


TOUCH_VENDOR = "0430"
TOUCH_PRODUCT = "0501"


class StartupFailure(RuntimeError):
    """Hardware was not ready before the deadline."""

    def __init__(self, message, detail=""):
        super().__init__(message)
        self.detail = detail


def touch_detected(input_devices="/proc/bus/input/devices"):
    """Check the N1800 USB touch device appears in the Linux input subsystem.

    Being present is a necessary but not sufficient condition for actual touch
    calibration: that must still be verified on the real device.
    """
    try:
        devices = Path(input_devices).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    for block in re.split(r"\n\s*\n", devices):
        identifier = re.search(r"\bVendor=([0-9a-f]{4})\s+Product=([0-9a-f]{4})\b",
                               block, re.IGNORECASE)
        if identifier and identifier.group(1).lower() == TOUCH_VENDOR and \
                identifier.group(2).lower() == TOUCH_PRODUCT and \
                re.search(r"\bevent\d+\b", block):
            return True
    return False


def wait_until_ready(find_device, read_options, report, *, touch_probe=touch_detected,
                     timeout=45, retry_delay=0.6, clock=time.monotonic, sleep=time.sleep):
    """Return (device, options) only once touch and SANE are both available.

    The callers must impose their own per-subprocess timeout; this function
    bounds retries, but cannot interrupt an arbitrary blocking callback.
    Report(step, message) is called only on status changes.
    """
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    deadline = clock() + timeout
    last = None
    last_error = ""

    def status(stage, message):
        nonlocal last
        item = (stage, message)
        if item != last:
            last = item
            report(*item)

    status("touch", "Touchscreen wird erkannt …")
    while clock() < deadline:
        try:
            if touch_probe():
                break
        except OSError as exc:
            last_error = str(exc)
        sleep(min(retry_delay, max(0, deadline - clock())))
    else:
        raise StartupFailure("Touchscreen nicht erkannt.",
                             "USB-Touchpanel 0430:0501 fehlt im Linux-Eingabesystem. "
                             + last_error)

    status("touch_ok", "Touchgerät erkannt")
    status("scanner", "Scanner wird gesucht …")
    while clock() < deadline:
        try:
            device = find_device()
            if not device:
                last_error = "Kein Fujitsu-SANE-Gerät gefunden."
            else:
                status("options", "Scaneinstellungen werden geladen …")
                options = read_options(device)
                if options:
                    status("ready", "Scanner bereit")
                    return device, options
                last_error = "Keine Scanoptionen verfügbar."
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            last_error = str(exc)
        status("scanner", "Scanner wird gesucht …")
        sleep(min(retry_delay, max(0, deadline - clock())))
    raise StartupFailure("Scanner nicht bereit.", last_error)
