#!/usr/bin/env bash
# Optional delivery worker installation: only after explicitly approved deployment.
# Run as root: bash setup-delivery.sh SCANNER_LINUX_USER
# Never called by the existing main-branch GUI update or installer.
set -euo pipefail
if [[ "$EUID" -ne 0 || "$#" -ne 1 ]]; then
  echo "Verwendung: als root bash setup-delivery.sh SCANNERBENUTZER" >&2
  exit 2
fi
KIOSK_USER="$1"
if [[ ! "$KIOSK_USER" =~ ^[a-z_][a-z0-9_-]*$ ]] ||
    ! id "$KIOSK_USER" >/dev/null 2>&1 ||
    [[ "$(id -u "$KIOSK_USER")" -eq 0 ]]; then
  echo "Bitte einen existierenden normalen Linux-Benutzer angeben." >&2
  exit 2
fi
HOME_DIR="$(getent passwd "$KIOSK_USER" | cut -d: -f6)"
ROOT="$HOME_DIR/ItomiScan"
if [[ ! "$HOME_DIR" =~ ^/[A-Za-z0-9/_-]+$ ]] ||
    [[ ! -f "$ROOT/itomiscan/integrations/worker.py" ]]; then
  echo "ItomiScan-Entwicklungsfassung beim Benutzer nicht gefunden." >&2
  exit 3
fi
UNIT="/etc/systemd/system/itomiscan-delivery.service"
if [[ -e "$UNIT" ]]; then
  echo "Vorhandener Dienst wird aus Sicherheitsgründen nicht überschrieben." >&2
  exit 4
fi
GROUP="$(id -gn "$KIOSK_USER")"
cat > "$UNIT" <<EOF
[Unit]
Description=ItomiScan durable outgoing PDF deliveries
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$KIOSK_USER
Group=$GROUP
WorkingDirectory=$ROOT
Environment=HOME=$HOME_DIR
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/usr/bin/python3 -m itomiscan.integrations.worker --interval 15
Restart=on-failure
RestartSec=10
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=full
ProtectKernelTunables=yes
ProtectControlGroups=yes
UMask=0077
MemoryMax=200M

[Install]
WantedBy=multi-user.target
EOF
chmod 0644 "$UNIT"
systemctl daemon-reload
systemctl enable --now itomiscan-delivery.service
echo "Zustelldienst läuft. Status: systemctl status itomiscan-delivery"
echo "Anhalten: systemctl disable --now itomiscan-delivery"
echo "SMB benötigt smbclient. Für Paperless HTTPS CA-Zertifikate konfigurieren."
echo "USB-Stick muss bereits eingehängt sein. Keine automatische CIFS-Mount-Freigabe."
