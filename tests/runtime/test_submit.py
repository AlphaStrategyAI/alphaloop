from __future__ import annotations

import pytest

from alphaloop.contracts.research_spec import new_research_spec
from alphaloop.runtime.submit import spec_from_submit_payload
from tests.runtime.test_supervisor import _spec


def test_full_spec_dict_round_trips():
    spec = _spec()
    assert spec_from_submit_payload(spec.to_dict()) == spec


def test_nested_payload_without_spec_id_builds_research_spec():
    spec = _spec()
    payload = spec.to_dict()
    payload.pop("spec_id")
    built = spec_from_submit_payload(payload)
    assert built == spec
    assert built.spec_id == spec.spec_id


def test_flat_payload_without_spec_id_builds_research_spec():
    spec = _spec()
    payload = {
        "statement": spec.hypothesis.statement,
        "economic_logic": spec.hypothesis.economic_logic,
        "signal_mechanism": spec.hypothesis.signal_mechanism,
        "market_scope": spec.hypothesis.market_scope,
        "market_profile": spec.hypothesis.market_profile,
        "benchmark": spec.hypothesis.benchmark,
        "hard_gates": list(spec.success_criteria.hard_gates),
        "seed": spec.seed,
        "time_budget_s": spec.time_budget_s,
        "cost_budget_usd": spec.cost_budget_usd,
    }
    built = spec_from_submit_payload(payload)
    assert built.spec_id == spec.spec_id


def test_wrong_spec_id_still_rejected():
    payload = _spec().to_dict()
    payload["spec_id"] = "rs_" + "0" * 32
    with pytest.raises(ValueError, match="spec_id"):
        spec_from_submit_payload(payload)
