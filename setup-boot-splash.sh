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
backup_dir="/var/lib/itomiscan/boot-backups/$(date -u +%Y%m%dT%H%M%SZ)-${BASHPID}"
install -d -m 0700 "$backup_dir"
cp -a /etc/default/grub "$backup_dir/grub.original"
chmod 0600 "$backup_dir/grub.original"
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
# Render the SAME icon geometry, colours, title and subtitle as gui/splash.py.
# Images are prepared once during setup, never during boot.
python3 - "$theme_dir" <<'PYIMAGE'
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import sys
out = Path(sys.argv[1])
bg = (16, 25, 39, 255)
cyan = (82, 195, 219, 255)
white = (241, 245, 251, 255)
muted = (168, 186, 205, 255)
fontpath = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
regular = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
# draw_logo(..., 84) from itomiscan/gui/home.py
icon = Image.new("RGBA", (84, 84), bg)
d = ImageDraw.Draw(icon)
s = 84 / 72
scale = lambda points: tuple(round(v*s) for v in points)
d.rectangle(scale((1, 1, 71, 71)), fill=(7, 61, 129, 255))
d.polygon(scale((23, 15, 44, 15, 52, 23, 52, 58, 23, 58)), fill=white)
d.rectangle(scale((15, 36, 57, 40)), fill=(66, 191, 234, 255))
for x,y,dx,dy in ((13,13,8,8),(59,13,-8,8),(13,59,8,-8),(59,59,-8,-8)):
    d.line(scale((x,y+dy,x,y,x+dx,y)), fill=(66,191,234,255), width=max(3,round(4*s)))
icon.save(out / "icon.png")
def centered_text(filename, parts, size, bold=True):
    font = ImageFont.truetype(fontpath if bold else regular, size)
    widths = [ImageDraw.Draw(Image.new("RGBA",(1,1))).textbbox((0,0),t,font=font)[2] for t,_ in parts]
    image = Image.new("RGBA",(max(1,sum(widths)),size+14),(0,0,0,0))
    d = ImageDraw.Draw(image)
    x = 0
    for (label,color),width in zip(parts,widths):
        d.text((x,0),label,font=font,fill=color)
        x += width
    image.save(out / filename)
centered_text("brand.png",[("Itomi",white),("Scan",cyan)],30)
centered_text("subtitle.png",[("Dokumentenscanner",muted)],13,False)
centered_text("status.png",[("Scanner wird vorbereitet",white)],19)
centered_text("detail.png",[("Systemstart …",muted)],12,False)
# Same ring dimensions and colours as Tk startup spinner.
ring = Image.new("RGBA",(150,150),(0,0,0,0))
rd = ImageDraw.Draw(ring)
rd.ellipse((21,21,129,129),outline=(52,71,94,255),width=11)
rd.arc((21,21,129,129),start=0,end=85,fill=cyan,width=11)
ring.save(out / "ring.png")
PYIMAGE
cat > "$theme_dir/itomiscan.plymouth" <<'THEME'
[Plymouth Theme]
Name=ItomiScan
Description=ItomiScan early boot splash matching Tk kiosk
ModuleName=script

[script]
ImageDir=/usr/share/plymouth/themes/itomiscan
ScriptFile=/usr/share/plymouth/themes/itomiscan/itomiscan.script
THEME
cat > "$theme_dir/itomiscan.script" <<'SCRIPT'
Window.SetBackgroundTopColor(0.062745, 0.098039, 0.152941);
Window.SetBackgroundBottomColor(0.062745, 0.098039, 0.152941);
# Mirror the vertical stacking of StartupSplash on a 1024x768 panel.
# Coordinates scale from screen centre, so smaller displays remain centred.
icon = Image("icon.png");
brand = Image("brand.png");
subtitle = Image("subtitle.png");
ring = Image("ring.png");
status = Image("status.png");
detail = Image("detail.png");
cx = Window.GetWidth() / 2;
top = (Window.GetHeight() - 768) / 2;
icon_sprite = Sprite(icon);
icon_sprite.SetX(cx - icon.GetWidth() / 2);
icon_sprite.SetY(top + 29);
brand_sprite = Sprite(brand);
brand_sprite.SetX(cx - brand.GetWidth() / 2);
brand_sprite.SetY(top + 126);
subtitle_sprite = Sprite(subtitle);
subtitle_sprite.SetX(cx - subtitle.GetWidth() / 2);
subtitle_sprite.SetY(top + 177);
ring_sprite = Sprite(ring);
ring_sprite.SetX(cx - ring.GetWidth() / 2);
ring_sprite.SetY(top + 228);
status_sprite = Sprite(status);
status_sprite.SetX(cx - status.GetWidth() / 2);
status_sprite.SetY(top + 410);
detail_sprite = Sprite(detail);
detail_sprite.SetX(cx - detail.GetWidth() / 2);
detail_sprite.SetY(top + 457);
# Rotation in Plymouth uses a native frame callback; the Tk screen animates
# independently after Xorg takes ownership of the display.
fun animate() {
    ring_sprite.SetImage(ring.Rotate(Plymouth.GetTime() * 2));
}
Plymouth.SetRefreshFunction(animate);
SCRIPT
# Hide the GRUB selection pause on this single-OS appliance.
if grep -Eq '^GRUB_TIMEOUT_STYLE=' /etc/default/grub; then
  sed -i -E 's/^GRUB_TIMEOUT_STYLE=.*/GRUB_TIMEOUT_STYLE=hidden/' /etc/default/grub
else
  printf '\nGRUB_TIMEOUT_STYLE=hidden\n' >> /etc/default/grub
fi
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
