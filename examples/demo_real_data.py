"""
Real-data smoke test for alphaloop data sources.

Runs against live APIs (yahoo / akshare / ccxt) and prints a summary.
Useful as a sanity check that the optional integrations still work after
upgrading the underlying libraries.

Usage:
    python examples/demo_real_data.py
    python examples/demo_real_data.py --output ./reports
"""
from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path


def try_fetch(name: str, fn, output_dir: Path | None) -> dict:
    """Run a fetch callable, return a small summary dict.

    Network failures are expected and reported gracefully — the demo's job
    is to show what works today, not to fail loudly on missing deps.
    """
    try:
        df = fn()
    except Exception as e:
        print(f"  [FAIL] {name}: {type(e).__name__}: {e}")
        return {"source": name, "ok": False, "error": f"{type(e).__name__}: {e}"}

    if df is None or df.empty:
        print(f"  [EMPTY] {name}: no rows returned")
        return {"source": name, "ok": False, "error": "empty"}

    summary = {
        "source": name,
        "ok": True,
        "rows": len(df),
        "start": str(df.index.min()),
        "end": str(df.index.max()),
        "last_close": float(df["close"].iloc[-1]) if "close" in df.columns else None,
    }
    print(f"  [OK]   {name}: {summary['rows']} rows  "
          f"{summary['start'][:10]} → {summary['end'][:10]}  "
          f"last_close={summary['last_close']}")

    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        out = output_dir / f"{name}.csv"
        df.to_csv(out)

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Real-data demo for alphaloop")
    parser.add_argument(
        "--output", help="Optional directory to dump CSV files for each source"
    )
    args = parser.parse_args()

    output_dir = Path(args.output) if args.output else None

    print("=" * 60)
    print("OpenStrategy — Real-Data Demo")
    print("=" * 60)
    print()

    summaries: list[dict] = []

    # --- Yahoo Finance ---
    print("Yahoo Finance — AAPL")
    try:
        from alphaloop.data import YahooFinanceSource

        summaries.append(
            try_fetch(
                "yahoo_AAPL",
                lambda: YahooFinanceSource().get_data("AAPL", period="1mo"),
                output_dir,
            )
        )
    except Exception as e:
        print(f"  [SKIP] yahoo: {e}")

    # --- AKShare (A-share) ---
    print("\nAKShare — 600519 (贵州茅台)")
    try:
        from alphaloop.data import AKShareSource

        summaries.append(
            try_fetch(
                "akshare_600519",
                lambda: AKShareSource().get_data("600519", period="1mo"),
                output_dir,
            )
        )
    except Exception as e:
        print(f"  [SKIP] akshare: {e}")

    # --- CCXT (crypto) ---
    print("\nCCXT — BTC/USDT (okx)")
    try:
        from alphaloop.data.ccxt import CCXTSource

        summaries.append(
            try_fetch(
                "ccxt_BTC_USDT_okx",
                # Public market data on OKX doesn't need a proxy; pass
                # use_proxy=False so users without a local proxy can run.
                lambda: CCXTSource(exchange="okx", use_proxy=False).get_data(
                    "BTC/USDT", period="1mo"
                ),
                output_dir,
            )
        )
    except Exception as e:
        print(f"  [SKIP] ccxt: {e}")

    # --- Summary ---
    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    ok = sum(1 for s in summaries if s.get("ok"))
    print(f"{ok}/{len(summaries)} sources returned data.")
    if output_dir:
        print(f"CSV files: {output_dir}")

    # Exit 0 if at least one source worked (others may be blocked by network
    # or missing optional deps in this environment).
    return 0 if ok > 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(130)