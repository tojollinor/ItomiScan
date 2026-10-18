#!/usr/bin/env bash
# ItomiScan N1800: isolated early-i915 initramfs candidate.
# check: read-only. build: opt-in only, creates ONE new image; never edits GRUB or existing initramfs.
set -Eeuo pipefail
mode="${1:-}"
[[ $# == 1 && ( "$mode" == check || "$mode" == build ) ]] || {
  echo "Usage: bash prepare-i915-early-test.sh check|build" >&2; exit 2;
}
kernel="6.1.0-50-686-pae"
root_uuid="5b4ffd28-6d80-43e9-bb65-bb62d0b845ac"
base="/boot/initrd.img-$kernel"
dep="/boot/initrd.img-$kernel-dep-test"
splash="/boot/initrd.img-$kernel-itomiscan-splash-test"
candidate="/boot/initrd.img-$kernel-i915-early-test"
theme_rel="usr/share/plymouth/themes/itomiscan"
guard() { echo "STOP: $*" >&2; exit 3; }
[[ "$(uname -r)" == "$kernel" ]] || guard "Unexpected kernel"
[[ ! -d /sys/firmware/efi ]] || guard "Expected BIOS/Legacy"
[[ "$(findmnt -nro UUID /)" == "$root_uuid" ]] || guard "Unexpected root UUID"
[[ "$(sed -nE 's/^GRUB_DEFAULT="?([^"]*)"?$/\1/p' /etc/default/grub | head -1)" == "itomiscan-initramfs-dep-test" ]] || guard "GRUB default changed"
[[ "$(sed -nE 's/^GRUB_TIMEOUT=([0-9]+)$/\1/p' /etc/default/grub | head -1)" == "2" ]] || guard "GRUB timeout changed"
[[ -z "$(grub-editenv /boot/grub/grubenv list | sed -n 's/^next_entry=//p')" ]] || guard "One-shot boot pending"
for f in "$base" "$dep" "$splash"; do [[ -s "$f" && ! -L "$f" ]] || guard "Missing or linked: $f"; done
[[ ! -e "$candidate" && ! -L "$candidate" ]] || guard "Candidate name already occupied"
for tool in lsinitramfs unmkinitramfs mkinitramfs cmp sha256sum stat; do
  command -v "$tool" >/dev/null || guard "Missing $tool"
done
[[ -f /etc/initramfs-tools/initramfs.conf ]] || guard "Missing initramfs config"
[[ "$(plymouth-set-default-theme 2>/dev/null)" == itomiscan ]] || guard "Unexpected Plymouth theme"
dep_list="$(lsinitramfs "$dep")"
splash_list="$(lsinitramfs "$splash")"
for module in i915/i915.ko usb/host/uhci-hcd.ko; do
  grep -Fq "/$module" <<< "$dep_list" || guard "DEP missing $module"
done
for asset in itomiscan.plymouth itomiscan.script scanline.png logo-base.png brand.png subtitle.png status.png detail.png; do
  grep -Fxq "$theme_rel/$asset" <<< "$splash_list" || guard "Splash image missing $asset"
done
[[ "$(df -Pk /boot | awk 'NR==2 {print $4}')" -gt 80000 ]] || guard "Insufficient free space"
echo "Prerequisites OK. DEP/Splash/GRUB remain untouched."
[[ "$mode" == check ]] && exit 0
[[ "$EUID" == 0 ]] || guard "build requires root and local physical recovery"
work="$(mktemp -d /boot/.itomiscan-i915-early.XXXXXXXX)"
trap 'rm -rf -- "$work"' EXIT
sha256sum "$base" "$dep" "$splash" > "$work/protected.sha256"
mkdir -p "$work/unpacked" "$work/config"
unmkinitramfs "$splash" "$work/unpacked"
source_theme=""
for dir in "$work/unpacked/$theme_rel" "$work/unpacked/main/$theme_rel"; do
  [[ -d "$dir" ]] && { source_theme="$dir"; break; }
done
[[ -n "$source_theme" ]] || guard "Cannot locate unpacked theme"
grep -Fq 'Plymouth.SetRefreshFunction(refresh_callback)' "$source_theme/itomiscan.script" || guard "Animated theme signature missing"
cp -a /etc/initramfs-tools/. "$work/config/"
mkdir -p "$work/config/itomiscan-overlay/itomiscan" "$work/config/hooks"
cp -a "$source_theme/." "$work/config/itomiscan-overlay/itomiscan/"
sed -i -E 's/^[[:space:]]*MODULES=.*/MODULES=dep/' "$work/config/initramfs.conf"
grep -Eq '^MODULES=dep$' "$work/config/initramfs.conf" || guard "MODULES=dep not set"
# The temporary config is the only place where additional module loading is requested.
printf '\ni915\nuhci_hcd\n' >> "$work/config/modules"
cat > "$work/config/hooks/zzzz-itomiscan-i915-overlay" <<'HOOK'
#!/bin/sh
set -eu
case "${1:-}" in prereqs) echo ""; exit 0 ;; esac
source_dir="$(dirname "$0")/../itomiscan-overlay/itomiscan"
dest_dir="${DESTDIR}/usr/share/plymouth/themes/itomiscan"
[ -d "$source_dir" ] && [ -d "$dest_dir" ] || exit 1
cp -a "$source_dir/." "$dest_dir/"
# initramfs-tools may generate /conf/modules independently of the -d config.
# Write explicitly into the image staging tree, never to the host.
mkdir -p "${DESTDIR}/conf"
touch "${DESTDIR}/conf/modules"
for module in i915 uhci_hcd; do
  grep -Fxq "$module" "${DESTDIR}/conf/modules" || printf '%s\\n' "$module" >> "${DESTDIR}/conf/modules"
done
HOOK
chmod 0755 "$work/config/hooks/zzzz-itomiscan-i915-overlay"
mkinitramfs -d "$work/config" -o "$work/candidate.initrd" "$kernel"
[[ -s "$work/candidate.initrd" ]] || guard "Empty candidate"
lsinitramfs "$work/candidate.initrd" > "$work/manifest"
for module in i915/i915.ko usb/host/uhci-hcd.ko; do
  grep -Fq "/$module" "$work/manifest" || guard "Candidate missing $module"
done
grep -Fq "$theme_rel/scanline.png" "$work/manifest" || guard "No scanline asset"
mkdir "$work/verified"
unmkinitramfs "$work/candidate.initrd" "$work/verified"
out=""
for d in "$work/verified/$theme_rel" "$work/verified/main/$theme_rel"; do
  [[ -d "$d" ]] && { out="$d"; break; }
done
[[ -n "$out" ]] || guard "No extracted candidate theme"
for f in itomiscan.plymouth itomiscan.script logo-base.png scanline.png brand.png subtitle.png status.png detail.png; do
  cmp -s "$source_theme/$f" "$out/$f" || guard "Theme differs: $f"
done
embedded=""
for f in "$work/verified/conf/modules" "$work/verified/main/conf/modules"; do
  [[ -f "$f" ]] && { embedded="$f"; break; }
done
[[ -n "$embedded" ]] || guard "Missing embedded /conf/modules"
grep -Fxq 'i915' "$embedded" || guard "Missing explicit i915"
grep -Fxq 'uhci_hcd' "$embedded" || guard "Missing explicit UHCI"
dep_bytes="$(stat -c %s "$dep")"
new_bytes="$(stat -c %s "$work/candidate.initrd")"
(( new_bytes <= dep_bytes * 2 )) || guard "Candidate >2x DEP size"
sha256sum -c "$work/protected.sha256" >/dev/null || guard "Protected image changed"
[[ ! -e "$candidate" && ! -L "$candidate" ]] || guard "Candidate path now occupied"
ln -- "$work/candidate.initrd" "$candidate"
echo "Built isolated candidate: $candidate ($new_bytes bytes)"
sha256sum "$base" "$dep" "$splash" "$candidate"
echo "NOT BOOT-APPROVED. No GRUB changes, no reboot, no overwrites."
