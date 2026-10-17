#!/usr/bin/env bash
# Manual, separate GRUB one-shot test for the ItomiScan splash candidate.
# Modes: status (read-only), prepare (backed-up GRUB entry), once (one-shot).
# No mode reboots, replaces initramfs images, or changes GRUB_DEFAULT.
set -Eeuo pipefail
KERNEL="6.1.0-50-686-pae"
ROOT_UUID="5b4ffd28-6d80-43e9-bb65-bb62d0b845ac"
ENTRY_ID="itomiscan-splash-candidate-test"
OLD_ID="itomiscan-initramfs-dep-test"
CANDIDATE="/boot/initrd.img-${KERNEL}-itomiscan-splash-test"
ORIGINAL="/boot/initrd.img-${KERNEL}"
DEP="/boot/initrd.img-${KERNEL}-dep-test"
VMLINUX="/boot/vmlinuz-${KERNEL}"
CUSTOM="/etc/grub.d/40_custom"
GRUB_CFG="/boot/grub/grub.cfg"
GRUB_ENV="/boot/grub/grubenv"
BACKUP_PARENT="/var/lib/itomiscan/boot-backups"
BEGIN_MARK="# BEGIN ITOMISCAN SPLASH CANDIDATE TEST"
END_MARK="# END ITOMISCAN SPLASH CANDIDATE TEST"
CONFIGURED_DEFAULT=''

usage() {
  echo "Verwendung: bash test-boot-splash-candidate.sh status|prepare|once" >&2
  exit 2
}
[[ $# -eq 1 ]] || usage
MODE="$1"
case "$MODE" in status|prepare|once) ;; *) usage ;; esac

check_host() {
  [[ "$(uname -r)" == "$KERNEL" ]] || { echo "Unerwarteter Kernel" >&2; exit 3; }
  [[ ! -d /sys/firmware/efi ]] || { echo "UEFI statt des geprueften BIOS/Legacy-Systems" >&2; exit 3; }
  [[ -r /etc/default/grub && -r "$GRUB_CFG" && -f "$CUSTOM" ]] || {
    echo "GRUB-Dateien fehlen" >&2; exit 3;
  }
  [[ -s "$ORIGINAL" && -s "$DEP" && -s "$VMLINUX" && -s "$CANDIDATE" ]] || {
    echo "Original-, DEP-, Kernel- oder Kandidaten-Datei fehlt" >&2; exit 3;
  }
  [[ ! -L "$CANDIDATE" ]] || { echo "Kandidat darf kein Symlink sein" >&2; exit 3; }
  [[ "$(findmnt -nro UUID /)" == "$ROOT_UUID" ]] || {
    echo "Root-UUID stimmt nicht mit dem N1800 ueberein" >&2; exit 3;
  }
  CONFIGURED_DEFAULT="$(sed -nE 's/^GRUB_DEFAULT="?([^"]*)"?$/\1/p' /etc/default/grub | head -n 1)"
  [[ "$CONFIGURED_DEFAULT" == "$OLD_ID" ]] || {
    echo "GRUB_DEFAULT ist nicht der bestaetigte DEP-Eintrag; sicherer Abbruch" >&2; exit 4;
  }
  grep -Eq '^GRUB_TIMEOUT=2$' /etc/default/grub || {
    echo "GRUB_TIMEOUT ist nicht mehr 2; sicherer Abbruch" >&2; exit 4;
  }
  local next_entry
  next_entry="$(grub-editenv "$GRUB_ENV" list | sed -n 's/^next_entry=//p' | head -n 1)"
  [[ -z "$next_entry" ]] || {
    echo "Andere einmalige Bootwahl ist bereits aktiv: $next_entry" >&2; exit 4;
  }
  command -v lsinitramfs >/dev/null
  local manifest
  manifest="$(lsinitramfs "$CANDIDATE")"
  grep -Fq "usr/lib/modules/$KERNEL/kernel/drivers/gpu/drm/i915/i915.ko" <<< "$manifest" || {
    echo "i915 fehlt im Kandidaten" >&2; exit 5;
  }
  grep -Fq "usr/share/plymouth/themes/itomiscan/itomiscan.script" <<< "$manifest" || {
    echo "Animiertes ItomiScan-Theme fehlt im Kandidaten" >&2; exit 5;
  }
  grep -Fq "usr/share/plymouth/themes/itomiscan/scanline.png" <<< "$manifest" || {
    echo "Scanliniengrafik fehlt im Kandidaten" >&2; exit 5;
  }
}

if [[ "$MODE" == status ]]; then
  echo "=== ItomiScan Splash-Kandidat: Status (nur lesend) ==="
  uname -r
  ls -lh "$ORIGINAL" "$DEP" "$CANDIDATE" "$VMLINUX" 2>&1 || true
  grep -E '^(GRUB_DEFAULT|GRUB_TIMEOUT|GRUB_TIMEOUT_STYLE)=' /etc/default/grub 2>/dev/null || true
  grub-editenv "$GRUB_ENV" list 2>/dev/null || true
  grep -F "$ENTRY_ID" "$GRUB_CFG" 2>/dev/null || true
  echo "Keine Einstellungen veraendert."
  exit 0
fi

[[ $EUID -eq 0 ]] || { echo "Nur root, nur mit physischem Recovery-Zugang" >&2; exit 2; }
for command_name in grub-editenv grub-reboot grub-script-check update-grub findmnt sha256sum; do
  command -v "$command_name" >/dev/null 2>&1 || {
    echo "Befehl fehlt: $command_name" >&2; exit 3;
  }
done
check_host

if [[ "$MODE" == once ]]; then
  grep -Fq -- "$BEGIN_MARK" "$CUSTOM" || {
    echo "Testeintrag nicht vorbereitet" >&2; exit 3;
  }
  grep -Fq -- "$ENTRY_ID" "$GRUB_CFG" || {
    echo "Testeintrag nicht in grub.cfg" >&2; exit 3;
  }
  grep -Fq -- "initrd /boot/initrd.img-${KERNEL}-itomiscan-splash-test" "$GRUB_CFG" || {
    echo "Testeintrag zeigt nicht auf den Kandidaten" >&2; exit 3;
  }
  grub-script-check "$GRUB_CFG"
  grub-reboot "$ENTRY_ID"
  grub-editenv "$GRUB_ENV" list | grep -Fx "next_entry=$ENTRY_ID" >/dev/null || {
    echo "GRUB-Einmalwahl nicht bestaetigt" >&2; exit 5;
  }
  echo "NUR naechster Start waehlt Testkandidaten. KEIN reboot ausgefuehrt."
  echo "Danach soll automatisch wieder GRUB_DEFAULT=$OLD_ID gelten."
  exit 0
fi

[[ -x "$CUSTOM" ]] || { echo "GRUB 40_custom nicht ausfuehrbar" >&2; exit 3; }
if grep -Fq -- "$BEGIN_MARK" "$CUSTOM" || grep -Fq -- "$ENTRY_ID" "$CUSTOM"; then
  if grep -Fq -- "$BEGIN_MARK" "$CUSTOM" &&
     grep -Fq -- "$END_MARK" "$CUSTOM" &&
     grep -Fq -- "menuentry 'ItomiScan Splash Kandidat' --id='$ENTRY_ID'" "$CUSTOM" &&
     grep -Fq -- "initrd /boot/initrd.img-${KERNEL}-itomiscan-splash-test" "$CUSTOM" &&
     grep -Fq -- "$ENTRY_ID" "$GRUB_CFG"; then
    echo "Testeintrag bereits vorhanden; keine Aenderung."
    grub-script-check "$GRUB_CFG"
    exit 0
  fi
  echo "Nicht eindeutig uebereinstimmender Splash-Testeintrag; Abbruch" >&2
  exit 4
fi

install -d -m 0700 "$BACKUP_PARENT"
backup="$(mktemp -d -p "$BACKUP_PARENT" "splash-grub-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXXXX")"
cp -a "$CUSTOM" "$backup/40_custom.before"
cp -a "$GRUB_CFG" "$backup/grub.cfg.before"
cp -a /etc/default/grub "$backup/grub.default.before"
sha256sum "$ORIGINAL" "$DEP" "$CANDIDATE" > "$backup/image-sha256.before"
for item in "$CUSTOM" "$GRUB_CFG" /etc/default/grub; do
  case "$item" in
    "$CUSTOM") save="$backup/40_custom.before" ;;
    "$GRUB_CFG") save="$backup/grub.cfg.before" ;;
    *) save="$backup/grub.default.before" ;;
  esac
  cmp -s "$item" "$save" || { echo "Sicherung fehlgeschlagen" >&2; exit 5; }
done
echo "Backup: $backup"

restore_grub() {
  cp -a "$backup/40_custom.before" "$CUSTOM"
  cp -a "$backup/grub.cfg.before" "$GRUB_CFG"
}
cat >> "$CUSTOM" <<EOF

$BEGIN_MARK
menuentry 'ItomiScan Splash Kandidat' --id='$ENTRY_ID' {
    insmod part_msdos
    insmod ext2
    search --no-floppy --fs-uuid --set=root $ROOT_UUID
    linux /boot/vmlinuz-$KERNEL root=UUID=$ROOT_UUID ro quiet splash
    initrd /boot/initrd.img-$KERNEL-itomiscan-splash-test
}
$END_MARK
EOF

if ! update-grub || ! grub-script-check "$GRUB_CFG" ||
   ! grep -Fq "$ENTRY_ID" "$GRUB_CFG"; then
  echo "GRUB-Eintrag konnte nicht sicher vorbereitet werden; Wiederherstellung" >&2
  restore_grub
  exit 6
fi

cmp -s /etc/default/grub "$backup/grub.default.before" || {
  echo "GRUB-Standard wurde unerwartet veraendert; Wiederherstellung" >&2
  cp -a "$backup/grub.default.before" /etc/default/grub
  restore_grub
  exit 6
}
sha256sum -c "$backup/image-sha256.before" >/dev/null || {
  echo "Initramfs-Daten sind nicht unveraendert; Wiederherstellung" >&2
  restore_grub
  exit 6
}
echo "Separater Testeintrag vorbereitet; originaler GRUB_DEFAULT bleibt unveraendert."
echo "Kein Neustart, kein grub-reboot ausgefuehrt."
echo "Einmalwahl nur im betreuten Wartungsfenster: bash test-boot-splash-candidate.sh once"
