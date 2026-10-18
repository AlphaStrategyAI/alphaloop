import struct
from pathlib import Path

pytest = __import__("pytest")
Image = pytest.importorskip("PIL.Image")

ICON_DIR = Path(__file__).resolve().parents[1] / "apps" / "desktop" / "src-tauri" / "icons"
TAURI_CONF = (
    Path(__file__).resolve().parents[1] / "apps" / "desktop" / "src-tauri" / "tauri.conf.json"
)


def _distinct_colors(path: Path) -> int:
    img = Image.open(path).convert("RGBA")
    return len({px for px in img.getdata() if px[3] > 0})


def _icns_chunk_count(data: bytes) -> int:
    if len(data) < 8 or data[4:8] != b"icns":
        return 0
    offset = 8
    count = 0
    while offset + 8 <= len(data):
        _type = data[offset : offset + 4]
        length = struct.unpack_from(">I", data, offset + 4)[0]
        if length < 8:
            break
        count += 1
        offset += length
    return count


def _ico_image_count(path: Path) -> int:
    data = path.read_bytes()
    if len(data) < 6 or data[:2] != b"\x00\x00":
        return 0
    return struct.unpack_from("<H", data, 4)[0]


def test_app_icons_exist_and_are_not_flat_placeholders() -> None:
    required = [
        ("32x32.png", 32),
        ("128x128.png", 128),
        ("128x128@2x.png", 256),
        ("icon.png", 512),
        ("icon-1024.png", 1024),
        ("icon.ico", None),
        ("icon.icns", None),
        ("source-icon.svg", None),
    ]
    for name, size in required:
        path = ICON_DIR / name
        assert path.is_file(), name
        if name.endswith(".svg"):
            min_bytes = 100
        elif name.endswith(".icns"):
            min_bytes = 8_000
        elif name.endswith(".ico"):
            min_bytes = 1_000
        elif name in {"32x32.png", "64x64.png"}:
            min_bytes = 250
        else:
            min_bytes = 650
        assert path.stat().st_size > min_bytes, f"{name} too small"
        if size is not None:
            img = Image.open(path)
            assert img.size == (size, size)
            assert _distinct_colors(path) >= 8


def test_icns_is_valid_multi_resolution() -> None:
    path = ICON_DIR / "icon.icns"
    data = path.read_bytes()
    assert data[4:8] == b"icns"
    assert len(data) > 8_000
    assert _icns_chunk_count(data) >= 5


def test_ico_has_multiple_embedded_sizes() -> None:
    path = ICON_DIR / "icon.ico"
    assert _ico_image_count(path) >= 3
    with Image.open(path) as img:
        assert max(img.size) >= 256


def test_windows_square_logos_match_filename_dimensions() -> None:
    samples = {
        "Square44x44Logo.png": 44,
        "Square150x150Logo.png": 150,
        "StoreLogo.png": 50,
    }
    for name, expected in samples.items():
        with Image.open(ICON_DIR / name) as img:
            assert img.size == (expected, expected)


def test_tauri_bundle_lists_platform_icon_files() -> None:
    text = TAURI_CONF.read_text(encoding="utf-8")
    for fragment in (
        "icons/32x32.png",
        "icons/128x128.png",
        "icons/128x128@2x.png",
        "icons/icon.icns",
        "icons/icon.ico",
    ):
        assert fragment in text
