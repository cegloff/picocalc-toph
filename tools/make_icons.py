#!/usr/bin/env python3
"""Generate all PicoCalcOS icons.

Produces:
  - apps/*/icon.raw for each existing app
  - firmware/picoware/ui/icons.py with embedded bytearrays for built-in icons

Requires: pip install Pillow
"""
import math
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("Error: Pillow is required. Install with: pip install Pillow")
    raise SystemExit(1)

ICON_SIZE = 48
MAGIC = 0x49
ROOT = Path(__file__).resolve().parent.parent

# Color palette (RGB tuples)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (128, 128, 128)
LIGHT_GRAY = (192, 192, 192)
DARK_GRAY = (64, 64, 64)

BLUE = (40, 120, 255)
DARK_BLUE = (20, 60, 160)
LIGHT_BLUE = (100, 180, 255)
CYAN = (0, 220, 220)

GREEN = (40, 200, 80)
DARK_GREEN = (20, 120, 40)
LIGHT_GREEN = (120, 255, 120)

RED = (220, 40, 40)
ORANGE = (240, 160, 40)
YELLOW = (240, 240, 40)
PURPLE = (160, 80, 220)
PINK = (240, 120, 180)


def rgb_to_rgb332(r, g, b):
    return (r & 0xE0) | ((g & 0xE0) >> 3) | ((b & 0xC0) >> 6)


def image_to_raw(img):
    """Convert a PIL Image to icon.raw bytes (header + RGB332 pixels)."""
    img = img.convert("RGB").resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS)
    pixels = bytearray(ICON_SIZE * ICON_SIZE)
    for y in range(ICON_SIZE):
        for x in range(ICON_SIZE):
            r, g, b = img.getpixel((x, y))
            pixels[y * ICON_SIZE + x] = rgb_to_rgb332(r, g, b)
    return bytes([MAGIC, ICON_SIZE, ICON_SIZE, 0x00]) + bytes(pixels)


def new_icon(bg=BLACK):
    """Create a new 48x48 image with draw context."""
    img = Image.new("RGB", (ICON_SIZE, ICON_SIZE), bg)
    draw = ImageDraw.Draw(img)
    return img, draw


# --- Built-in icon designs ---

def make_settings_icon():
    """Gear/cog with metallic look."""
    img, draw = new_icon()
    cx, cy = 24, 24

    # Gear body
    teeth = 8
    outer_r = 21
    inner_r = 15
    tooth_half = math.pi / teeth / 2.2

    points = []
    for i in range(teeth):
        angle = 2 * math.pi * i / teeth - math.pi / 2
        for da in [-tooth_half, tooth_half]:
            a = angle + da
            points.append((cx + outer_r * math.cos(a), cy + outer_r * math.sin(a)))
        gap_angle = angle + math.pi / teeth
        for da in [-tooth_half, tooth_half]:
            a = gap_angle + da
            points.append((cx + inner_r * math.cos(a), cy + inner_r * math.sin(a)))

    draw.polygon(points, fill=LIGHT_GRAY)
    # Inner ring highlight
    draw.ellipse([cx - 12, cy - 12, cx + 12, cy + 12], fill=GRAY)
    draw.ellipse([cx - 10, cy - 10, cx + 10, cy + 10], fill=LIGHT_GRAY)
    # Center hole
    draw.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=DARK_GRAY)
    draw.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=BLACK)
    return img


def make_appstore_icon():
    """Shopping bag with down arrow."""
    img, draw = new_icon()

    # Bag body
    draw.rounded_rectangle([8, 14, 39, 42], radius=4, fill=BLUE)
    draw.rounded_rectangle([10, 16, 37, 40], radius=3, fill=DARK_BLUE)

    # Bag handle
    draw.arc([16, 4, 31, 20], start=180, end=360, fill=LIGHT_BLUE, width=3)

    # Down arrow
    draw.rectangle([21, 22, 26, 32], fill=WHITE)
    draw.polygon([(15, 32), (24, 40), (33, 32)], fill=WHITE)
    return img


def make_poweroff_icon():
    """Power symbol — red accent."""
    img, draw = new_icon()
    cx, cy = 24, 25

    # Outer glow circle
    draw.ellipse([6, 7, 42, 43], fill=DARK_GRAY)
    draw.ellipse([8, 9, 40, 41], fill=BLACK)

    # Power arc
    draw.arc([10, 11, 38, 39], start=35, end=325, fill=RED, width=3)

    # Vertical line
    draw.rectangle([22, 9, 26, 25], fill=RED)

    return img


def make_chat_icon():
    """AI chat — speech bubble with sparkle/brain motif."""
    img, draw = new_icon()

    # Main bubble
    draw.rounded_rectangle([2, 4, 45, 34], radius=8, fill=PURPLE)
    draw.rounded_rectangle([4, 6, 43, 32], radius=7, fill=(120, 60, 180))

    # Tail
    draw.polygon([(8, 33), (16, 33), (6, 43)], fill=(120, 60, 180))

    # AI sparkle — three dots connected
    draw.ellipse([12, 15, 18, 21], fill=CYAN)
    draw.ellipse([21, 13, 27, 19], fill=WHITE)
    draw.ellipse([30, 15, 36, 21], fill=CYAN)
    # connecting lines
    draw.line([(15, 18), (24, 16)], fill=LIGHT_BLUE, width=1)
    draw.line([(24, 16), (33, 18)], fill=LIGHT_BLUE, width=1)
    # small sparkle dots
    draw.ellipse([17, 24, 19, 26], fill=LIGHT_BLUE)
    draw.ellipse([23, 22, 25, 24], fill=WHITE)
    draw.ellipse([29, 24, 31, 26], fill=LIGHT_BLUE)

    return img


def make_graphcalc_icon():
    """Graph calculator — colored axes with sine + parabola."""
    img, draw = new_icon()

    # Grid background
    for gx in range(10, 44, 8):
        draw.line([(gx, 4), (gx, 42)], fill=DARK_GRAY, width=1)
    for gy in range(6, 44, 8):
        draw.line([(8, gy), (42, gy)], fill=DARK_GRAY, width=1)

    # Y axis
    draw.line([(10, 4), (10, 44)], fill=WHITE, width=2)
    # X axis
    draw.line([(6, 38), (44, 38)], fill=WHITE, width=2)

    # Sine wave (cyan)
    points = []
    for px in range(11, 43):
        t = (px - 11) / 32.0 * 2.5 * math.pi
        sy = 26 - int(10 * math.sin(t))
        points.append((px, sy))
    if len(points) > 1:
        draw.line(points, fill=CYAN, width=2)

    # Parabola (orange)
    points2 = []
    for px in range(11, 43):
        t = (px - 27) / 16.0
        sy = 36 - int(14 * (1 - t * t))
        if 4 <= sy <= 42:
            points2.append((px, sy))
    if len(points2) > 1:
        draw.line(points2, fill=ORANGE, width=2)

    # Axis arrows
    draw.polygon([(10, 4), (7, 8), (13, 8)], fill=WHITE)
    draw.polygon([(44, 38), (40, 35), (40, 41)], fill=WHITE)

    return img


def make_hello_world_icon():
    """Hello World — globe with grid lines."""
    img, draw = new_icon()
    cx, cy = 24, 24

    # Globe body
    draw.ellipse([4, 4, 43, 43], fill=DARK_BLUE)
    draw.ellipse([6, 6, 41, 41], fill=BLUE)

    # Continent-like blobs
    draw.ellipse([14, 10, 26, 22], fill=GREEN)
    draw.ellipse([22, 16, 36, 30], fill=GREEN)
    draw.ellipse([10, 26, 22, 36], fill=GREEN)
    draw.ellipse([28, 30, 38, 38], fill=DARK_GREEN)

    # Latitude lines
    for offset in [-10, 0, 10]:
        y = cy + offset
        # clip to circle
        if abs(offset) < 18:
            half_w = int(math.sqrt(max(0, 18**2 - offset**2)))
            draw.arc(
                [cx - half_w, y - 2, cx + half_w, y + 2],
                start=0, end=360, fill=(80, 160, 255), width=1
            )

    # Center meridian (elliptical)
    draw.ellipse([18, 5, 30, 42], outline=(80, 160, 255), width=1)

    # Shine highlight
    draw.ellipse([12, 8, 20, 16], fill=(120, 200, 255))

    return img


def make_snake_icon():
    """Snake — coiled green snake with eyes and tongue."""
    img, draw = new_icon()

    # Snake body — thick curved path
    body_color = GREEN
    body_dark = DARK_GREEN
    body_light = LIGHT_GREEN

    # Body segments as a winding path
    seg = 7
    path = [
        (6, 10), (13, 10), (20, 10), (27, 10), (34, 10),
        (34, 17), (34, 24),
        (27, 24), (20, 24), (13, 24),
        (13, 31),
        (20, 31), (27, 31), (34, 31),
        (34, 38),
        (27, 38),
    ]

    for i, (x, y) in enumerate(path):
        c = body_light if i % 3 == 0 else (body_color if i % 3 == 1 else body_dark)
        draw.rounded_rectangle([x, y, x + seg - 1, y + seg - 1], radius=2, fill=c)

    # Head
    hx, hy = path[-1]
    draw.rounded_rectangle([hx - 1, hy - 1, hx + seg, hy + seg], radius=3, fill=LIGHT_GREEN)

    # Eyes
    draw.ellipse([hx + 1, hy + 1, hx + 3, hy + 3], fill=WHITE)
    draw.ellipse([hx + 1, hy + 1, hx + 2, hy + 2], fill=BLACK)
    draw.ellipse([hx + 4, hy + 1, hx + 6, hy + 3], fill=WHITE)
    draw.ellipse([hx + 5, hy + 1, hx + 6, hy + 2], fill=BLACK)

    # Tongue
    draw.line([(hx + 3, hy + seg), (hx + 3, hy + seg + 3)], fill=RED, width=1)
    draw.line([(hx + 3, hy + seg + 3), (hx + 1, hy + seg + 5)], fill=RED, width=1)
    draw.line([(hx + 3, hy + seg + 3), (hx + 5, hy + seg + 5)], fill=RED, width=1)

    # Apple food item in top-right
    draw.ellipse([38, 4, 45, 11], fill=RED)
    draw.line([(41, 3), (43, 1)], fill=GREEN, width=1)

    return img


def make_ssh_icon():
    """SSH Terminal — detailed terminal window with colored text."""
    img, draw = new_icon()

    # Window chrome
    draw.rounded_rectangle([2, 3, 45, 44], radius=4, fill=DARK_GRAY)

    # Title bar
    draw.rounded_rectangle([2, 3, 45, 13], radius=4, fill=GRAY)
    draw.rectangle([2, 10, 45, 13], fill=GRAY)

    # Traffic light dots
    draw.ellipse([5, 5, 9, 9], fill=RED)
    draw.ellipse([12, 5, 16, 9], fill=YELLOW)
    draw.ellipse([19, 5, 23, 9], fill=GREEN)

    # Terminal background
    draw.rectangle([4, 14, 43, 42], fill=(15, 15, 30))

    # Prompt line 1: $ ssh user@host
    draw.rectangle([6, 16, 8, 18], fill=GREEN)  # $
    draw.rectangle([10, 16, 28, 18], fill=CYAN)  # command text
    draw.rectangle([30, 16, 42, 18], fill=WHITE)  # args

    # Prompt line 2: Connected
    draw.rectangle([6, 22, 32, 24], fill=GREEN)  # success text

    # Prompt line 3: user@remote:~$
    draw.rectangle([6, 28, 24, 30], fill=CYAN)  # prompt
    draw.rectangle([26, 28, 28, 30], fill=WHITE)  # $

    # Blinking cursor
    draw.rectangle([30, 28, 32, 30], fill=LIGHT_GREEN)

    # Prompt line 4: partial command
    draw.rectangle([6, 34, 18, 36], fill=GRAY)

    return img


# --- Map app slugs to icon generators ---

APP_ICONS = {
    "chat": make_chat_icon,
    "graphcalc": make_graphcalc_icon,
    "hello_world": make_hello_world_icon,
    "snake": make_snake_icon,
    "ssh_terminal": make_ssh_icon,
}

BUILTIN_ICONS = {
    "ICON_SETTINGS": make_settings_icon,
    "ICON_APPSTORE": make_appstore_icon,
    "ICON_POWEROFF": make_poweroff_icon,
}


def generate_app_icons():
    """Generate icon.raw for each app in apps/."""
    apps_dir = ROOT / "apps"
    for slug, make_fn in APP_ICONS.items():
        app_dir = apps_dir / slug
        if not app_dir.exists():
            print(f"  Skipping {slug} (directory not found)")
            continue
        img = make_fn()
        raw = image_to_raw(img)
        out = app_dir / "icon.raw"
        out.write_bytes(raw)
        print(f"  {out} ({len(raw)} bytes)")


def generate_icons_py():
    """Generate firmware/picoware/ui/icons.py with frozen bytearrays."""
    lines = [
        '# Auto-generated by tools/make_icons.py — do not edit',
        '# Built-in icon data for PicoCalcOS launcher',
        '#',
        '# Format: 4-byte header (magic, width, height, flags) + 2304 bytes RGB332',
        '',
    ]

    for name, make_fn in BUILTIN_ICONS.items():
        img = make_fn()
        raw = image_to_raw(img)
        # Format as bytes literal, 16 bytes per line
        hex_lines = []
        for i in range(0, len(raw), 16):
            chunk = raw[i:i + 16]
            hex_str = "".join(f"\\x{b:02x}" for b in chunk)
            hex_lines.append(f'    b"{hex_str}"')
        lines.append(f"{name} = (")
        lines.append("\n".join(hex_lines))
        lines.append(")")
        lines.append("")

    out = ROOT / "firmware" / "picoware" / "ui" / "icons.py"
    out.write_text("\n".join(lines) + "\n")
    print(f"  {out}")


def main():
    print("Generating app icons...")
    generate_app_icons()
    print("Generating icons.py...")
    generate_icons_py()
    print("Done.")


if __name__ == "__main__":
    main()
