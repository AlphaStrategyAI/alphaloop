"""Exploration and holdout visibility for one research.

PR2 freezes the split, caps probes at the exploration end, and records the
one-shot claim. Later batches read only the exploration panel and render the
grade on cards and packages.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from engine.research.models import EvidencePolicy, Research
from engine.research.symbol_pool import pool_by_version, pool_final_grade


def authorize_evidence_split(
    research: Research,
    *,
    explore_end: date,
    holdout_start: date,
    holdout_end: date,
    isolation_days: int = 0,
    mode: str = "adaptive",
) -> Research:
    policy = EvidencePolicy(
        mode=mode,
        explore_end=explore_end,
        holdout_start=holdout_start,
        holdout_end=holdout_end,
        isolation_days=isolation_days,
        sealed=True,
    )
    return replace(research, evidence_policy=policy)


def bounded_probe_end(research: Research, end: date) -> date | None:
    """Latest date a price probe may request.

    ``None`` means the split is not fixed yet, so the caller shows the static
    pool and does not ask a provider for bars.
    """
    policy = research.evidence_policy
    if policy is None:
        return end
    if policy.explore_end is None:
        return None
    if policy.sealed:
        return min(end, policy.explore_end)
    return end


def evidence_grade(research: Research) -> tuple[str, str]:
    """``(grade, reason)``. Legacy researches keep their original inspection scope."""
    policy = research.evidence_policy
    if policy is None:
        return ("legacy", "")
    if policy.mode == "exploratory" or policy.explore_end is None:
        return ("exploratory", "未锁定未见行情，只交研究记录")
    pool = pool_by_version(research.symbol_list_version) if research.symbol_list_version else None
    grade, reason = pool_final_grade(pool, policy.explore_end)
    if grade != "final":
        return ("exploratory", reason)
    if policy.sealed or not policy.final_receipt:
        return ("exploratory", "保留段尚未开封，或还没有一次性评价回执")
    return ("final", "")


def strategy_pack_block_reason(research: Research) -> str | None:
    grade, reason = evidence_grade(research)
    if grade == "legacy" or grade == "final":
        return None
    return reason or "当前证据等级不能交策略包"


def evidence_grade_view(research: Research) -> dict[str, str]:
    grade, reason = evidence_grade(research)
    policy = research.evidence_policy
    return {
        "grade": grade,
        "reason": reason,
        "sealed": "true" if policy is None or policy.sealed else "false",
        "exploreEnd": "" if policy is None or policy.explore_end is None else policy.explore_end.isoformat(),
        "holdoutEnd": "" if policy is None or policy.holdout_end is None else policy.holdout_end.isoformat(),
    }
