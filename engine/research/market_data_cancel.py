"""Stop a market-data load so a timed-out fetch does not start more requests."""

from __future__ import annotations

import contextvars
import threading

import requests

_generation: contextvars.ContextVar[int] = contextvars.ContextVar(
    "market_data_generation", default=0
)
_active_research: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "market_data_research", default=None
)
_lock = threading.Lock()
_next_generation = 0
_cancelled: set[int] = set()
_sessions: dict[int, requests.Session] = {}
_by_research: dict[str, set[int]] = {}
_original_get = requests.get
_guard_installed = False


class MarketDataCancelled(Exception):
    """The load's deadline fired. Callers must not start another request."""


def current_market_data_generation() -> int:
    return _generation.get()


def bind_market_data_generation(generation: int) -> contextvars.Token[int]:
    return _generation.set(generation)


def bind_active_research(research_id: str) -> contextvars.Token[str | None]:
    """Attribute market-data generations on this thread to one research."""
    return _active_research.set(research_id)


def reset_active_research(token: contextvars.Token[str | None]) -> None:
    _active_research.reset(token)


def _note_owner(generation: int) -> None:
    owner = _active_research.get()
    if not owner or generation == 0:
        return
    with _lock:
        _by_research.setdefault(owner, set()).add(generation)


def begin_market_data_generation() -> tuple[int, contextvars.Token[int] | None]:
    """Outermost load opens a generation. Nested calls reuse the current one.

    Thread pools do not copy context, so the returned generation is bound again
    inside each worker before it touches the network.
    """
    current = _generation.get()
    if current != 0:
        _note_owner(current)
        return current, None
    global _next_generation
    with _lock:
        _next_generation += 1
        generation = _next_generation
        _cancelled.discard(generation)
    _note_owner(generation)
    return generation, _generation.set(generation)


def end_market_data_generation(token: contextvars.Token[int] | None) -> None:
    if token is not None:
        _generation.reset(token)


def cancel_generation(generation: int) -> None:
    """Cancel one load from any thread and close its HTTP session."""
    if generation == 0:
        return
    with _lock:
        _cancelled.add(generation)
        session = _sessions.pop(generation, None)
    if session is not None:
        try:
            session.close()
        except Exception:
            pass


def cancel_market_data() -> None:
    """Mark this generation cancelled and close its HTTP session."""
    cancel_generation(_generation.get())


def cancel_market_data_for_research(research_id: str) -> None:
    """Stop in-flight loads that were started for this research."""
    with _lock:
        generations = list(_by_research.get(research_id, ()))
    for generation in generations:
        cancel_generation(generation)


def forget_research_market_data(research_id: str) -> None:
    """Drop generation bookkeeping after the research row is created again."""
    with _lock:
        _by_research.pop(research_id, None)


def generation_is_cancelled(generation: int | None = None) -> bool:
    if generation is None:
        generation = _generation.get()
    return generation != 0 and generation in _cancelled


def raise_if_market_data_cancelled() -> None:
    if generation_is_cancelled():
        raise MarketDataCancelled()


def _session(generation: int) -> requests.Session:
    with _lock:
        session = _sessions.get(generation)
        if session is None:
            session = requests.Session()
            _sessions[generation] = session
        return session


def _guarded_get(url: str, **kwargs: object) -> object:
    generation = _generation.get()
    if generation == 0:
        return _original_get(url, **kwargs)  # type: ignore[arg-type]
    raise_if_market_data_cancelled()
    from engine.research.market_data_timeouts import CN_HTTP_TIMEOUT_SEC

    kwargs.setdefault("timeout", CN_HTTP_TIMEOUT_SEC)
    return _session(generation).get(url, **kwargs)  # type: ignore[arg-type]


def install_market_data_request_guard() -> None:
    """Route ``requests.get`` through the cancel gate while a load is active."""
    global _guard_installed
    if _guard_installed:
        return
    requests.get = _guarded_get  # type: ignore[assignment]
    _guard_installed = True
