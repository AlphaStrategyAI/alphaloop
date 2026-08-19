from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from alphaloop.contracts.research_spec import ResearchSpec

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

    if not spec.success_criteria.hard_gates:
        errors.append("at least one hard gate is required")

    if spec.time_budget_s <= 0:
        errors.append("time budget must be positive")

    if spec.cost_budget_usd < 0:
        errors.append("cost budget cannot be negative")

    errors.extend(_check_data_dir(data_dir, min_free_bytes))

    return PreflightResult(
        ok=not errors,
        errors=tuple(errors),
        warnings=(),
        host_constraint=HOST_CONSTRAINT,
    )
