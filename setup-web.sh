#!/usr/bin/env bash
# Explicit, opt-in installation of a non-root HTTPS admin service on Debian 12.
# Usage (root): bash setup-web.sh KIOSK_USER LAN_IPv4
# Not part of the normal installer and never triggered by GUI updates.
set -euo pipefail
umask 077

if [[ $EUID -ne 0 || $# -ne 2 ]]; then
  echo "Verwendung: als root bash setup-web.sh BENUTZER LAN_IPv4" >&2
  exit 2
fi
USER_NAME="$1"
BIND_IP="$2"
if [[ ! "$USER_NAME" =~ ^[a-z_][a-z0-9_-]*$ ]] || ! id "$USER_NAME" >/dev/null 2>&1 || [[ "$(id -u "$USER_NAME")" -eq 0 ]]; then
  echo "Ein gültiger normaler Linux-Benutzer ist erforderlich." >&2
  exit 2
fi
if ! /usr/bin/python3 - "$BIND_IP" <<'PY'
import ipaddress
import sys
try:
    addr = ipaddress.ip_address(sys.argv[1])
except ValueError:
    sys.exit(1)
# Allow RFC1918 networks and the CGNAT range for certain VPNs.
private = addr.is_private or addr in ipaddress.ip_network("100.64.0.0/10")
sys.exit(0 if addr.version == 4 and private and not addr.is_loopback
         and not addr.is_unspecified else 1)
PY
then
  echo "Bitte eine konkrete LAN-/VPN-IPv4-Adresse angeben (kein 0.0.0.0)." >&2
  exit 2
fi

HOME_DIR="$(getent passwd "$USER_NAME" | cut -d: -f6)"
PROJECT="$HOME_DIR/ItomiScan"
if [[ ! "$HOME_DIR" =~ ^/[a-zA-Z0-9/_-]+$ ]] || [[ ! -f "$PROJECT/itomiscan/web/server.py" ]]; then
  echo "Projekt oder Benutzerpfad ist ungültig. Erst Entwicklungsfassung installieren." >&2
  exit 3
fi
# Refuse public installation before a strong password is configured.
if ! runuser -u "$USER_NAME" -- /usr/bin/env PYTHONPATH="$PROJECT" \
       /usr/bin/python3 -m itomiscan.web.cli is-ready; then
  echo "Vorher als Scannerbenutzer ausführen:" >&2
  echo "cd $PROJECT && python3 -m itomiscan.web.cli init-admin" >&2
  exit 3
fi
if ! command -v openssl >/dev/null 2>&1; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get install -y --no-install-recommends openssl
fi
TLS_DIR="$HOME_DIR/.config/itomiscan/tls"
install -o "$USER_NAME" -g "$(id -gn "$USER_NAME")" -m 0700 -d "$TLS_DIR"
if [[ ! -f "$TLS_DIR/cert.pem" || ! -f "$TLS_DIR/key.pem" ]]; then
  runuser -u "$USER_NAME" -- openssl req -x509 -newkey rsa:2048 \
    -nodes -days 365 \
    -subj "/CN=$BIND_IP" -addext "subjectAltName=IP:$BIND_IP" \
    -keyout "$TLS_DIR/key.pem" -out "$TLS_DIR/cert.pem"
fi
chmod 0600 "$TLS_DIR/key.pem"
chmod 0644 "$TLS_DIR/cert.pem"

SERVICE=/etc/systemd/system/itomiscan-web.service
if [[ -e "$SERVICE" ]]; then
  echo "Dienst existiert bereits. Sicherheitsbedingt kein Überschreiben." >&2
  exit 4
fi
cat >"$SERVICE" <<EOF
[Unit]
Description=ItomiScan HTTPS Webadministration
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER_NAME
Group=$(id -gn "$USER_NAME")
WorkingDirectory=$PROJECT
Environment=HOME=$HOME_DIR
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/usr/bin/python3 -m itomiscan.web.server --bind $BIND_IP --port 8443 --cert $TLS_DIR/cert.pem --key $TLS_DIR/key.pem
Restart=on-failure
RestartSec=5
NoNewPrivileges=yes
PrivateTmp=no
# Xorg exposes the kiosk X11 Unix socket under /tmp/.X11-unix.
# Keep the remaining systemd hardening and the loopback-only VNC policy.
ProtectSystem=full
ProtectKernelTunables=yes
ProtectControlGroups=yes
UMask=0077
MemoryMax=128M

[Install]
WantedBy=multi-user.target
EOF
chmod 0644 "$SERVICE"
systemctl daemon-reload
systemctl enable --now itomiscan-web.service
echo "Webadministration aktiviert: https://$BIND_IP:8443"
echo "Self-signed-Zertifikat: Browser warnt bis das Zertifikat vertraut wird."
echo "Nicht ins öffentliche Internet freigeben. Zugriff nur aus LAN/VPN."
