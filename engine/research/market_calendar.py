"""Canonical asset calendar shared by the first simulation, reverify, and pack runner.

Revision ``asset-calendar-v1`` drops sessions the asset panel does not trade and
keeps the benchmark level on the remaining dates. A benchmark-only day is not a
return step: 100 then 110 then 121, with the asset missing the middle day,
settles the next asset session at 21%.
"""

from __future__ import annotations

import pandas as pd

CALENDAR_REVISION = "asset-calendar-v1"


def align_asset_calendar(
    prices: pd.DataFrame,
    benchmark: pd.Series,
) -> tuple[pd.DataFrame, pd.Series]:
    """Return prices and benchmark on the asset's own dates, original order kept."""
    if prices.empty:
        return prices, benchmark.reindex(prices.index)
    asset = prices.dropna(how="all")
    if asset.empty:
        asset = prices
    aligned_benchmark = benchmark.reindex(asset.index)
    if aligned_benchmark.name is None:
        aligned_benchmark.name = getattr(benchmark, "name", None) or "benchmark"
    return asset, aligned_benchmark
