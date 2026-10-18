#!/usr/bin/env python3
"""Generate alphaloop app icons from the formal 1024×1024 master PNG."""

from __future__ import annotations

import io
import struct
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # pragma: no cover - CI installs pillow for this script
    Image = None  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "apps" / "desktop" / "src-tauri" / "icons"
MASTER_PNG = ICON_DIR / "icon-1024.png"
SOURCE_SVG = ICON_DIR / "source-icon.svg"

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

_ICO_SIZES = (16, 32, 48, 64, 128, 256)


def _load_master() -> "Image.Image":
    if not MASTER_PNG.is_file():
        raise SystemExit(f"Missing master icon: {MASTER_PNG} (see icons/ICON.md)")
    with Image.open(MASTER_PNG) as img:
        if img.size != (1024, 1024):
            raise SystemExit(f"Master icon must be 1024×1024, got {img.size}")
        return img.convert("RGBA")


def render_master(size: int, master: "Image.Image | None" = None) -> "Image.Image":
    base = master if master is not None else _load_master()
    if size == 1024:
        return base.copy()
    resample = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
    return base.resize((size, size), resample)


def write_png(path: Path, size: int, master: "Image.Image") -> None:
    render_master(size, master).save(path, format="PNG")


def _png_bytes(size: int, master: "Image.Image") -> bytes:
    buf = io.BytesIO()
    render_master(size, master).save(buf, format="PNG")
    return buf.getvalue()


def write_ico(path: Path, master: "Image.Image") -> None:
    images = [render_master(s, master) for s in _ICO_SIZES]
    images[-1].save(
        path,
        format="ICO",
        sizes=[(s, s) for s in _ICO_SIZES],
        append_images=images[:-1],
    )


def write_icns(path: Path, master: "Image.Image") -> None:
    """Standard multi-resolution ICNS with embedded PNGs (Dock/Finder)."""
    chunk_bodies: list[bytes] = []
    for ostype, size in _ICNS_PNG_CHUNKS:
        png = _png_bytes(size, master)
        payload = ostype + struct.pack(">I", 8 + len(png)) + png
        chunk_bodies.append(payload)
    data = b"".join(chunk_bodies)
    file_length = 8 + len(data)
    path.write_bytes(struct.pack(">I4s", file_length, b"icns") + data)


def main() -> None:
    if Image is None:
        raise SystemExit("Pillow is required: pip install pillow")
    if not SOURCE_SVG.is_file():
        raise SystemExit(f"Missing vector source: {SOURCE_SVG}")
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    master = _load_master()
    write_png(ICON_DIR / "32x32.png", 32, master)
    write_png(ICON_DIR / "64x64.png", 64, master)
    write_png(ICON_DIR / "128x128.png", 128, master)
    write_png(ICON_DIR / "128x128@2x.png", 256, master)
    write_png(ICON_DIR / "icon.png", 512, master)
    write_ico(ICON_DIR / "icon.ico", master)
    write_icns(ICON_DIR / "icon.icns", master)
    for name, size in _WINDOWS_SQUARE_LOGOS.items():
        write_png(ICON_DIR / name, size, master)


if __name__ == "__main__":
    main()
