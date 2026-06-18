#!/usr/bin/env python3
"""Generates Nudge.app icon: the Claude pixel mascot on dark background."""
import os
import subprocess
from PIL import Image, ImageDraw

# Colors matching buddy.py SpriteWidget
BODY_COLOR   = (0xD6, 0x7E, 0x64, 255)  # salmon
BORDER_COLOR = (255, 255, 255, 255)      # white sticker border
EYE_COLOR    = (0x1A, 0x1A, 0x1A, 255)  # near-black
ROPE_COLOR   = (0x66, 0xBB, 0x6A, 255)  # green
BG_COLOR     = (11, 11, 22, 255)         # dark bg matching the app


def draw_mascot(draw: ImageDraw.ImageDraw, size: int):
    """Draw the Claude pixel mascot scaled to fit the icon."""
    # Leave some padding so the character has breathing room
    pad = size * 0.10
    canvas = size - 2 * pad

    # The sprite is defined on a 13.5-unit-wide, 10.5-unit-tall grid
    # (char_w = 14*unit but drawn body spans ~13.5 units including legs)
    u = canvas / 14.0

    def r(x, y, w, h, border=0):
        """Draw a rectangle with optional white border then body fill."""
        bx = pad + x * u
        by = pad + y * u
        bw = w * u
        bh = h * u
        if border:
            b = border * u
            draw.rectangle([bx - b, by - b, bx + bw + b, by + bh + b],
                           fill=BORDER_COLOR)
        draw.rectangle([bx, by, bx + bw, by + bh], fill=BODY_COLOR)

    def eye(x, y, w, h):
        bx = pad + x * u
        by = pad + y * u
        draw.rectangle([bx, by, bx + w * u, by + h * u], fill=EYE_COLOR)

    border = 0.55  # sticker border width in units

    # Body: 10u wide, 7u tall starting at (2, 1)
    r(2, 1, 10, 7, border=border)

    # Left arm: (0.5, 2.5) size (1.5, 2)
    r(0.5, 2.5, 1.5, 2, border=border)

    # Right arm: (12, 2.5) size (1.5, 2)
    r(12, 2.5, 1.5, 2, border=border)

    # Legs (4): width 1.8, height 2.5, y=8
    for lx in [2.2, 4.7, 7.2, 9.7]:
        r(lx, 8, 1.8, 2.5, border=border)

    # Eyes
    eye(3.0, 2.5, 1.0, 1.0)
    eye(10.0, 2.5, 1.0, 1.0)

    # Rope (green arc, simplified as a quadratic-ish curve)
    if size >= 64:
        _draw_rope(draw, pad, u, size)


def _draw_rope(draw, pad, u, size):
    """Approximate the quadratic rope arc using line segments."""
    import math
    left_x  = pad + 0.0 * u
    right_x = pad + 13.5 * u
    hand_y  = pad + 3.5 * u
    ctrl_x  = pad + 7.0 * u
    arc_radius = 12.0 * u
    # Static mid-swing angle
    ctrl_y = hand_y + math.sin(0.4) * arc_radius

    points = []
    steps = max(20, size // 8)
    for i in range(steps + 1):
        t = i / steps
        # Quadratic bezier: (1-t)^2*P0 + 2t(1-t)*P1 + t^2*P2
        x = (1 - t)**2 * left_x + 2*t*(1-t) * ctrl_x + t**2 * right_x
        y = (1 - t)**2 * hand_y + 2*t*(1-t) * ctrl_y + t**2 * hand_y
        points.append((x, y))

    rope_w = max(1, int(u * 0.5))
    for i in range(len(points) - 1):
        draw.line([points[i], points[i+1]], fill=ROPE_COLOR, width=rope_w)


def create_icon(size: int) -> Image.Image:
    img = Image.new('RGBA', (size, size), BG_COLOR)
    draw = ImageDraw.Draw(img)
    draw_mascot(draw, size)
    return img


def make_iconset(out_dir: str):
    os.makedirs(out_dir, exist_ok=True)
    specs = [
        ("icon_16x16.png",      16),
        ("icon_16x16@2x.png",   32),
        ("icon_32x32.png",      32),
        ("icon_32x32@2x.png",   64),
        ("icon_128x128.png",    128),
        ("icon_128x128@2x.png", 256),
        ("icon_256x256.png",    256),
        ("icon_256x256@2x.png", 512),
        ("icon_512x512.png",    512),
        ("icon_512x512@2x.png", 1024),
    ]
    for filename, size in specs:
        img = create_icon(size)
        img.save(os.path.join(out_dir, filename))
        print(f"  {filename}")


if __name__ == "__main__":
    iconset = "/tmp/Nudge.iconset"
    icns    = "NudgeApp/AppIcon.icns"

    print("Generating icon sizes...")
    make_iconset(iconset)

    print("Packaging .icns...")
    subprocess.run(["iconutil", "-c", "icns", iconset, "-o", icns], check=True)
    print(f"Done: {icns}")
