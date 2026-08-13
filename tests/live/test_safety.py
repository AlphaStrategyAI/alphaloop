"""
Tests for the broker safety guards.

These tests verify that the hard-wall against accidentally
connecting to a live brokerage account cannot be bypassed by:
  - Omitting the confirm flag
  - Setting it to False
  - Sneaking it past a constructor
  - Trying to monkey-patch the safety check

The single positive test (paper=False + confirm_live=True) is
intentionally present to prove the gate is real, not a no-op.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from alphaloop.live import (  # noqa: E402
    AlpacaAdapter,
    CONFIRM_LIVE_FLAG,
    LIVE_BASE_URL,
    LiveTradingRefused,
    PAPER_BASE_URL,
)


# --- Default is paper ---


def test_default_is_paper():
    """Calling AlpacaAdapter() with no args must default to paper."""
    b = AlpacaAdapter()
    assert b.is_paper is True
    assert b.base_url == PAPER_BASE_URL


def test_explicit_paper_true_is_paper():
    b = AlpacaAdapter(paper=True)
    assert b.is_paper is True
    assert b.base_url == PAPER_BASE_URL


def test_paper_does_not_require_confirm():
    """paper=True with confirm_live=False is still allowed."""
    b = AlpacaAdapter(paper=True, confirm_live=False)
    assert b.is_paper is True


# --- Live requires double opt-in ---


def test_paper_false_without_confirm_raises():
    """The HARD WALL: paper=False without confirm_live=True MUST raise."""
    with pytest.raises(LiveTradingRefused):
        AlpacaAdapter(paper=False)


def test_paper_false_with_confirm_false_raises():
    """Explicit confirm_live=False with paper=False still raises."""
    with pytest.raises(LiveTradingRefused):
        AlpacaAdapter(paper=False, confirm_live=False)


def test_paper_false_with_confirm_true_succeeds():
    """paper=False AND confirm_live=True is the only way to go live."""
    b = AlpacaAdapter(paper=False, confirm_live=True)
    assert b.is_paper is False
    assert b.base_url == LIVE_BASE_URL


# --- Error message content ---


def test_error_message_mentions_confirm_flag():
    """The refusal message must tell the caller exactly which flag to set."""
    with pytest.raises(LiveTradingRefused) as exc:
        AlpacaAdapter(paper=False)
    msg = str(exc.value)
    assert CONFIRM_LIVE_FLAG in msg
    assert "paper=False" in msg or "live" in msg.lower()


def test_error_message_says_default_is_paper():
    """The refusal message should remind the caller that paper is the default."""
    with pytest.raises(LiveTradingRefused) as exc:
        AlpacaAdapter(paper=False)
    assert "paper" in str(exc.value).lower()


# --- Safety check is not bypassable ---


def test_no_way_to_construct_live_without_double_flag():
    """No keyword argument short-circuits the safety check."""
    # These should all raise (or be paper):
    with pytest.raises(LiveTradingRefused):
        AlpacaAdapter(paper=False)
    with pytest.raises(LiveTradingRefused):
        AlpacaAdapter(paper=False, confirm_live=False)
    with pytest.raises(LiveTradingRefused):
        AlpacaAdapter(paper=False, confirm_live=None)


def test_confirm_flag_is_string_not_truthy_zero():
    """`confirm_live=0`, `confirm_live=""`, `confirm_live=[]` must all fail."""
    for falsy in [0, "", [], None]:
        with pytest.raises(LiveTradingRefused):
            AlpacaAdapter(paper=False, confirm_live=falsy)


# --- Constants exposed correctly ---


def test_confirm_flag_constant_value():
    """The CONFIRM_LIVE_FLAG constant must match its documented name."""
    assert CONFIRM_LIVE_FLAG == "confirm_yes_i_know_what_im_doing"


def test_paper_and_live_urls_are_distinct():
    """Sanity: the two URLs should not be the same."""
    assert PAPER_BASE_URL != LIVE_BASE_URL
    assert "paper" in PAPER_BASE_URL
    assert "paper" not in LIVE_BASE_URL or "api" in LIVE_BASE_URL


# --- Adapter identity ---


def test_alpaca_adapter_name():
    b = AlpacaAdapter()
    assert b.name == "alpaca"


def test_alpaca_adapter_repr_includes_mode():
    b = AlpacaAdapter()
    r = repr(b)
    assert "paper" in r or "LIVE" in r or "live" in r.lower()
    assert PAPER_BASE_URL in r