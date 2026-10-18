#!/usr/bin/env bash
# ItomiScan: make previously hardware-tested animated splash image default.
# Never rebuilds initramfs, changes kernel flags, or reboots.
set -Eeuo pipefail
mode="$1"
case "$mode" in check|apply) ;; *) echo "Use check|apply" >&2; exit 2;; esac
[[ $EUID == 0 ]] || { echo 'Root required' >&2; exit 2; }
old='GRUB_DEFAULT="itomiscan-initramfs-dep-test"'
new='GRUB_DEFAULT="itomiscan-animated-default"'
uuid=5b4ffd28-6d80-43e9-bb65-bb62d0b845ac
kernel=6.1.0-50-686-pae
image=/boot/initrd.img-6.1.0-50-686-pae-itomiscan-splash-test
custom=/etc/grub.d/43_itomiscan_animated_default
grub=/etc/default/grub
cfg=/boot/grub/grub.cfg
state=/root/itomiscan-animated-default-backup
p=/etc/systemd/system/plymouth-quit.service.d/90-itomiscan-retain-splash.conf
g=/etc/systemd/system/getty@tty1.service.d/zz-itomiscan-quiet-getty.conf
silent_state=/var/lib/itomiscan/silent-handover-test
die() { echo "STOP: $*" >&2; exit 3; }
[[ "$(uname -r)" == "$kernel" && ! -d /sys/firmware/efi ]] || die 'Unexpected kernel/boot mode'
[[ "$(findmnt -nro UUID /)" == "$uuid" ]] || die 'Unexpected root filesystem'
[[ -s "$image" && -s "/boot/vmlinuz-$kernel" && -s "$cfg" ]] || die 'Required files missing'
[[ ! -L "$image" ]] || die 'Image symlink'
grep -Fxq "$old" "$grub" || die 'Boot default not expected DEP setting'
[[ ! -e "$custom" && ! -L "$custom" && ! -e "$state" ]] || die 'Test entry or backup already exists'
[[ -z "$(grub-editenv /boot/grub/grubenv list | sed -n 's/^next_entry=//p')" ]] || die 'Pending one-shot selection'
# Confirm the tested animated Plymouth assets are embedded in this image.
manifest="$(lsinitramfs "$image")"
grep -Fxq 'usr/share/plymouth/themes/itomiscan/itomiscan.script' <<< "$manifest" || die 'Theme script missing'
grep -Fxq 'usr/share/plymouth/themes/itomiscan/scanline.png' <<< "$manifest" || die 'Animation image missing'
# Only revert our previous handover experiment if both files match its recorded hashes.
if [[ -e "$p" || -e "$g" || -e "$silent_state" ]]; then
  [[ -f "$p" && -f "$g" && -f "$silent_state/plymouth.sha" && -f "$silent_state/getty.sha" ]] ||
    die 'Incomplete silent-handover test; refusing to modify'
  [[ "$(sha256sum "$p" | cut -d' ' -f1)" == "$(cat "$silent_state/plymouth.sha")" ]] || die 'Plymouth test modified'
  [[ "$(sha256sum "$g" | cut -d' ' -f1)" == "$(cat "$silent_state/getty.sha")" ]] || die 'Getty test modified'
  rollback_silent=yes
else
  rollback_silent=no
fi
echo "Animated image: $image"
echo 'Permanent boot entry: itomiscan-animated-default'
echo "Undo unsuccessful handover test: $rollback_silent"
if [[ "$mode" == check ]]; then echo 'Read-only check OK'; exit 0; fi
mkdir -m 0700 "$state"
cp -a "$grub" "$state/default-grub"
cp -a "$cfg" "$state/grub.cfg"
sha256sum "$image" "/boot/vmlinuz-$kernel" > "$state/boot.sha256"
cat > "$custom" <<ENTRY
#!/bin/sh
exec tail -n +3 \$0
menuentry 'ItomiScan Animated Default' --id='itomiscan-animated-default' {
  insmod part_msdos
  insmod ext2
  search --no-floppy --fs-uuid --set=root $uuid
  linux /boot/vmlinuz-$kernel root=UUID=$uuid ro quiet splash
  initrd /boot/initrd.img-$kernel-itomiscan-splash-test
}
ENTRY
chmod 755 "$custom"
python3 - "$grub" "$old" "$new" <<'PY'
import sys
from pathlib import Path
path = Path(sys.argv[1])
text = path.read_text()
if text.splitlines().count(sys.argv[2]) != 1:
    raise SystemExit('Unexpected GRUB default')
path.write_text(text.replace(sys.argv[2], sys.argv[3], 1))
PY
if ! update-grub || ! grub-script-check "$cfg" ||
  ! grep -Fq 'itomiscan-animated-default' "$cfg" ||
  ! sha256sum -c "$state/boot.sha256" >/dev/null; then
  cp -a "$state/default-grub" "$grub"
  cp -a "$state/grub.cfg" "$cfg"
  rm -f -- "$custom"
  die 'GRUB verification failed; GRUB restored'
fi
if [[ "$rollback_silent" == yes ]]; then
  cp -a "$p" "$state/plymouth-test"
  cp -a "$g" "$state/getty-test"
  rm -- "$p" "$g"
  systemctl daemon-reload
fi
echo 'Animated image is now the permanent GRUB default.'
echo "Backup: $state"
echo 'No reboot executed. DEP image unchanged.'
