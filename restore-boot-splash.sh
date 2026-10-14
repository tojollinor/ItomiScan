#!/usr/bin/env bash
# Restore GRUB defaults saved by setup-boot-splash.sh.
# Usage: sudo bash restore-boot-splash.sh /var/lib/itomiscan/boot-backups/BACKUP
set -Eeuo pipefail
[[ $EUID -eq 0 && $# -eq 1 ]] || { echo "Als root mit genau einem Sicherungsordner aufrufen." >&2; exit 2; }
BACKUP="$(realpath -e -- "$1")"
case "$BACKUP" in /var/lib/itomiscan/boot-backups/*) ;; *) echo "Ungültiger Sicherungspfad." >&2; exit 2;; esac
[[ -f "$BACKUP/grub.original" ]] || { echo "GRUB-Sicherung fehlt." >&2; exit 3; }
command -v update-grub >/dev/null
command -v update-initramfs >/dev/null
install -m 0644 "$BACKUP/grub.original" /etc/default/grub
if [[ -s "$BACKUP/plymouth-theme.original" ]]; then
  PREVIOUS="$(head -n 1 "$BACKUP/plymouth-theme.original")"
  if [[ "$PREVIOUS" =~ ^[a-zA-Z0-9_-]+$ ]]; then
    plymouth-set-default-theme "$PREVIOUS"
  fi
fi
update-initramfs -u
update-grub
echo "GRUB und Plymouth-Konfiguration wiederhergestellt. Bitte Neustart prüfen."
