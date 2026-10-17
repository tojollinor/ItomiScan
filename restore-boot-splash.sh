#!/usr/bin/env bash
# Restore the theme and GRUB settings backed up by setup-boot-splash.sh.
# Usage: sudo bash restore-boot-splash.sh /var/lib/itomiscan/boot-backups/BACKUP
set -Eeuo pipefail

[[ $EUID -eq 0 && $# -eq 1 ]] || {
  echo "Als root mit genau einem Sicherungsordner aufrufen." >&2
  exit 2
}
BACKUP="$(realpath -e -- "$1")"
case "$BACKUP" in
  /var/lib/itomiscan/boot-backups/*) ;;
  *) echo "Ungültiger Sicherungspfad." >&2; exit 2 ;;
esac
[[ -f "$BACKUP/grub.original" ]] || { echo "GRUB-Sicherung fehlt." >&2; exit 3; }
command -v update-grub >/dev/null
command -v update-initramfs >/dev/null
command -v plymouth-set-default-theme >/dev/null

# A saved configuration that selects the custom DEP image needs its own
# explicit initramfs recovery plan. Do not restore it and update the wrong image.
SAVED_DEFAULT="$(sed -nE 's/^GRUB_DEFAULT="?([^"]*)"?$/\1/p' "$BACKUP/grub.original" | head -n 1)"
if [[ "$SAVED_DEFAULT" == "itomiscan-initramfs-dep-test" ]]; then
  echo "Abbruch: die Sicherung wählt die separate DEP-Test-Initramfs."
  echo "Eine getrennte Wiederherstellung der aktiven Initramfs ist erforderlich."
  exit 4
fi

theme_dir="/usr/share/plymouth/themes/itomiscan"
static_theme_dir="/usr/share/plymouth/themes/itomiscan-static"
rollback_dir="$(mktemp -d -p /var/lib/itomiscan/boot-backups "restore-current-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXXXX")"
cp -a /etc/default/grub "$rollback_dir/grub.current"
[[ ! -d "$theme_dir" ]] || cp -a "$theme_dir" "$rollback_dir/itomiscan.current"
[[ ! -d "$static_theme_dir" ]] || cp -a "$static_theme_dir" "$rollback_dir/itomiscan-static.current"
echo "Aktueller Zustand vor Wiederherstellung gesichert: $rollback_dir"

restore_theme() {
  local source="$1" target="$2" absent_marker="$3"
  if [[ -d "$source" ]]; then
    local staged="${target}.restore.$$"
    rm -rf -- "$staged"
    cp -a -- "$source" "$staged"
    rm -rf -- "$target"
    mv -- "$staged" "$target"
  elif [[ -f "$absent_marker" ]]; then
    rm -rf -- "$target"
  fi
}
restore_theme "$BACKUP/previous-itomiscan-theme" "$theme_dir" "$BACKUP/previous-itomiscan-theme.absent"
restore_theme "$BACKUP/previous-itomiscan-static-theme" "$static_theme_dir" "$BACKUP/previous-itomiscan-static-theme.absent"

install -m 0644 "$BACKUP/grub.original" /etc/default/grub
if [[ -s "$BACKUP/previous-theme-name" ]]; then
  PREVIOUS="$(head -n 1 "$BACKUP/previous-theme-name")"
  if [[ "$PREVIOUS" =~ ^[a-zA-Z0-9_-]+$ ]]; then
    plymouth-set-default-theme "$PREVIOUS"
  fi
fi
update-initramfs -u
update-grub
echo "Plymouth-Theme und GRUB-Konfiguration aus der Sicherung wiederhergestellt."
echo "Die normale Kernel-Initramfs wurde neu erzeugt; Neustart vor Ort prüfen."
echo "Sicherung des Zustands vor der Wiederherstellung: $rollback_dir"
