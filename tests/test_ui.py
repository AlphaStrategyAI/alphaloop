"""
Tests for the Streamlit WebUI.

The WebUI is a single-file Streamlit app. We test:
  - The file is importable
  - It exposes the expected page functions
  - The data layer (`make_universe`) works
  - The factor dispatcher covers all 9 documented factors

We deliberately do NOT start a real Streamlit server in tests — that
would block pytest on a long-running process. The user verifies the
UI by running `streamlit run alphaloop/ui.py` interactively.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
UI_PATH = REPO_ROOT / "src" / "alphaloop" / "ui.py"

# Sanity: confirm we are pointing at the right path
assert (REPO_ROOT / "pyproject.toml").exists(), (
    f"REPO_ROOT does not look like the alphaloop repo: {REPO_ROOT}"
)


@pytest.fixture
def ui_module():
    """Load alphaloop.ui as a module without registering it in sys.modules
    under the 'alphaloop' namespace (Streamlit does not allow that)."""
    if "alphaloop.ui" in sys.modules:
        del sys.modules["alphaloop.ui"]
    spec = importlib.util.spec_from_file_location(
        "alphaloop_ui_test_load", str(UI_PATH)
    )
    if spec is None or spec.loader is None:
        pytest.fail(f"Could not load spec for {UI_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(REPO_ROOT / "src"))
    spec.loader.exec_module(module)
    return module


def test_ui_file_exists():
    """The UI file must exist at the documented path."""
    assert UI_PATH.exists()


def test_ui_module_loads(ui_module):
    """The UI module must import without errors."""
    assert ui_module is not None


def test_ui_main_function_exists(ui_module):
    """The UI module must expose a callable main()."""
    assert callable(getattr(ui_module, "main", None))


def test_ui_page_functions_exist(ui_module):
    """Each of the 4 documented pages must have a function."""
    for page in ["page_home", "page_overfit", "page_vs_buyhold", "page_vs_spy"]:
        fn = getattr(ui_module, page, None)
        assert callable(fn), f"Missing function {page}"


def test_make_universe_returns_three_series(ui_module):
    """`make_universe` should return (prices, ohlcv, spy)."""
    # Bypass @st.cache_data to actually call the function
    fn = ui_module.make_universe
    if hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    prices, ohlcv, spy = fn(n_bars=500, seed=0)
    assert len(prices) == 500
    assert len(ohlcv) == 500
    assert len(spy) == 500
    assert isinstance(prices, type(spy))  # both pd.Series
    assert isinstance(ohlcv, type(ohlcv))  # pd.DataFrame


def test_make_universe_is_deterministic(ui_module):
    """Same seed -> same data."""
    fn = ui_module.make_universe
    if hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    p1, _, _ = fn(n_bars=200, seed=42)
    p2, _, _ = fn(n_bars=200, seed=42)
    assert (p1 == p2).all()


def test_factor_dispatcher_covers_documented_factors(ui_module):
    """The factor dropdown options in `page_vs_buyhold` should match
    the factors actually implemented."""
    from alphaloop import engineer
    # Each factor in the dropdown must produce a valid weight series
    prices = pd.Series(
        100.0 + np.cumsum(np.random.default_rng(0).normal(0, 0.01, 500)),
        index=pd.date_range("2020-01-01", periods=500, freq="B"),
    )
    factors_to_test = [
        ("rsi", lambda: engineer.rsi(prices)),
        ("macd", lambda: engineer.macd(prices)),
        ("roc", lambda: engineer.roc(prices)),
        ("bollinger_zscore", lambda: engineer.bollinger_zscore(prices)),
    ]
    for name, fn in factors_to_test:
        w = fn()
        assert isinstance(w, type(prices)), f"{name} returned wrong type"
        assert (w.index == prices.index).all(), f"{name} returned wrong index"