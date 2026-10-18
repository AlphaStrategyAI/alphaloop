#!/usr/bin/env python3
"""Generate alphaloop app icons (provisional brand mark until designer delivery)."""

from __future__ import annotations

import io
import struct
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

# PNG-in-ICNS type codes (macOS 10.7+), size in pixels.
_ICNS_PNG_CHUNKS: tuple[tuple[bytes, int], ...] = (
    (b"icp4", 16),
    (b"icp5", 32),
    (b"icp6", 64),
    (b"ic07", 128),
    (b"ic08", 256),
    (b"ic09", 512),
    (b"ic10", 1024),
)

_WINDOWS_SQUARE_LOGOS: dict[str, int] = {
    "Square30x30Logo.png": 30,
    "Square44x44Logo.png": 44,
    "Square71x71Logo.png": 71,
    "Square89x89Logo.png": 89,
    "Square107x107Logo.png": 107,
    "Square142x142Logo.png": 142,
    "Square150x150Logo.png": 150,
    "Square284x284Logo.png": 284,
    "Square310x310Logo.png": 310,
    "StoreLogo.png": 50,
}


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


def _png_bytes(size: int) -> bytes:
    buf = io.BytesIO()
    render_master(size).save(buf, format="PNG")
    return buf.getvalue()


def write_ico(path: Path) -> None:
    sizes = [16, 32, 48, 64, 128, 256]
    images = [render_master(s) for s in sizes]
    # Pillow embeds multiple sizes only when the largest image is saved first.
    images[-1].save(
        path,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[:-1],
    )


def write_icns(path: Path) -> None:
    """Standard multi-resolution ICNS with embedded PNGs (Dock/Finder)."""
    chunk_bodies: list[bytes] = []
    for ostype, size in _ICNS_PNG_CHUNKS:
        png = _png_bytes(size)
        payload = ostype + struct.pack(">I", 8 + len(png)) + png
        chunk_bodies.append(payload)
    data = b"".join(chunk_bodies)
    file_length = 8 + len(data)
    path.write_bytes(struct.pack(">I4s", file_length, b"icns") + data)


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
    write_png(ICON_DIR / "icon-1024.png", 1024)
    write_ico(ICON_DIR / "icon.ico")
    write_icns(ICON_DIR / "icon.icns")
    for name, size in _WINDOWS_SQUARE_LOGOS.items():
        write_png(ICON_DIR / name, size)


if __name__ == "__main__":
    main()
