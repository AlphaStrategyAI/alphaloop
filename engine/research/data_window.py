"""Cumulative implementation rounds M on a frozen data window (B2 / B5)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from engine.research.models import Research, RoundV2
from engine.verifiers import method_set_excluding_pit


@dataclass(frozen=True, slots=True)
class DataWindowKey:
    """Identity: locked universe symbols + simulation calendar window."""

    market: str
    symbols: tuple[str, ...]
    start: date
    end: date

    def serialize(self) -> str:
        return (
            f"{self.market}|{','.join(self.symbols)}|"
            f"{self.start.isoformat()}|{self.end.isoformat()}"
        )


def data_window_key_from_round(round_: RoundV2) -> DataWindowKey | None:
    attempt = round_.accepted_attempt
    if attempt.spec is None:
        return None
    simulation = attempt.simulation
    universe = attempt.spec.universe
    if simulation is None:
        return None
    start = getattr(simulation, "start", None)
    end = getattr(simulation, "end", None)
    if start is None or end is None:
        return None
    if isinstance(start, str):
        start = date.fromisoformat(start)
    if isinstance(end, str):
        end = date.fromisoformat(end)
    return DataWindowKey(
        market=universe.market.value,
        symbols=tuple(sorted(universe.symbols)),
        start=start,
        end=end,
    )


def anchor_data_window_key(research: Research) -> DataWindowKey | None:
    for version in reversed(research.versions):
        for round_ in reversed(version.rounds):
            key = data_window_key_from_round(round_)
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
            key = data_window_key_from_round(round_)
            if key == anchor:
                ordered.append((version.number, round_))
    return ordered


def cumulative_rounds_on_window(research: Research) -> int:
    return len(rounds_on_window_chronological(research))


def _verification_passed_round(round_: RoundV2, research: Research) -> bool:
    attempt = round_.accepted_attempt
    method_set = method_set_excluding_pit(
        research.brief.round1_methods.value or attempt.spec.method_set
    )
    if attempt.verification is None:
        return False
    return attempt.verification.passed_for(method_set)


def _failed_gate_ids(round_: RoundV2) -> tuple[str, ...]:
    verification = round_.accepted_attempt.verification
    if verification is None:
        return ()
    return tuple(item.verifier_id for item in verification.results if not item.passed)


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


def trial_tracking_for_view(research: Research) -> dict[str, Any]:
    anchor = anchor_data_window_key(research)
    return {
        "dataWindowKey": anchor.serialize() if anchor else None,
        "cumulativeRoundsOnWindow": cumulative_rounds_on_window(research),
    }
