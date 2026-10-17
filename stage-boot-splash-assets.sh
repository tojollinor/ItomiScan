#!/usr/bin/env bash
# Generate ItomiScan Plymouth theme in an isolated workspace, never in /usr/share.
# Usage: bash stage-boot-splash-assets.sh check|stage [output-directory]
set -Eeuo pipefail
[[ $# -ge 1 && $# -le 2 ]] || { echo "Usage: $0 check|stage [output-directory]" >&2; exit 2; }
mode="$1"
[[ "$mode" == check || "$mode" == stage ]] || { echo "Mode must be check or stage" >&2; exit 2; }
root="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
target="$(realpath -m -- "${2:-$PWD/itomiscan-splash-stage}")"
case "$target" in
  /|/usr|/usr/*|/etc|/etc/*|/boot|/boot/*|/var|/var/*)
    echo "Only workspace paths are permitted: $target" >&2; exit 3 ;;
esac
[[ -d "$(dirname "$target")" ]] || { echo "Parent workspace directory missing" >&2; exit 3; }
[[ ! -e "$target" && ! -L "$target" ]] || {
  echo "Stage destination already exists; will not replace: $target" >&2
  exit 3
}
[[ -f "$root/itomiscan/branding.py" ]] || { echo "Branding source missing" >&2; exit 3; }
/usr/bin/python3 -c 'import PIL' || { echo "Python Pillow required" >&2; exit 3; }
if [[ "$mode" == check ]]; then
  echo "Theme generator and free workspace destination verified; no files changed."
  exit 0
fi
mkdir -- "$target"
cleanup_on_error() {
  if [[ $? -ne 0 ]]; then
    echo "Staging failed; directory retained for inspection: $target" >&2
  fi
}
trap cleanup_on_error EXIT
(
  cd "$root"
  /usr/bin/python3 -m itomiscan.branding --output "$target/itomiscan"
)
for file in logo-base.png scanline.png brand.png subtitle.png status.png detail.png \
            itomiscan.plymouth itomiscan.script; do
  [[ -s "$target/itomiscan/$file" ]] || { echo "Missing generated asset: $file" >&2; exit 4; }
done
for file in static-boot.png itomiscan-static.plymouth itomiscan-static.script; do
  [[ -s "$target/itomiscan-static/$file" ]] || { echo "Missing static asset: $file" >&2; exit 4; }
done
grep -Fq 'Plymouth.SetRefreshFunction(refresh_callback)' "$target/itomiscan/itomiscan.script"
echo "Staged both themes in $target"
echo "NO host Plymouth theme, initramfs or GRUB config changed."
echo "Staging is NOT a bootable image and must NOT be copied into /boot as-is."
