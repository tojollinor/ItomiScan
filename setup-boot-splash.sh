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
if ! plymouth-set-default-theme --list | grep -Eq '^[[:space:]]*spinner[[:space:]]*$'; then
  echo "Plymouth-Spinner-Theme fehlt. Boot-Konfiguration unverändert." >&2
  exit 3
fi

backup_dir="/var/lib/itomiscan/boot-backups/$(date -u +%Y%m%dT%H%M%SZ)"
install -d -m 0700 "$backup_dir"
cp -a /etc/default/grub "$backup_dir/grub.original"
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
for arg in ('quiet', 'splash'):
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
text = "ItomiScan"
bbox = draw.textbbox((0, 0), text, font=font)
draw.text(((520 - (bbox[2] - bbox[0])) / 2, 32), text, font=font, fill=(241, 245, 251, 255))
im.save(sys.argv[1])
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
SCRIPT
plymouth-set-default-theme itomiscan
update-initramfs -u
update-grub
printf '\nItomiScan Boot-Splash eingerichtet. Backup: %s\n' "$backup_dir"
printf 'Nach Neustart prüfen. BIOS/GRUB und kurze Konsolenübergänge können weiterhin sichtbar sein.\n'
printf 'Wiederherstellung: gesicherte GRUB-Datei zurückkopieren, vorheriges Theme setzen, update-initramfs -u und update-grub ausführen.\n'
