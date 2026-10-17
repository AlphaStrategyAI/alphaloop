from engine.research.method_body_display import format_method_body_display


def test_scorecard_body_renders_chinese_not_raw_json() -> None:
    body = '{"revision":"scorecard-v1","sharpe_oos_min_exclusive":0.0}'
    text = format_method_body_display("scorecard.market", body)
    assert "{" not in text
    assert "样本外夏普" in text
