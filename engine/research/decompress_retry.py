"""Retry a market read once when zlib rejects the payload header.

``Error -3 while decompressing data: incorrect header check`` is raised by
Python's zlib, not by the quote vendor. It shows up when a gzip/deflate body
does not match ``Content-Encoding``, when yfinance reloads a broken cookie
pickle, or when ``pandas.read_pickle`` walks a damaged frame. One fresh
attempt is enough: drop the on-disk yfinance cache and ask HTTP for an
uncompressed body. A second failure becomes a normal market-data error
instead of an unmapped ``RUN_LOOP_FAILED``.
"""

from __future__ import annotations

import os
import zlib
from collections.abc import Callable

from engine.research.user_errors import UserFacingError

_IDENTITY = "_alphaloop_identity_encoding"


def is_decompress_error(error: BaseException) -> bool:
    """True for a zlib header failure, including ones wrapped by HTTP clients."""
    if isinstance(error, UserFacingError):
        return False
    seen: set[int] = set()
    stack: list[BaseException] = [error]
    while stack:
        current = stack.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, zlib.error):
            return True
        text = str(current)
        if "incorrect header check" in text or "Error -3 while decompressing" in text:
            return True
        for linked in (current.__cause__, current.__context__):
            if linked is not None:
                stack.append(linked)
    return False


def purge_yfinance_disk_cache() -> None:
    """Close and remove yfinance's sqlite caches so a bad pickle is not reloaded."""
    try:
        from yfinance import cache as yf_cache
    except ImportError:
        return
    pairs = (
        ("_CookieDBManager", "_CookieCacheManager", "_Cookie_cache"),
        ("_TzDBManager", "_TzCacheManager", "_tz_cache"),
        ("_ISINDBManager", "_ISINCacheManager", "_isin_cache"),
    )
    for manager_name, cache_name, attr in pairs:
        manager = getattr(yf_cache, manager_name, None)
        cache = getattr(yf_cache, cache_name, None)
        if manager is None:
            continue
        db = getattr(manager, "_db", None)
        if db is not None:
            try:
                db.close()
            except (OSError, RuntimeError, ValueError, TypeError):
                manager._db = None
            else:
                manager._db = None
        directory = getattr(manager, "_cache_dir", None)
        if directory and os.path.isdir(directory):
            for name in os.listdir(directory):
                if name.endswith((".db", ".db-wal", ".db-shm")):
                    try:
                        os.remove(os.path.join(directory, name))
                    except OSError:
                        pass
        if cache is not None and hasattr(cache, attr):
            setattr(cache, attr, None)


def _with_identity_encoding[T](fn: Callable[[], T]) -> T:
    import requests

    original_request = requests.request
    original_get = requests.get

    def request(method: str, url: str, **kwargs: object) -> object:
        headers = dict(kwargs.get("headers") or {})  # type: ignore[arg-type]
        headers["Accept-Encoding"] = "identity"
        kwargs["headers"] = headers
        return original_request(method, url, **kwargs)

    def get(url: str, **kwargs: object) -> object:
        headers = dict(kwargs.get("headers") or {})  # type: ignore[arg-type]
        headers["Accept-Encoding"] = "identity"
        kwargs["headers"] = headers
        return original_get(url, **kwargs)

    setattr(request, _IDENTITY, True)
    setattr(get, _IDENTITY, True)
    requests.request = request  # type: ignore[assignment]
    requests.get = get  # type: ignore[method-assign]
    try:
        return fn()
    finally:
        requests.request = original_request  # type: ignore[assignment]
        requests.get = original_get  # type: ignore[method-assign]


def retry_on_decompress[T](fn: Callable[[], T]) -> T:
    """Run ``fn`` once more after a zlib header failure. Same source, no new vendor."""
    try:
        return fn()
    except Exception as error:
        if not is_decompress_error(error):
            raise
        purge_yfinance_disk_cache()
        try:
            return _with_identity_encoding(fn)
        except Exception as second:
            if not is_decompress_error(second):
                raise
            raise UserFacingError(
                "MARKET_DATA_FETCH_FAILED",
                "行情压缩数据无法解开，请稍后重试。",
                params={"symbol": "行情"},
                detail=str(error),
            ) from second
