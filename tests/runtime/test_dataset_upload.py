from __future__ import annotations

import pytest

from alphaloop.contracts.artifacts import hash_bytes
from alphaloop.runtime.dataset_cache import (
    DatasetRejected,
    dataset_parquet_path,
    put_dataset_bytes,
)
from alphaloop.runtime.example_dataset import example_dataset_bytes


def test_put_dataset_bytes_writes_hash_named_cache(tmp_path):
    blob = example_dataset_bytes()
    ref = put_dataset_bytes(tmp_path, blob)
    assert ref.sha256 == hash_bytes(blob)
    assert ref.dataset_id == "ds_" + ref.sha256[:16]
    stored = dataset_parquet_path(tmp_path, ref.dataset_id)
    assert stored.read_bytes() == blob
    again = put_dataset_bytes(tmp_path, blob)
    assert again == ref


def test_put_dataset_bytes_rejects_empty(tmp_path):
    with pytest.raises(DatasetRejected, match="empty"):
        put_dataset_bytes(tmp_path, b"")


def test_put_dataset_bytes_rejects_non_parquet(tmp_path):
    with pytest.raises(DatasetRejected, match="parquet"):
        put_dataset_bytes(tmp_path, b"not a parquet file")


def test_put_dataset_bytes_rejects_too_large(tmp_path, monkeypatch):
    import alphaloop.runtime.dataset_cache as cache

    monkeypatch.setattr(cache, "MAX_DATASET_BYTES", 8)
    with pytest.raises(DatasetRejected, match="too large"):
        put_dataset_bytes(tmp_path, b"PAR1xxxxx")
