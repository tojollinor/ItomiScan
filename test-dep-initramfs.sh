#!/usr/bin/env bash
# ItomiScan: opt-in one-time boot of an already tested dependency initramfs.
# Never changes the default boot entry or replaces the original initramfs.
# Usage (as root, locally recoverable system): bash test-dep-initramfs.sh prepare|once|status
set -Eeuo pipefail

ROOT_UUID="5b4ffd28-6d80-43e9-bb65-bb62d0b845ac"
KERNEL="6.1.0-50-686-pae"
ENTRY_ID="itomiscan-initramfs-dep-test"
MARK_BEGIN="# BEGIN ITOMISCAN DEP INITRAMFS TEST"
MARK_END="# END ITOMISCAN DEP INITRAMFS TEST"
CUSTOM="/etc/grub.d/40_custom"
INITRD="/boot/initrd.img-${KERNEL}-dep-test"
ORIGINAL="/boot/initrd.img-${KERNEL}"
VMLINUX="/boot/vmlinuz-${KERNEL}"
BACKUPS="/var/lib/itomiscan/boot-backups"

usage() {
  echo "Verwendung: sudo bash test-dep-initramfs.sh prepare|once|status" >&2
  exit 2
}
[[ $# -eq 1 ]] || usage
MODE="$1"
[[ "$MODE" == prepare || "$MODE" == once || "$MODE" == status ]] || usage

if [[ "$MODE" == status ]]; then
  echo "=== ItomiScan Initramfs-Teststatus (nur lesend) ==="
  echo "Kernel: $(uname -r)"
  ls -lh -- "$ORIGINAL" "$INITRD" "$VMLINUX" 2>&1 || true
  echo "GRUB-Standard:"
  grep -E '^(GRUB_DEFAULT|GRUB_TIMEOUT|GRUB_TIMEOUT_STYLE)=' /etc/default/grub || true
  echo "GRUB-Einmalwahl:"
  grub-editenv /boot/grub/grubenv list 2>/dev/null || true
  echo "Testeintrag in generiertem GRUB:"
  grep -F -- "$ENTRY_ID" /boot/grub/grub.cfg || true
  echo "Keine Änderungen vorgenommen."
  exit 0
fi

[[ $EUID -eq 0 ]] || { echo "Nur als root ausführen." >&2; exit 2; }
[[ "$(uname -r)" == "$KERNEL" ]] || {
  echo "Unerwarteter Kernel. Test nur für $KERNEL freigegeben." >&2; exit 3;
}
[[ ! -d /sys/firmware/efi ]] || {
  echo "Nur BIOS/Legacy-Boot vorgeprüft, kein UEFI-Test." >&2; exit 3;
}
[[ -f "$CUSTOM" && -x "$CUSTOM" && -s "$ORIGINAL" && -s "$INITRD" && -s "$VMLINUX" ]] || {
  echo "Benötigte GRUB-Datei, Original- oder Test-Initramfs fehlt." >&2; exit 3;
}
[[ -f /boot/grub/grub.cfg && -f /etc/default/grub ]] || {
  echo "GRUB-Dateien fehlen." >&2; exit 3;
}
command -v update-grub >/dev/null
command -v grub-script-check >/dev/null
command -v grub-editenv >/dev/null
command -v grub-reboot >/dev/null
if command -v findmnt >/dev/null 2>&1; then
  actual_uuid="$(findmnt -nro UUID / || true)"
  [[ "$actual_uuid" == "$ROOT_UUID" ]] || {
    echo "Root-UUID weicht von geprüftem N1800 ab; Abbruch." >&2; exit 3;
  }
fi
# Never clobber a pending unrelated one-shot boot request.
next_entry="$(grub-editenv /boot/grub/grubenv list | sed -n 's/^next_entry=//p')"
[[ -z "$next_entry" ]] || {
  echo "Es ist bereits ein GRUB-Einmalstart vorgemerkt: $next_entry" >&2; exit 4;
}
# An untouched GRUB default must be retained; no automatic permanent promotion.
grep -Eq '^GRUB_DEFAULT=0$' /etc/default/grub || {
  echo "GRUB_DEFAULT ist nicht 0; den neuen Test zuerst manuell prüfen." >&2; exit 4;
}
grep -Eq '^GRUB_TIMEOUT=0$' /etc/default/grub || {
  echo "GRUB_TIMEOUT weicht vom dokumentierten System ab." >&2; exit 4;
}

if [[ "$MODE" == once ]]; then
  # A test entry is required already; prepare never implied by once.
  grep -Fq -- "$ENTRY_ID" /boot/grub/grub.cfg || {
    echo "Testeintrag nicht eingerichtet. Erst 'prepare' ausführen." >&2; exit 3;
  }
  grub-script-check /boot/grub/grub.cfg
  grub-reboot "$ENTRY_ID"
  grub-editenv /boot/grub/grubenv list | grep -Fx "next_entry=$ENTRY_ID" >/dev/null || {
    echo "Einmalwahl konnte nicht verifiziert werden." >&2; exit 5;
  }
  echo "NUR nächster Boot auf Test-Initramfs vorgemerkt. Kein Neustart ausgelöst."
  echo "Vor physischem reboot Rettungszugriff sicherstellen."
  exit 0
fi

# Prepare a dedicated menu entry without touching the existing default.
if grep -Fq -- "$MARK_BEGIN" "$CUSTOM"; then
  if grep -Fq -- "$MARK_END" "$CUSTOM" && grep -Fq -- "$ENTRY_ID" "$CUSTOM"; then
    echo "ItomiScan-Testeintrag ist bereits vorhanden. Keine erneute Änderung."
    grub-script-check /boot/grub/grub.cfg
    exit 0
  fi
  echo "Beschädigter/uneindeutiger bestehender Testeintrag; Abbruch." >&2
  exit 4
fi
if grep -Fq -- "$ENTRY_ID" "$CUSTOM"; then
  # Earlier N1800 testing already appended this exact entry manually.
  # Accept an existing entry only when its known kernel, test image and UUID
  # are present. Do not duplicate, rewrite, or silently override it.
  if grep -Fq -- "menuentry 'ItomiScan Initramfs DEP Test' --id='$ENTRY_ID'" "$CUSTOM" &&
     grep -Fq -- "initrd /boot/initrd.img-$KERNEL-dep-test" "$CUSTOM" &&
     grep -Fq -- "root=UUID=$ROOT_UUID" "$CUSTOM" &&
     grep -Fq -- "$ENTRY_ID" /boot/grub/grub.cfg; then
    grub-script-check /boot/grub/grub.cfg
    echo "Bereits geprüfter manueller N1800-Testeintrag vorhanden; keine Änderung."
    exit 0
  fi
  echo "Abweichender Eintrag mit derselben ID vorhanden; sicherer Abbruch." >&2
  exit 4
fi

install -d -m 0700 "$BACKUPS"
backup_dir="$(mktemp -d -p "$BACKUPS" "dep-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXXXX")"
cp -a "$CUSTOM" "$backup_dir/40_custom.original"
cp -a /boot/grub/grub.cfg "$backup_dir/grub.cfg.original"
cp -a /etc/default/grub "$backup_dir/grub.default.original"
cmp -s "$CUSTOM" "$backup_dir/40_custom.original" || exit 5
cmp -s /boot/grub/grub.cfg "$backup_dir/grub.cfg.original" || exit 5
echo "Backup: $backup_dir"
# Preserve all original GRUB entries, including menuentry 0.
cat >> "$CUSTOM" <<EOF

$MARK_BEGIN
menuentry 'ItomiScan Initramfs DEP Test' --id='$ENTRY_ID' {
    insmod part_msdos
    insmod ext2
    search --no-floppy --fs-uuid --set=root $ROOT_UUID
    linux /boot/vmlinuz-$KERNEL root=UUID=$ROOT_UUID ro quiet splash
    initrd /boot/initrd.img-$KERNEL-dep-test
}
$MARK_END
EOF

if ! update-grub || ! grub-script-check /boot/grub/grub.cfg; then
  echo "GRUB-Prüfung fehlgeschlagen. Versuche Sicherung zurückzusetzen." >&2
  cp -a "$backup_dir/40_custom.original" "$CUSTOM"
  cp -a "$backup_dir/grub.cfg.original" /boot/grub/grub.cfg
  exit 6
fi
grep -Fq -- "$ENTRY_ID" /boot/grub/grub.cfg || {
  echo "Testeintrag fehlt im generierten GRUB! Backup: $backup_dir" >&2
  exit 6
}
echo "Einmal-Testeintrag eingerichtet; GRUB_DEFAULT und Original-Initramfs unverändert."
echo "Nächster Schritt (nur bei physischer Rettungsmöglichkeit):"
echo "  sudo bash test-dep-initramfs.sh once"
echo "Danach bewusst reboot ausführen, Funktionen prüfen, Bootzeiten vergleichen."
