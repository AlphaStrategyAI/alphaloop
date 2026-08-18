from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence


ALLOWED_PROFILES = ("us-equity-daily", "crypto-daily")


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


@dataclass(frozen=True)
class ResearchSpec:
    spec_id: str
    hypothesis: Hypothesis
    success_criteria: SuccessCriteria
    seed: int
    time_budget_s: int
    cost_budget_usd: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ResearchSpec":
        hyp = payload["hypothesis"]
        crit = payload["success_criteria"]
        return cls(
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
        )


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
    payload = {
        "hypothesis": asdict(hypothesis),
        "success_criteria": asdict(criteria),
        "seed": seed,
        "time_budget_s": time_budget_s,
        "cost_budget_usd": cost_budget_usd,
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
    )
