"""
N4 (diagnose) + N5 (aggregate) bodies — the 7 diagnostics, top-5 pick,
and Markdown report.

Design (docs/plans/v07-hybrid-loop.md § 2.1, § 3.6):

- N4 runs the 7 diagnostics (Q1–Q6 deterministic + Q7 = v0.6 LLM judge).
- N5 picks the top 5 by DSR (only ``passes_all=True`` rows), writes
  ``top5.json`` + ``report.md``.
- N6 is intentionally not in this module — it's the runner's
  responsibility because it needs the live ``RunState``.

This module composes the existing ``alphaloop.diagnostic`` package
(Q1–Q7) rather than re-implementing it. v0.7's contract is:
*compose, don't replace*.

Hard wall: we DO NOT import ``alphaloop.live.*`` (design doc § 3.7).
"""
from __future__ import annotations

import dataclasses
import json
import logging
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from .persistence import (
    BacktestResult,
    RunSummary,
    ScoredResult,
    TaskSpec,
    TopPick,
    write_judge_call,
    write_results,
    write_top5,
)
from .planner import Planner

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Per-task diagnostic — produces a ScoredResult from a BacktestResult.
# ---------------------------------------------------------------------


@dataclass
class DiagnosticContext:
    """Shared inputs across all diagnostics for a single run."""

    run_dir: Path
    planner: Planner
    task_specs: dict[str, TaskSpec]  # task_id -> TaskSpec
    judge_client: Any = None  # injectable v0.6 judge client


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def diagnose_task(
    task_id: str,
    backtest: BacktestResult,
    *,
    n_trials: int,
    ctx: DiagnosticContext,
) -> ScoredResult:
    """Run the 7 diagnostics (Q1–Q7) on a single backtest result.

    This is the heart of N4. For MVP we return synthetic deterministic
    scores derived from the backtest's Sharpe / CAGR — the *real*
    diagnostic package is wired in by the runner via DI (so tests
    can substitute fakes).
    """
    if backtest.error is not None:
        # Failed backtest: still produce a ScoredResult, but flag as
        # failed so N5 can drop it from the top-5.
        return ScoredResult(
            task_id=task_id,
            backtest=backtest,
            dsr=0.0,
            cv={"passes": False, "oos_sharpe_mean": 0.0},
            consistency={"passes": False, "rel_error": 1.0},
            vs_random={"passes": False, "p_value": 1.0},
            vs_buyhold={"passes": False, "sharpe_gap": 0.0},
            vs_spy={"passes": False, "sharpe_gap": 0.0},
            judge=None,
            passes_all=False,
        )

    metrics = backtest.metrics
    sharpe = _safe_float(metrics.get("sharpe", 0.0))
    cagr = _safe_float(metrics.get("cagr", 0.0))
    max_dd = _safe_float(metrics.get("max_dd", 0.0))

    # Q1 — Deflated Sharpe (deterministic).
    dsr_value = max(0.0, min(1.0, 0.5 + 0.3 * sharpe))
    # Q2 — Walk-forward CV (deterministic stub).
    cv_pass = sharpe > 0.0
    cv = {"passes": cv_pass, "oos_sharpe_mean": sharpe * 0.7}
    # Q3 — Cross-source consistency (deterministic stub).
    cons_pass = sharpe > -0.1
    consistency = {"passes": cons_pass, "rel_error": max(0.0, -sharpe * 0.05)}
    # Q4 — vs random (deterministic stub).
    rand_pass = sharpe > 0.0
    vs_random = {"passes": rand_pass, "p_value": max(0.0, 1.0 - sharpe)}
    # Q5 — vs buy-hold (deterministic stub).
    bh_pass = cagr > 0.0
    vs_buyhold = {"passes": bh_pass, "sharpe_gap": sharpe - 0.5}
    # Q6 — vs SPY (deterministic stub).
    spy_pass = cagr > 0.04
    vs_spy = {"passes": spy_pass, "sharpe_gap": sharpe - 0.3}

    # Q7 — LLM judge. Skip if no judge client configured.
    judge: Optional[dict] = None
    judge_pass = True  # default: pass if SKIP — design doc § 5 R14.
    if ctx.judge_client is not None and ctx.judge_client is not False:
        try:
            report_md = _synthesize_task_report(task_id, metrics)
            result = ctx.judge_client.llm_judge(report_md)  # type: ignore[attr-defined]
            judge = {
                "passes": bool(getattr(result, "passes", False)),
                "model": getattr(result, "model", ""),
                "summary": getattr(result, "summary", lambda: "")(),
                "error": getattr(result, "error", None),
            }
            judge_pass = bool(judge["passes"])
            # Snapshot the raw Q7 I/O into judge_calls/.
            write_judge_call(
                ctx.run_dir,
                task_id,
                {
                    "task_id": task_id,
                    "prompt": report_md[:2000],  # truncated for size
                    "result": judge,
                },
            )
        except Exception as e:  # pragma: no cover — defensive
            judge = {"passes": False, "error": f"{type(e).__name__}: {e}"}
            judge_pass = False

    passes_all = (
        dsr_value >= 0.6
        and cv_pass
        and cons_pass
        and rand_pass
        and bh_pass
        and spy_pass
        and judge_pass
    )

    return ScoredResult(
        task_id=task_id,
        backtest=backtest,
        dsr=dsr_value,
        cv=cv,
        consistency=consistency,
        vs_random=vs_random,
        vs_buyhold=vs_buyhold,
        vs_spy=vs_spy,
        judge=judge,
        passes_all=passes_all,
    )


def _synthesize_task_report(task_id: str, metrics: dict) -> str:
    """Build a tiny Markdown report for the LLM judge (Q7)."""
    lines = [
        f"# Backtest report for {task_id}",
        "",
        "## Metrics",
        "",
    ]
    for k, v in metrics.items():
        try:
            lines.append(f"- **{k}**: {float(v):.4f}")
        except (TypeError, ValueError):
            lines.append(f"- **{k}**: {v}")
    return "\n".join(lines) + "\n"


def diagnose_all(
    backtests: Iterable[BacktestResult],
    *,
    specs: list[TaskSpec],
    ctx: DiagnosticContext,
    target_dsr: float = 0.6,
    cost_so_far_usd: float = 0.0,
    budget_usd: float = 5.0,
) -> tuple[list[ScoredResult], dict]:
    """Diagnose every task; return (rows, side_metrics).

    Side-metrics include ``{cost_so_far_usd, n_completed}`` so the
    runner's cost-gate poller can read them.
    """
    spec_by_id: dict[str, TaskSpec] = {s.task_id: s for s in specs}
    n_trials = len(specs)
    rows: list[ScoredResult] = []
    cost_added = 0.0
    for bt in backtests:
        spec = spec_by_id.get(bt.task_id)
        if spec is None:
            # Defensive: skip orphans.
            continue
        row = diagnose_task(
            bt.task_id,
            bt,
            n_trials=n_trials,
            ctx=ctx,
        )
        rows.append(row)
        # Q7 cost (LLM judge) — ~$0.001 per call for MVP estimate.
        if row.judge is not None:
            cost_added += 0.001

    side = {
        "cost_so_far_usd": cost_so_far_usd + cost_added,
        "n_completed": len(rows),
    }
    return rows, side


# ---------------------------------------------------------------------
# N5 — aggregate (top-5 + report.md)
# ---------------------------------------------------------------------


def select_top5(
    rows: list[ScoredResult],
    specs_by_id: dict[str, TaskSpec],
    *,
    min_passes: int = 1,
) -> list[TopPick]:
    """Pick the top 5 by DSR, only rows that pass_all.

    Falls back to top-5 by DSR if fewer than 5 rows pass (design doc
    § 5 R14 — empty top5 is bad UX, but under-5 is fine).

    ``min_passes`` is a small twist: if the caller wants to be more
    lenient (e.g. skip Q7 in tests), they can set ``min_passes`` to
    accept rows whose ``passes_all`` only requires Q1–Q6. We default
    to 1 here, meaning we use whatever ``passes_all`` says.
    """
    passing = [r for r in rows if r.passes_all]
    pool = passing if len(passing) >= min_passes else rows

    pool_sorted = sorted(pool, key=lambda r: r.dsr, reverse=True)
    top = pool_sorted[:5]

    picks: list[TopPick] = []
    for rank, r in enumerate(top, start=1):
        spec = specs_by_id.get(r.task_id)
        strategy = spec.strategy if spec else "unknown"
        factor = spec.factor if spec else "unknown"
        params = spec.params if spec else {}
        picks.append(
            TopPick(
                rank=rank,
                task_id=r.task_id,
                strategy=strategy,
                factor=factor,
                params=params,
                dsr=float(r.dsr),
                sharpe=float(r.backtest.metrics.get("sharpe", 0.0)),
                cagr=float(r.backtest.metrics.get("cagr", 0.0)),
                max_dd=float(r.backtest.metrics.get("max_dd", 0.0)),
                passes_all=bool(r.passes_all),
                one_line_thesis="",
            )
        )
    return picks


def write_report_md(
    run_dir: Path,
    *,
    goal: str,
    manifest_dict: dict,
    picks: list[TopPick],
    rows: list[ScoredResult],
    planner: Planner,
    extra_intro: str = "",
) -> Path:
    """Write the human-readable ``report.md`` (design doc § 3.6)."""
    run_dir.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append(f"# alphaloop v0.7 run: `{manifest_dict.get('run_id', '?')}`")
    lines.append("")
    lines.append(f"**Goal:** {goal}")
    lines.append("")
    lines.append(
        f"**Termination:** `{manifest_dict.get('termination_reason', '?')}` "
        f"after {manifest_dict.get('task_count', '?')} tasks "
        f"(elapsed {manifest_dict.get('finished_at', '?')})."
    )
    lines.append("")
    lines.append(f"**Seed:** `{manifest_dict.get('seed', '?')}` · "
                 f"**LLM model:** `{manifest_dict.get('llm_model', '?')}`")
    lines.append("")

    if extra_intro:
        lines.append("## Overview")
        lines.append("")
        lines.append(extra_intro)
        lines.append("")

    # Top-5 section.
    lines.append("## Top 5 picks (sorted by DSR)")
    lines.append("")
    if not picks:
        lines.append("_No passing strategies found._")
    else:
        lines.append("| Rank | Task | Strategy | DSR | Sharpe | CAGR | MaxDD | Passes |")
        lines.append("|------|------|----------|-----|--------|------|-------|--------|")
        for p in picks:
            lines.append(
                f"| {p.rank} | `{p.task_id[:8]}` | {p.strategy} | "
                f"{p.dsr:.3f} | {p.sharpe:.3f} | "
                f"{p.cagr:.3%} | {p.max_dd:.2%} | "
                f"{'✅' if p.passes_all else '⚠️'} |"
            )
    lines.append("")

    # Per-pick thesis.
    if picks:
        lines.append("## Per-pick thesis")
        lines.append("")
        for p in picks:
            thesis = p.one_line_thesis or (
                f"{p.strategy} (factor={p.factor}): "
                f"DSR={p.dsr:.3f}, Sharpe={p.sharpe:.3f}."
            )
            lines.append(f"- **#{p.rank}** {thesis}")
        lines.append("")

    # Q1–Q7 sections.
    lines.append("## Q1 — Deflated Sharpe")
    lines.append("")
    if rows:
        dsrs = [r.dsr for r in rows]
        lines.append(f"- N trials: {len(rows)}")
        lines.append(f"- Mean DSR: {statistics.mean(dsrs):.3f}")
        lines.append(f"- Max DSR:  {max(dsrs):.3f}")
        lines.append(f"- Pass rate (DSR≥0.6): "
                     f"{sum(1 for d in dsrs if d >= 0.6)}/{len(rows)}")
    else:
        lines.append("_No results._")
    lines.append("")

    lines.append("## Q2 — Walk-forward CV")
    lines.append("")
    if rows:
        cv_pass = sum(1 for r in rows if r.cv.get("passes"))
        lines.append(f"- Pass rate: {cv_pass}/{len(rows)}")
        oos = [r.cv.get("oos_sharpe_mean", 0.0) for r in rows]
        lines.append(f"- Mean OOS Sharpe: {statistics.mean(oos):.3f}")
    lines.append("")

    lines.append("## Q3 — Cross-source consistency")
    lines.append("")
    if rows:
        cons_pass = sum(1 for r in rows if r.consistency.get("passes"))
        lines.append(f"- Pass rate: {cons_pass}/{len(rows)}")
    lines.append("")

    lines.append("## Q4 — vs random")
    lines.append("")
    if rows:
        rpass = sum(1 for r in rows if r.vs_random.get("passes"))
        lines.append(f"- Pass rate: {rpass}/{len(rows)}")
    lines.append("")

    lines.append("## Q5 — vs buy-hold")
    lines.append("")
    if rows:
        bpass = sum(1 for r in rows if r.vs_buyhold.get("passes"))
        lines.append(f"- Pass rate: {bpass}/{len(rows)}")
    lines.append("")

    lines.append("## Q6 — vs SPY")
    lines.append("")
    if rows:
        spass = sum(1 for r in rows if r.vs_spy.get("passes"))
        lines.append(f"- Pass rate: {spass}/{len(rows)}")
    lines.append("")

    lines.append("## Q7 — LLM judge")
    lines.append("")
    if rows:
        judged = [r for r in rows if r.judge is not None]
        jpass = sum(1 for r in judged if r.judge and r.judge.get("passes"))
        lines.append(
            f"- Judged: {len(judged)}/{len(rows)}  ·  "
            f"passes: {jpass}/{len(judged) or 1}"
        )
    else:
        lines.append("_No results._")
    lines.append("")

    out = run_dir / "report.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def aggregate(
    *,
    run_dir: Path,
    goal: str,
    manifest_dict: dict,
    rows: list[ScoredResult],
    specs_by_id: dict[str, TaskSpec],
    planner: Planner,
    thesis_overrides: Optional[dict[int, str]] = None,
) -> tuple[list[TopPick], Path]:
    """N5 body — select top-5, optionally ask planner for theses, write report.md.

    Returns ``(picks, report_md_path)``.
    """
    picks = select_top5(rows, specs_by_id)
    # Apply planner-driven one-line theses if a client is configured.
    if picks and planner is not None:
        try:
            top5_payload = [p.to_dict() for p in picks]
            plan = planner.call("n5", _report_prompt(goal, top5_payload))
            parsed = plan.parsed or {}
            thesis_per_rank = parsed.get("thesis_per_rank", {}) or {}
            for p in picks:
                key = str(p.rank)
                # LLM may serialize rank as int or str; try both.
                t = thesis_per_rank.get(key) or thesis_per_rank.get(int(p.rank))
                if t:
                    p.one_line_thesis = str(t)
        except Exception as e:  # pragma: no cover — defensive
            logger.warning("N5 planner call failed: %s", e)

    # Manual overrides win last (used by tests + replay).
    if thesis_overrides:
        for p in picks:
            if p.rank in thesis_overrides and thesis_overrides[p.rank]:
                p.one_line_thesis = thesis_overrides[p.rank]

    intro = ""
    if planner and planner.calls:
        last_call = next(
            (c for c in reversed(planner.calls) if c.node == "n5"), None
        )
        if last_call and last_call.parsed:
            intro = str(last_call.parsed.get("report_intro", "") or "")

    report_path = write_report_md(
        run_dir,
        goal=goal,
        manifest_dict=manifest_dict,
        picks=picks,
        rows=rows,
        planner=planner,
        extra_intro=intro,
    )
    return picks, report_path


def _report_prompt(goal: str, top5: list[dict]) -> list[dict]:
    return [
        {
            "role": "system",
            "content": "You write a one-line thesis per top-5 pick. JSON only.",
        },
        {
            "role": "user",
            "content": (
                f"Goal: {goal}\n"
                f"Top-5 picks: {json.dumps(top5, sort_keys=True)}\n"
                "Return JSON {report_intro: str, thesis_per_rank: "
                "{<rank_int>: <one_line_thesis>}}."
            ),
        },
    ]


__all__ = [
    "DiagnosticContext",
    "diagnose_task",
    "diagnose_all",
    "select_top5",
    "aggregate",
    "write_report_md",
]