from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Sequence

from .status import JobStatus, ResearchOutcome, derive_research_outcome


class IncompleteEvidenceError(ValueError):
    """Raised when a required hard gate is missing from the evidence set."""


class HardGateName(str, Enum):
    DSR = "dsr"
    WALK_FORWARD = "walk_forward"
    VS_RANDOM = "vs_random"
    VS_BUY_HOLD = "vs_buy_hold"
    VS_BENCHMARK = "vs_benchmark"
    DATA_CONSISTENCY = "data_consistency"


@dataclass(frozen=True)
class GateResult:
    name: HardGateName
    passed: bool
    detail: dict


@dataclass(frozen=True)
class GateEvidence:
    results: tuple[GateResult, ...]
    required: tuple[HardGateName, ...]

    @property
    def complete(self) -> bool:
        present = {row.name for row in self.results}
        return all(name in present for name in self.required)

    @property
    def all_passed(self) -> bool:
        if not self.required:
            return False
        if not self.complete:
            return False
        by_name = {row.name: row.passed for row in self.results}
        return all(by_name[name] for name in self.required)


def evaluate_hard_gates(
    required: Sequence[HardGateName],
    results: Iterable[GateResult],
) -> GateEvidence:
    if not required:
        raise IncompleteEvidenceError("required hard gates must not be empty")
    rows = tuple(results)
    seen: set[HardGateName] = set()
    for row in rows:
        if row.name in seen:
            raise ValueError(f"duplicate hard gate result: {row.name.value}")
        seen.add(row.name)
    present = {row.name for row in rows}
    missing = [name for name in required if name not in present]
    if missing:
        raise IncompleteEvidenceError(
            "missing hard gates: " + ", ".join(name.value for name in missing)
        )
    return GateEvidence(results=rows, required=tuple(required))


def outcome_from_evidence(job_status: JobStatus, evidence: GateEvidence) -> ResearchOutcome:
    return derive_research_outcome(
        job_status,
        evidence_complete=evidence.complete,
        all_gates_passed=evidence.all_passed,
    )
