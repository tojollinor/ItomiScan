#!/bin/sh
# Xorg starts exclusively on the local scanner display; no web listener.
set -eu
xset s off 2>/dev/null || true
xset -dpms 2>/dev/null || true
exec /usr/bin/python3 "$(dirname "$0")/app.py"
