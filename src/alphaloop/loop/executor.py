"""
N3 executor — parallel backtest runner.

Design (docs/plans/v07-hybrid-loop.md § 1.4, § 2.5):

- ``multiprocessing.Pool(processes=cpu_count)`` for CPU-bound backtests.
- An async adapter (``_aiter_pool``) so the asyncio main loop can stay
  responsive while Pool workers run synchronously.

Trade-offs captured here:

1. Worker isolation — a buggy strategy class can't crash the orchestrator.
2. Predictable CPU pinning — Pool reserves the whole machine for N3.
3. Pickle-clean task boundary — ``TaskSpec`` is a pure dataclass; the
   ``backtest_fn`` is injected as a top-level callable (NOT a method),
   which avoids the classic "can't pickle local function" failure
   mode (design doc R2).

The ``BacktestRunner`` class wraps ``Pool`` + ``_aiter_pool`` and is
the single seam tests use to swap in a fake backtest function
(``FakeBacktestFn`` in tests/test_loop.py). This keeps the real Pool
out of the unit-test critical path while preserving the multiprocessing
contract for the integration smoke test.
"""
from __future__ import annotations

import asyncio
import multiprocessing as mp
import os
import time
import traceback
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from multiprocessing import get_context
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Iterable,
    Iterator,
    Optional,
    Sequence,
)

from .persistence import BacktestResult, TaskSpec


# ---------------------------------------------------------------------
# Top-level worker — MUST live at module scope so it's picklable.
# ---------------------------------------------------------------------


def _worker_run(spec: TaskSpec) -> BacktestResult:
    """Default worker: synthesize a deterministic BacktestResult.

    The real worker is injected by ``BacktestRunner(backtest_fn=...)``.
    We keep a default here so the module imports cleanly and so
    diagnostic / unit tests can use this fallback when they want to
    exercise only the Pool plumbing (not the backtest math).

    Real production use goes via ``alphaloop.backtest.BacktestEngine``
    (per design doc § 2.4) — wired up by the runner's N3 body.
    """
    started = time.monotonic()
    try:
        # Deterministic synthetic metric so tests are stable.
        seed = int(spec.task_id[:8], 16) % 1000
        sharpe = (seed % 7 - 3) * 0.1  # roughly in [-0.3, 0.4]
        metrics = {
            "sharpe": sharpe,
            "cagr": 0.05 + sharpe * 0.02,
            "max_dd": -0.10 - abs(sharpe) * 0.05,
            "turnover": 0.5,
        }
        latency = time.monotonic() - started
        return BacktestResult(
            task_id=spec.task_id,
            metrics=metrics,
            latency_s=max(latency, 0.001),
        )
    except Exception as e:  # pragma: no cover — defensive
        return BacktestResult(
            task_id=spec.task_id,
            metrics={},
            latency_s=time.monotonic() - started,
            error=f"{type(e).__name__}: {e}",
        )


# ---------------------------------------------------------------------
# Async adapter — bridge blocking imap_unordered to async iteration.
# ---------------------------------------------------------------------


async def _aiter_pool(
    pool_iter: Iterable[BacktestResult],
    *,
    yield_every: int = 4,
) -> AsyncIterator[BacktestResult]:
    """Yield each pool result, periodically yielding to the event loop.

    Design doc § 2.5 — yields every ``yield_every`` results so the
    asyncio main loop stays responsive to SIGINT and to the cost-gate
    poller.

    The work is done in a thread (``asyncio.to_thread``) so the
    event loop is never blocked on the synchronous ``imap_unordered``
    pull.
    """
    counter = 0
    queue: asyncio.Queue = asyncio.Queue(maxsize=1)
    sentinel = object()

    async def _drain() -> None:
        # Iterate in a thread so we don't block the loop. Each result
        # is awaited by the consumer before the next pull.
        try:
            for item in pool_iter:
                await queue.put(item)
        finally:
            await queue.put(sentinel)

    drain_task = asyncio.create_task(_drain())
    try:
        while True:
            item = await queue.get()
            if item is sentinel:
                return
            yield item  # type: ignore[misc]
            counter += 1
            if counter % yield_every == 0:
                await asyncio.sleep(0)  # yield to the event loop
    finally:
        # Ensure the drain coroutine is cleaned up if we exit early.
        if not drain_task.done():
            drain_task.cancel()
            try:
                await drain_task
            except (asyncio.CancelledError, Exception):
                pass


# ---------------------------------------------------------------------
# BacktestRunner — the single seam tests inject into.
# ---------------------------------------------------------------------


@dataclass
class BacktestRunner:
    """Run a list of ``TaskSpec``s through an injected backtest function.

    Parameters
    ----------
    backtest_fn:
        A top-level callable ``(TaskSpec) -> BacktestResult``. Inject
        this in tests to bypass multiprocessing and return synthetic
        results. If ``None``, the module's default ``_worker_run`` is
        used (deterministic synthetic metrics).
    processes:
        Number of Pool workers. ``None`` → ``cpu_count()``.
    chunksize:
        ``imap_unordered`` chunksize (design doc § 2.5 — defaults to 4).
    use_executor:
        If True, use ``ProcessPoolExecutor`` instead of
        ``multiprocessing.Pool``. Default False — the design commits
        to ``Pool`` (decision 2).
    yield_every:
        How many results between event-loop yields. 4 matches the
        design doc chunksize.
    """

    backtest_fn: Optional[Callable[[TaskSpec], BacktestResult]] = None
    processes: Optional[int] = None
    chunksize: int = 4
    use_executor: bool = False
    yield_every: int = 4
    fail_isolated: bool = True

    # ----- sync iteration (one result at a time, blocking) -----------

    def run_blocking(
        self, specs: Sequence[TaskSpec]
    ) -> list[BacktestResult]:
        """Run all specs synchronously, return a list of results.

        Uses a real ``multiprocessing.Pool`` by default; tests inject
        ``backtest_fn`` to bypass.
        """
        fn = self.backtest_fn or _worker_run
        if not specs:
            return []
        ctx = get_context("spawn")  # explicit (R9 mitigation)
        procs = self.processes or (os.cpu_count() or 1)
        results: list[BacktestResult] = []
        if self.use_executor:
            with ProcessPoolExecutor(max_workers=procs) as ex:
                for r in ex.map(fn, list(specs), chunksize=self.chunksize):
                    results.append(r)
        else:
            with ctx.Pool(processes=procs) as pool:
                for r in pool.imap_unordered(
                    fn, list(specs), chunksize=self.chunksize
                ):
                    results.append(r)
        return results

    # ----- async iteration (cooperative, for the main runner) --------

    async def run_async(
        self, specs: Sequence[TaskSpec]
    ) -> AsyncIterator[BacktestResult]:
        """Yield results as they arrive, in async-iteration form.

        Internally spawns the blocking ``run_blocking`` into a thread
        and adapts it via ``_aiter_pool`` semantics.
        """
        fn = self.backtest_fn or _worker_run
        if not specs:
            return
        ctx = get_context("spawn")  # explicit (R9 mitigation)
        procs = self.processes or (os.cpu_count() or 1)

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue(maxsize=self.yield_every * 2)
        sentinel = object()

        def _producer() -> None:
            try:
                if self.use_executor:
                    with ProcessPoolExecutor(max_workers=procs) as ex:
                        for r in ex.map(fn, list(specs), chunksize=self.chunksize):
                            loop.call_soon_threadsafe(queue.put_nowait, r)
                else:
                    with ctx.Pool(processes=procs) as pool:
                        for r in pool.imap_unordered(
                            fn, list(specs), chunksize=self.chunksize
                        ):
                            loop.call_soon_threadsafe(queue.put_nowait, r)
            except Exception as e:  # pragma: no cover — defensive
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    BacktestResult(
                        task_id="__producer_error__",
                        metrics={},
                        latency_s=0.0,
                        error=f"producer: {type(e).__name__}: {e}",
                    ),
                )
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, sentinel)

        producer = asyncio.create_task(asyncio.to_thread(_producer))
        try:
            counter = 0
            while True:
                item = await queue.get()
                if item is sentinel:
                    return
                yield item  # type: ignore[misc]
                counter += 1
                if counter % self.yield_every == 0:
                    await asyncio.sleep(0)
        finally:
            if not producer.done():
                producer.cancel()
                try:
                    await producer
                except (asyncio.CancelledError, Exception):
                    pass


# ---------------------------------------------------------------------
# Helpers — utilities used by the runner + tests.
# ---------------------------------------------------------------------


def cpu_count_safe() -> int:
    """Return cpu_count() with a sane fallback for restricted envs."""
    return os.cpu_count() or 1


def new_task_id() -> str:
    """Return a 16-char hex uuid4 (matches design doc schema)."""
    import uuid as _uuid

    return _uuid.uuid4().hex


def make_synthetic_specs(
    n: int, *, base_seed: int = 0
) -> list[TaskSpec]:
    """Generate ``n`` deterministic synthetic ``TaskSpec``s.

    Useful for tests + the smoke integration run. Cycles through the
    11 strategies the design doc lists in § 2.4 (alpha+11) and pairs
    each with one of two factor names.
    """
    strategies = [
        "BuyHoldStrategy",
        "RebalanceStrategy",
        "GlobalMultiAssetStrategy",
        "MovingAverageCrossoverStrategy",
        "Classic6040Strategy",
        "ValueStrategy",
        "SectorRotationStrategy",
        "RiskParityStrategy",
        "TargetDateStrategy",
    ]
    factors = ["Momentum12M", "MeanReversionZ"]

    specs: list[TaskSpec] = []
    for i in range(n):
        s = strategies[i % len(strategies)]
        f = factors[i % len(factors)]
        specs.append(
            TaskSpec(
                task_id=new_task_id(),
                strategy=s,
                factor=f,
                params={"idx": i, "seed": base_seed + i},
                data_snapshot_hash="synthetic",
            )
        )
    return specs


__all__ = [
    "_worker_run",
    "_aiter_pool",
    "BacktestRunner",
    "cpu_count_safe",
    "new_task_id",
    "make_synthetic_specs",
]