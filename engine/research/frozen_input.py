"""One frozen input panel per research version. Later rounds reuse it."""

from __future__ import annotations

import hashlib
import os
import pickle
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from engine.metrics import benchmark_for
from engine.research.a1_copy import (
    DATA_SOURCE_UNBOUND,
    DATA_WINDOW_UNPINNED,
    FROZEN_INPUT_UNREADABLE,
)
from engine.research.gather import DataPort, GatherBatch, MaterialPort, gather_materials
from engine.research.models import Research
from engine.research.user_errors import UserFacingError


@dataclass(slots=True)
class FrozenVersionInput:
    prices: pd.DataFrame
    benchmark: pd.DataFrame
    benchmark_id: str
    start: date
    end: date
    batch: GatherBatch

    def load_daily(
        self,
        symbols: tuple[str, ...],
        start: date,
        end: date,
    ) -> pd.DataFrame:
        del start, end
        from engine.research.data_errors import EmptySymbolsError

        if not symbols:
            raise EmptySymbolsError()
        if symbols == (self.benchmark_id,):
            return self.benchmark
        return self.prices.loc[:, list(symbols)]


def simulation_window(
    research: Research,
    fallback_start: date | None,
    fallback_end: date | None,
) -> tuple[date, date]:
    """Pinned confirm-time dates win. Never substitute the process start date."""
    if research.data_window_start is not None and research.data_window_end is not None:
        return research.data_window_start, research.data_window_end
    if fallback_start is not None and fallback_end is not None:
        return fallback_start, fallback_end
    if research.current_version_number is not None and research.versions:
        version = research.versions[research.current_version_number - 1]
        if version.rounds:
            simulation = version.rounds[-1].accepted_attempt.simulation
            start = getattr(simulation, "start", None)
            end = getattr(simulation, "end", None)
            if isinstance(start, date) and isinstance(end, date):
                return start, end
    raise UserFacingError("DATA_WINDOW_UNPINNED", DATA_WINDOW_UNPINNED)


def frozen_input_path(snapshot_root: Path, research_id: str, version_number: int) -> Path:
    return snapshot_root / "frozen-inputs" / f"{research_id}-v{version_number}.pkl"


def ensure_frozen_version_input(
    *,
    snapshot_root: Path,
    research: Research,
    version_number: int,
    symbols: tuple[str, ...],
    start: date,
    end: date,
    thesis: str,
    material_ports: tuple[MaterialPort, ...],
    live_port: DataPort | None,
    live_port_factory: Callable[[], DataPort] | None = None,
) -> FrozenVersionInput:
    path = frozen_input_path(snapshot_root, research.research_id, version_number)
    if path.is_file() or _hash_path(path).is_file():
        return _read_frozen(path)
    universe = research.brief.universe.value
    if universe is None:
        raise ValueError("running research requires a universe")
    port = live_port if live_port is not None else (
        live_port_factory() if live_port_factory is not None else None
    )
    if port is None:
        raise UserFacingError("DATA_SOURCE_UNBOUND", DATA_SOURCE_UNBOUND)
    batch = gather_materials(thesis, material_ports)
    prices = port.load_daily(symbols, start, end)
    benchmark_id = benchmark_for(universe).benchmark_id
    benchmark = port.load_daily((benchmark_id,), start, end)
    frozen = FrozenVersionInput(
        prices=prices,
        benchmark=benchmark,
        benchmark_id=benchmark_id,
        start=start,
        end=end,
        batch=batch,
    )
    _write_frozen(path, frozen)
    return frozen


def _hash_path(path: Path) -> Path:
    return path.parent / f"{path.name}.sha256"


def frozen_file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_frozen(path: Path, frozen: FrozenVersionInput) -> None:
    from engine.research.e2e_hooks import crash_barrier

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    pd.to_pickle(frozen, temporary)
    digest = hashlib.sha256(temporary.read_bytes()).hexdigest()
    os.replace(temporary, path)
    hash_path = _hash_path(path)
    hash_tmp = hash_path.with_suffix(".sha256.tmp")
    hash_tmp.write_text(digest + "\n", encoding="utf-8")
    os.replace(hash_tmp, hash_path)
    crash_barrier("after_freeze")


def _read_frozen(path: Path) -> FrozenVersionInput:
    hash_path = _hash_path(path)
    if hash_path.is_file() and not path.is_file():
        raise UserFacingError("FROZEN_INPUT_UNREADABLE", FROZEN_INPUT_UNREADABLE)
    if not path.is_file():
        raise UserFacingError("FROZEN_INPUT_UNREADABLE", FROZEN_INPUT_UNREADABLE)
    if hash_path.is_file():
        expected = hash_path.read_text(encoding="utf-8").strip()
        actual = frozen_file_hash(path)
        if expected != actual:
            raise UserFacingError("FROZEN_INPUT_UNREADABLE", FROZEN_INPUT_UNREADABLE)
    try:
        loaded = pd.read_pickle(path)
    except (OSError, EOFError, ValueError, TypeError, AttributeError, pickle.UnpicklingError):
        raise UserFacingError("FROZEN_INPUT_UNREADABLE", FROZEN_INPUT_UNREADABLE) from None
    if not isinstance(loaded, FrozenVersionInput):
        raise UserFacingError("FROZEN_INPUT_UNREADABLE", FROZEN_INPUT_UNREADABLE)
    return loaded
