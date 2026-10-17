"""Cumulative implementation rounds M on a frozen data window (B2 / B5)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, TYPE_CHECKING

from engine.research.models import Research, RoundV2
from engine.research.planned_data_window import DEFAULT_DATA_SOURCE_ID
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
        data_source=research.data_source_id or DEFAULT_DATA_SOURCE_ID,
        start=research.data_window_start,
        end=research.data_window_end,
    )


def data_window_key_from_round(round_: RoundV2, research: Research) -> DataWindowKey | None:
    attempt = round_.accepted_attempt
    simulation = attempt.simulation
    if simulation is None:
        return data_window_key_from_research(research)
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
        data_source=research.data_source_id or DEFAULT_DATA_SOURCE_ID,
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
                "paramChanges": [list(item) for item in impl.param_changes],
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


def trial_tracking_for_view(
    research: Research,
    store: SQLiteStore | None = None,
) -> dict[str, Any]:
    anchor = anchor_data_window_key(research)
    research_m = cumulative_rounds_on_window(research)
    window_all = research_m
    if store is not None and anchor is not None:
        window_all = window_cumulative_all_researches(store, anchor)
    from engine.research.honest_stop import trial_budget_view

    budget = trial_budget_view(research)
    version_number = research.current_version_number or 1
    return {
        "dataWindowKey": anchor.serialize() if anchor else None,
        "cumulativeRoundsOnWindow": research_m,
        "windowCumulativeRoundsAllResearches": window_all,
        "versionTrialLabel": f"本版本 {budget.used}/{budget.budget} 轮",
        "researchCumulativeLabel": f"本研究累计 {research_m} 轮",
        "windowCumulativeLabel": f"本窗口所有研究累计 {window_all} 轮",
    }
