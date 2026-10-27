"""English UI chrome from the v0.9.1 Linux smoke.

The dashed outline was a catalog mark drawn only in English. The chat box was
a single-line input, so a long method sentence scrolled out of view.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_english_placeholder_mark_does_not_draw_a_box() -> None:
    css = (ROOT / "apps/desktop/src/i18n/placeholder.css").read_text(encoding="utf-8")
    assert "dashed" not in css
    assert "::after" not in css
    assert "outline: none" in css


def test_dialogue_input_wraps_instead_of_clipping() -> None:
    css = (ROOT / "apps/desktop/src/night.css").read_text(encoding="utf-8")
    assert "textarea.dialogue-input" in css
    assert "white-space: pre-wrap" in css
    assert "overflow-wrap: anywhere" in css
