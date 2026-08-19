from __future__ import annotations

from typing import Any, Mapping, Optional

from alphaloop.contracts.artifacts import DatasetRef
from alphaloop.contracts.research_spec import ResearchSpec, new_research_spec


def _optional_dataset(raw_ds: Any) -> Optional[DatasetRef]:
    if isinstance(raw_ds, dict) and raw_ds.get("dataset_id") and raw_ds.get("sha256"):
        return DatasetRef(
            dataset_id=str(raw_ds["dataset_id"]), sha256=str(raw_ds["sha256"])
        )
    return None


def spec_from_submit_payload(payload: Mapping[str, Any]) -> ResearchSpec:
    if not isinstance(payload, Mapping):
        raise ValueError("research spec must be a mapping")
    if "spec_id" in payload:
        return ResearchSpec.from_dict(payload)
    if "hypothesis" in payload:
        hyp = payload["hypothesis"]
        crit = payload["success_criteria"]
        return new_research_spec(
            statement=str(hyp["statement"]),
            economic_logic=str(hyp["economic_logic"]),
            signal_mechanism=str(hyp["signal_mechanism"]),
            market_scope=str(hyp["market_scope"]),
            market_profile=str(hyp["market_profile"]),
            benchmark=str(hyp["benchmark"]),
            hard_gates=tuple(crit["hard_gates"]),
            seed=int(payload["seed"]),
            time_budget_s=int(payload["time_budget_s"]),
            cost_budget_usd=float(payload["cost_budget_usd"]),
            dataset=_optional_dataset(payload.get("dataset")),
        )
    return new_research_spec(
        statement=str(payload["statement"]),
        economic_logic=str(payload["economic_logic"]),
        signal_mechanism=str(payload["signal_mechanism"]),
        market_scope=str(payload["market_scope"]),
        market_profile=str(payload["market_profile"]),
        benchmark=str(payload["benchmark"]),
        hard_gates=tuple(payload["hard_gates"]),
        seed=int(payload["seed"]),
        time_budget_s=int(payload["time_budget_s"]),
        cost_budget_usd=float(payload["cost_budget_usd"]),
        dataset=_optional_dataset(payload.get("dataset")),
    )
