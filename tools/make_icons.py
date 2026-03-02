#!/usr/bin/env python3
"""Generate all PicoCalcOS icons.

Produces:
  - apps/*/icon.raw for each existing app
  - firmware/picoware/ui/icons.py with embedded bytearrays for built-in icons

Requires: pip install Pillow
"""
import math
import struct
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("Error: Pillow is required. Install with: pip install Pillow")
    raise SystemExit(1)

ICON_SIZE = 48
MAGIC = 0x49
ROOT = Path(__file__).resolve().parent.parent


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


def new_icon():
    """Create a new black 48x48 image with draw context."""
    img = Image.new("RGB", (ICON_SIZE, ICON_SIZE), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    return img, draw


# --- Built-in icon designs ---

def make_settings_icon():
    """Gear/cog icon."""
    img, draw = new_icon()
    cx, cy = 24, 24
    # Outer gear teeth
    teeth = 8
    outer_r = 20
    inner_r = 14
    tooth_half = math.pi / teeth / 2
    points = []
    for i in range(teeth):
        angle = 2 * math.pi * i / teeth
        # Outer tooth
        for da in [-tooth_half, tooth_half]:
            a = angle + da
            points.append((cx + outer_r * math.cos(a), cy + outer_r * math.sin(a)))
        # Inner gap
        gap_angle = angle + math.pi / teeth
        for da in [-tooth_half, tooth_half]:
            a = gap_angle + da
            points.append((cx + inner_r * math.cos(a), cy + inner_r * math.sin(a)))
    draw.polygon(points, fill=(255, 255, 255))
    # Center hole
    draw.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], fill=(0, 0, 0))
    return img


def make_appstore_icon():
    """Download arrow in box."""
    img, draw = new_icon()
    # Box outline
    draw.rectangle([8, 8, 39, 39], outline=(255, 255, 255), width=2)
    # Arrow shaft
    draw.rectangle([21, 14, 26, 28], fill=(255, 255, 255))
    # Arrow head
    draw.polygon([(14, 28), (24, 38), (34, 28)], fill=(255, 255, 255))
    # Bottom line (tray)
    draw.rectangle([10, 36, 37, 38], fill=(255, 255, 255))
    return img


def make_poweroff_icon():
    """Power symbol (circle + line)."""
    img, draw = new_icon()
    cx, cy = 24, 24
    # Circle (arc with gap at top)
    draw.arc([8, 8, 40, 40], start=40, end=320, fill=(255, 255, 255), width=3)
    # Vertical line
    draw.rectangle([22, 6, 26, 24], fill=(255, 255, 255))
    return img


def make_chat_icon():
    """Speech bubble."""
    img, draw = new_icon()
    # Bubble body
    draw.rounded_rectangle([4, 6, 43, 32], radius=6, fill=(255, 255, 255))
    # Tail
    draw.polygon([(10, 32), (16, 32), (8, 42)], fill=(255, 255, 255))
    # Dots for text
    for x in [15, 24, 33]:
        draw.ellipse([x - 2, 17, x + 2, 21], fill=(0, 0, 0))
    return img


def make_graphcalc_icon():
    """Axes + sine wave."""
    img, draw = new_icon()
    # Y axis
    draw.line([(10, 6), (10, 42)], fill=(255, 255, 255), width=2)
    # X axis
    draw.line([(6, 38), (42, 38)], fill=(255, 255, 255), width=2)
    # Sine wave
    points = []
    for px in range(12, 42):
        t = (px - 12) / 30.0 * 2 * math.pi
        sy = 24 - int(12 * math.sin(t))
        points.append((px, sy))
    if len(points) > 1:
        draw.line(points, fill=(255, 255, 255), width=2)
    return img


def make_hello_world_icon():
    """Star."""
    img, draw = new_icon()
    cx, cy = 24, 24
    points = []
    for i in range(5):
        # Outer point
        a = math.pi / 2 + 2 * math.pi * i / 5
        points.append((cx + 18 * math.cos(a), cy - 18 * math.sin(a)))
        # Inner point
        a2 = a + math.pi / 5
        points.append((cx + 8 * math.cos(a2), cy - 8 * math.sin(a2)))
    draw.polygon(points, fill=(255, 255, 255))
    return img


def make_snake_icon():
    """Snake body segments."""
    img, draw = new_icon()
    seg = 6
    # Snake body: zigzag segments
    segments = [
        (8, 12), (14, 12), (20, 12), (26, 12), (32, 12),
        (32, 18), (32, 24), (26, 24), (20, 24), (14, 24),
        (14, 30), (14, 36), (20, 36), (26, 36), (32, 36),
    ]
    for x, y in segments:
        draw.rectangle([x, y, x + seg - 1, y + seg - 1], fill=(255, 255, 255))
    # Head (last segment is slightly different)
    hx, hy = segments[-1]
    draw.rectangle([hx, hy, hx + seg - 1, hy + seg - 1], fill=(255, 255, 255))
    # Eye
    draw.rectangle([hx + 4, hy + 1, hx + 5, hy + 2], fill=(0, 0, 0))
    return img


def make_ssh_icon():
    """>_ terminal prompt."""
    img, draw = new_icon()
    # Terminal box
    draw.rounded_rectangle([4, 6, 43, 41], radius=4, outline=(255, 255, 255), width=2)
    # Title bar
    draw.rectangle([4, 6, 43, 14], fill=(255, 255, 255))
    # > prompt
    draw.line([(10, 22), (18, 27), (10, 32)], fill=(255, 255, 255), width=2)
    # _ cursor
    draw.line([(22, 32), (32, 32)], fill=(255, 255, 255), width=2)
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
