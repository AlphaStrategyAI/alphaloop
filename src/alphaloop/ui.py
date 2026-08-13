"""
alphaloop WebUI — Streamlit single-file interface.

Run:
    cd /Users/assistant/hermes-lab/alphaloop
    streamlit run alphaloop/ui.py

The UI is intentionally simple: 4 pages, all offline (synthetic data).
No login, no remote calls, no database. Just the v1.0 diagnostic
tools in a clickable form.

Pages:
  1. Home — overview + v1.0 acceptance summary
  2. Overfit Check — DSR visualization
  3. vs Buy & Hold — alpha factor comparison
  4. vs SPY — the hardest benchmark

Data source: synthetic random walk (1500 bars, mild drift). This is
intentional: we want the user to see the tools in action without
needing to download market data. A future version can add a real-data
tab behind the same UI.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Allow running without `pip install -e .`
sys.path.insert(0, str(Path(__file__).resolve().parents))

try:
    import streamlit as st  # type: ignore
except ImportError:  # pragma: no cover - exercised only when streamlit is missing
    # Streamlit is an *optional* dep: the WebUI is a convenience layer.
    # The diagnostic / engineer packages below work without it. When
    # streamlit is not installed, we expose a minimal shim so that the
    # `@st.cache_data` decorator and `st.title` / `st.markdown` etc.
    # become harmless no-ops. This lets `tests/test_ui.py` load the
    # module for structural inspection (page-function existence,
    # factor dispatcher coverage) without forcing every contributor to
    # install streamlit just to run the test suite.
    class _StreamlitShim:
        @staticmethod
        def cache_data(fn=None, **_kwargs):
            # Mirrors `streamlit.cache_data`'s behaviour: can be used
            # either as `@st.cache_data` (no-arg call returns decorator)
            # or `@st.cache_data(...)` (call with kwargs returns deco).
            if fn is not None and callable(fn):
                return fn
            def _decorator(f):
                return f
            return _decorator

        # Page-config / sidebar / display calls — all no-ops offline.
        def set_page_config(self, *_, **__):
            pass

        def title(self, *_, **__):
            pass

        def header(self, *_, **__):
            pass

        def subheader(self, *_, **__):
            pass

        def markdown(self, *_, **__):
            pass

        def code(self, *_, **__):
            pass

        def slider(self, *_, **__):
            return 0

        def selectbox(self, *_, **__):
            return ""

        def success(self, *_, **__):
            pass

        def info(self, *_, **__):
            pass

        def warning(self, *_, **__):
            pass

        def error(self, *_, **__):
            pass

    class _StreamlitSidebar:
        def selectbox(self, *_, **__):
            return ""

        def markdown(self, *_, **__):
            pass

    class _StreamlitModule:
        def __init__(self) -> None:
            self.cache_data = _StreamlitShim.cache_data
            self.sidebar = _StreamlitSidebar()

        # Delegate everything else to the no-op shim.
        def __getattr__(self, name):
            return getattr(_StreamlitShim, name)

    st = _StreamlitModule()  # type: ignore

import alphaloop.diagnostic as diagnostic
import alphaloop.engineer as engineer


# ---------------------------------------------------------------------------
# Data: synthetic universe (deterministic)
# ---------------------------------------------------------------------------


@st.cache_data
def make_universe(
    n_bars: int = 1500, seed: int = 42
) -> tuple[pd.Series, pd.DataFrame, pd.Series]:
    """Cached synthetic universe. @st.cache_data makes this fast."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2018-01-01", periods=n_bars, freq="B")
    rets = rng.normal(0.0005, 0.012, n_bars)
    close = 100.0 * np.exp(np.cumsum(rets))
    prices = pd.Series(close, index=idx)
    ohlcv = pd.DataFrame(
        {
            "open": close,
            "high": close * (1.0 + np.abs(rng.normal(0, 0.005, n_bars))),
            "low": close * (1.0 - np.abs(rng.normal(0, 0.005, n_bars))),
            "close": close,
            "volume": rng.integers(1_000_000, 5_000_000, n_bars).astype(float),
        },
        index=idx,
    )
    spy_rets = rng.normal(0.0003, 0.009, n_bars)
    spy = pd.Series(
        100.0 * np.exp(np.cumsum(spy_rets)), index=idx
    )
    return prices, ohlcv, spy


# ---------------------------------------------------------------------------
# Page: Home
# ---------------------------------------------------------------------------


def page_home(prices: pd.Series, ohlcv: pd.DataFrame, spy: pd.Series) -> None:
    st.title("alphaloop v1.0")
    st.markdown(
        """
        **Honest, verifiable quantitative research infrastructure.**

        Not "find alpha" — "don't waste time on strategies that don't work."
        """
    )

    st.header("The 6 v1.0 acceptance questions")
    st.markdown(
        """
        1. **Overfit?** — Deflated Sharpe Ratio
        2. **Data sources consistent?** — Cross-source consistency check
        3. **Out-of-sample valid?** — Walk-forward CV
        4. **Beats a random strategy?** — Block-shuffled baseline
        5. **Beats passive buy-and-hold?** — Same-window benchmark
        6. **Beats SPY buy-and-hold?** — The hardest test

        Click the sidebar to explore each question.
        """
    )

    st.header("Run a synthetic-data sanity check")
    n_trials = st.slider(
        "Number of trials (for DSR correction)",
        min_value=1,
        max_value=100,
        value=20,
        step=1,
    )
    returns = prices.pct_change().dropna()
    annualized_sharpe = (
        returns.mean() / returns.std() * np.sqrt(252)
    )
    dsr = diagnostic.deflated_sharpe(
        observed_sharpe=float(annualized_sharpe),
        n_trials=n_trials,
        returns=returns,
    )
    st.code(dsr.summary(), language="text")

    st.header("What's running")
    st.markdown(
        """
        - Synthetic universe: **1500 bars** of random-walk with mild
          positive drift (annualized ~1.0 Sharpe)
        - SPY-like baseline: lower drift (annualized ~0.8 Sharpe)
        - All diagnostics run **offline** — no network calls, no data
          downloads, no login
        """
    )


# ---------------------------------------------------------------------------
# Page: Overfit check
# ---------------------------------------------------------------------------


def page_overfit(prices: pd.Series) -> None:
    st.title("Overfit Check — Deflated Sharpe Ratio")
    st.markdown(
        """
        The DSR adjusts an observed Sharpe ratio for the number of
        trials. With 20 strategy variants tried, the expected max
        Sharpe under the null (no skill) is around 0.10. Your observed
        Sharpe has to clear that bar to be considered meaningful.
        """
    )
    n_trials = st.slider("n_trials", 1, 100, 20)
    observed = st.slider(
        "observed_sharpe",
        min_value=-1.0,
        max_value=3.0,
        value=1.0,
        step=0.1,
    )
    returns = prices.pct_change().dropna()
    result = diagnostic.deflated_sharpe(
        observed_sharpe=float(observed),
        n_trials=n_trials,
        returns=returns,
    )
    st.code(result.summary(), language="text")

    if result.passes:
        st.success("Passes the overfit test.")
    else:
        st.error(
            "Fails the overfit test. Consider this strategy as candidate, "
            "not as proven."
        )


# ---------------------------------------------------------------------------
# Page: vs Buy & Hold
# ---------------------------------------------------------------------------


def page_vs_buyhold(prices: pd.Series, ohlcv: pd.DataFrame) -> None:
    st.title("vs Buy & Hold — Alpha factor comparison")
    st.markdown(
        """
        Each factor below generates a long-only weight series. We
        backtest the resulting strategy and compare its Sharpe to
        the same-window buy-and-hold of the universe.
        """
    )

    factor_name = st.selectbox(
        "Choose a factor",
        [
            "rsi",
            "macd",
            "roc",
            "momentum_12_1",
            "bollinger_zscore",
            "ohlr_4_pct",
            "atr_breakout",
            "obv_slope",
            "pairs_spread",
        ],
    )

    factors = {
        "rsi": lambda: engineer.rsi(prices),
        "macd": lambda: engineer.macd(prices),
        "roc": lambda: engineer.roc(prices),
        "momentum_12_1": lambda: engineer.momentum_12_1(prices),
        "bollinger_zscore": lambda: engineer.bollinger_zscore(prices),
        "ohlr_4_pct": lambda: engineer.ohlr_4_pct(ohlcv),
        "atr_breakout": lambda: engineer.atr_breakout(ohlcv),
        "obv_slope": lambda: engineer.obv_slope(prices, ohlcv["volume"]),
        "pairs_spread": lambda: engineer.pairs_spread(
            prices, prices * 1.5, window=20
        ),
    }
    w = factors[factor_name]()

    if w.sum() == 0:
        st.warning(
            f"Factor `{factor_name}` produced 0 long bars. "
            "Try a different factor or seed."
        )
        return

    rets = prices.pct_change() * w.shift(1)
    rets = rets.dropna().fillna(0)
    bh = diagnostic.vs_buy_hold(rets, prices)
    st.code(bh.summary(), language="text")

    if bh.passes:
        st.success(f"{factor_name} beats buy & hold on this synthetic data.")
    else:
        st.info(
            f"{factor_name} does not beat buy & hold. "
            "This is honest reporting; many factors fail this test."
        )


# ---------------------------------------------------------------------------
# Page: vs SPY
# ---------------------------------------------------------------------------


def page_vs_spy(prices: pd.Series, spy: pd.Series) -> None:
    st.title("vs SPY — The hardest benchmark")
    st.markdown(
        """
        Most individual strategies do not beat SPY buy-and-hold after
        fees and slippage. v1.0 acceptance criterion #6 is exactly
        this comparison: if your strategy doesn't beat SPY, it doesn't
        ship.
        """
    )

    factor_name = st.selectbox(
        "Choose a strategy to compare",
        ["buy_and_hold (universe)", "rsi", "roc"],
    )
    if factor_name == "buy_and_hold (universe)":
        w = pd.Series(1.0, index=prices.index)
    elif factor_name == "rsi":
        w = engineer.rsi(prices)
    else:
        w = engineer.roc(prices)

    rets = prices.pct_change() * w.shift(1)
    rets = rets.dropna().fillna(0)
    spy_bh = diagnostic.vs_spy_buyhold(rets, spy)
    st.code(spy_bh.summary(), language="text")

    if spy_bh.passes:
        st.success(f"{factor_name} beats SPY buy-and-hold. (Rare!)")
    else:
        st.warning(
            f"{factor_name} does not beat SPY. "
            "This is the most common honest result."
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    st.set_page_config(
        page_title="alphaloop v1.0",
        page_icon="📊",
        layout="wide",
    )

    prices, ohlcv, spy = make_universe()

    page = st.sidebar.selectbox(
        "Page",
        ["Home", "Overfit Check", "vs Buy & Hold", "vs SPY"],
    )

    if page == "Home":
        page_home(prices, ohlcv, spy)
    elif page == "Overfit Check":
        page_overfit(prices)
    elif page == "vs Buy & Hold":
        page_vs_buyhold(prices, ohlcv)
    elif page == "vs SPY":
        page_vs_spy(prices, spy)

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        """
        **Honest disclosure**: synthetic random-walk data. Most
        strategies will not beat SPY on this universe. The point of
        this UI is to make the tools accessible — not to declare
        winners.
        """
    )


if __name__ == "__main__":
    main()