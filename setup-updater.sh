#!/usr/bin/env bash
# Install the root-owned, argument-restricted beta updater. Run only as root.
set -euo pipefail
umask 077
if [[ "$EUID" -ne 0 || "$#" -ne 1 ]]; then
  echo "Verwendung: als root bash setup-updater.sh BENUTZERNAME" >&2
  exit 2
fi
USER_NAME="$1"
if [[ ! "$USER_NAME" =~ ^[a-z_][a-z0-9_-]*$ ]] ||
   ! id "$USER_NAME" >/dev/null 2>&1 ||
   [[ "$(id -u "$USER_NAME")" -eq 0 ]]; then
  echo "Ungültiger Scanner-Benutzer." >&2
  exit 2
fi
HOME_DIR="$(getent passwd "$USER_NAME" | cut -d: -f6)"
if [[ ! "$HOME_DIR" =~ ^/home/[a-zA-Z0-9_-]+$ ]]; then
  echo "Ungeeignetes Home-Verzeichnis." >&2
  exit 2
fi
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
HELPER="$SCRIPT_DIR/scripts/itomiscan-beta-updater.py"
[[ -f "$HELPER" ]] || { echo "Updater-Helfer fehlt." >&2; exit 3; }
/usr/bin/python3 -m py_compile "$HELPER"
install -d -o root -g root -m 0755 /usr/local/libexec
install -d -o root -g root -m 0700 /etc/itomiscan
install -d -o root -g root -m 0700 /var/lib/itomiscan-updater
install -o root -g root -m 0755 "$HELPER" /usr/local/libexec/itomiscan-beta-updater
USER_NAME="$USER_NAME" HOME_DIR="$HOME_DIR" /usr/bin/python3 - <<'PY'
import json, os
from pathlib import Path
path = Path("/etc/itomiscan/updater.json")
tmp = path.with_suffix(".tmp")
with tmp.open("w", encoding="utf-8") as handle:
    json.dump({"user": os.environ["USER_NAME"], "home": os.environ["HOME_DIR"]}, handle)
tmp.chmod(0o600)
tmp.replace(path)
PY
RULE="/etc/sudoers.d/itomiscan-beta-updater"
TEMP="$(mktemp /etc/sudoers.d/.itomiscan-beta-updater.XXXXXX)"
trap 'rm -f "$TEMP"' EXIT
printf '%s ALL=(root) NOPASSWD: /usr/local/libexec/itomiscan-beta-updater install, /usr/local/libexec/itomiscan-beta-updater rollback\n' "$USER_NAME" > "$TEMP"
chmod 0440 "$TEMP"
visudo -cf "$TEMP" >/dev/null
install -o root -g root -m 0440 "$TEMP" "$RULE"
visudo -cf "$RULE" >/dev/null
echo "ItomiScan Beta-Updater eingerichtet (nur install/rollback, als Root-Hilfe)."
