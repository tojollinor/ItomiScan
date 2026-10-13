#!/bin/sh
# Xorg starts exclusively on the local scanner display; no web listener.
set -eu
xset s off 2>/dev/null || true
xset -dpms 2>/dev/null || true
# Resolve the repository root so the package and the old app.py are importable.
ROOT=$(CDPATH= cd "$(dirname "$0")" && pwd)
cd "$ROOT"
exec /usr/bin/python3 -m itomiscan.gui.kiosk
