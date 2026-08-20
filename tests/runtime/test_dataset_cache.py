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


def test_cache_dataset_file_converts_wide_csv(tmp_path):
    from alphaloop.runtime.dataset_cache import cache_dataset_file, dataset_parquet_path

    idx = pd.bdate_range("2018-01-01", periods=5)
    frame = pd.DataFrame(
        {"AAPL": 100.0, "MSFT": 100.0, "SPY": 100.0},
        index=idx,
    )
    src = tmp_path / "prices.csv"
    frame.to_csv(src)
    ref = cache_dataset_file(tmp_path, src)
    stored = pd.read_parquet(dataset_parquet_path(tmp_path, ref.dataset_id))
    assert list(stored.columns) == ["AAPL", "MSFT", "SPY"]
    assert len(stored) == 5


def test_cache_dataset_file_rejects_plain_text(tmp_path):
    from alphaloop.runtime.dataset_cache import DatasetRejected, cache_dataset_file

    src = tmp_path / "notes.txt"
    src.write_text("not a snapshot", encoding="utf-8")
    with pytest.raises(DatasetRejected, match="parquet or csv"):
        cache_dataset_file(tmp_path, src)


def test_cache_dataset_bytes_converts_wide_csv(tmp_path):
    from alphaloop.runtime.dataset_cache import cache_dataset_bytes, dataset_parquet_path

    idx = pd.bdate_range("2018-01-01", periods=5)
    frame = pd.DataFrame({"AAPL": 100.0, "MSFT": 100.0, "SPY": 100.0}, index=idx)
    blob = frame.to_csv().encode("utf-8")
    ref = cache_dataset_bytes(tmp_path, blob)
    stored = pd.read_parquet(dataset_parquet_path(tmp_path, ref.dataset_id))
    assert list(stored.columns) == ["AAPL", "MSFT", "SPY"]


def test_cache_dataset_bytes_rejects_plain_text(tmp_path):
    from alphaloop.runtime.dataset_cache import DatasetRejected, cache_dataset_bytes

    with pytest.raises(DatasetRejected, match="parquet or csv"):
        cache_dataset_bytes(tmp_path, b"not parquet")


def test_format_dataset_receipt_is_pasteable_yaml():
    from alphaloop.runtime.dataset_cache import DATASET_NO_ALPHA, format_dataset_receipt

    text = format_dataset_receipt(
        dataset_id="ds_abc",
        sha256="deadbeef",
        cached_path="/tmp/prices.parquet",
    )
    assert text.splitlines() == [
        "dataset:",
        "  dataset_id: ds_abc",
        "  sha256: deadbeef",
        "Cached: /tmp/prices.parquet",
        DATASET_NO_ALPHA,
    ]
    assert "FOUND" not in text
