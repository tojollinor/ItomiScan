"""Shared ItomiScan identity and Plymouth artwork; no Tk/X server needed.

This module is the one source for the colours, scan-line geometry and
initial placement used by the Debian Plymouth theme and the Tk kiosk.
"""
from pathlib import Path

BG = "#101927"
BLUE = "#073d81"
CYAN = "#42bfea"
WHITE = "#f1f5fb"
MUTED = "#a8bacd"

LOGO_UNITS = 72
LOGO_SIZE = 150
LINE_LEFT = 15
LINE_RIGHT = 57
LINE_HEIGHT = 4
LINE_MIN = 20
LINE_MAX = 52
LINE_START = 36
DOCUMENT = (23, 15, 44, 15, 52, 23, 52, 58, 23, 58)
CORNERS = ((13, 13, 8, 8), (59, 13, -8, 8),
           (13, 59, 8, -8), (59, 59, -8, -8))
# Absolute Y coordinates for the N1800's 1024x768 screen.
LOGO_Y = 141
BRAND_Y = 325
SUBTITLE_Y = 387
STATUS_Y = 458
DETAIL_Y = 506


def scaled(values, size=LOGO_SIZE):
    factor = size / LOGO_UNITS
    return tuple(round(v * factor) for v in values)


def _text_image(parts, pixels, bold=True):
    """Render boot text with the same DejaVu family used by Tk."""
    from PIL import Image, ImageDraw, ImageFont

    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    path = Path("/usr/share/fonts/truetype/dejavu") / name
    font = ImageFont.truetype(str(path), pixels)
    pieces = []
    for message, colour in parts:
        bbox = font.getbbox(message)
        width = max(1, bbox[2] - bbox[0])
        height = max(1, bbox[3] - bbox[1])
        pieces.append((message, colour, bbox, width, height))
    height = max(part[4] for part in pieces) + 8
    width = sum(part[3] for part in pieces)
    img = Image.new("RGBA", (max(1, width), max(1, height)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    x = 0
    for message, colour, bbox, part_width, _ in pieces:
        draw.text((x - bbox[0], 4 - bbox[1]), message, font=font, fill=colour)
        x += part_width
    return img


def render_plymouth_assets(directory):
    """Generate static transparent images in initramfs once, never at boot."""
    from PIL import Image, ImageDraw

    output = Path(directory)
    output.mkdir(parents=True, exist_ok=True)
    size = LOGO_SIZE
    bg_rgba = (16, 25, 39, 255)
    logo = Image.new("RGBA", (size, size), bg_rgba)
    draw = ImageDraw.Draw(logo)
    draw.rectangle(scaled((1, 1, 71, 71)), fill=BLUE)
    draw.polygon(scaled(DOCUMENT), fill="#ffffff")
    for x, y, dx, dy in CORNERS:
        draw.line(scaled((x, y + dy, x, y, x + dx, y)),
                  fill=CYAN, width=max(3, round(4 * size / LOGO_UNITS)))
    logo.save(output / "logo-base.png")
    line_width = round((LINE_RIGHT - LINE_LEFT) * size / LOGO_UNITS)
    line_height = round(LINE_HEIGHT * size / LOGO_UNITS)
    line = Image.new("RGBA", (line_width, line_height), CYAN)
    line.save(output / "scanline.png")
    titles = (
        ("brand.png", (("Itomi", WHITE), ("Scan", CYAN)), 40, True),
        ("subtitle.png", (("Dokumentenscanner", MUTED),), 17, False),
        ("status.png", (("Scanner wird vorbereitet", WHITE),), 25, True),
        ("detail.png", (("Systemstart …", MUTED),), 16, False),
    )
    for filename, parts, px, bold in titles:
        _text_image(parts, px, bold).save(output / filename)
    # Plymouth's script is generated from the SAME geometry constants as Tk.
    # Keep layout values out of shell installer scripts to prevent drift.
    theme = """[Plymouth Theme]
Name=ItomiScan
Description=Boot screen matching the Tk animated document logo
ModuleName=script

[script]
ImageDir=/usr/share/plymouth/themes/itomiscan
ScriptFile=/usr/share/plymouth/themes/itomiscan/itomiscan.script
"""
    (output / "itomiscan.plymouth").write_text(theme)
    line_x = scaled((LINE_LEFT,))[0]
    script = f"""Window.SetBackgroundTopColor(0.062745, 0.098039, 0.152941);
Window.SetBackgroundBottomColor(0.062745, 0.098039, 0.152941);
cx = Window.GetWidth() / 2;
top = (Window.GetHeight() - 768) / 2;
logo = Image("logo-base.png");
line = Image("scanline.png");
brand = Image("brand.png");
subtitle = Image("subtitle.png");
status = Image("status.png");
detail = Image("detail.png");
logo_sprite = Sprite(logo);
logo_sprite.SetX(cx - logo.GetWidth() / 2);
logo_sprite.SetY(top + {LOGO_Y});
line_sprite = Sprite(line);
line_sprite.SetX(cx - logo.GetWidth() / 2 + {line_x});
line_position = {LINE_START};
line_sprite.SetY(top + {LOGO_Y} + line_position * {LOGO_SIZE} / {LOGO_UNITS});
brand_sprite = Sprite(brand);
brand_sprite.SetX(cx - brand.GetWidth() / 2);
brand_sprite.SetY(top + {BRAND_Y});
subtitle_sprite = Sprite(subtitle);
subtitle_sprite.SetX(cx - subtitle.GetWidth() / 2);
subtitle_sprite.SetY(top + {SUBTITLE_Y});
status_sprite = Sprite(status);
status_sprite.SetX(cx - status.GetWidth() / 2);
status_sprite.SetY(top + {STATUS_Y});
detail_sprite = Sprite(detail);
detail_sprite.SetX(cx - detail.GetWidth() / 2);
detail_sprite.SetY(top + {DETAIL_Y});
line_direction = 1;
frames = 0;
fun refresh_callback () {{
    frames++;
    if (frames % 3 == 0) {{
        line_position += line_direction * 2.5;
        if (line_position >= {LINE_MAX}) {{
            line_position = {LINE_MAX};
            line_direction = -1;
        }}
        if (line_position <= {LINE_MIN}) {{
            line_position = {LINE_MIN};
            line_direction = 1;
        }}
        line_sprite.SetY(top + {LOGO_Y} + line_position * {LOGO_SIZE} / {LOGO_UNITS});
    }}
}}
Plymouth.SetRefreshFunction(refresh_callback);
"""
    (output / "itomiscan.script").write_text(script)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate matching ItomiScan boot artwork")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    render_plymouth_assets(args.output)
