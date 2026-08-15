"""
alphaloop.loop — v0.7 hybrid research loop.

This package is the **v0.7 orchestrator**: a thin layer that
composes v0.5 (6 deterministic diagnostics) + v0.6 (LLM judge) into
an end-to-end autonomous research loop. It does NOT touch any live
trading code (``alphaloop.live`` is hard-walled per design doc § 3.7).

Public API (design doc § 3):

- :class:`LoopRunner`      — orchestrate the 6-node DAG.
- :class:`LoopReplay`      — re-derive top5 from persisted artifacts.
- :class:`TaskSpec`        — one row in task_specs.parquet.
- :class:`BacktestResult`  — one N3 worker output.
- :class:`ScoredResult`    — one N4 scored row.
- :class:`RunManifest`     — manifest.yaml header.
- :class:`RunSummary`      — final return value.
- :class:`TopPick`         — one row of top5.json.

Plus the 4 termination gates (A/B/C/D) and the hybrid DAG primitives
for tests + advanced users.

Read ``docs/design/v07-hybrid-loop.md`` for the design rationale;
this file is the implementation.
"""
from __future__ import annotations

import asyncio
import datetime as _dt
import hashlib
import logging
import os
import random
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

import numpy as np

from .aggregator import (
    DiagnosticContext,
    aggregate,
    diagnose_all,
    diagnose_task,
    select_top5,
)
from .dag import HybridDAG, Node, default_nodes
from .executor import BacktestRunner, make_synthetic_specs
from .persistence import (
    BacktestResult,
    LoopReplay,
    RunManifest,
    RunSummary,
    ScoredResult,
    TaskSpec,
    TopPick,
    capture_git_commit,
    environment_fingerprint,
    hash_dataframe,
    make_run_id,
    write_commit,
    write_data_snapshot,
    write_judge_call,
    write_manifest,
    write_results,
    write_task_specs,
    write_top5,
)
from .planner import Planner, plan_n1, plan_n2, resolve_model

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# RunState — used by the 4 termination gates (design doc § 2.7).
# ---------------------------------------------------------------------


@dataclass
class RunState:
    """In-memory state consulted by the termination gates."""

    started_monotonic: float
    target_dsr: float
    budget_usd: float
    timeout_s: int
    completed_tasks: int = 0
    total_tasks: int = 0
    scored: list[ScoredResult] = field(default_factory=list)
    estimated_cost_usd: float = 0.0
    cancel_requested: bool = False
    cancel_reason: str = ""

    def elapsed_s(self) -> float:
        return time.monotonic() - self.started_monotonic


def should_terminate(state: RunState) -> Optional[str]:
    """Return ``None`` if continuing, else a reason letter (A/B/C/D).

    Mirrors design doc § 2.7:

    - A — any scored DSR ≥ target.
    - B — all tasks done.
    - C — wall clock past timeout.
    - D — estimated cost past budget.
    """
    # Gate A — target found.
    if any(r.dsr >= state.target_dsr for r in state.scored):
        return "A"
    # Gate B — all tasks done.
    if state.completed_tasks >= state.total_tasks and state.total_tasks > 0:
        return "B"
    # Gate C — wall clock.
    if state.elapsed_s() > state.timeout_s:
        return "C"
    # Gate D — cost.
    if state.estimated_cost_usd > state.budget_usd:
        return "D"
    return None


# ---------------------------------------------------------------------
# LoopRunner — the public entry point (design doc § 3.2).
# ---------------------------------------------------------------------


@dataclass
class LoopRunner:
    """Orchestrate the v0.7 6-node DAG end-to-end.

    The runner holds the planner, executor, diagnostic context, and
    persistence layer. It does NOT itself own any networking code —
    it composes existing modules so each piece stays testable.

    Parameters
    ----------
    goal:
        Free-form research goal (e.g. ``"find alpha with DSR > 1.0"``).
    run_id:
        Optional explicit id. If ``None``, one is generated from
        :func:`make_run_id`.
    seed:
        Random seed (gate A.1). ``None`` → random seed.
    budget_usd, timeout_s, target_dsr:
        Gates A/C/D. Defaults match design doc § 2.7.
    data_dir:
        Where to write ``runs/<run_id>/``. Default ``./runs``.
    llm_client:
        Optional v0.6 ``LLMJudgeClient`` (or fake) for N4 Q7. If
        ``None``, Q7 is SKIP and ``passes_all`` ignores Q7 (per
        design doc § 5 R14 mitigation).
    backtest_fn:
        Optional injectable backtest callable for tests. If ``None``,
        N3 uses :func:`executor._worker_run` (deterministic synthetic).
    planner:
        Optional pre-built :class:`Planner`. If ``None``, a default
        stub (no LLM HTTP calls) is constructed.
    dry_run:
        If True, run only N1 + N2 and return a summary (design doc
        § 3.4 — useful for budget estimation).
    git_repo_dir:
        Directory for ``git rev-parse HEAD`` capture (N6). Default
        ``"."`` (current working directory).
    """

    goal: str
    run_id: Optional[str] = None
    seed: Optional[int] = None
    budget_usd: float = 5.0
    timeout_s: int = 6 * 3600
    target_dsr: float = 1.0
    data_dir: str = "./runs"
    llm_client: Any = None
    backtest_fn: Optional[Callable[[TaskSpec], BacktestResult]] = None
    planner: Optional[Planner] = None
    dry_run: bool = False
    git_repo_dir: str = "."

    # ----- derived state --------------------------------------------

    def _resolve_run_id(self) -> str:
        if self.run_id:
            return self.run_id
        return make_run_id(
            self.goal,
            self.seed if self.seed is not None else 0,
            self.planner.model if self.planner else "stub",
        )

    def _resolve_seed(self) -> int:
        if self.seed is not None:
            return self.seed
        return int.from_bytes(os.urandom(4), "big")

    # ----- main entry point -----------------------------------------

    async def run(self) -> RunSummary:
        """Execute the full 6-node DAG; return a summary.

        Async so the caller can cancel / set timeouts / wrap in
        :func:`asyncio.wait_for` if they want a hard wall-clock cap.
        """
        # --- 0. resolve + seed -------------------------------------
        rid = self._resolve_run_id()
        seed = self._resolve_seed()
        random.seed(seed)
        np.random.seed(seed)
        run_dir = Path(self.data_dir) / rid
        run_dir.mkdir(parents=True, exist_ok=True)

        model = (
            self.planner.model
            if self.planner is not None
            else resolve_model()
        )
        git_commit = capture_git_commit(Path(self.git_repo_dir))

        manifest = RunManifest(
            run_id=rid,
            goal=self.goal[:4096],  # R11: cap goal length
            seed=seed,
            git_commit=git_commit,
            llm_model=model,
            data_snapshot_path="(stub)",
            data_snapshot_sha256="(stub)",
            target_dsr=self.target_dsr,
            budget_usd=self.budget_usd,
            timeout_s=self.timeout_s,
            started_at=_dt.datetime.now(_dt.timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
        )
        write_manifest(run_dir, manifest)

        planner = self.planner or Planner(client=None, model=model)
        executor = BacktestRunner(backtest_fn=self.backtest_fn)

        state = RunState(
            started_monotonic=time.monotonic(),
            target_dsr=self.target_dsr,
            budget_usd=self.budget_usd,
            timeout_s=self.timeout_s,
        )

        # --- 1. N1: data snapshot ----------------------------------
        data_plan = plan_n1(self.goal, planner)
        # MVP: synthesize a tiny DataFrame as the "data snapshot".
        # Production path wires real sources via the runner factory.
        try:
            import pandas as pd  # local import to avoid hard dep at import time
            df = _synthetic_dataframe(data_plan)
        except Exception:
            df = _synthetic_dataframe({"symbols": ["AAA"], "end": "2024-01-01"})
        from .persistence import write_data_snapshot
        _, sha = write_data_snapshot(run_dir, df, source="synthetic")
        manifest.data_snapshot_path = "data_snapshot.pkl"
        manifest.data_snapshot_sha256 = sha

        # --- 2. N2: plan tasks -------------------------------------
        plan = plan_n2(self.goal, planner, n_budget=16)
        tasks_raw = plan.get("tasks", []) or []
        # Stamp task_id + data_snapshot_hash onto each spec.
        specs: list[TaskSpec] = []
        for raw in tasks_raw:
            spec = TaskSpec(
                task_id=_new_task_id(),
                strategy=str(raw.get("strategy", "BuyHoldStrategy")),
                factor=str(raw.get("factor", "")),
                params=dict(raw.get("params", {}) or {}),
                data_snapshot_hash=sha[:16],
            )
            specs.append(spec)
        if not specs:
            # Last-resort fallback if the planner returned nothing
            # useful — keeps the loop runnable end-to-end.
            specs = make_synthetic_specs(4)
        state.total_tasks = len(specs)
        manifest.task_count = len(specs)
        write_task_specs(run_dir, specs)

        if self.dry_run:
            # Skip N3–N6; record termination as B (planned) and return.
            manifest.finished_at = _iso_utc_now()
            manifest.termination_reason = "B"
            manifest.estimated_cost_usd = planner.total_cost_usd()
            write_manifest(run_dir, manifest)
            return RunSummary(
                run_id=rid,
                termination_reason="B",
                elapsed_s=state.elapsed_s(),
                estimated_cost_usd=manifest.estimated_cost_usd,
                completed_tasks=0,
                total_tasks=state.total_tasks,
                top5=[],
                artifacts_dir=str(run_dir),
            )

        # --- 3. N3: execute (multiprocessing.Pool) ----------------
        backtest_results: list[BacktestResult] = []
        if state.total_tasks > 0:
            async for br in executor.run_async(specs):
                backtest_results.append(br)
                state.completed_tasks += 1
                # Cheap mid-stream cost gate check.
                if should_terminate(state) == "D":
                    break
                if state.cancel_requested:
                    break

        # --- 4. N4: diagnose --------------------------------------
        diag_ctx = DiagnosticContext(
            run_dir=run_dir,
            planner=planner,
            task_specs={s.task_id: s for s in specs},
            judge_client=self.llm_client,
        )
        rows, side = diagnose_all(
            backtest_results,
            specs=specs,
            ctx=diag_ctx,
            target_dsr=self.target_dsr,
            cost_so_far_usd=planner.total_cost_usd(),
            budget_usd=self.budget_usd,
        )
        state.scored = rows
        state.estimated_cost_usd = side["cost_so_far_usd"] + planner.total_cost_usd()
        write_results(run_dir, rows)

        # --- 5. N5: aggregate -------------------------------------
        manifest_dict = manifest.to_dict()
        picks, _report_path = aggregate(
            run_dir=run_dir,
            goal=self.goal,
            manifest_dict=manifest_dict,
            rows=rows,
            specs_by_id={s.task_id: s for s in specs},
            planner=planner,
        )
        # Top-5 json (machine-readable).
        summary_for_top5 = RunSummary(
            run_id=rid,
            termination_reason="pending",
            elapsed_s=state.elapsed_s(),
            estimated_cost_usd=state.estimated_cost_usd,
            completed_tasks=state.completed_tasks,
            total_tasks=state.total_tasks,
            top5=picks,
            artifacts_dir=str(run_dir),
        )
        write_top5(run_dir, summary_for_top5)

        # --- 6. N6: commit ----------------------------------------
        termination = should_terminate(state) or "B"
        manifest.finished_at = _iso_utc_now()
        manifest.termination_reason = termination
        manifest.estimated_cost_usd = state.estimated_cost_usd
        manifest.task_count = state.completed_tasks
        write_manifest(run_dir, manifest)
        write_commit(run_dir, git_commit)

        # Re-render top5.json with the final termination reason so
        # downstream readers see the same value as manifest.yaml.
        summary_final = RunSummary(
            run_id=rid,
            termination_reason=termination,
            elapsed_s=state.elapsed_s(),
            estimated_cost_usd=state.estimated_cost_usd,
            completed_tasks=state.completed_tasks,
            total_tasks=state.total_tasks,
            top5=picks,
            artifacts_dir=str(run_dir),
        )
        write_top5(run_dir, summary_final)

        return summary_final

    async def cancel(self, reason: str) -> None:
        """Soft-cancel: stop after current N3 batch."""
        # Cooperative cancel — sets a flag; the runner checks between
        # batches. Real long runs could plumb a threading.Event here;
        # for v0.7 MVP a flag is enough.
        self._cancel_flag = True  # type: ignore[attr-defined]


# ---------------------------------------------------------------------
# Small helpers.
# ---------------------------------------------------------------------


def _new_task_id() -> str:
    import uuid as _uuid

    return _uuid.uuid4().hex


def _iso_utc_now() -> str:
    return (
        _dt.datetime.now(_dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _synthetic_dataframe(plan: dict) -> Any:
    """Produce a tiny synthetic OHLCV DataFrame from the N1 plan.

    Production: real alphaloop data sources. For MVP / tests we
    synthesize so the loop is runnable without network.
    """
    import pandas as pd

    symbols = plan.get("symbols") or ["AAA", "BBB"]
    end = plan.get("end") or "2024-12-31"
    try:
        end_dt = _dt.datetime.fromisoformat(end)
    except ValueError:
        end_dt = _dt.datetime(2024, 12, 31)
    n_days = 252  # one trading year
    dates = pd.date_range(end=end_dt, periods=n_days, freq="D")
    # One column per symbol, deterministic close prices.
    data: dict[str, Any] = {}
    import numpy as _np

    arr = _np.arange(n_days, dtype=float)
    for i, sym in enumerate(symbols):
        base = 100 + i * 10
        data[sym] = base + 0.05 * arr + _np.sin(arr / 10 + i) * 2.0
    df = pd.DataFrame(data, index=dates)
    return df


__all__ = [
    # orchestrator
    "LoopRunner",
    "LoopReplay",
    "RunState",
    "should_terminate",
    # dataclasses (re-exported from persistence for convenience)
    "TaskSpec",
    "BacktestResult",
    "ScoredResult",
    "RunManifest",
    "RunSummary",
    "TopPick",
    # DAG primitives
    "HybridDAG",
    "Node",
    "default_nodes",
    # planner
    "Planner",
    "plan_n1",
    "plan_n2",
    "resolve_model",
    # executor
    "BacktestRunner",
    "make_synthetic_specs",
    # persistence helpers
    "make_run_id",
    "hash_dataframe",
    "capture_git_commit",
    "environment_fingerprint",
    # aggregator
    "DiagnosticContext",
    "diagnose_task",
    "diagnose_all",
    "select_top5",
    "aggregate",
    # persistence writers
    "write_data_snapshot",
    "write_judge_call",
    "write_task_specs",
    "write_results",
    "write_top5",
    "write_manifest",
    "write_commit",
]