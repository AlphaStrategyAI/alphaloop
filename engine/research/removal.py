"""In-process cancellation for a research that was deleted while work was in flight."""

from __future__ import annotations

import threading

_lock = threading.Lock()
_removed: set[str] = set()


class ResearchRemoved(Exception):
    """The research row is gone. Callers must not reload it or record a run failure."""

    def __init__(self, research_id: str) -> None:
        super().__init__(research_id)
        self.research_id = research_id


def mark_research_removed(research_id: str) -> None:
    """Remember the id and stop market-data loads that belong to it."""
    with _lock:
        _removed.add(research_id)
    from engine.research.market_data_cancel import cancel_market_data_for_research

    cancel_market_data_for_research(research_id)


def forget_research_removed(research_id: str) -> None:
    """A newly created row with this id is not the one that was deleted."""
    with _lock:
        _removed.discard(research_id)
    from engine.research.market_data_cancel import forget_research_market_data

    forget_research_market_data(research_id)


def research_was_removed(research_id: str) -> bool:
    with _lock:
        return research_id in _removed
