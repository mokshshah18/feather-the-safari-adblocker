#!/usr/bin/env python3
"""Render the app icon set into App/Assets.xcassets/AppIcon.appiconset.

One vector-ish drawing (a feather on a dark field), rendered with Pillow at
every size Xcode wants: a single 1024px square for iOS, and the ten
rounded-corner sizes macOS needs. Requires: pip install pillow
"""
import json
import pathlib

from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parent.parent
ICONSET = ROOT / "App" / "Assets.xcassets" / "AppIcon.appiconset"

BACKGROUND = (20, 36, 52, 255)
FEATHER = (244, 241, 232, 255)
SUPERSAMPLE = 4


def draw(size: int, rounded: bool) -> Image.Image:
    s = size * SUPERSAMPLE
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if rounded:
        # macOS icon grid: the rounded square sits inside a 10% margin.
        inset = s * 0.10
        d.rounded_rectangle([inset, inset, s - inset, s - inset],
                            radius=(s - 2 * inset) * 0.2237, fill=BACKGROUND)
    else:
        d.rectangle([0, 0, s, s], fill=BACKGROUND)

    # Feather: an upright leaf with a carved spine and a quill, then tilted.
    layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    cx, cy = s / 2, s / 2
    half_len, half_wid = s * 0.27, s * 0.105
    ld.ellipse([cx - half_wid, cy - half_len, cx + half_wid, cy + half_len], fill=FEATHER)
    spine = s * 0.011
    ld.rounded_rectangle([cx - spine, cy - half_len * 0.92, cx + spine, cy + half_len * 0.98],
                         radius=spine, fill=BACKGROUND)
    ld.rounded_rectangle([cx - spine, cy + half_len * 0.85, cx + spine, cy + half_len * 1.30],
                         radius=spine, fill=FEATHER)
    # Two notches on the left edge so it reads as a feather, not a leaf.
    for frac in (0.15, 0.45):
        y = cy - half_len * frac
        ld.polygon([(cx - half_wid * 1.05, y), (cx - half_wid * 0.35, y + s * 0.05),
                    (cx - half_wid * 1.05, y + s * 0.07)], fill=BACKGROUND)
    layer = layer.rotate(-32, resample=Image.BICUBIC, center=(cx, cy))
    img.alpha_composite(layer)

    img = img.resize((size, size), Image.LANCZOS)
    return img if rounded else img.convert("RGB")


def main() -> None:
    ICONSET.mkdir(parents=True, exist_ok=True)
    images = []

    draw(1024, rounded=False).save(ICONSET / "ios-1024.png")
    images.append({"filename": "ios-1024.png", "idiom": "universal",
                   "platform": "ios", "size": "1024x1024"})

    for points in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            px = points * scale
            name = f"mac-{points}" + ("@2x" if scale == 2 else "") + ".png"
            draw(px, rounded=True).save(ICONSET / name)
            images.append({"filename": name, "idiom": "mac",
                           "scale": f"{scale}x", "size": f"{points}x{points}"})

    (ICONSET / "Contents.json").write_text(json.dumps(
        {"images": images, "info": {"author": "xcode", "version": 1}}, indent=2) + "\n")
    (ICONSET.parent / "Contents.json").write_text(json.dumps(
        {"info": {"author": "xcode", "version": 1}}, indent=2) + "\n")
    print(f"wrote {len(images)} icons to {ICONSET.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
