"""
Diagnostic demo - answers the 6 v1.0 acceptance questions offline.

This demo runs without any network access. It uses synthetic data
shaped like the kind of returns a momentum strategy might produce,
then asks each of the diagnostic questions and prints a verdict.

Run:
    cd /Users/assistant/hermes-lab/openstrategy
    python3 examples/diagnostic_demo.py

Or via the openstrategy package:
    python3 -c "import openstrategy; openstrategy.diagnostic_demo()"
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Allow running without pip install
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openstrategy.diagnostic import (  # noqa: E402
    data_source_consistency,
    deflated_sharpe,
    vs_buy_hold,
    vs_random,
    vs_spy_buyhold,
    walk_forward_cv,
)


def _make_synthetic_strategy(
    n: int = 1000,
    seed: int = 0,
    drift: float = 0.0008,
    vol: float = 0.012,
) -> pd.DataFrame:
    """Build a synthetic price series with controllable drift and vol.

    The default (drift=0.0008, vol=0.012, daily) yields an annualized
    Sharpe of ~1.27, which is realistic for a single-factor strategy.
    """
    rng = np.random.default_rng(seed)
    rets = rng.normal(drift, vol, n)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {
            "open": 100.0 * np.exp(np.cumsum(rets)),
            "high": 100.0 * np.exp(np.cumsum(rets) + 0.005),
            "low": 100.0 * np.exp(np.cumsum(rets) - 0.005),
            "close": 100.0 * np.exp(np.cumsum(rets)),
            "volume": np.full(n, 1_000_000),
        },
        index=idx,
    )


def _make_spy_like(n: int = 1000, seed: int = 99) -> pd.Series:
    """S&P 500-like baseline (lower drift, similar vol)."""
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0003, 0.009, n)
    return pd.Series(
        100.0 * np.exp(np.cumsum(rets)),
        index=pd.date_range("2018-01-01", periods=n, freq="B"),
    )


def _make_second_source(
    primary: pd.DataFrame, seed: int = 1, bias: float = 0.0, noise: float = 0.001
) -> pd.DataFrame:
    """Simulate a second data source for the same symbol.

    bias: systematic multiplicative offset (e.g. 0.02 = 2% high)
    noise: random multiplicative noise per bar (e.g. 0.001 = 0.1% std)
    """
    rng = np.random.default_rng(seed)
    secondary = primary.copy()
    n = len(secondary)
    secondary["close"] = (
        secondary["close"] * (1.0 + bias) * (1.0 + rng.normal(0.0, noise, n))
    )
    return secondary


def _buy_and_hold(prices: pd.Series) -> pd.Series:
    """Strategy: always hold."""
    return pd.Series(1.0, index=prices.index)


def _answer_acceptance_questions() -> None:
    print("=" * 70)
    print("OPENSTRATEGY v1.0 DIAGNOSTIC DEMO")
    print("Answering the 6 acceptance questions for a synthetic strategy")
    print("=" * 70)
    print()

    # Build synthetic data
    strategy = _make_synthetic_strategy()
    spy = _make_spy_like()
    source_b = _make_second_source(strategy, bias=0.0, noise=0.0005)

    strategy_returns = strategy["close"].pct_change().dropna()
    spy_returns = spy.pct_change().dropna()

    # ------------------------------------------------------------------
    # 1. Is the strategy overfit?  (DSR)
    # ------------------------------------------------------------------
    print("Q1: Is the strategy overfit? (Deflated Sharpe Ratio)")
    print("-" * 70)
    annualized_sharpe = (
        strategy_returns.mean()
        / strategy_returns.std()
        * np.sqrt(252)
    )
    dsr = deflated_sharpe(
        observed_sharpe=float(annualized_sharpe),
        n_trials=20,  # assume you tried 20 strategy variants
        returns=strategy_returns,
    )
    print(dsr.summary())
    print()

    # ------------------------------------------------------------------
    # 2. Are the data sources consistent?  (Cross-source check)
    # ------------------------------------------------------------------
    print("Q2: Are the data sources consistent? (yahoo vs akshare simulated)")
    print("-" * 70)
    consistency = data_source_consistency(strategy, source_b, symbol="AAPL")
    print(consistency.summary())
    print()

    # ------------------------------------------------------------------
    # 3. Out-of-sample valid?  (Walk-Forward CV)
    # ------------------------------------------------------------------
    print("Q3: Out-of-sample valid? (Walk-Forward CV)")
    print("-" * 70)
    cv = walk_forward_cv(
        strategy["close"],
        _buy_and_hold,
        train_size=252,
        test_size=63,
        step_size=63,
    )
    print(cv.summary())
    print()

    # ------------------------------------------------------------------
    # 4. Beats a random strategy?  (block-shuffled baseline)
    # ------------------------------------------------------------------
    print("Q4: Beats a random strategy? (block-shuffled baseline)")
    print("-" * 70)
    rand = vs_random(strategy_returns, n_simulations=500, block_size=21)
    print(rand.summary())
    print()

    # ------------------------------------------------------------------
    # 5. Beats passive buy-and-hold?
    # ------------------------------------------------------------------
    print("Q5: Beats passive buy-and-hold of the same instrument?")
    print("-" * 70)
    bh = vs_buy_hold(strategy_returns, strategy["close"])
    print(bh.summary())
    print()

    # ------------------------------------------------------------------
    # 6. Beats SPY buy-and-hold?  (v1.0 acceptance criterion)
    # ------------------------------------------------------------------
    print("Q6: Beats SPY buy-and-hold? (v1.0 acceptance #6)")
    print("-" * 70)
    spy_bh = vs_spy_buyhold(strategy_returns, spy)
    print(spy_bh.summary())
    print()

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    results = {
        "Q1 DSR": dsr.passes,
        "Q2 Consistency": consistency.passes,
        "Q3 Walk-Forward CV": cv.passes,
        "Q4 vs Random": rand.passes,
        "Q5 vs Buy & Hold": bh.passes,
        "Q6 vs SPY": spy_bh.passes,
    }
    print("=" * 70)
    print("VERDICT SUMMARY")
    print("=" * 70)
    for q, passed in results.items():
        verdict = "PASS" if passed else "FAIL"
        print(f"  {q:<25} {verdict}")
    n_pass = sum(results.values())
    n_total = len(results)
    print()
    print(f"Overall: {n_pass}/{n_total} acceptance questions pass.")
    if n_pass == n_total:
        print("v1.0 acceptance criteria met.")
    else:
        print("v1.0 acceptance criteria NOT met. See failing question(s) above.")


if __name__ == "__main__":
    _answer_acceptance_questions()
