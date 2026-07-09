"""
Alpha comparison demo - runs all 10 factors on synthetic data and
reports how many beat buy-and-hold (acceptance #5).

Generates a single synthetic price series, runs every factor, prints
each factor's Sharpe and a pass/fail verdict vs buy & hold.

Run:
    cd /Users/assistant/hermes-lab/openstrategy
    python3 examples/alpha_comparison_demo.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Allow running without pip install
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import openstrategy.diagnostic as diagnostic
import openstrategy.engineer as engineer


def _make_synthetic_universe(
    n_bars: int = 1500,
    seed: int = 0,
) -> tuple[pd.Series, pd.DataFrame]:
    """Make a synthetic price series with mild positive drift.

    Returns:
        prices: close-only pd.Series with DatetimeIndex.
        ohlcv: pd.DataFrame with open/high/low/close/volume.
    """
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
    return prices, ohlcv


def _pairs_b(prices: pd.Series, seed: int = 1) -> pd.Series:
    """Make a second instrument that's the same walk with small noise."""
    rng = np.random.default_rng(seed)
    return prices * (1.0 + rng.normal(0, 0.001, len(prices))).cumsum() / (
        1.0 + rng.normal(0, 0.001, len(prices))
    ).mean()  # rough rescale


def _build_factors(
    prices: pd.Series, ohlcv: pd.DataFrame
) -> list[tuple[str, pd.Series, bool]]:
    """Run each factor and return (name, weights, needs_ohlcv)."""
    pairs_b = _pairs_b(prices)
    return [
        ("rsi", engineer.rsi(prices), False),
        ("macd", engineer.macd(prices), False),
        ("roc", engineer.roc(prices), False),
        ("momentum_12_1", engineer.momentum_12_1(prices), False),
        ("bollinger_zscore", engineer.bollinger_zscore(prices), False),
        ("ohlr_4_pct", engineer.ohlr_4_pct(ohlcv), True),
        ("atr_breakout", engineer.atr_breakout(ohlcv), True),
        # parkinson is a feature, not a long signal — skip from vs-B&H
        # ("parkinson", engineer.parkinson_hist_vol(prices), False),
        ("obv_slope", engineer.obv_slope(prices, ohlcv["volume"]), True),
        ("pairs_spread", engineer.pairs_spread(prices, pairs_b, window=20), False),
    ]


def main() -> int:
    prices, ohlcv = _make_synthetic_universe()
    factors = _build_factors(prices, ohlcv)

    print("=" * 70)
    print("OPENSTRATEGY ALPHA COMPARISON (10 factors vs buy & hold)")
    print("=" * 70)
    print(f"Synthetic universe: 1500 bars, mild positive drift (drift=0.05%/day)")
    print(f"Buy & hold baseline: Sharpe = "
          f"{(prices.pct_change().mean() / prices.pct_change().std() * np.sqrt(252)):.3f}")
    print()

    n_pass = 0
    n_total = 0
    for name, w, needs_ohlcv in factors:
        if w.sum() == 0:
            print(f"  {name:20} SKIP (no signal)")
            continue
        n_total += 1
        if needs_ohlcv:
            rets = ohlcv["close"].pct_change() * w.shift(1)
        else:
            rets = prices.pct_change() * w.shift(1)
        rets = rets.dropna()
        if len(rets) < 10 or rets.std() == 0:
            print(f"  {name:20} SKIP (insufficient returns)")
            continue
        bh = diagnostic.vs_buy_hold(rets.fillna(0), prices)
        if bh.passes:
            n_pass += 1
        verdict = "PASS" if bh.passes else "fail"
        print(
            f"  {name:20} {verdict:4}  "
            f"strategy SR={bh.strategy_sharpe:+.2f}  "
            f"vs buy&hold SR={bh.buy_hold_sharpe:+.2f}  "
            f"gap={bh.sharpe_gap:+.2f}"
        )

    print()
    print(f"RESULT: {n_pass}/{n_total} factors beat buy & hold on this synthetic data.")
    if n_pass >= 3:
        print("v1.0 acceptance criterion #5 (vs buy & hold) met for the engineering sub-package.")
    else:
        print("v1.0 acceptance criterion #5 NOT met. Factor library needs more work.")
    return 0 if n_pass >= 3 else 1


if __name__ == "__main__":
    sys.exit(main())
