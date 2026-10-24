"""Cumulative implementation rounds M on a frozen data window (B2 / B5)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, TYPE_CHECKING

from engine.research.display_names import param_label
from engine.research.window_copy import (
    all_researches_on_window_label,
    research_on_window_label,
    version_trial_label,
)
from engine.research.models import Research, RoundV2
from engine.verifiers import method_set_excluding_pit

if TYPE_CHECKING:
    from engine.research.store import SQLiteStore


@dataclass(frozen=True, slots=True)
class DataWindowKey:
    """Identity: symbol-list version + simulation calendar + data source."""

    symbol_list_version: str
    data_source: str
    start: date
    end: date

    def serialize(self) -> str:
        return (
            f"{self.symbol_list_version}|{self.data_source}|"
            f"{self.start.isoformat()}|{self.end.isoformat()}"
        )


def data_window_key_from_research(research: Research) -> DataWindowKey | None:
    if research.data_window_start is None or research.data_window_end is None:
        return None
    version = research.symbol_list_version or ""
    return DataWindowKey(
        symbol_list_version=version,
        data_source=research.data_source_id or "unset",
        start=research.data_window_start,
        end=research.data_window_end,
    )


def data_window_key_from_round(round_: RoundV2, research: Research) -> DataWindowKey | None:
    """Count a round on the research's pinned window when one exists.

    The confirm-time key (end = the day the run was confirmed) is what
    ``increment_window_round_count`` uses. The last backtest bar is often an
    earlier session, so keying the round off ``simulation.end`` never matches
    that anchor and the exported cumulative M stays 0.
    """
    pinned = data_window_key_from_research(research)
    if pinned is not None:
        return pinned
    attempt = round_.accepted_attempt
    simulation = attempt.simulation
    if simulation is None:
        return None
    start = getattr(simulation, "start", None)
    end = getattr(simulation, "end", None)
    if start is None or end is None:
        return data_window_key_from_research(research)
    if isinstance(start, str):
        start = date.fromisoformat(start)
    if isinstance(end, str):
        end = date.fromisoformat(end)
    version = research.symbol_list_version or ""
    if attempt.spec is not None and attempt.spec.universe.symbol_list_version:
        version = attempt.spec.universe.symbol_list_version
    return DataWindowKey(
        symbol_list_version=version,
        data_source=research.data_source_id or "unset",
        start=start,
        end=end,
    )


def anchor_data_window_key(research: Research) -> DataWindowKey | None:
    pinned = data_window_key_from_research(research)
    if pinned is not None:
        return pinned
    for version in reversed(research.versions):
        for round_ in reversed(version.rounds):
            key = data_window_key_from_round(round_, research)
            if key is not None:
                return key
    return None


def rounds_on_window_chronological(research: Research) -> list[tuple[int, RoundV2]]:
    anchor = anchor_data_window_key(research)
    if anchor is None:
        return []
    ordered: list[tuple[int, RoundV2]] = []
    for version in research.versions:
        for round_ in version.rounds:
            key = data_window_key_from_round(round_, research)
            if key == anchor:
                ordered.append((version.number, round_))
    return ordered


def cumulative_rounds_on_window(research: Research) -> int:
    return len(rounds_on_window_chronological(research))


def window_cumulative_all_researches(store: SQLiteStore, key: DataWindowKey) -> int:
    return store.window_round_count(key.serialize())


def _verification_passed_round(round_: RoundV2, research: Research) -> bool:
    attempt = round_.accepted_attempt
    method_set = method_set_excluding_pit(
        research.brief.round1_methods.value or attempt.spec.method_set
    )
    if attempt.verification is None:
        return False
    return attempt.verification.passed_for(method_set)


def _failed_gate_ids(round_: RoundV2) -> tuple[str, ...]:
    from engine.research.methods import format_verifier_ids

    verification = round_.accepted_attempt.verification
    if verification is None:
        return ()
    raw = tuple(item.verifier_id for item in verification.results if not item.passed)
    return format_verifier_ids(raw)


def late_pass_presentation(research: Research) -> dict[str, Any] | None:
    if research.status.value not in {"completed", "running"}:
        pass
    ordered = rounds_on_window_chronological(research)
    if not ordered:
        return None
    m = len(ordered)
    _, concluding = ordered[-1]
    if not _verification_passed_round(concluding, research):
        return None
    version_round_number = concluding.number
    if version_round_number == 1 and m == 1:
        return None
    prior_records = []
    for index, (version_number, round_) in enumerate(ordered[:-1], start=1):
        if _verification_passed_round(round_, research):
            continue
        impl = round_.implementation_delta
        prior_records.append(
            {
                "roundId": round_.round_id,
                "versionNumber": version_number,
                "roundNumber": round_.number,
                "cumulativeRoundOnWindow": index,
                "verificationPassed": _verification_passed_round(round_, research),
                "failedGateIds": list(_failed_gate_ids(round_)),
                "paramChanges": [
                    [param_label(param), str(before), str(after)]
                    for param, before, after in impl.param_changes
                ],
                "modelChanges": list(impl.model_changes),
            }
        )
    return {
        "show": True,
        "tone": "verification",
        "cumulativeRoundsOnWindow": m,
        "conclusionRoundId": concluding.round_id,
        "priorFailureRecords": prior_records,
    }


def disclosure_rounds_on_window(
    research: Research,
    store: SQLiteStore | None = None,
) -> int:
    """Canonical window M for user disclosure (B2/B5): global count when store has it."""
    anchor = anchor_data_window_key(research)
    research_m = cumulative_rounds_on_window(research)
    if store is not None and anchor is not None:
        return max(research_m, window_cumulative_all_researches(store, anchor))
    return research_m


def trial_tracking_for_view(
    research: Research,
    store: SQLiteStore | None = None,
) -> dict[str, Any]:
    anchor = anchor_data_window_key(research)
    research_m = cumulative_rounds_on_window(research)
    window_all = research_m
    if store is not None and anchor is not None:
        window_all = window_cumulative_all_researches(store, anchor)
    disclosure_m = disclosure_rounds_on_window(research, store)
    from engine.research.honest_stop import trial_budget_view

    budget = trial_budget_view(research)
    return {
        "cumulativeRoundsOnWindow": disclosure_m,
        "researchRoundsOnWindow": research_m,
        "windowCumulativeRoundsAllResearches": window_all,
        "versionTrialLabel": version_trial_label(budget.used, budget.budget),
        "researchCumulativeLabel": research_on_window_label(research_m),
        "windowCumulativeLabel": all_researches_on_window_label(disclosure_m),
        "workbenchHeaderSummary": all_researches_on_window_label(disclosure_m),
    }
