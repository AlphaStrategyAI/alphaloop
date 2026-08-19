from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Optional, Sequence

from .artifacts import DatasetRef
from .gates import HardGateName

ALLOWED_PROFILES = ("us-equity-daily", "crypto-daily")


def _validate_hard_gate_names(names: Sequence[str]) -> tuple[str, ...]:
    validated: list[str] = []
    for name in names:
        try:
            HardGateName(name)
        except ValueError as exc:
            raise ValueError(f"unsupported hard gate: {name}") from exc
        validated.append(name)
    return tuple(validated)


@dataclass(frozen=True)
class Hypothesis:
    statement: str
    economic_logic: str
    signal_mechanism: str
    market_scope: str
    market_profile: str
    benchmark: str

    def __post_init__(self) -> None:
        if self.market_profile not in ALLOWED_PROFILES:
            raise ValueError(f"unsupported market_profile: {self.market_profile}")


@dataclass(frozen=True)
class SuccessCriteria:
    hard_gates: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "hard_gates", _validate_hard_gate_names(self.hard_gates))


@dataclass(frozen=True)
class ResearchSpec:
    spec_id: str
    hypothesis: Hypothesis
    success_criteria: SuccessCriteria
    seed: int
    time_budget_s: int
    cost_budget_usd: float
    dataset: Optional[DatasetRef] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ResearchSpec":
        hyp = payload["hypothesis"]
        crit = payload["success_criteria"]
        raw_ds = payload.get("dataset")
        dataset = None
        if isinstance(raw_ds, dict) and raw_ds.get("dataset_id") and raw_ds.get("sha256"):
            dataset = DatasetRef(
                dataset_id=str(raw_ds["dataset_id"]), sha256=str(raw_ds["sha256"])
            )
        spec = cls(
            spec_id=str(payload["spec_id"]),
            hypothesis=Hypothesis(
                statement=str(hyp["statement"]),
                economic_logic=str(hyp["economic_logic"]),
                signal_mechanism=str(hyp["signal_mechanism"]),
                market_scope=str(hyp["market_scope"]),
                market_profile=str(hyp["market_profile"]),
                benchmark=str(hyp["benchmark"]),
            ),
            success_criteria=SuccessCriteria(
                hard_gates=tuple(crit["hard_gates"]),
            ),
            seed=int(payload["seed"]),
            time_budget_s=int(payload["time_budget_s"]),
            cost_budget_usd=float(payload["cost_budget_usd"]),
            dataset=dataset,
        )
        expected = new_research_spec(
            statement=spec.hypothesis.statement,
            economic_logic=spec.hypothesis.economic_logic,
            signal_mechanism=spec.hypothesis.signal_mechanism,
            market_scope=spec.hypothesis.market_scope,
            market_profile=spec.hypothesis.market_profile,
            benchmark=spec.hypothesis.benchmark,
            hard_gates=spec.success_criteria.hard_gates,
            seed=spec.seed,
            time_budget_s=spec.time_budget_s,
            cost_budget_usd=spec.cost_budget_usd,
            dataset=spec.dataset,
        )
        if spec.spec_id != expected.spec_id:
            raise ValueError(
                f"spec_id does not match payload: expected {expected.spec_id}"
            )
        return spec


def new_research_spec(
    *,
    statement: str,
    economic_logic: str,
    signal_mechanism: str,
    market_scope: str,
    market_profile: str,
    benchmark: str,
    hard_gates: Sequence[str],
    seed: int,
    time_budget_s: int,
    cost_budget_usd: float,
    dataset: Optional[DatasetRef] = None,
) -> ResearchSpec:
    hypothesis = Hypothesis(
        statement=statement,
        economic_logic=economic_logic,
        signal_mechanism=signal_mechanism,
        market_scope=market_scope,
        market_profile=market_profile,
        benchmark=benchmark,
    )
    criteria = SuccessCriteria(hard_gates=tuple(hard_gates))
    payload: dict[str, Any] = {
        "hypothesis": asdict(hypothesis),
        "success_criteria": asdict(criteria),
        "seed": seed,
        "time_budget_s": time_budget_s,
        "cost_budget_usd": cost_budget_usd,
    }
    if dataset is not None:
        payload["dataset"] = {
            "dataset_id": dataset.dataset_id,
            "sha256": dataset.sha256,
        }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return ResearchSpec(
        spec_id="rs_" + digest[:32],
        hypothesis=hypothesis,
        success_criteria=criteria,
        seed=seed,
        time_budget_s=time_budget_s,
        cost_budget_usd=cost_budget_usd,
        dataset=dataset,
    )
