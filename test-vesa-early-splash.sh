#!/usr/bin/env bash
# N1800 legacy VESA diagnostic: separate GRUB entry, one-shot only.
# status reads; prepare creates an entry and backup; once selects next boot.
set -Eeuo pipefail
mode="$1"
case "$mode" in status|prepare|once) ;; *) echo "Use status|prepare|once"; exit 2;; esac
kernel=6.1.0-50-686-pae
uuid=5b4ffd28-6d80-43e9-bb65-bb62d0b845ac
id=itomiscan-vesa-early-test
custom=/etc/grub.d/42_itomiscan_vesa_early
cfg=/boot/grub/grub.cfg
envfile=/boot/grub/grubenv
dep=/boot/initrd.img-6.1.0-50-686-pae-dep-test
splash=/boot/initrd.img-6.1.0-50-686-pae-itomiscan-splash-test
die() { echo "STOP: $*" >&2; exit 3; }
if [[ "$mode" == status ]]; then
  echo '=== Nur lesen: VESA Teststatus ==='
  grep -E '^(GRUB_DEFAULT|GRUB_TIMEOUT|GRUB_TIMEOUT_STYLE)=' /etc/default/grub || true
  grub-editenv "$envfile" list || true
  ls -lh "$dep" "$splash" "$custom" 2>&1 || true
  grep -F "$id" "$cfg" || true
  exit 0
fi
[[ $EUID == 0 ]] || die 'Root required'
[[ "$(uname -r)" == "$kernel" && ! -d /sys/firmware/efi ]] || die 'Different system'
[[ "$(findmnt -nro UUID /)" == "$uuid" ]] || die 'Root UUID differs'
grep -Fxq 'GRUB_DEFAULT="itomiscan-initramfs-dep-test"' /etc/default/grub || die 'Default changed'
grep -Fxq 'GRUB_TIMEOUT=2' /etc/default/grub || die 'Timeout changed'
[[ -s "$dep" && -s "$splash" && -s "/boot/vmlinuz-$kernel" ]] || die 'Boot image missing'
[[ ! -L "$dep" && ! -L "$splash" ]] || die 'Boot image symlink'
[[ -z "$(grub-editenv "$envfile" list | sed -n 's/^next_entry=//p')" ]] || die 'Another one-time choice exists'
lsinitramfs "$splash" | grep -Fxq 'usr/share/plymouth/themes/itomiscan/scanline.png' || die 'Missing animated splash'
if [[ "$mode" == once ]]; then
  [[ -f "$custom" ]] || die 'Test entry missing'
  grep -Fq "menuentry 'ItomiScan VESA Early Splash Test' --id='$id'" "$custom" || die 'Entry mismatch'
  grep -Fq 'vga=0x318' "$custom" || die 'VESA parameter missing'
  grep -Fq "initrd /boot/initrd.img-$kernel-itomiscan-splash-test" "$custom" || die 'Wrong initramfs'
  grep -Fq "$id" "$cfg" || die 'Not in grub.cfg'
  grub-script-check "$cfg" || die 'GRUB syntax bad'
  grub-reboot "$id"
  grub-editenv "$envfile" list | grep -Fxq "next_entry=$id" || die 'One-shot not set'
  echo 'Einmalstart vorgemerkt. Kein Neustart ausgefuehrt.'
  exit 0
fi
[[ ! -e "$custom" && ! -L "$custom" ]] || die 'Test file exists'
backup="$(mktemp -d /root/itomiscan-vesa-grub-XXXXXXXX)"
chmod 700 "$backup"
cp -a /etc/default/grub "$backup/default-grub"
cp -a "$cfg" "$backup/grub.cfg"
sha256sum "$dep" "$splash" "/boot/vmlinuz-$kernel" > "$backup/images.sha256"
cat > "$custom" <<GRUB
#!/bin/sh
exec tail -n +3 \$0
menuentry 'ItomiScan VESA Early Splash Test' --id='$id' {
  insmod part_msdos
  insmod ext2
  search --no-floppy --fs-uuid --set=root $uuid
  set gfxpayload=keep
  linux /boot/vmlinuz-$kernel root=UUID=$uuid ro quiet splash vga=0x318
  initrd /boot/initrd.img-$kernel-itomiscan-splash-test
}
GRUB
chmod 755 "$custom"
if ! update-grub || ! grub-script-check "$cfg" ||
   ! grep -Fq "$id" "$cfg" ||
   ! cmp -s /etc/default/grub "$backup/default-grub" ||
   ! sha256sum -c "$backup/images.sha256" >/dev/null; then
  cp -a "$backup/grub.cfg" "$cfg"
  rm -f -- "$custom"
  die 'Preparation failed; previous grub.cfg restored'
fi
echo "Vorbereitet. Backup: $backup"
echo 'Default unveraendert; kein Einmalstart gesetzt; kein Neustart.'
