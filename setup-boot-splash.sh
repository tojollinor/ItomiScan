#!/usr/bin/env bash
# Opt-in Debian 12 boot splash. Run as root ONLY after reviewing the changes.
# Never called by a GitHub GUI update or by the default installer.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Bitte als root ausführen." >&2
  exit 2
fi
if [[ ! -f /etc/default/grub ]] || ! command -v update-grub >/dev/null 2>&1 || ! command -v update-initramfs >/dev/null 2>&1; then
  echo "GRUB/update-initramfs nicht gefunden. Boot-Konfiguration unverändert." >&2
  exit 3
fi
if ! grep -q 'VERSION_CODENAME=bookworm' /etc/os-release; then
  echo "Nur für Debian 12 (bookworm) vorgesehen. Boot-Konfiguration unverändert." >&2
  exit 3
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends plymouth plymouth-themes python3-pil fonts-dejavu-core
backup_dir="/var/lib/itomiscan/boot-backups/$(date -u +%Y%m%dT%H%M%SZ)-$"
install -d -m 0700 "$backup_dir"
cp -a /etc/default/grub "$backup_dir/grub.original"
[[ ! -f /boot/grub/grub.cfg ]] || cp -a /boot/grub/grub.cfg "$backup_dir/grub.cfg.original"
plymouth-set-default-theme > "$backup_dir/plymouth-theme.original" || true

echo "Backup angelegt: $backup_dir"
# Set only the kernel command line used by GRUB. Never remove existing flags.
python3 - <<'PY'
from pathlib import Path
import re
path = Path('/etc/default/grub')
text = path.read_text()
pattern = re.compile(r'^(GRUB_CMDLINE_LINUX_DEFAULT=)"([^"]*)"$', re.MULTILINE)
match = pattern.search(text)
if not match:
    raise SystemExit('GRUB_CMDLINE_LINUX_DEFAULT fehlt oder enthält ungeprüfte Syntax; nichts ändern.')
flags = match.group(2).split()
for arg in ('quiet', 'splash', 'loglevel=3', 'systemd.show_status=false', 'vt.global_cursor_default=0'):
    if arg not in flags:
        flags.append(arg)
path.write_text(text[:match.start()] + match.group(1) + '"' + ' '.join(flags) + '"' + text[match.end():])
PY

theme_dir=/usr/share/plymouth/themes/itomiscan
install -d "$theme_dir"
python3 - "$theme_dir/itomiscan.png" <<'PYIMAGE'
from PIL import Image, ImageDraw, ImageFont
import sys
im = Image.new("RGBA", (520, 160), (0, 0, 0, 0))
draw = ImageDraw.Draw(im)
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 62)
left, right = "Itomi", "Scan"
w1 = draw.textbbox((0, 0), left, font=font)[2]
w2 = draw.textbbox((0, 0), right, font=font)[2]
x = (520 - w1 - w2) / 2
draw.text((x, 32), left, font=font, fill=(241, 245, 251, 255))
draw.text((x + w1, 32), right, font=font, fill=(66, 191, 234, 255))
im.save(sys.argv[1])
ring = Image.new("RGBA", (84, 84), (0, 0, 0, 0))
ImageDraw.Draw(ring).arc((10, 10, 74, 74), 15, 315, fill=(66, 191, 234, 255), width=9)
ring.save(str(sys.argv[1]).replace("itomiscan.png", "ring.png"))
PYIMAGE
cat > "$theme_dir/itomiscan.plymouth" <<'THEME'
[Plymouth Theme]
Name=ItomiScan
Description=ItomiScan early boot splash
ModuleName=script

[script]
ImageDir=/usr/share/plymouth/themes/itomiscan
ScriptFile=/usr/share/plymouth/themes/itomiscan/itomiscan.script
THEME
cat > "$theme_dir/itomiscan.script" <<'SCRIPT'
Window.SetBackgroundTopColor(0.063, 0.098, 0.153);
Window.SetBackgroundBottomColor(0.063, 0.098, 0.153);
logo = Image("itomiscan.png");
sprite = Sprite(logo);
sprite.SetX((Window.GetWidth() - logo.GetWidth()) / 2);
sprite.SetY((Window.GetHeight() - logo.GetHeight()) / 2);
ring = Image("ring.png");
ring_sprite = Sprite(ring);
ring_sprite.SetX((Window.GetWidth() - ring.GetWidth()) / 2);
ring_sprite.SetY((Window.GetHeight() - ring.GetHeight()) / 2 + 125);
SCRIPT
# Hide the GRUB selection pause on this single-OS appliance.
if grep -Eq '^GRUB_TIMEOUT=' /etc/default/grub; then
  sed -i -E 's/^GRUB_TIMEOUT=.*/GRUB_TIMEOUT=0/' /etc/default/grub
else
  printf '\nGRUB_TIMEOUT=0\n' >> /etc/default/grub
fi
plymouth-set-default-theme itomiscan
echo 'Aktualisiere initramfs; dies kann auf dem Atom N270 einige Minuten dauern.'
update-initramfs -u
update-grub
printf '\nItomiScan Boot-Splash eingerichtet. Backup: %s\n' "$backup_dir"
printf 'Nach Neustart prüfen. BIOS/GRUB und kurze Konsolenübergänge können weiterhin sichtbar sein.\n'
printf 'Wiederherstellung: gesicherte GRUB-Datei zurückkopieren, vorheriges Theme setzen, update-initramfs -u und update-grub ausführen.\n'
