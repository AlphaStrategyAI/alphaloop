import threading
from collections.abc import Callable
from dataclasses import dataclass, field, replace

from engine.research.models import Research, ResearchStatus

SLICE_SECONDS = 5.0


@dataclass(slots=True)
class _Slice:
    started: float
    last_persisted: float


@dataclass(slots=True)
class TimeBudget:
    """Per-research effective time. One open slice never charges another research."""

    monotonic: Callable[[], float]
    _started: float | None = None
    _slices: dict[str, _Slice] = field(default_factory=dict)

    def begin(self, status: ResearchStatus, research_id: str | None = None) -> None:
        if status is not ResearchStatus.RUNNING:
            if research_id:
                self._slices.pop(research_id, None)
            else:
                self._slices.pop("", None)
                self._started = None
            return
        key = research_id if research_id is not None else ""
        if key not in self._slices:
            now = self.monotonic()
            self._slices[key] = _Slice(now, now)
        if key == "" and self._started is None:
            self._started = self._slices[""].started

    def elapsed_open(self, research_id: str | None = None) -> float:
        """Seconds since begin, without closing the slice. Zero when idle."""
        key = research_id if research_id is not None else ""
        slice_ = self._slices.get(key)
        if slice_ is None and key == "" and self._started is not None:
            return max(0.0, self.monotonic() - self._started)
        if slice_ is None:
            return 0.0
        return max(0.0, self.monotonic() - slice_.started)

    def open_research_ids(self) -> tuple[str, ...]:
        return tuple(research_id for research_id in self._slices if research_id)

    def checkpoint(self, research_id: str, store: object) -> float:
        """Persist complete 5s quanta. The returned tail is the unsaved fragment."""
        slice_ = self._slices.get(research_id)
        if slice_ is None:
            return 0.0
        now = self.monotonic()
        pending = now - slice_.last_persisted
        quanta = int(pending // SLICE_SECONDS)
        if quanta <= 0:
            return max(0.0, pending)
        seconds = quanta * SLICE_SECONDS
        add = getattr(store, "add_effective_slice", None)
        if add is not None:
            add(research_id, seconds)
        slice_.last_persisted += seconds
        return max(0.0, now - slice_.last_persisted)

    def finish(self, research: Research, store: object | None = None) -> Research:
        slice_ = self._slices.pop(research.research_id, None)
        if slice_ is None and "" in self._slices:
            slice_ = self._slices.pop("")
            self._started = None
        if slice_ is None and self._started is not None and not self._slices:
            elapsed = max(0.0, self.monotonic() - self._started)
            self._started = None
            return replace(research, effective_seconds=research.effective_seconds + elapsed)
        if slice_ is None:
            return research
        now = self.monotonic()
        remainder = max(0.0, now - slice_.last_persisted)
        if store is not None and remainder > 0:
            add = getattr(store, "add_effective_slice", None)
            if add is not None:
                add(research.research_id, remainder)
        elapsed = max(0.0, now - slice_.started)
        if not self._slices:
            self._started = None
        return replace(research, effective_seconds=research.effective_seconds + elapsed)


def start_budget_heartbeats(
    budget: TimeBudget,
    store: object,
    stop: threading.Event,
) -> None:
    """Every 5 wall-clock seconds, flush open slices. A crash loses at most one."""

    def run() -> None:
        while not stop.wait(SLICE_SECONDS):
            for research_id in budget.open_research_ids():
                budget.checkpoint(research_id, store)

    threading.Thread(target=run, name="effective-time-heartbeat", daemon=True).start()
