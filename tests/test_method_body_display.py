import json

from engine.verifiers import PIT_VERIFIER_REVISION, VERIFIER_REVISIONS

from engine.research.method_body_display import format_method_body_display


def test_scorecard_body_renders_chinese_not_raw_json() -> None:
    body = '{"revision":"scorecard-v1","sharpe_oos_min_exclusive":0.0}'
    text = format_method_body_display("scorecard.market", body)
    assert "{" not in text
    assert "样本外夏普" in text
    assert "scorecard-v1" not in text


def test_pit_body_renders_chinese_without_english_or_escapes() -> None:
    body = json.dumps(dict(PIT_VERIFIER_REVISION["pit.consistency"]), ensure_ascii=True)
    text = format_method_body_display("pit.consistency", body)
    assert "\\u" not in text
    assert "Point-in-Time" not in text
    assert "Lookahead" not in text
    assert "时点一致性" in text


def test_cost_body_hides_revision_token() -> None:
    body = json.dumps(dict(VERIFIER_REVISIONS["cost.turnover"]))
    text = format_method_body_display("cost.turnover", body)
    assert "cost-v1" not in text
    assert "A 股成本" in text
