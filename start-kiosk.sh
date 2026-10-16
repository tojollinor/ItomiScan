#!/bin/sh
# Xorg starts exclusively on the local scanner display; no web listener.
set -eu
xset s off 2>/dev/null || true
xset -dpms 2>/dev/null || true
# Colour the X root immediately, before Tk starts, to avoid a black flash
# between the display-server handoff and the application splash.
xsetroot -solid "#101927" 2>/dev/null || true
# Resolve the repository root so the package and the old app.py are importable.
ROOT=$(CDPATH= cd "$(dirname "$0")" && pwd)
cd "$ROOT"
# Keep Debian SANE defaults untouched. Only this kiosk process and its
# scanimage subprocesses use the faster Fujitsu-only backend list.
# Include /etc/sane.d as fallback for fujitsu.conf and other backend settings.
export SANE_CONFIG_DIR="$ROOT/itomiscan/sane-config:/etc/sane.d"
exec /usr/bin/python3 -m itomiscan.gui.kiosk
