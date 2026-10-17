#!/usr/bin/env bash
# Opt-in, separate initramfs candidate builder for the original N1800.
# Never calls update-initramfs, update-grub, grub-reboot, or reboot.
# Run only with explicit approval when physical recovery is available.
set -Eeuo pipefail

KERNEL="6.1.0-50-686-pae"
ROOT_UUID="5b4ffd28-6d80-43e9-bb65-bb62d0b845ac"
BASE="/boot/initrd.img-${KERNEL}"
DEP="/boot/initrd.img-${KERNEL}-dep-test"
CANDIDATE="/boot/initrd.img-${KERNEL}-itomiscan-splash-test"
THEME="/usr/share/plymouth/themes/itomiscan"
STAGE="${ITOMISCAN_SPLASH_STAGE:-}"
MODE="${ITOMISCAN_SPLASH_MODE:-animated}"

usage() {
  echo "Usage: bash prepare-boot-candidate.sh check|build" >&2
  echo "check only reads files; build creates one separate initramfs but does not alter boot selection." >&2
  exit 2
}
[[ $# -eq 1 ]] || usage
[[ "$1" == check || "$1" == build ]] || usage
[[ "$MODE" == animated ]] || { echo "Isolated builder currently supports animated only" >&2; exit 2; }

# Each required file is validated up front. There is no call to an installer.
check() {
  local count=0
  [[ "$(uname -r)" == "$KERNEL" ]] || { echo "Kernel differs"; count=$((count+1)); }
  [[ ! -d /sys/firmware/efi ]] || { echo "Expected legacy BIOS"; count=$((count+1)); }
  [[ -s "$BASE" && -s "$DEP" && -r /etc/default/grub ]] || {
    echo "Required original / DEP initramfs or GRUB config missing"
    count=$((count+1))
  }
  if command -v findmnt >/dev/null 2>&1; then
    [[ "$(findmnt -nro UUID /)" == "$ROOT_UUID" ]] || {
      echo "Unexpected root filesystem UUID"
      count=$((count+1))
    }
  else
    echo "findmnt missing"
    count=$((count+1))
  fi
  for cmd in mkinitramfs lsinitramfs sha256sum stat; do
    command -v "$cmd" >/dev/null 2>&1 || { echo "Missing command: $cmd"; count=$((count+1)); }
  done
  [[ -d /etc/initramfs-tools && -f /etc/initramfs-tools/initramfs.conf ]] || {
    echo "initramfs-tools config missing"
    count=$((count+1))
  }
  # Staged files only. The active Plymouth theme on disk stays untouched.
  [[ -n "$STAGE" && -d "$STAGE/itomiscan" ]] || {
    echo "Set ITOMISCAN_SPLASH_STAGE to a staged theme directory"
    count=$((count+1))
  }
  if [[ -d "$STAGE/itomiscan" ]]; then
    for f in itomiscan.plymouth itomiscan.script logo-base.png scanline.png brand.png subtitle.png status.png detail.png; do
      [[ -s "$STAGE/itomiscan/$f" ]] || { echo "Staged asset missing: $f"; count=$((count+1)); }
    done
    if [[ -s "$STAGE/itomiscan/itomiscan.script" ]] &&
       ! grep -Fq 'Plymouth.SetRefreshFunction(refresh_callback)' "$STAGE/itomiscan/itomiscan.script"; then
      echo "Staged theme is not animated"
      count=$((count+1))
    fi
  fi
  # Plymouth's stock hook must first load its normal 'itomiscan' theme.
  # Our local hook overlays staged files in DESTDIR after the stock hook.
  local selected=""
  if command -v plymouth-set-default-theme >/dev/null 2>&1; then
    selected="$(plymouth-set-default-theme 2>/dev/null || true)"
  fi
  [[ "$selected" == itomiscan ]] || {
    echo "Installed theme selection must remain itomiscan (got '$selected')"
    count=$((count+1))
  }
  # Refuse overwriting anything, including zero-sized or symlink candidates.
  [[ ! -e "$CANDIDATE" && ! -L "$CANDIDATE" ]] || {
    echo "Candidate path occupied: $CANDIDATE"
    count=$((count+1))
  }
  if (( count != 0 )); then
    echo "$count unmet prerequisites. No image generated."
    return 1
  fi
  echo "Prerequisites for an isolated build satisfied; no boot setting modified."
}

if [[ "$1" == check ]]; then
  check
  exit 0
fi

[[ $EUID -eq 0 ]] || { echo "Build requires root and physical recovery access"; exit 3; }
check
work="$(mktemp -d /boot/.itomiscan-candidate.XXXXXXXX)"
image="$work/candidate.initrd"
cleanup() { rm -rf -- "$work"; }
trap cleanup EXIT

# Preserve the host configuration but never edit it; stage a copy separately.
cp -a /etc/initramfs-tools "$work/config"
mkdir -p "$work/config/itomiscan-overlay/itomiscan"
cp -a "$STAGE/itomiscan/." "$work/config/itomiscan-overlay/itomiscan/"
mkdir -p "$work/config/hooks"
cat > "$work/config/hooks/zzzz-itomiscan-overlay" <<'OVERLAY'
#!/bin/sh
set -eu
case "${1:-}" in prereqs) echo ""; exit 0 ;; esac
# Locally injected into the mkinitramfs -d staging config only.
source_dir="$(dirname "$0")/../itomiscan-overlay/itomiscan"
dest_dir="${DESTDIR}/usr/share/plymouth/themes/itomiscan"
[ -d "$source_dir" ] && [ -d "$dest_dir" ] || exit 1
cp -a "$source_dir/." "$dest_dir/"
OVERLAY
chmod 0755 "$work/config/hooks/zzzz-itomiscan-overlay"
if grep -Eq '^[[:space:]]*MODULES=' "$work/config/initramfs.conf"; then
  sed -i -E 's/^[[:space:]]*MODULES=.*/MODULES=dep/' "$work/config/initramfs.conf"
else
  printf '\nMODULES=dep\n' >> "$work/config/initramfs.conf"
fi

# Debian Bookworm mkinitramfs supports -d <alternative config directory>.
# The normal Plymouth hook reads the old host theme; a local hook overlays# only the staging output in the candidate initramfs destination.
mkinitramfs -d "$work/config" -o "$image" "$KERNEL"
[[ -s "$image" ]] || { echo "Empty output image"; exit 4; }
listing="$work/contents"
lsinitramfs "$image" > "$listing"
expected="itomiscan"
for needed in "usr/share/plymouth/themes/$expected/$expected.plymouth" \
              "usr/share/plymouth/themes/$expected/$expected.script" \
              "usr/share/plymouth/themes/$expected/scanline.png" \
              "usr/lib/modules/$KERNEL/kernel/drivers/gpu/drm/i915/i915.ko"; do
  grep -Fq "$needed" "$listing" || {
    echo "Image lacks required file: $needed"
    exit 4
  }
done

# Stop if the generated image unexpectedly differs too much in size.
# This is a review limit, not a claim that candidate boots correctly.
dep_bytes="$(stat -c %s "$DEP")"
new_bytes="$(stat -c %s "$image")"
echo "DEP size: $dep_bytes; new candidate: $new_bytes bytes"
if (( new_bytes > dep_bytes * 2 )); then
  echo "Candidate >2x DEP baseline; review compression/modules before publishing."
  exit 4
fi

# Atomic no-clobber link on the /boot filesystem. Fails if output exists.
ln -- "$image" "$CANDIDATE"
echo "Candidate prepared: $CANDIDATE"
sha256sum "$BASE" "$DEP" "$CANDIDATE"
echo "No original image overwritten; GRUB and boot selection unchanged."
echo "NOT READY TO BOOT: separate GRUB entry and hardware acceptance are still required."
