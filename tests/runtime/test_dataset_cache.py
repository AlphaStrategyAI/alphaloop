from __future__ import annotations

import pandas as pd
import pytest

from alphaloop.contracts.artifacts import DatasetRef, RunLayout, hash_bytes
from alphaloop.contracts.research_spec import new_research_spec
from alphaloop.runtime.dataset_cache import DatasetUnavailableError, load_prices


def _spec(**overrides):
    payload = dict(
        statement="12-1 momentum works",
        economic_logic="past winners continue",
        signal_mechanism="momentum_12_1",
        market_scope="AAPL, MSFT",
        market_profile="us-equity-daily",
        benchmark="SPY",
        hard_gates=("dsr",),
        seed=7,
        time_budget_s=30,
        cost_budget_usd=1.0,
    )
    payload.update(overrides)
    return new_research_spec(**payload)


def _write_dataset(tmp_path, columns):
    idx = pd.bdate_range("2018-01-01", periods=20)
    frame = pd.DataFrame({name: range(20) for name in columns}, index=idx)
    path = tmp_path / "datasets" / "ds_cols" / "prices.parquet"
    path.parent.mkdir(parents=True)
    frame.to_parquet(path)
    digest = hash_bytes(path.read_bytes())
    spec = _spec(dataset=DatasetRef(dataset_id="ds_cols", sha256=digest))
    layout = RunLayout(tmp_path / "j_cols")
    layout.run_dir.mkdir()
    return layout, spec


def test_missing_universe_column_raises(tmp_path):
    layout, spec = _write_dataset(tmp_path, ("MSFT", "SPY"))
    with pytest.raises(DatasetUnavailableError, match="AAPL"):
        load_prices(layout, spec, data_dir=tmp_path)


def test_missing_benchmark_column_raises(tmp_path):
    layout, spec = _write_dataset(tmp_path, ("AAPL", "MSFT"))
    with pytest.raises(DatasetUnavailableError, match="SPY"):
        load_prices(layout, spec, data_dir=tmp_path)
