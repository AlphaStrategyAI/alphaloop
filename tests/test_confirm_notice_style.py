"""Confirm-card fetch failures use the existing stop color, not the amber hold color."""

from pathlib import Path


def test_confirm_data_notice_uses_stop_token() -> None:
    css = Path("apps/desktop/src/night.css").read_text(encoding="utf-8")
    start = css.index(".confirm-data-notice {")
    rule = css[start : css.index("}", start)]
    assert "var(--stop)" in rule
    assert "var(--hold)" not in rule
    assert "var(--text)" not in rule
    assert "rgba(248, 113, 113, 0.12)" in rule
