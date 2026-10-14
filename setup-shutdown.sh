#!/usr/bin/env bash
# Configure narrowly scoped poweroff and reboot privileges for the kiosk user.
# Run as root. Optionally pass the existing non-root kiosk user name.
set -euo pipefail

if [[ $EUID -ne 0 || $# -gt 1 ]]; then
  echo "Verwendung (als root): bash setup-shutdown.sh [BENUTZERNAME]" >&2
  exit 2
fi

if [[ $# -eq 1 ]]; then
  USER_NAME="$1"
else
  CONFIG="/etc/systemd/system/getty@tty1.service.d/itomiscan.conf"
  if [[ ! -r "$CONFIG" ]]; then
    echo "ItomiScan-Autologin nicht gefunden. Benutzername als Argument angeben." >&2
    exit 2
  fi
  USER_NAME="$(sed -n 's/.*--autologin \([^ ]*\).*/\1/p' "$CONFIG" | head -n 1)"
fi

if [[ ! "$USER_NAME" =~ ^[a-z_][a-z0-9_-]*$ ]] || ! id "$USER_NAME" >/dev/null 2>&1 || [[ "$(id -u "$USER_NAME")" -eq 0 ]]; then
  echo "Ungueltiger normaler ItomiScan-Benutzer: $USER_NAME" >&2
  exit 2
fi

if [[ ! -x /usr/bin/systemctl ]]; then
  echo "/usr/bin/systemctl nicht vorhanden; Herunterfahren kann nicht eingerichtet werden." >&2
  exit 3
fi

if ! command -v sudo >/dev/null 2>&1; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get install -y --no-install-recommends sudo
fi

install -d -m 0755 /etc/sudoers.d
RULE="/etc/sudoers.d/itomiscan-poweroff"
TEMP="$(mktemp /etc/sudoers.d/.itomiscan-poweroff.XXXXXX)"
trap 'rm -f "$TEMP"' EXIT
printf '%s ALL=(root) NOPASSWD: /usr/bin/systemctl poweroff, /usr/bin/systemctl reboot\n' "$USER_NAME" >"$TEMP"
chmod 0440 "$TEMP"
visudo -cf "$TEMP" >/dev/null
install -o root -g root -m 0440 "$TEMP" "$RULE"
visudo -cf "$RULE" >/dev/null

echo "Ausschalten eingerichtet fuer $USER_NAME."
echo "Erlaubt: sudo -n /usr/bin/systemctl poweroff oder reboot"
