"""On-disk close prices so a second load of the same window does not hit the network."""

from __future__ import annotations

import json
import threading
from datetime import date
from pathlib import Path

import pandas as pd

_lock = threading.Lock()
_dir: Path | None = None
_disabled = False


def set_price_cache_dir(path: Path | None) -> None:
    """``None`` restores the default data-root cache."""
    global _dir, _disabled
    _dir = path
    _disabled = False


def disable_price_cache() -> None:
    global _disabled
    _disabled = True


def price_cache_dir() -> Path | None:
    if _disabled:
        return None
    if _dir is not None:
        return _dir
    from engine.research.data_paths import resolve_data_root

    return resolve_data_root(ensure_exists=True) / "price-cache"


def get_cached_close(
    source: str,
    symbol: str,
    start: date,
    end: date,
) -> pd.Series | None:
    root = price_cache_dir()
    if root is None:
        return None
    meta_path = _meta_path(root, source, symbol)
    csv_path = _csv_path(root, source, symbol)
    if not meta_path.is_file() or not csv_path.is_file():
        return None
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    cached_start = date.fromisoformat(meta["start"])
    cached_end = date.fromisoformat(meta["end"])
    if cached_start > start or cached_end < end:
        return None
    frame = pd.read_csv(csv_path, parse_dates=["date"])
    series = pd.Series(
        frame["close"].to_numpy(),
        index=pd.to_datetime(frame["date"]),
        name=symbol,
    )
    if series.empty:
        return series
    return series.loc[pd.Timestamp(start) : pd.Timestamp(end)]


def put_cached_close(
    source: str,
    symbol: str,
    start: date,
    end: date,
    series: pd.Series,
) -> None:
    root = price_cache_dir()
    if root is None:
        return
    csv_path = _csv_path(root, source, symbol)
    meta_path = _meta_path(root, source, symbol)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(
        {"date": pd.to_datetime(series.index), "close": series.to_numpy()}
    )
    text = frame.to_csv(index=False)
    meta = json.dumps({"start": start.isoformat(), "end": end.isoformat()})
    with _lock:
        csv_path.write_text(text, encoding="utf-8")
        meta_path.write_text(meta, encoding="utf-8")


def _safe(symbol: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-._" else "_" for ch in symbol)


def _csv_path(root: Path, source: str, symbol: str) -> Path:
    return root / source / f"{_safe(symbol)}.csv"


def _meta_path(root: Path, source: str, symbol: str) -> Path:
    return root / source / f"{_safe(symbol)}.json"
