#!/usr/bin/env bash
# Read-only boot diagnosis. Does not change GRUB, Plymouth or services.
set -euo pipefail
echo "=== ItomiScan: Bootdiagnose (nur lesend) ==="
date -Is
echo
echo "=== Gesamte Startdauer ==="
if command -v systemd-analyze >/dev/null 2>&1; then
  systemd-analyze time || true
  echo
  echo "=== Langsamste Dienste ==="
  systemd-analyze blame --no-pager | head -n 25 || true
  echo
  echo "=== Kritischer Startpfad ==="
  systemd-analyze critical-chain --no-pager || true
else
  echo "systemd-analyze nicht verfügbar"
fi
echo
echo "=== GRUB (nur aktuelle Werte) ==="
if [[ -r /etc/default/grub ]]; then
  grep -E '^(GRUB_TIMEOUT|GRUB_TIMEOUT_STYLE|GRUB_CMDLINE_LINUX_DEFAULT)=' /etc/default/grub || true
else
  echo "GRUB-Konfiguration nicht lesbar"
fi
echo
echo "=== Dienste mit Fehlerstatus ==="
systemctl --failed --no-pager || true
echo
echo "=== Plymouth / Display ==="
systemctl is-enabled display-manager.service 2>/dev/null || true
command -v plymouth-set-default-theme >/dev/null 2>&1 && plymouth-set-default-theme || true
echo
echo "Diagnose beendet. Es wurden keine Einstellungen verändert."
