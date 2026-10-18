import hashlib
import struct
from pathlib import Path

pytest = __import__("pytest")
Image = pytest.importorskip("PIL.Image")

ICON_DIR = Path(__file__).resolve().parents[1] / "apps" / "desktop" / "src-tauri" / "icons"
TAURI_CONF = (
    Path(__file__).resolve().parents[1] / "apps" / "desktop" / "src-tauri" / "tauri.conf.json"
)

# v2 master from 设计小迪 (larger α); guards against reverting to v1 small-α art.
V2_ICON_1024_SHA256 = (
    "47e661190f61172de163863bea9ae4d614c359247b6f6b16da1bbe713380a269"
)
MIN_ALPHA_MARK_WIDTH_RATIO = 0.55


def _distinct_colors(path: Path) -> int:
    img = Image.open(path).convert("RGBA")
    return len({px for px in img.getdata() if px[3] > 0})


def _parse_icns_chunks(data: bytes) -> list[bytes]:
    """Return chunk type fourccs for a standard ICNS (magic at offset 0)."""
    if len(data) < 8 or data[:4] != b"icns":
        return []
    file_length = struct.unpack_from(">I", data, 4)[0]
    if file_length != len(data):
        return []
    offset = 8
    types: list[bytes] = []
    while offset + 8 <= len(data):
        chunk_type = data[offset : offset + 4]
        length = struct.unpack_from(">I", data, offset + 4)[0]
        if length < 8 or offset + length > len(data):
            break
        types.append(chunk_type)
        offset += length
    return types


def _ink_cyan_bbox_width_ratio(path: Path) -> float:
    """Horizontal span of ink/cyan foreground on the 1024 master (v2 α ≈ 65% width)."""
    img = Image.open(path).convert("RGBA")
    width, height = img.size
    assert width == height == 1024
    pixels = img.load()
    xs: list[int] = []
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if a < 64:
                continue
            if r > 200 and g > 200 and b > 200:
                xs.append(x)
                continue
            if g > 170 and b > 150 and r < 160:
                xs.append(x)
    if not xs:
        return 0.0
    return (max(xs) - min(xs) + 1) / width


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


def test_icon_1024_is_v2_master_with_large_alpha() -> None:
    path = ICON_DIR / "icon-1024.png"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == V2_ICON_1024_SHA256
    ratio = _ink_cyan_bbox_width_ratio(path)
    assert ratio >= MIN_ALPHA_MARK_WIDTH_RATIO, f"α mark too narrow ({ratio:.2%} of canvas)"


def test_icns_is_valid_multi_resolution() -> None:
    path = ICON_DIR / "icon.icns"
    data = path.read_bytes()
    assert data[:4] == b"icns", "ICNS magic must be at offset 0"
    assert data[4:8] != b"icns", "length field must not look like inverted magic"
    file_length = struct.unpack_from(">I", data, 4)[0]
    assert file_length == len(data)
    assert len(data) > 8_000
    chunk_types = _parse_icns_chunks(data)
    assert len(chunk_types) >= 5
    assert b"icp4" in chunk_types
    assert b"ic10" in chunk_types


def test_icns_rejects_inverted_header_layout() -> None:
    """Regression: length-before-magic header fooled older tests and broke macOS."""
    path = ICON_DIR / "icon.icns"
    data = path.read_bytes()
    inverted = data[4:8] + data[:4] + data[8:]
    assert inverted[:4] != b"icns"
    assert inverted[4:8] == b"icns"
    assert _parse_icns_chunks(inverted) == []


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
