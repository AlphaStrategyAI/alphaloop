from __future__ import annotations

from pathlib import Path

import pandas as pd

from alphaloop.contracts.artifacts import (
    DatasetMismatchError,
    RunLayout,
    require_dataset,
)
from alphaloop.contracts.research_spec import ResearchSpec


class DatasetUnavailableError(FileNotFoundError):
    """Raised when no dataset snapshot or legacy prices.parquet is available."""


def dataset_parquet_path(data_dir: Path, dataset_id: str) -> Path:
    return Path(data_dir) / "datasets" / dataset_id / "prices.parquet"


def _universe(market_scope: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in market_scope.split(",") if part.strip())


def _frame_to_prices(
    frame: pd.DataFrame, spec: ResearchSpec
) -> tuple[dict[str, pd.Series], pd.Series, pd.Series]:
    prices = {str(col): frame[col].astype(float) for col in frame.columns}
    universe = _universe(spec.hypothesis.market_scope)
    primary_key = universe[0] if universe else next(iter(prices))
    buy_hold = prices.get(primary_key, next(iter(prices.values())))
    benchmark_key = spec.hypothesis.benchmark
    benchmark = prices.get(benchmark_key, buy_hold) if benchmark_key else buy_hold
    return prices, buy_hold, benchmark


def load_prices(
    layout: RunLayout,
    spec: ResearchSpec,
    *,
    data_dir: Path,
) -> tuple[dict[str, pd.Series], pd.Series, pd.Series]:
    """Load prices from the declared dataset cache or a legacy run-dir parquet.

    Prefer the hashed cache when ``spec.dataset`` is set. Fall back to
    ``layout.run_dir / "prices.parquet"`` only when dataset is unset.
    """
    data_dir = Path(data_dir)

    if spec.dataset is not None:
        path = dataset_parquet_path(data_dir, spec.dataset.dataset_id)
        if not path.is_file():
            raise DatasetUnavailableError(
                f"dataset snapshot unavailable: {path}"
            )
        blob = path.read_bytes()
        require_dataset(spec.dataset, blob)
        frame = pd.read_parquet(path)
        return _frame_to_prices(frame, spec)

    legacy = layout.run_dir / "prices.parquet"
    if legacy.is_file():
        frame = pd.read_parquet(legacy)
        return _frame_to_prices(frame, spec)

    raise DatasetUnavailableError(
        f"no dataset snapshot and no legacy prices at {legacy}"
    )
