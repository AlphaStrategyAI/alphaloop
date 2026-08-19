from __future__ import annotations

from pathlib import Path

import pytest

from alphaloop.contracts.artifacts import (
    DatasetMismatchError,
    DatasetRef,
    RunLayout,
    hash_bytes,
    require_dataset,
)


def test_run_layout_paths(tmp_path: Path):
    layout = RunLayout(tmp_path / "runs" / "rid")
    assert layout.research_spec.name == "research-spec.yaml"
    assert layout.manifest.name == "manifest.yaml"
    assert layout.trial_ledger.name == "trial-ledger.jsonl"
    assert layout.checkpoints.name == "checkpoints"
    assert layout.candidates.name == "candidates.parquet"
    assert layout.evidence.name == "evidence"
    assert layout.recommendations.name == "recommendations.json"
    assert layout.report.name == "report.md"


def test_require_dataset_accepts_matching_hash():
    blob = b"ohlcv-v1"
    ref = DatasetRef(dataset_id="ds_test", sha256=hash_bytes(blob))
    require_dataset(ref, blob)


def test_require_dataset_fails_closed_on_mismatch():
    ref = DatasetRef(dataset_id="ds_test", sha256=hash_bytes(b"a"))
    with pytest.raises(DatasetMismatchError):
        require_dataset(ref, b"b")
