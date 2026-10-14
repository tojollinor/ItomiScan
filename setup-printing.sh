#!/usr/bin/env bash
# Manual opt-in: install CUPS and enable driverless printer administration.
# NEVER invoked by main-branch scanner updates or the standard installer.
# Usage as root: bash setup-printing.sh SCANNER_USER
set -euo pipefail
umask 077

if [[ "$EUID" -ne 0 || "$#" -ne 1 ]]; then
  echo "Als root: bash setup-printing.sh SCANNERBENUTZER" >&2
  exit 2
fi
SCANNER_USER="$1"
if [[ ! "$SCANNER_USER" =~ ^[a-z_][a-z0-9_-]*$ ]] ||
   ! id "$SCANNER_USER" >/dev/null 2>&1 ||
   [[ "$(id -u "$SCANNER_USER")" -eq 0 ]]; then
  echo "Ein gueltiger, existierender Linux-Normalbenutzer ist erforderlich." >&2
  exit 2
fi

HOME_DIR="$(getent passwd "$SCANNER_USER" | cut -d: -f6)"
ROOT="$HOME_DIR/ItomiScan"
if [[ ! "$HOME_DIR" =~ ^/[A-Za-z0-9/_-]+$ ]] ||
   [[ ! -f "$ROOT/itomiscan/integrations/printing.py" ]]; then
  echo "Die ItomiScan-Entwicklungs-/Releasefassung wurde nicht gefunden." >&2
  exit 3
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends cups cups-client cups-filters
systemctl enable --now cups.service

# CUPS UI / IPP service must stay local. ItomiScan's authenticated webadmin
# is the only service deliberately exposed on the LAN.
cupsctl --no-remote-admin --no-share-printers --no-remote-any

# CUPS lpadmin is privileged queue administration. This group membership is
# explicitly opt-in; its consequences are documented in docs/PRINTING.md.
usermod -a -G lpadmin "$SCANNER_USER"
systemctl restart cups.service

# Group changes require a freshly started webadmin user process.
if systemctl is-active --quiet itomiscan-web.service; then
  systemctl restart itomiscan-web.service
fi

echo "CUPS eingerichtet, remote CUPS-Administration ist gesperrt."
echo "Benutzer $SCANNER_USER ist in der Gruppe lpadmin."
echo "Webadministration: ItomiScan > Drucker; IPP Everywhere registrieren."
echo "CUPS-Test: lpstat -e"
echo "ACHTUNG: lpadmin ermoeglicht diesem Linux-Benutzer die Verwaltung aller CUPS-Queues."
echo "Keine Drucker/Scandokumente wurden automatisch gesendet oder geloescht."
