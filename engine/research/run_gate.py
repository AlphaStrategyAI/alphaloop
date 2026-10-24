"""Single predicate for whether Confirm-to-run may start.

The desktop enables Run only when this gate is runnable. ``confirm_run`` raises
the same code. A stored per-source acknowledgement counts: Yahoo's timestamp
does not satisfy AkShare, and removing one market does not keep the other
market's missing acknowledgement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from engine.research.a1_copy import DATA_SOURCE_UNBOUND, STRATEGY_FAMILY_NOT_RUNNABLE
from engine.research.family_intent import classify_thesis
from engine.research.models import Research
from engine.research.source_acknowledgement import acknowledged_at, is_unlicensed_source
from engine.research.thesis_scope import MEAN_REVERSION_ACK_REQUIRED, MEAN_REVERSION_ONLY_NOTICE
from engine.research.universe_pool import pool_resolvable
from engine.research.universe_validation import (
    reject_market_mismatches,
    reject_mixed_markets,
    reject_pending_symbol_asks,
    reject_source_market_mismatch,
    reject_unresolved_symbols,
    reject_unspecified_market,
)
from engine.research.user_errors import UserFacingError


@dataclass(frozen=True, slots=True)
class RunGate:
    runnable: bool
    code: str | None = None
    message: str | None = None
    params: dict[str, Any] = field(default_factory=dict)


def _from_error(error: UserFacingError) -> RunGate:
    return RunGate(False, error.code, error.message, dict(error.params))


def evaluate_run_gate(
    research: Research,
    *,
    data_source_id: str,
    unlicensed_acknowledged: bool,
    settings_path: Path,
) -> RunGate:
    """Return the first reason Run must stay disabled, or a runnable gate.

    Order: universe shape, then a family the spec says cannot run, then the
    price source and its stored acknowledgement. A checkbox acknowledgement
    satisfies only the source on this call. A timestamp already stored for
    that source satisfies it with no checkbox.
    """
    for check in (
        reject_unspecified_market,
        reject_market_mismatches,
        reject_unresolved_symbols,
        reject_pending_symbol_asks,
        reject_mixed_markets,
    ):
        try:
            check(research)
        except UserFacingError as error:
            return _from_error(error)

    thesis = str(research.brief.thesis.value or "")
    hit = classify_thesis(thesis)
    repick = research.repicked_family
    if repick == "mean_reversion":
        pass
    elif repick:
        if not research.mean_reversion_adopted:
            return RunGate(False, MEAN_REVERSION_ACK_REQUIRED, MEAN_REVERSION_ONLY_NOTICE)
    elif hit.outcome == "block":
        return RunGate(False, "STRATEGY_FAMILY_NOT_RUNNABLE", STRATEGY_FAMILY_NOT_RUNNABLE)
    elif hit.outcome == "disclose" and not research.mean_reversion_adopted:
        return RunGate(False, MEAN_REVERSION_ACK_REQUIRED, MEAN_REVERSION_ONLY_NOTICE)

    source = data_source_id.strip()
    if pool_resolvable(research) and not source:
        return RunGate(False, "DATA_SOURCE_UNBOUND", DATA_SOURCE_UNBOUND)
    if source and is_unlicensed_source(source):
        stored = acknowledged_at(source, settings_path)
        if stored is None and not unlicensed_acknowledged:
            return RunGate(
                False,
                "UNLICENSED_SOURCE_UNACKNOWLEDGED",
                "使用未经许可的数据前，请确认仅用于个人研究。",
            )
    if source:
        try:
            reject_source_market_mismatch(research, source, settings_path)
        except UserFacingError as error:
            return _from_error(error)
    return RunGate(True)
