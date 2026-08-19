from __future__ import annotations

import dataclasses

import pytest

from alphaloop.contracts.artifacts import DatasetRef
from alphaloop.contracts.research_spec import (
    Hypothesis,
    ResearchSpec,
    SuccessCriteria,
    new_research_spec,
)


def _spec() -> ResearchSpec:
    return new_research_spec(
        statement="12-1 momentum works in US large caps net of costs",
        economic_logic="past winners continue",
        signal_mechanism="12-1 momentum",
        market_scope="US large-cap equities",
        market_profile="us-equity-daily",
        benchmark="SPY",
        hard_gates=("dsr", "walk_forward", "vs_benchmark"),
        seed=7,
        time_budget_s=3600,
        cost_budget_usd=5.0,
    )


def test_spec_is_frozen():
    spec = _spec()
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.seed = 8  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.hypothesis.signal_mechanism = "mean-reversion"  # type: ignore[misc]


def test_round_trip_yaml_dict_preserves_fields():
    spec = _spec()
    again = ResearchSpec.from_dict(spec.to_dict())
    assert again == spec
    assert again.hypothesis.market_profile == "us-equity-daily"


def test_from_dict_rejects_spec_id_that_does_not_match_payload():
    payload = _spec().to_dict()
    payload["spec_id"] = "rs_" + "0" * 32

    with pytest.raises(ValueError, match="spec_id"):
        ResearchSpec.from_dict(payload)


def test_new_spec_ids_are_stable_for_same_payload_and_seed():
    a = _spec()
    b = _spec()
    assert a.spec_id == b.spec_id


def test_existing_spec_id_unchanged_without_dataset():
    spec = _spec()
    again = new_research_spec(
        statement="12-1 momentum works in US large caps net of costs",
        economic_logic="past winners continue",
        signal_mechanism="12-1 momentum",
        market_scope="US large-cap equities",
        market_profile="us-equity-daily",
        benchmark="SPY",
        hard_gates=("dsr", "walk_forward", "vs_benchmark"),
        seed=7,
        time_budget_s=3600,
        cost_budget_usd=5.0,
    )
    assert spec.spec_id == again.spec_id
    assert getattr(spec, "dataset", None) is None


def test_dataset_changes_spec_id_and_round_trips():
    ref = DatasetRef(dataset_id="ds_fixture", sha256="a" * 64)
    with_ds = new_research_spec(
        statement="12-1 momentum works in US large caps net of costs",
        economic_logic="past winners continue",
        signal_mechanism="12-1 momentum",
        market_scope="US large-cap equities",
        market_profile="us-equity-daily",
        benchmark="SPY",
        hard_gates=("dsr", "walk_forward", "vs_benchmark"),
        seed=7,
        time_budget_s=3600,
        cost_budget_usd=5.0,
        dataset=ref,
    )
    assert with_ds.dataset == ref
    assert with_ds.spec_id != _spec().spec_id
    assert ResearchSpec.from_dict(with_ds.to_dict()) == with_ds


def test_hard_gates_reject_llm_judge():
    with pytest.raises(ValueError, match="llm_judge"):
        new_research_spec(
            statement="test",
            economic_logic="test",
            signal_mechanism="test",
            market_scope="test",
            market_profile="us-equity-daily",
            benchmark="SPY",
            hard_gates=("llm_judge",),
            seed=1,
            time_budget_s=60,
            cost_budget_usd=1.0,
        )
