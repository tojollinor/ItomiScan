#!/bin/bash
# Install ItomiScan on Debian 12 (i386). Run as root: bash install.sh USERNAME
set -euo pipefail

if [[ $EUID -ne 0 || $# -ne 1 ]]; then
  echo "Verwendung: sudo bash install.sh BENUTZERNAME" >&2
  exit 2
fi

USER_NAME="$1"
if ! id "$USER_NAME" >/dev/null 2>&1 || [[ "$USER_NAME" == "root" ]]; then
  echo "Bitte einen existierenden normalen Benutzer angeben (nicht root)." >&2
  exit 2
fi
USER_HOME="$(getent passwd "$USER_NAME" | cut -d: -f6)"
PROJECT="$USER_HOME/ItomiScan"
if [[ "$( . /etc/os-release; echo "$VERSION_CODENAME" )" != "bookworm" ]]; then
  echo "Hinweis: Dieses Installationsskript wurde für Debian 12 (bookworm) entworfen."
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
  xserver-xorg-core xserver-xorg-input-libinput xserver-xorg-video-intel \
  xinit x11-xserver-utils xauth \
  python3 python3-tk python3-pil python3-pil.imagetk \
  sane-utils img2pdf git ca-certificates fonts-dejavu-core

if [[ -e "$PROJECT" && ! -d "$PROJECT/.git" ]]; then
  echo "Abbruch: $PROJECT existiert, ist aber kein Git-Repository." >&2
  exit 3
fi
if [[ ! -d "$PROJECT/.git" ]]; then
  runuser -u "$USER_NAME" -- git clone \
    https://github.com/tojollinor/ItomiScan.git "$PROJECT"
fi
# Prevent kiosk autostart from being enabled with syntactically invalid code.
/usr/bin/python3 -m py_compile "$PROJECT/app.py"
chmod +x "$PROJECT/start-kiosk.sh"
# GitHub Contents creates mode 100644; ignore this local executable-bit change.
runuser -u "$USER_NAME" -- git -C "$PROJECT" config core.filemode false
if getent group scanner >/dev/null; then
  usermod -aG scanner "$USER_NAME"
fi

PROFILE="$USER_HOME/.profile"
[[ -f "$USER_HOME/.bash_profile" ]] && PROFILE="$USER_HOME/.bash_profile"
if ! grep -q '# ITOMISCAN_KIOSK_START' "$PROFILE" 2>/dev/null; then
  cat >>"$PROFILE" <<'KIOSK'

# ITOMISCAN_KIOSK_START
# Only start X on the physical console, not during SSH connections.
if [ -z "$DISPLAY" ] && [ "$(tty)" = "/dev/tty1" ]; then
  startx "$HOME/ItomiScan/start-kiosk.sh" -- :0 vt1
fi
KIOSK
  chown "$USER_NAME":"$(id -gn "$USER_NAME")" "$PROFILE"
fi

install -d /etc/systemd/system/getty@tty1.service.d
cat >/etc/systemd/system/getty@tty1.service.d/itomiscan.conf <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin $USER_NAME --noclear %I \$TERM
EOF
systemctl daemon-reload
echo ""
echo "ItomiScan installiert: $PROJECT"
echo "Kiosk-Autostart beim naechsten Neustart aktiviert."
echo "Die bisherigen SSH-Einstellungen bleiben unveraendert."
echo "Zum Starten: sudo reboot"
echo "Beenden schliesst nur die GUI. Die Linux-Konsole bleibt verfuegbar."
