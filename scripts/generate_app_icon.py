#!/usr/bin/env python3
"""Generate alphaloop app icons (provisional brand mark until designer delivery)."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover - CI installs pillow for this script
    Image = None  # type: ignore
    ImageDraw = None  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "apps" / "desktop" / "src-tauri" / "icons"
SOURCE_SVG = ICON_DIR / "source-icon.svg"

BG = (7, 9, 12)
TEAL = (94, 234, 212)
INK = (232, 238, 245)


def write_svg(path: Path) -> None:
    path.write_text(
        """<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024">
  <rect width="1024" height="1024" rx="220" fill="#07090C"/>
  <path d="M320 640c120-200 264-200 384 0" fill="none" stroke="#5EEAD4" stroke-width="72" stroke-linecap="round"/>
  <text x="512" y="430" text-anchor="middle" font-family="Georgia, serif" font-size="300" fill="#E8EEF5">α</text>
</svg>
""",
        encoding="utf-8",
    )


def render_master(size: int) -> "Image.Image":
    img = Image.new("RGBA", (size, size), BG + (255,))
    draw = ImageDraw.Draw(img)
    radius = int(size * 0.215)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=BG + (255,))
    draw.arc(
        (int(size * 0.18), int(size * 0.42), int(size * 0.82), int(size * 0.82)),
        start=200,
        end=340,
        fill=TEAL + (255,),
        width=max(8, size // 14),
    )
    draw.text((size * 0.5, size * 0.36), "α", fill=INK + (255,), anchor="mm")
    return img


def write_png(path: Path, size: int) -> None:
    render_master(size).save(path, format="PNG")


def write_ico(path: Path) -> None:
    sizes = [16, 32, 48, 64, 128, 256]
    images = [render_master(s) for s in sizes]
    images[0].save(
        path,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[1:],
    )


def write_icns(path: Path) -> None:
    """Minimal ICNS with one 128x128 PNG chunk (sufficient for Linux deb)."""
    png = render_master(128)
    import io

    buf = io.BytesIO()
    png.save(buf, format="PNG")
    png_bytes = buf.getvalue()
    chunk_type = b"ic08"
    header = struct.pack(">II", 128, 128)
    data = chunk_type + header + png_bytes
    length = len(data)
    file_length = 8 + length
    out = struct.pack(">I4sI", file_length, b"icns", length) + data
    path.write_bytes(out)


def main() -> None:
    if Image is None:
        raise SystemExit("Pillow is required: pip install pillow")
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    write_svg(SOURCE_SVG)
    write_png(ICON_DIR / "32x32.png", 32)
    write_png(ICON_DIR / "64x64.png", 64)
    write_png(ICON_DIR / "128x128.png", 128)
    write_png(ICON_DIR / "128x128@2x.png", 256)
    write_png(ICON_DIR / "icon.png", 512)
    write_ico(ICON_DIR / "icon.ico")
    write_icns(ICON_DIR / "icon.icns")
    for name in (
        "Square30x30Logo.png",
        "Square44x44Logo.png",
        "Square71x71Logo.png",
        "Square89x89Logo.png",
        "Square107x107Logo.png",
        "Square142x142Logo.png",
        "Square150x150Logo.png",
        "Square284x284Logo.png",
        "Square310x310Logo.png",
        "StoreLogo.png",
    ):
        write_png(ICON_DIR / name, 256)


if __name__ == "__main__":
    main()
