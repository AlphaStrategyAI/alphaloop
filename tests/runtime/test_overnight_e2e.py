from __future__ import annotations

import json

import pandas as pd

from alphaloop.contracts.artifacts import RunLayout, DatasetRef, hash_bytes
from alphaloop.contracts.gates import HardGateName, evidence_from_dict
from alphaloop.contracts.research_spec import new_research_spec
from alphaloop.runtime.api import JobAPI
from alphaloop.runtime.store import JobStore
from alphaloop.runtime.supervisor import Supervisor
from alphaloop.runtime.worker import run_worker
from tests.runtime.test_supervisor import FakeWorker


def _prices_frame():
    idx = pd.bdate_range("2018-01-01", periods=260)
    return pd.DataFrame(
        {
            "AAPL": 100.0 + pd.Series(range(260), index=idx, dtype=float),
            "MSFT": 100.0 + pd.Series(range(260), index=idx, dtype=float),
            "SPY": 100.0 + pd.Series(range(260), index=idx, dtype=float),
        }
    )


def _api(tmp_path) -> JobAPI:
    store = JobStore(tmp_path / "state.db", tmp_path)
    worker = FakeWorker()
    sup = Supervisor(store, tmp_path, worker, heartbeat_timeout_s=60.0)
    return JobAPI(store, sup, tmp_path)


def test_shortened_overnight_writes_required_artifacts(tmp_path):
    frame = _prices_frame()
    parquet = tmp_path / "datasets" / "ds_e2e" / "prices.parquet"
    parquet.parent.mkdir(parents=True)
    frame.to_parquet(parquet)
    digest = hash_bytes(parquet.read_bytes())
    spec = new_research_spec(
        statement="12-1 momentum works",
        economic_logic="past winners continue",
        signal_mechanism="momentum_12_1",
        market_scope="AAPL, MSFT",
        market_profile="us-equity-daily",
        benchmark="SPY",
        hard_gates=("dsr",),
        seed=7,
        time_budget_s=30,
        cost_budget_usd=1.0,
        dataset=DatasetRef(dataset_id="ds_e2e", sha256=digest),
    )
    api = _api(tmp_path)
    created = api.create_run(spec)
    run_id = created["run_id"]
    assert api.supervisor.worker.spawned == []
    layout = RunLayout(tmp_path / run_id)
    assert layout.research_spec.is_file()
    assert run_worker(run_id, tmp_path) == 0
    assert layout.manifest.is_file()
    assert layout.trial_ledger.is_file()
    assert layout.candidates.is_file()
    assert layout.report.is_file()
    report = layout.report.read_text(encoding="utf-8")
    assert any(token in report for token in ("FOUND", "NO_EVIDENCE", "INCONCLUSIVE"))
    assert "target found" not in report
    first = (layout.evidence / "gates.json").read_bytes() if (layout.evidence / "gates.json").is_file() else None
    created2 = api.create_run(spec)
    layout2 = RunLayout(tmp_path / created2["run_id"])
    assert run_worker(created2["run_id"], tmp_path) == 0
    if first is not None:
        second = (layout2.evidence / "gates.json").read_bytes()
        assert first == second


def test_macd_walk_forward_records_regime_stable(tmp_path):
    frame = _prices_frame()
    parquet = tmp_path / "datasets" / "ds_macd" / "prices.parquet"
    parquet.parent.mkdir(parents=True)
    frame.to_parquet(parquet)
    digest = hash_bytes(parquet.read_bytes())
    spec = new_research_spec(
        statement="MACD crossover works in US large caps net of costs",
        economic_logic="trend continuation after EMA spread confirmation",
        signal_mechanism="macd",
        market_scope="AAPL, MSFT",
        market_profile="us-equity-daily",
        benchmark="SPY",
        hard_gates=("walk_forward",),
        seed=7,
        time_budget_s=30,
        cost_budget_usd=1.0,
        dataset=DatasetRef(dataset_id="ds_macd", sha256=digest),
    )
    api = _api(tmp_path)
    created = api.create_run(spec)
    run_id = created["run_id"]
    layout = RunLayout(tmp_path / run_id)
    assert run_worker(run_id, tmp_path) == 0
    gates_path = layout.evidence / "gates.json"
    assert gates_path.is_file()
    evidence = evidence_from_dict(json.loads(gates_path.read_text(encoding="utf-8")))
    by_name = {row.name: row for row in evidence.results}
    assert HardGateName.WALK_FORWARD in by_name
    assert "regime_stable" in by_name[HardGateName.WALK_FORWARD].detail
    assert isinstance(by_name[HardGateName.WALK_FORWARD].detail["regime_stable"], bool)


def test_bollinger_overnight_records_method_trials(tmp_path):
    frame = _prices_frame()
    parquet = tmp_path / "datasets" / "ds_bb" / "prices.parquet"
    parquet.parent.mkdir(parents=True)
    frame.to_parquet(parquet)
    digest = hash_bytes(parquet.read_bytes())
    spec = new_research_spec(
        statement="Bollinger mean reversion works in US large caps net of costs",
        economic_logic="prices revert after stretching below the lower band",
        signal_mechanism="bollinger_zscore",
        market_scope="AAPL, MSFT",
        market_profile="us-equity-daily",
        benchmark="SPY",
        hard_gates=("dsr",),
        seed=7,
        time_budget_s=30,
        cost_budget_usd=1.0,
        dataset=DatasetRef(dataset_id="ds_bb", sha256=digest),
    )
    api = _api(tmp_path)
    created = api.create_run(spec)
    run_id = created["run_id"]
    layout = RunLayout(tmp_path / run_id)
    assert run_worker(run_id, tmp_path) == 0
    rows = [
        json.loads(line)
        for line in layout.trial_ledger.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows
    assert all(row.get("kind") == "bollinger_zscore" for row in rows)


def test_ohlr_overnight_records_method_trials(tmp_path):
    frame = _prices_frame()
    parquet = tmp_path / "datasets" / "ds_ohlr" / "prices.parquet"
    parquet.parent.mkdir(parents=True)
    frame.to_parquet(parquet)
    digest = hash_bytes(parquet.read_bytes())
    spec = new_research_spec(
        statement="Williams percent R oversold longs work in US large caps net of costs",
        economic_logic="closes near the N-bar low revert",
        signal_mechanism="ohlr_4_pct",
        market_scope="AAPL, MSFT",
        market_profile="us-equity-daily",
        benchmark="SPY",
        hard_gates=("dsr",),
        seed=7,
        time_budget_s=30,
        cost_budget_usd=1.0,
        dataset=DatasetRef(dataset_id="ds_ohlr", sha256=digest),
    )
    api = _api(tmp_path)
    created = api.create_run(spec)
    run_id = created["run_id"]
    layout = RunLayout(tmp_path / run_id)
    assert run_worker(run_id, tmp_path) == 0
    rows = [
        json.loads(line)
        for line in layout.trial_ledger.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows
    assert all(row.get("kind") == "ohlr_4_pct" for row in rows)


def test_pairs_overnight_records_method_trials(tmp_path):
    frame = _prices_frame()
    parquet = tmp_path / "datasets" / "ds_pairs" / "prices.parquet"
    parquet.parent.mkdir(parents=True)
    frame.to_parquet(parquet)
    digest = hash_bytes(parquet.read_bytes())
    spec = new_research_spec(
        statement="Pairs spread mean reversion works in US large caps net of costs",
        economic_logic="close substitutes revert after the log spread stretches",
        signal_mechanism="pairs_spread",
        market_scope="AAPL, MSFT",
        market_profile="us-equity-daily",
        benchmark="SPY",
        hard_gates=("dsr",),
        seed=7,
        time_budget_s=30,
        cost_budget_usd=1.0,
        dataset=DatasetRef(dataset_id="ds_pairs", sha256=digest),
    )
    api = _api(tmp_path)
    created = api.create_run(spec)
    run_id = created["run_id"]
    layout = RunLayout(tmp_path / run_id)
    assert run_worker(run_id, tmp_path) == 0
    rows = [
        json.loads(line)
        for line in layout.trial_ledger.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows
    assert all(row.get("kind") == "pairs_spread" for row in rows)


def test_atr_overnight_records_method_trials(tmp_path):
    frame = _prices_frame()
    parquet = tmp_path / "datasets" / "ds_atr" / "prices.parquet"
    parquet.parent.mkdir(parents=True)
    frame.to_parquet(parquet)
    digest = hash_bytes(parquet.read_bytes())
    spec = new_research_spec(
        statement="ATR buffered Donchian breakouts work in US large caps net of costs",
        economic_logic="new highs after a volatility buffer continue",
        signal_mechanism="atr_breakout",
        market_scope="AAPL, MSFT",
        market_profile="us-equity-daily",
        benchmark="SPY",
        hard_gates=("dsr",),
        seed=7,
        time_budget_s=30,
        cost_budget_usd=1.0,
        dataset=DatasetRef(dataset_id="ds_atr", sha256=digest),
    )
    api = _api(tmp_path)
    created = api.create_run(spec)
    run_id = created["run_id"]
    layout = RunLayout(tmp_path / run_id)
    assert run_worker(run_id, tmp_path) == 0
    rows = [
        json.loads(line)
        for line in layout.trial_ledger.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows
    assert all(row.get("kind") == "atr_breakout" for row in rows)
