#!/usr/bin/env python3
"""Convert a PNG image to PicoCalcOS icon.raw format.

Usage: python3 png_to_icon.py input.png [output.raw]

Icon format:
  Byte 0: 0x49 ('I') magic
  Byte 1: width (48)
  Byte 2: height (48)
  Byte 3: flags (0x00, reserved)
  Bytes 4..2307: 48*48 = 2304 bytes RGB332, row-major

Total file size: 2308 bytes.
"""
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Error: Pillow is required. Install with: pip install Pillow")
    sys.exit(1)

ICON_SIZE = 48
MAGIC = 0x49


def rgb_to_rgb332(r, g, b):
    """Convert 8-bit RGB to RGB332."""
    return (r & 0xE0) | ((g & 0xE0) >> 3) | ((b & 0xC0) >> 6)


def png_to_icon(input_path, output_path=None):
    if output_path is None:
        output_path = Path(input_path).with_suffix(".raw")

    img = Image.open(input_path).convert("RGB")
    img = img.resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS)

    pixels = bytearray(ICON_SIZE * ICON_SIZE)
    for y in range(ICON_SIZE):
        for x in range(ICON_SIZE):
            r, g, b = img.getpixel((x, y))
            pixels[y * ICON_SIZE + x] = rgb_to_rgb332(r, g, b)

    header = bytes([MAGIC, ICON_SIZE, ICON_SIZE, 0x00])

    with open(output_path, "wb") as f:
        f.write(header)
        f.write(pixels)

    print(f"Wrote {output_path} ({len(header) + len(pixels)} bytes)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} input.png [output.raw]")
        sys.exit(1)

    out = sys.argv[2] if len(sys.argv) > 2 else None
    png_to_icon(sys.argv[1], out)
