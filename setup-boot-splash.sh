#!/usr/bin/env bash
# Opt-in ItomiScan Plymouth splash for Debian 12 i386.
# This script is never called by the kiosk update button or normal installer.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Bitte als root über SSH ausführen." >&2
  exit 2
fi
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if [[ ! -f "$ROOT/itomiscan/branding.py" ]]; then
  echo "ItomiScan-Brandingmodul fehlt; keine Boot-Änderungen." >&2
  exit 3
fi
if [[ ! -f /etc/default/grub || ! -d /boot/grub ]] ||
   ! command -v update-grub >/dev/null 2>&1 ||
   ! command -v update-initramfs >/dev/null 2>&1; then
  echo "GRUB/initramfs nicht vollständig vorhanden; keine Boot-Änderungen." >&2
  exit 3
fi
if ! grep -q '^VERSION_CODENAME=bookworm$' /etc/os-release; then
  echo "Nur für Debian 12 (bookworm); keine Boot-Änderungen." >&2
  exit 3
fi
if ! grep -Eq '^GRUB_CMDLINE_LINUX_DEFAULT="[^"]*"$' /etc/default/grub; then
  echo "GRUB_CMDLINE_LINUX_DEFAULT nicht eindeutig lesbar; keine Änderungen." >&2
  exit 3
fi

# Make a separate, collision-free copy BEFORE changing theme or GRUB.
backup_parent="/var/lib/itomiscan/boot-backups"
install -d -m 0700 "$backup_parent"
backup_dir="$(mktemp -d -p "$backup_parent" "boot-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXXXX")"
cp -a /etc/default/grub "$backup_dir/grub.original"
cmp -s /etc/default/grub "$backup_dir/grub.original" || {
  echo "GRUB-Sicherung unvollständig, Abbruch." >&2
  exit 4
}
if [[ -f /boot/grub/grub.cfg ]]; then
  cp -a /boot/grub/grub.cfg "$backup_dir/grub.cfg.original"
fi
theme_dir="/usr/share/plymouth/themes/itomiscan"
if [[ -d "$theme_dir" ]]; then
  cp -a "$theme_dir" "$backup_dir/previous-itomiscan-theme"
fi
if command -v plymouth-set-default-theme >/dev/null 2>&1; then
  plymouth-set-default-theme > "$backup_dir/previous-theme-name" || true
fi
printf 'Sicherung: %s\n' "$backup_dir"

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
  plymouth plymouth-themes python3-pil fonts-dejavu-core

# Produce the Plymouth files using the SAME constants as the Tk logo.
# Images are prepared once during setup, not by the Atom N270 at boot.
install -d -m 0755 "$theme_dir"
(
  cd "$ROOT"
  python3 -m itomiscan.branding --output "$theme_dir"
)
for asset in logo-base.png scanline.png brand.png subtitle.png status.png detail.png itomiscan.plymouth itomiscan.script; do
  [[ -s "$theme_dir/$asset" ]] || {
    echo "Splash-Grafik $asset wurde nicht erstellt; Abbruch vor GRUB-Änderung." >&2
    exit 5
  }
done

# Preserve existing flags, add only the known quiet splash defaults.
python3 - <<'PY'
from pathlib import Path
import re
path = Path("/etc/default/grub")
source = path.read_text()
pattern = re.compile(r'^(GRUB_CMDLINE_LINUX_DEFAULT=)"([^"]*)"$',
                     re.MULTILINE)
match = pattern.search(source)
if match is None:
    raise SystemExit("GRUB-Konfiguration unerwartet geändert; Abbruch.")
flags = match.group(2).split()
for flag in ("quiet", "splash", "loglevel=3", "systemd.show_status=false",
             "vt.global_cursor_default=0"):
    if flag not in flags:
        flags.append(flag)
source = (source[:match.start()] + match.group(1) + '"' +
          " ".join(flags) + '"' + source[match.end():])
for key, value in (("GRUB_TIMEOUT_STYLE", "hidden"), ("GRUB_TIMEOUT", "0")):
    line = f"{key}={value}"
    regexp = re.compile(rf"^{key}=.*$", re.MULTILINE)
    source, count = regexp.subn(line, source)
    if count == 0:
        source += "\n" + line + "\n"
path.write_text(source)
PY

plymouth-set-default-theme itomiscan
update-initramfs -u
update-grub
printf '\nItomiScan-Boottheme aktualisiert; Neustart zur Prüfung nötig.\n'
printf 'Sicherung für Wiederherstellung: %s\n' "$backup_dir"
printf 'Hinweis: BIOS-Ausgaben und der Wechsel zu Xorg können kurz sichtbar bleiben.\n'
