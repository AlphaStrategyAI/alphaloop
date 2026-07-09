"""
Comparison demo - run 5 different strategies on synthetic data and
report honest results.

This is the v1.0 "5 策略对比样例" promised in the v1.0 goal README.

The 5 strategies are intentionally diverse (trend, mean-reversion,
volatility, volume, baseline) and the synthetic universe is a
random walk with mild drift. The honest result: most strategies
lose to SPY on random-walk data, which is the whole point.

Run:
    cd /Users/assistant/hermes-lab/openstrategy
    python3 examples/comparison_demo.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Allow running without pip install
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import openstrategy
import openstrategy.diagnostic as diagnostic
import openstrategy.engineer as engineer


def _make_universe(n_bars: int = 1500, seed: int = 42) -> tuple[
    pd.Series, pd.DataFrame, pd.Series
]:
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
        100.0 * np.exp(np.cumsum(spy_rets)),
        index=idx,
    )
    return prices, ohlcv, spy


def _evaluate(
    name: str,
    weights: pd.Series,
    prices: pd.Series,
    ohlcv: pd.DataFrame,
    spy: pd.Series,
) -> dict:
    """Evaluate a strategy: returns, Sharpe, vs buy-hold, vs SPY, vs random."""
    rets = prices.pct_change() * weights.shift(1)
    rets = rets.dropna().fillna(0)
    if rets.std() == 0:
        return {
            "name": name, "sharpe": 0.0, "vs_bh": "—", "vs_spy": "—",
            "vs_random": "—", "max_dd": "—",
        }
    bh = diagnostic.vs_buy_hold(rets, prices)
    spy_bh = diagnostic.vs_spy_buyhold(rets, spy)
    rand = diagnostic.vs_random(rets, n_simulations=200)
    cum = (1.0 + rets).cumprod()
    peak = cum.cummax()
    max_dd = float(((cum - peak) / peak).min())
    return {
        "name": name,
        "sharpe": float(rets.mean() / rets.std() * np.sqrt(252)),
        "vs_bh": "PASS" if bh.passes else "fail",
        "vs_spy": "PASS" if spy_bh.passes else "fail",
        "vs_random": "PASS" if rand.passes else "fail",
        "max_dd": f"{max_dd:.2%}",
    }


def main() -> int:
    prices, ohlcv, spy = _make_universe()

    # 5 strategies
    weights = {
        "buy_and_hold": pd.Series(1.0, index=prices.index),
        "rsi_momentum": engineer.rsi(prices, window=14),
        "bollinger_meanrev": engineer.bollinger_zscore(prices, window=20, num_std=1.5),
        "atr_breakout": engineer.atr_breakout(ohlcv),
        "obv_volume": engineer.obv_slope(prices, ohlcv["volume"]),
    }

    print("=" * 80)
    print("OPENSTRATEGY v1.0 — 5-STRATEGY COMPARISON DEMO")
    print("=" * 80)
    print(f"Universe: 1500 bars synthetic random walk (drift=0.05%/day)")
    print(f"SPY baseline Sharpe: "
          f"{(spy.pct_change().mean() / spy.pct_change().std() * np.sqrt(252)):.3f}")
    print()

    results = []
    for name, w in weights.items():
        results.append(_evaluate(name, w, prices, ohlcv, spy))

    # Print table
    headers = ["Strategy", "Sharpe", "vs Buy & Hold", "vs SPY", "vs Random", "Max DD"]
    print(f"{headers[0]:<22} {headers[1]:>8} {headers[2]:>14} {headers[3]:>10} {headers[4]:>11} {headers[5]:>10}")
    print("-" * 80)
    for r in results:
        print(
            f"{r['name']:<22} {r['sharpe']:>+8.2f} {r['vs_bh']:>14} "
            f"{r['vs_spy']:>10} {r['vs_random']:>11} {r['max_dd']:>10}"
        )
    print()

    # Honest summary
    n_pass_spy = sum(1 for r in results if r["vs_spy"] == "PASS")
    n_total = len(results)
    print("=" * 80)
    print("HONEST SUMMARY")
    print("=" * 80)
    print(
        f"Of {n_total} strategies tested, {n_pass_spy} beat SPY buy-and-hold. "
        "This is on a synthetic random walk; real markets may differ. "
        "The point of this demo is to show that the tools work — not "
        "to declare a winner."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())