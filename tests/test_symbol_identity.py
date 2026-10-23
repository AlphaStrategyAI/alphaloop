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

_UNCERTAIN = (
    "900901",  # Shanghai B share
    "200011",  # Shenzhen B share
    "160119",  # Shenzhen LOF, not in the ETF allow-list
    "110038",  # convertible bond
    "123456",
    "610000",  # 61 is not 60 or 68
    "400001",  # 40 is not 43
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
        SymbolMention(raw="SPY", canonical="SPY", inferred=False),
        SymbolMention(raw="QQQ", canonical="QQQ", inferred=False),
    )


def test_lowercase_prose_ticker_is_not_inferred_from_a_description() -> None:
    assert extract_symbol_mentions("看看 spy 和 qqq") == ()


def test_share_class_suffix_still_parses() -> None:
    mentions = extract_symbol_mentions("持有 BRK.B")
    assert mentions == (SymbolMention(raw="BRK.B", canonical="BRK.B", inferred=False),)


def test_symbol_field_accepts_a_bare_code_and_a_lowercase_ticker() -> None:
    assert parse_symbol_field("600519") == (
        SymbolMention(raw="600519", canonical="600519.SH", inferred=True),
    )
    assert parse_symbol_field("spy") == (
        SymbolMention(raw="SPY", canonical="SPY", inferred=False),
    )
    assert parse_symbol_field("900901") == (
        SymbolMention(raw="900901", canonical=None, inferred=False),
    )


def test_symbol_field_does_not_treat_a_sentence_as_several_tickers() -> None:
    mentions = parse_symbol_field("mean reversion")
    assert mentions == (SymbolMention(raw="mean reversion", canonical=None, inferred=False),)
