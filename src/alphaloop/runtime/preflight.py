from __future__ import annotations

import math
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from alphaloop.contracts.artifacts import DatasetMismatchError, require_dataset
from alphaloop.contracts.research_spec import ResearchSpec
from alphaloop.protocol.dsl import ALLOWED_KINDS, FEATURE_KINDS, VOLUME_KINDS

HOST_CONSTRAINT = (
    "The host must remain awake while a local worker is running. "
    "Closing the browser or terminal does not stop a job, but "
    "suspending or powering off the host stops computation."
)


@dataclass(frozen=True)
class PreflightResult:
    ok: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    host_constraint: str


def _check_data_dir(data_dir: Path, min_free_bytes: int) -> list[str]:
    errors: list[str] = []

    if data_dir.exists() and not data_dir.is_dir():
        errors.append("data directory path is not a directory")
        return errors

    try:
        data_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        errors.append("data directory cannot be created")
        return errors

    if not os.access(data_dir, os.W_OK):
        errors.append("data directory is not writable")

    try:
        usage = shutil.disk_usage(data_dir)
        if usage.free < min_free_bytes:
            errors.append(
                f"insufficient disk space: {usage.free} bytes free, "
                f"need at least {min_free_bytes} bytes"
            )
    except OSError:
        errors.append("unable to check disk space for data directory")

    return errors


def preflight(
    spec: ResearchSpec,
    data_dir: Path,
    *,
    min_free_bytes: int = 67108864,
) -> PreflightResult:
    errors: list[str] = []

    if spec.hypothesis.signal_mechanism in FEATURE_KINDS:
        errors.append(
            "parkinson_hist_vol is a volatility feature, not a directional signal_mechanism"
        )
    elif spec.hypothesis.signal_mechanism in VOLUME_KINDS:
        errors.append(
            "obv_slope requires a volume series; first-release snapshots are close-only"
        )
    elif spec.hypothesis.signal_mechanism not in ALLOWED_KINDS:
        errors.append(
            "unsupported signal_mechanism: "
            f"{spec.hypothesis.signal_mechanism}"
        )

    if not spec.success_criteria.hard_gates:
        errors.append("at least one hard gate is required")

    if not math.isfinite(spec.time_budget_s) or spec.time_budget_s <= 0:
        errors.append("time budget must be finite and positive")

    if not math.isfinite(spec.cost_budget_usd) or spec.cost_budget_usd < 0:
        errors.append("cost budget must be finite and non-negative")

    errors.extend(_check_data_dir(data_dir, min_free_bytes))

    dataset = getattr(spec, "dataset", None)
    if dataset is None:
        errors.append("dataset snapshot is required")
    else:
        path = Path(data_dir) / "datasets" / dataset.dataset_id / "prices.parquet"
        if not path.is_file():
            errors.append("dataset snapshot is unavailable")
        else:
            try:
                require_dataset(dataset, path.read_bytes())
            except DatasetMismatchError:
                errors.append("dataset snapshot hash mismatch")

    return PreflightResult(
        ok=not errors,
        errors=tuple(errors),
        warnings=(),
        host_constraint=HOST_CONSTRAINT,
    )
