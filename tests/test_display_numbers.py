from engine.research.display_names import format_display_number
from engine.research.method_body_display import format_method_body_display


def test_same_sign_ratio_renders_as_fraction() -> None:
    assert format_display_number(2 / 3) == "2/3"


def test_stability_method_body_no_long_decimal() -> None:
    body = (
        '{"revision":"stability-v1","segments_min":3,"same_sign_ratio_min":0.6666666666666666}'
    )
    text = format_method_body_display("stability.oos", body)
    assert "0.666667" not in text
    assert "2/3" in text


def test_no_more_than_four_decimal_digits_in_formatted_ratio() -> None:
    text = format_display_number(0.123456789)
    if "." in text:
        assert len(text.split(".")[-1].rstrip("%")) <= 4
