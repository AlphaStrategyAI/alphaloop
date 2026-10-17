from pathlib import Path

from PIL import Image

ICON_DIR = Path(__file__).resolve().parents[1] / "apps" / "desktop" / "src-tauri" / "icons"


def _distinct_colors(path: Path) -> int:
    img = Image.open(path).convert("RGBA")
    return len({px for px in img.getdata() if px[3] > 0})


def test_app_icons_exist_and_are_not_flat_placeholders() -> None:
    required = [
        ("32x32.png", 32),
        ("128x128.png", 128),
        ("128x128@2x.png", 256),
        ("icon.png", 512),
        ("icon.ico", None),
        ("icon.icns", None),
        ("source-icon.svg", None),
    ]
    for name, size in required:
        path = ICON_DIR / name
        assert path.is_file(), name
        if name.endswith(".svg"):
            min_bytes = 100
        elif name.endswith(".icns") or name.endswith(".ico"):
            min_bytes = 200
        elif name in {"32x32.png", "64x64.png"}:
            min_bytes = 250
        else:
            min_bytes = 650
        assert path.stat().st_size > min_bytes, f"{name} too small"
        if size is not None:
            img = Image.open(path)
            assert img.size == (size, size)
            assert _distinct_colors(path) >= 8
