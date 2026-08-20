"""Packaged close-only example snapshot for Load example → Preview."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from alphaloop.contracts.artifacts import DatasetRef, hash_bytes
from alphaloop.runtime.dataset_cache import dataset_parquet_path

EXAMPLE_DATASET_ID = "ds_example"


def example_dataset_bytes() -> bytes:
    return (
        files("alphaloop.runtime.example_dataset")
        .joinpath("prices.parquet")
        .read_bytes()
    )


def example_dataset_ref() -> DatasetRef:
    return DatasetRef(
        dataset_id=EXAMPLE_DATASET_ID,
        sha256=hash_bytes(example_dataset_bytes()),
    )


def ensure_example_dataset(data_dir: Path) -> DatasetRef:
    ref = example_dataset_ref()
    path = dataset_parquet_path(Path(data_dir), ref.dataset_id)
    blob = example_dataset_bytes()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file() or path.read_bytes() != blob:
        path.write_bytes(blob)
    return ref
