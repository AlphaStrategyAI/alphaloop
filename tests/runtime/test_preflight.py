from __future__ import annotations

from alphaloop.contracts.research_spec import new_research_spec
from alphaloop.runtime.preflight import HOST_CONSTRAINT, preflight


def _spec(**overrides):
    payload = dict(
        statement="12-1 momentum works in US large caps net of costs",
        economic_logic="past winners continue",
        signal_mechanism="momentum_12_1",
        market_scope="AAPL, MSFT",
        market_profile="us-equity-daily",
        benchmark="SPY",
        hard_gates=("dsr", "walk_forward", "vs_benchmark"),
        seed=7,
        time_budget_s=3600,
        cost_budget_usd=5.0,
    )
    payload.update(overrides)
    return new_research_spec(**payload)


def test_host_constraint_text_is_locked():
    assert HOST_CONSTRAINT == (
        "The host must remain awake while a local worker is running. "
        "Closing the browser or terminal does not stop a job, but "
        "suspending or powering off the host stops computation."
    )


def test_ok_spec_includes_host_constraint(tmp_path):
    result = preflight(_spec(), tmp_path)
    assert result.ok is True
    assert result.errors == ()
    assert result.host_constraint == HOST_CONSTRAINT


def test_empty_hard_gates_rejected(tmp_path):
    result = preflight(_spec(hard_gates=()), tmp_path)
    assert result.ok is False
    assert any("hard gate" in err.lower() for err in result.errors)
    assert result.host_constraint == HOST_CONSTRAINT


def test_zero_time_budget_rejected(tmp_path):
    result = preflight(_spec(time_budget_s=0), tmp_path)
    assert result.ok is False
    assert any("time" in err.lower() for err in result.errors)


def test_nan_cost_budget_rejected(tmp_path):
    result = preflight(_spec(cost_budget_usd=float("nan")), tmp_path)
    assert result.ok is False
    assert any("cost" in err.lower() for err in result.errors)


def test_unknown_dsl_kind_rejected(tmp_path):
    result = preflight(_spec(signal_mechanism="12-1 momentum"), tmp_path)
    assert result.ok is False
    assert any("signal_mechanism" in err.lower() or "kind" in err.lower() for err in result.errors)
    assert result.host_constraint == HOST_CONSTRAINT


def test_data_dir_that_is_a_file_rejected(tmp_path):
    target = tmp_path / "blocked"
    target.write_text("not-a-directory", encoding="utf-8")
    result = preflight(_spec(), target)
    assert result.ok is False
    assert any("writ" in err.lower() or "data" in err.lower() for err in result.errors)
