from collections.abc import Callable
from dataclasses import dataclass, replace

from engine.research.models import Research, ResearchStatus


@dataclass(slots=True)
class TimeBudget:
    monotonic: Callable[[], float]
    _started: float | None = None

    def begin(self, status: ResearchStatus) -> None:
        if status is not ResearchStatus.RUNNING:
            self._started = None
            return
        if self._started is None:
            self._started = self.monotonic()

    def finish(self, research: Research) -> Research:
        if self._started is None:
            self._started = None
            return research
        elapsed = max(0.0, self.monotonic() - self._started)
        self._started = None
        return replace(research, effective_seconds=research.effective_seconds + elapsed)
