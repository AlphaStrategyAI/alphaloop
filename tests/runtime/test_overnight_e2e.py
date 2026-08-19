from __future__ import annotations

import json

import pandas as pd
import yaml

from alphaloop.contracts.artifacts import RunLayout, DatasetRef, hash_bytes
from alphaloop.contracts.research_spec import new_research_spec
from alphaloop.contracts.status import ResearchOutcome
from alphaloop.runtime.worker import run_worker


def _prices_frame():
    idx = pd.bdate_range("2018-01-01", periods=260)
    return pd.DataFrame(
        {
            "AAPL": 100.0 + pd.Series(range(260), index=idx, dtype=float),
            "MSFT": 100.0 + pd.Series(range(260), index=idx, dtype=float),
            "SPY": 100.0 + pd.Series(range(260), index=idx, dtype=float),
        }
    )


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
    run_id = "j_e2e"
    layout = RunLayout(tmp_path / run_id)
    layout.run_dir.mkdir()
    layout.research_spec.write_text(yaml.safe_dump(spec.to_dict()), encoding="utf-8")
    assert run_worker(run_id, tmp_path) == 0
    assert layout.manifest.is_file()
    assert layout.trial_ledger.is_file()
    assert layout.candidates.is_file()
    assert layout.report.is_file()
    report = layout.report.read_text(encoding="utf-8")
    assert any(token in report for token in ("FOUND", "NO_EVIDENCE", "INCONCLUSIVE"))
    assert "target found" not in report
    first = (layout.evidence / "gates.json").read_bytes() if (layout.evidence / "gates.json").is_file() else None
    layout2 = RunLayout(tmp_path / "j_e2e_b")
    layout2.run_dir.mkdir()
    layout2.research_spec.write_text(yaml.safe_dump(spec.to_dict()), encoding="utf-8")
    assert run_worker("j_e2e_b", tmp_path) == 0
    if first is not None:
        second = (layout2.evidence / "gates.json").read_bytes()
        assert first == second
