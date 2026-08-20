from __future__ import annotations

from pathlib import Path

import pandas as pd

from alphaloop.contracts.artifacts import (
    DatasetRef,
    RunLayout,
    hash_bytes,
    require_dataset,
)
from alphaloop.contracts.research_spec import ResearchSpec

PARQUET_MAGIC = b"PAR1"
MAX_DATASET_BYTES = 64 * 1024 * 1024
DATASET_NO_ALPHA = "This cache does not claim alpha or future profitability."


class DatasetUnavailableError(FileNotFoundError):
    """Raised when no dataset snapshot or legacy prices.parquet is available."""


class DatasetRejected(ValueError):
    """Raised when uploaded snapshot bytes are empty, too large, or not parquet."""


def dataset_parquet_path(data_dir: Path, dataset_id: str) -> Path:
    return Path(data_dir) / "datasets" / dataset_id / "prices.parquet"


def format_dataset_receipt(
    *, dataset_id: str, sha256: str, cached_path: str
) -> str:
    return (
        "\n".join(
            [
                f"dataset_id: {dataset_id}",
                f"sha256: {sha256}",
                f"Cached: {cached_path}",
                DATASET_NO_ALPHA,
            ]
        )
        + "\n"
    )


def put_dataset_bytes(data_dir: Path, blob: bytes) -> DatasetRef:
    if not blob:
        raise DatasetRejected("dataset snapshot is empty")
    if len(blob) > MAX_DATASET_BYTES:
        raise DatasetRejected("dataset snapshot is too large")
    if not blob.startswith(PARQUET_MAGIC):
        raise DatasetRejected("dataset snapshot must be parquet")
    digest = hash_bytes(blob)
    dataset_id = "ds_" + digest[:16]
    path = dataset_parquet_path(data_dir, dataset_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(blob)
    ref = DatasetRef(dataset_id=dataset_id, sha256=digest)
    require_dataset(ref, path.read_bytes())
    return ref


def _universe(market_scope: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in market_scope.split(",") if part.strip())


def _frame_to_prices(
    frame: pd.DataFrame, spec: ResearchSpec
) -> tuple[dict[str, pd.Series], pd.Series, pd.Series]:
    prices = {str(col): frame[col].astype(float) for col in frame.columns}
    universe = _universe(spec.hypothesis.market_scope)
    required = list(universe)
    benchmark_key = spec.hypothesis.benchmark
    if benchmark_key:
        required.append(benchmark_key)
    missing = [key for key in required if key not in prices]
    if missing or not universe:
        detail = ", ".join(missing) if missing else "universe is empty"
        raise DatasetUnavailableError(
            f"dataset missing required columns: {detail}"
        )
    buy_hold = prices[universe[0]]
    benchmark = prices[benchmark_key] if benchmark_key else buy_hold
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
