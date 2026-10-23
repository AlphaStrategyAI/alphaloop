"""User-entered security identifiers: infer an exchange only when the prefix is certain."""

from __future__ import annotations

import pytest

from engine.research.symbol_identity import (
    SymbolMention,
    extract_symbol_mentions,
    parse_symbol_field,
)

# Prefix groups the product treats as unambiguous. Anything else stays unresolved.
_CERTAIN = (
    ("600519", "SH"),
    ("601318", "SH"),
    ("688111", "SH"),
    ("689009", "SH"),
    ("000001", "SZ"),
    ("001979", "SZ"),
    ("002594", "SZ"),
    ("003816", "SZ"),
    ("300750", "SZ"),
    ("301269", "SZ"),
    ("430047", "BJ"),
    ("830799", "BJ"),
    ("870001", "BJ"),
    ("920002", "BJ"),
    ("510300", "SH"),
    ("560010", "SH"),
    ("588000", "SH"),
    ("159915", "SZ"),
)

# Real listings whose venue we do not guess: B shares, other funds, convertibles.
_UNCERTAIN = (
    "900901",  # Shanghai B share
    "200011",  # Shenzhen B share
    "160119",  # Shenzhen LOF, outside the 15 ETF rule
    "180101",  # Shenzhen fund
    "110038",  # Shanghai convertible
    "123456",  # Shenzhen convertible (12)
    "501018",  # Shanghai fund, outside 51/56/58
)


@pytest.mark.parametrize("code,suffix", _CERTAIN)
def test_certain_prefix_gains_only_that_exchange(code: str, suffix: str) -> None:
    mentions = extract_symbol_mentions(f"A股股票 {code} 均值回归")
    assert mentions == (SymbolMention(raw=code, canonical=f"{code}.{suffix}", inferred=True),)


@pytest.mark.parametrize("code", _UNCERTAIN)
def test_uncertain_six_digit_code_is_not_given_a_suffix(code: str) -> None:
    mentions = extract_symbol_mentions(f"请看 {code} 这只")
    assert mentions == (SymbolMention(raw=code, canonical=None, inferred=False),)


def test_explicit_suffix_is_kept_and_not_marked_inferred() -> None:
    mentions = extract_symbol_mentions("A股股票 600519.SH、000001.sz 的均值回归")
    assert mentions == (
        SymbolMention(raw="600519.SH", canonical="600519.SH", inferred=False),
        SymbolMention(raw="000001.sz", canonical="000001.SZ", inferred=False),
    )


def test_explicit_suffix_wins_over_the_prefix_table() -> None:
    """The user wrote the venue. Do not 'correct' it from the digits."""
    mentions = extract_symbol_mentions("就这只 600519.SZ")
    assert mentions == (SymbolMention(raw="600519.SZ", canonical="600519.SZ", inferred=False),)


def test_unknown_suffix_is_not_rewritten() -> None:
    mentions = extract_symbol_mentions("代码 600519.SS 不对")
    assert mentions == (SymbolMention(raw="600519.SS", canonical=None, inferred=False),)


def test_code_glued_to_chinese_is_still_the_same_token() -> None:
    mentions = extract_symbol_mentions("关注600519的走势")
    assert mentions == (SymbolMention(raw="600519", canonical="600519.SH", inferred=True),)


@pytest.mark.parametrize(
    "text",
    [
        "用 100000 元本金做均值回归",
        "投入100000元",
        "买 100000 股",
        "100000万元",
        "100000 shares of nothing",
        "100000 USD",
        "成本 100000.50",
        "大约 100,000 元",
        "预算 100000 做研究",
        "代码 610000 不存在",
        "老三板 400001",
    ],
)
def test_quantities_and_non_listings_are_not_symbols(text: str) -> None:
    assert extract_symbol_mentions(text) == ()


def test_a_real_code_next_to_a_unit_is_a_quantity() -> None:
    assert extract_symbol_mentions("准备 600519元") == ()
    assert extract_symbol_mentions("关注600519的走势") == (
        SymbolMention(raw="600519", canonical="600519.SH", inferred=True),
    )


def test_six_digits_inside_a_longer_number_are_not_a_symbol() -> None:
    assert extract_symbol_mentions("编号6005190不是代码") == ()
    assert extract_symbol_mentions("从1600519开始") == ()


def test_ordinary_english_is_not_read_as_tickers() -> None:
    text = "mean reversion on large cap US stocks with daily prices and an ETF sleeve"
    assert extract_symbol_mentions(text) == ()


def test_ordinary_chinese_is_not_read_as_tickers() -> None:
    text = "美股股票的均值回归，关注低波动和日常换手，不指定具体代码"
    assert extract_symbol_mentions(text) == ()


def test_uppercasing_prose_does_not_invent_tickers() -> None:
    """The old extractor uppercased every token, so THE, MEAN, US, and ETF became symbols."""
    text = "THE MEAN REVERSION ETF AND US STOCKS FOR A DAILY LOW CAP FUND"
    assert extract_symbol_mentions(text) == ()


def test_chinese_sentence_with_latin_prose_has_no_false_symbol() -> None:
    text = "A股股票的均值回归 mean reversion daily ETF"
    assert extract_symbol_mentions(text) == ()


def test_explicit_us_tickers_in_a_sentence_are_kept() -> None:
    mentions = extract_symbol_mentions("美股股票 SPY、QQQ 的均值回归")
    assert mentions == (
        SymbolMention(raw="SPY", canonical="SPY", inferred=True),
        SymbolMention(raw="QQQ", canonical="QQQ", inferred=True),
    )


def test_lowercase_prose_ticker_is_not_inferred_from_a_description() -> None:
    assert extract_symbol_mentions("看看 spy 和 qqq") == ()


def test_share_class_suffix_still_parses() -> None:
    mentions = extract_symbol_mentions("持有 BRK.B")
    assert mentions == (SymbolMention(raw="BRK.B", canonical="BRK.B", inferred=True),)


def test_symbol_field_accepts_a_bare_code_and_a_lowercase_ticker() -> None:
    assert parse_symbol_field("600519") == (
        SymbolMention(raw="600519", canonical="600519.SH", inferred=True),
    )
    assert parse_symbol_field("spy") == (
        SymbolMention(raw="SPY", canonical="SPY", inferred=True),
    )
    assert parse_symbol_field("900901") == (
        SymbolMention(raw="900901", canonical=None, inferred=False),
    )


@pytest.mark.parametrize("text", ["RSI", "MACD", "KDJ", "BOLL", "ATR", "SMA", "EMA", "VWAP"])
def test_indicator_names_are_not_tickers(text: str) -> None:
    assert extract_symbol_mentions(f"A股股票 {text} 均值回归") == ()


def test_all_caps_prose_is_not_a_ticker() -> None:
    assert extract_symbol_mentions("A股股票 FIND CAPS TECH 均值回归") == ()


def test_dollar_marker_is_a_ticker_even_for_a_word() -> None:
    mentions = extract_symbol_mentions("研究 $TSLA 和 $FIND")
    assert mentions == (
        SymbolMention(raw="$TSLA", canonical="TSLA", inferred=True),
        SymbolMention(raw="$FIND", canonical="FIND", inferred=True),
    )


def test_non_word_ticker_shape_is_still_a_candidate() -> None:
    mentions = extract_symbol_mentions("美股股票 ZZZZQ 的均值回归")
    assert mentions == (SymbolMention(raw="ZZZZQ", canonical="ZZZZQ", inferred=True),)


def test_symbol_field_does_not_treat_a_sentence_as_several_tickers() -> None:
    mentions = parse_symbol_field("mean reversion")
    assert mentions == (SymbolMention(raw="mean reversion", canonical=None, inferred=False),)
