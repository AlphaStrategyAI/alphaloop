"""
`alphaloop report` — generate the v1.0 acceptance report.

This is the "30 minutes to answer 6 questions" tool: it runs every
diagnostic from M1 and every alpha factor from M2 on synthetic data
and writes a single Markdown file summarizing pass/fail for each of
the 6 v1.0 acceptance questions.

Honest by design: a strategy that fails 4/6 questions is reported
as such, not glossed over. The whole point of alphaloop is to
surface uncomfortable truths, not to make your backtest look good.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


def _make_universe(
    n_bars: int = 1500,
    seed: int = 0,
) -> tuple[pd.Series, pd.DataFrame, pd.Series]:
    """Synthetic universe: prices, OHLCV, and a SPY-like baseline."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2018-01-01", periods=n_bars, freq="B")

    # Strategy universe: mild positive drift
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

    # SPY-like: lower drift, slightly lower vol
    spy_rets = rng.normal(0.0003, 0.009, n_bars)
    spy = pd.Series(
        100.0 * np.exp(np.cumsum(spy_rets)),
        index=idx,
    )
    return prices, ohlcv, spy


def _section(title: str) -> str:
    return f"\n## {title}\n\n"


def _verdict(passes: bool) -> str:
    return "**PASS**" if passes else "**FAIL**"


def _acceptance_q1(prices: pd.Series) -> tuple[bool, str]:
    """Q1: Is the strategy overfit? (Deflated Sharpe Ratio)"""
    import alphaloop
    returns = prices.pct_change().dropna()
    annualized_sharpe = (
        returns.mean() / returns.std() * np.sqrt(252)
    )
    dsr = alphaloop.deflated_sharpe(
        observed_sharpe=float(annualized_sharpe),
        n_trials=20,
        returns=returns,
    )
    body = dsr.summary()
    return dsr.passes, body


def _acceptance_q2(prices: pd.Series, ohlcv: pd.DataFrame) -> tuple[bool, str]:
    """Q2: Are data sources consistent?"""
    import alphaloop
    # Simulate a second source with mild noise
    rng = np.random.default_rng(2)
    secondary = ohlcv.copy()
    n = len(secondary)
    secondary["close"] = secondary["close"] * (
        1.0 + rng.normal(0.0, 0.0005, n)
    )
    result = alphaloop.data_source_consistency(
        ohlcv, secondary, symbol="AAPL"
    )
    return result.passes, result.summary()


def _acceptance_q3(prices: pd.Series) -> tuple[bool, str]:
    """Q3: Out-of-sample valid? (Walk-Forward CV)"""
    import alphaloop
    cv = alphaloop.walk_forward_cv(
        prices,
        lambda p: pd.Series(1.0, index=p.index),
        train_size=252,
        test_size=63,
        step_size=63,
    )
    return cv.passes, cv.summary()


def _acceptance_q4(prices: pd.Series) -> tuple[bool, str]:
    """Q4: Beats a random strategy?"""
    import alphaloop
    returns = prices.pct_change().dropna()
    rand = alphaloop.vs_random(returns, n_simulations=500, block_size=21)
    return rand.passes, rand.summary()


def _acceptance_q5(prices: pd.Series) -> tuple[bool, str]:
    """Q5: Beats passive buy-and-hold?"""
    import alphaloop
    returns = prices.pct_change().dropna()
    bh = alphaloop.vs_buy_hold(returns, prices)
    return bh.passes, bh.summary()


def _acceptance_q6(prices: pd.Series, spy: pd.Series) -> tuple[bool, str]:
    """Q6: Beats SPY buy-and-hold?"""
    import alphaloop
    returns = prices.pct_change().dropna()
    spy_bh = alphaloop.vs_spy_buyhold(returns, spy)
    return spy_bh.passes, spy_bh.summary()


def _alpha_comparison(prices: pd.Series, ohlcv: pd.DataFrame) -> str:
    """Run all 10 alpha factors and report pass/fail vs buy & hold."""
    import alphaloop.diagnostic as diagnostic
    import alphaloop.engineer as engineer

    rng = np.random.default_rng(99)
    pairs_b = prices * (1.0 + rng.normal(0, 0.001, len(prices)))

    factors = [
        ("rsi", lambda: engineer.rsi(prices), False),
        ("macd", lambda: engineer.macd(prices), False),
        ("roc", lambda: engineer.roc(prices), False),
        ("momentum_12_1", lambda: engineer.momentum_12_1(prices), False),
        ("bollinger_zscore", lambda: engineer.bollinger_zscore(prices), False),
        ("ohlr_4_pct", lambda: engineer.ohlr_4_pct(ohlcv), True),
        ("atr_breakout", lambda: engineer.atr_breakout(ohlcv), True),
        # parkinson is a feature, not a signal — skip
        ("obv_slope", lambda: engineer.obv_slope(prices, ohlcv["volume"]), True),
        ("pairs_spread", lambda: engineer.pairs_spread(prices, pairs_b, window=20), False),
    ]
    rows = []
    n_pass = 0
    for name, fn, needs_ohlcv in factors:
        w = fn()
        if w.sum() == 0:
            rows.append((name, "SKIP", "no signal", "—", "—"))
            continue
        if needs_ohlcv:
            rets = ohlcv["close"].pct_change() * w.shift(1)
        else:
            rets = prices.pct_change() * w.shift(1)
        rets = rets.dropna()
        if len(rets) < 10 or rets.std() == 0:
            rows.append((name, "SKIP", "insufficient returns", "—", "—"))
            continue
        bh = diagnostic.vs_buy_hold(rets.fillna(0), prices)
        verdict = "PASS" if bh.passes else "fail"
        if bh.passes:
            n_pass += 1
        rows.append((name, verdict, f"{bh.strategy_sharpe:+.2f}", f"{bh.buy_hold_sharpe:+.2f}", f"{bh.sharpe_gap:+.2f}"))

    out = "| Factor | Verdict | Strategy SR | vs Buy & Hold SR | Gap |\n"
    out += "|---|---|---|---|---|\n"
    for name, verdict, sr, bh, gap in rows:
        out += f"| {name} | {verdict} | {sr} | {bh} | {gap} |\n"
    out += f"\n**Result**: {n_pass}/{len(rows)} factors beat buy-and-hold "
    out += f"({'acceptance #5 met' if n_pass >= 3 else 'acceptance #5 NOT met'}).\n"
    return out


def run_report(args: argparse.Namespace) -> int:
    prices, ohlcv, spy = _make_universe(seed=args.seed)

    sections: list[str] = []
    sections.append("# alphaloop v1.0 Acceptance Report\n\n")
    sections.append(
        f"_Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}_\n\n"
    )
    sections.append(
        "This report answers the 6 v1.0 acceptance questions on a synthetic "
        "universe (1500 bars, mild positive drift). Pass/fail is honest: "
        "no sugar-coating.\n"
    )

    sections.append(_section("Q1: Is the strategy overfit?"))
    q1_pass, q1_body = _acceptance_q1(prices)
    sections.append(f"{_verdict(q1_pass)}\n\n```\n{q1_body}\n```\n")

    sections.append(_section("Q2: Are data sources consistent?"))
    q2_pass, q2_body = _acceptance_q2(prices, ohlcv)
    sections.append(f"{_verdict(q2_pass)}\n\n```\n{q2_body}\n```\n")

    sections.append(_section("Q3: Out-of-sample valid?"))
    q3_pass, q3_body = _acceptance_q3(prices)
    sections.append(f"{_verdict(q3_pass)}\n\n```\n{q3_body}\n```\n")

    sections.append(_section("Q4: Beats a random strategy?"))
    q4_pass, q4_body = _acceptance_q4(prices)
    sections.append(f"{_verdict(q4_pass)}\n\n```\n{q4_body}\n```\n")

    sections.append(_section("Q5: Beats passive buy-and-hold?"))
    q5_pass, q5_body = _acceptance_q5(prices)
    sections.append(f"{_verdict(q5_pass)}\n\n```\n{q5_body}\n```\n")

    sections.append(_section("Q6: Beats SPY buy-and-hold?"))
    q6_pass, q6_body = _acceptance_q6(prices, spy)
    sections.append(f"{_verdict(q6_pass)}\n\n```\n{q6_body}\n```\n")

    sections.append(_section("Alpha factor library (10 factors vs buy-and-hold)"))
    sections.append(_alpha_comparison(prices, ohlcv))

    sections.append(_section("Summary"))
    n_pass = sum([q1_pass, q2_pass, q3_pass, q4_pass, q5_pass, q6_pass])
    sections.append(
        f"**Acceptance questions passed**: {n_pass}/6\n\n"
    )
    if n_pass == 6:
        sections.append("v1.0 acceptance criteria fully met.\n")
    else:
        sections.append(
            f"v1.0 acceptance: {n_pass}/6 questions passed. "
            "This is honest reporting — see failing question(s) above.\n"
        )

    report = "".join(sections)

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(report, encoding="utf-8")
        print(f"Report written to {out_path}")
    else:
        print(report)
    return 0


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the `report` subcommand."""
    parser = subparsers.add_parser(
        "report",
        help="Generate the v1.0 acceptance report (Markdown).",
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file path. If omitted, prints to stdout.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Random seed for synthetic universe (default 0).",
    )
    parser.set_defaults(func=run_report)


if __name__ == "__main__":
    # Allow standalone execution: `python -m alphaloop.cli.report`
    parser = argparse.ArgumentParser(description="alphaloop report")
    register(parser.add_subparsers())
    args = parser.parse_args()
    if hasattr(args, "func"):
        sys.exit(args.func(args))
    parser.print_help()
    sys.exit(1)