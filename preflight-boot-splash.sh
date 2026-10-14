#!/usr/bin/env bash
# Read-only preflight for the optional ItomiScan Plymouth/GRUB setup.
# Safe to run over SSH before scheduling a local maintenance window.
set -euo pipefail
echo "=== ItomiScan Boot-Vorprüfung (nur lesend) ==="
echo "System: $(. /etc/os-release; echo "${PRETTY_NAME:-unbekannt}")"
echo "Architektur: $(dpkg --print-architecture 2>/dev/null || uname -m)"
echo "Kernel: $(uname -r)"
echo "Boot-Modus: $(if [[ -d /sys/firmware/efi ]]; then echo UEFI; else echo BIOS/Legacy; fi)"
echo "Aktive Plymouth-Vorgabe:"
if command -v plymouth-set-default-theme >/dev/null 2>&1; then
  plymouth-set-default-theme || true
else
  echo "Plymouth ist noch nicht installiert."
fi
echo "GRUB-Einstellungen:"
if [[ -r /etc/default/grub ]]; then
  grep -E '^(GRUB_TIMEOUT|GRUB_TIMEOUT_STYLE|GRUB_CMDLINE_LINUX_DEFAULT)=' /etc/default/grub || true
else
  echo "/etc/default/grub fehlt oder ist nicht lesbar."
fi
echo "Grafik-/Konsolenparameter:"
cat /proc/cmdline
echo "Bildschirmgeräte:"
ls -1 /sys/class/drm 2>/dev/null || true
echo "Displaymanager/getty:"
systemctl is-enabled getty@tty1.service 2>/dev/null || true
echo "Vorhandene ItomiScan-Boot-Sicherungen:"
if [[ -d /var/lib/itomiscan/boot-backups ]]; then
  find /var/lib/itomiscan/boot-backups -mindepth 1 -maxdepth 1 -type d -printf '%f\n' 2>/dev/null | sort
else
  echo "Noch keine Sicherungen."
fi
echo "Boot-Zeiten (sofern systemd-analyze verfügbar):"
if command -v systemd-analyze >/dev/null 2>&1; then
  systemd-analyze 2>/dev/null || true
fi
echo "=== Keine Systemdateien verändert. ==="
