from __future__ import annotations

import json

import pytest

from alphaloop.contracts.gates import (
    GateResult,
    HardGateName,
    evidence_to_dict,
    evaluate_hard_gates,
)
from alphaloop.contracts.status import ResearchOutcome
from alphaloop.runtime.morning import (
    EXPORT_NO_ALPHA,
    STOP_REASON_ALL_GATES_PASSED,
    STOP_REASON_HARD_GATE_FAILED,
    STOP_REASON_INCOMPLETE_EVIDENCE,
    format_export_handoff,
    format_status_verdict,
    morning_view,
    replay_view,
)
from alphaloop.runtime.store import JobStore
from tests.runtime.test_supervisor import _spec


def _gates_for(spec, *, fail_first: bool = False):
    required = tuple(HardGateName(name) for name in spec.success_criteria.hard_gates)
    rows = []
    for i, name in enumerate(required):
        ok = not (fail_first and i == 0)
        rows.append(GateResult(name=name, passed=ok, detail={}))
    return evaluate_hard_gates(required, tuple(rows))


def test_missing_gates_is_inconclusive(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(_spec())
    done = store.complete_from_artifacts(job.run_id)
    view = morning_view(done, tmp_path)
    assert view["research_outcome"] == ResearchOutcome.INCONCLUSIVE.value
    assert view["evidence"] is None
    assert view["stop_reason"] == STOP_REASON_INCOMPLETE_EVIDENCE
    assert view["funnel"]["dominant_failures"] == []
    assert view["funnel"]["dominant_failure_labels"] == []
    assert view["queued_hypotheses"] == []
    assert view["primary_evidence"] == "no sealed gates.json"


def test_passing_gates_found(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(_spec())
    evidence = _gates_for(job.spec)
    evidence_dir = tmp_path / job.run_id / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "gates.json").write_text(json.dumps(evidence_to_dict(evidence)))
    done = store.complete_from_artifacts(job.run_id)
    view = morning_view(done, tmp_path)
    assert view["research_outcome"] == ResearchOutcome.FOUND.value
    assert view["stop_reason"] == STOP_REASON_ALL_GATES_PASSED
    assert view["evidence"]["all_passed"] is True
    assert view["funnel"]["dominant_failures"] == []
    assert view["funnel"]["dominant_failure_labels"] == []
    assert view["hypothesis"]["signal_mechanism"] == "momentum_12_1"
    assert view["time_budget_s"] == job.spec.time_budget_s
    assert view["cost_budget_usd"] == job.spec.cost_budget_usd
    assert "dataset" in view
    assert view["qualifying_candidates"] == [
        {
            "trial_id": "gates.json",
            "kind": None,
            "kind_label": None,
            "parameters": {},
        }
    ]
    assert view["primary_evidence"] == "all required hard gates passed"


def test_failed_gate_is_no_evidence(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(_spec())
    evidence = _gates_for(job.spec, fail_first=True)
    evidence_dir = tmp_path / job.run_id / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "gates.json").write_text(json.dumps(evidence_to_dict(evidence)))
    done = store.complete_from_artifacts(job.run_id)
    view = morning_view(done, tmp_path)
    assert view["research_outcome"] == ResearchOutcome.NO_EVIDENCE.value
    assert view["stop_reason"] == STOP_REASON_HARD_GATE_FAILED
    assert view["funnel"]["dominant_failures"] == [job.spec.success_criteria.hard_gates[0]]
    assert view["funnel"]["dominant_failure_labels"] == ["dsr — Deflated Sharpe Ratio"]
    assert view["qualifying_candidates"] == []
    assert view["primary_evidence"] == "dsr — Deflated Sharpe Ratio failed"


def test_corrupt_gates_does_not_claim_found(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(_spec())
    evidence_dir = tmp_path / job.run_id / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "gates.json").write_text("{not-json")
    done = store.complete_from_artifacts(job.run_id)
    view = morning_view(done, tmp_path)
    assert view["research_outcome"] != ResearchOutcome.FOUND.value
    assert view["evidence"] is None


def test_revisions_and_queued_hypotheses(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(_spec())
    run_dir = tmp_path / job.run_id
    (run_dir / "trial-ledger.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"trial_id": "c_1", "revision": "none", "parameters": {}}),
                json.dumps(
                    {
                        "trial_id": "c_2",
                        "revision": "method",
                        "kind": "momentum_12_1",
                        "parameters": {"window": 21},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "recommendations.json").write_text(
        json.dumps({"queued_hypotheses": [{"statement": "try mean reversion"}]}),
        encoding="utf-8",
    )
    view = morning_view(store.get(job.run_id), tmp_path)
    assert [row["trial_id"] for row in view["revisions"]] == ["c_2"]
    assert view["revisions"][0]["revision"] == "method"
    assert view["revisions"][0]["kind_label"] == "momentum_12_1 — 12-1 momentum"
    assert view["n_trials"] == 2
    assert view["queued_hypotheses"][0]["statement"] == "try mean reversion"
    assert view["research_outcome"] == ResearchOutcome.NONE.value
    assert view["stop_reason"] is None
    assert view["primary_evidence"] is None


def test_revisions_omit_first_frozen_grid_point(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(_spec())
    run_dir = tmp_path / job.run_id
    (run_dir / "trial-ledger.jsonl").write_text(
        json.dumps({"trial_id": "c_1", "revision": "none"}) + "\n",
        encoding="utf-8",
    )
    view = morning_view(store.get(job.run_id), tmp_path)
    assert view["revisions"] == []
    assert view["n_trials"] == 1


def test_morning_view_exposes_seed_and_unique_n_trials(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(_spec())
    run_dir = tmp_path / job.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "trial-ledger.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"trial_id": "c_1", "revision": "none"}),
                json.dumps({"trial_id": "c_1", "revision": "method"}),
                json.dumps({"trial_id": "c_2", "revision": "none"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    view = morning_view(store.get(job.run_id), tmp_path)
    assert view["seed"] == job.spec.seed
    assert view["n_trials"] == 2
    assert view["spec_id"] == job.spec.spec_id


def test_morning_view_n_trials_zero_without_ledger(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(_spec())
    view = morning_view(store.get(job.run_id), tmp_path)
    assert view["n_trials"] == 0
    assert view["seed"] == 7


def test_morning_view_exposes_planned_n_trials(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(_spec())
    view = morning_view(store.get(job.run_id), tmp_path)
    assert view["planned_n_trials"] == 3
    assert view["n_trials"] == 0


def test_morning_view_exposes_heartbeat_at(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(_spec())
    view = morning_view(job, tmp_path)
    assert view["heartbeat_at"] is None
    beat = store.set_heartbeat(job.run_id, pid=7, at="2026-08-20T00:00:00+00:00")
    view = morning_view(beat, tmp_path)
    assert view["heartbeat_at"] == "2026-08-20T00:00:00+00:00"


def test_funnel_aggregates_trial_files_not_only_last_gates(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(_spec())
    run_dir = tmp_path / job.run_id
    (run_dir / "trial-ledger.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"trial_id": "c_a", "revision": "none"}),
                json.dumps({"trial_id": "c_b", "revision": "method"}),
                json.dumps({"trial_id": "c_c", "revision": "method"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    required = tuple(HardGateName(name) for name in job.spec.success_criteria.hard_gates)
    dsr_fail = evaluate_hard_gates(
        required,
        tuple(
            GateResult(name=name, passed=name is not HardGateName.DSR, detail={})
            for name in required
        ),
    )
    both_fail = evaluate_hard_gates(
        required,
        tuple(GateResult(name=name, passed=False, detail={}) for name in required),
    )
    evidence_dir = run_dir / "evidence"
    trials = evidence_dir / "trials"
    trials.mkdir(parents=True)
    (trials / "c_a.json").write_text(json.dumps(evidence_to_dict(dsr_fail)))
    (trials / "c_b.json").write_text(json.dumps(evidence_to_dict(dsr_fail)))
    (trials / "c_c.json").write_text(json.dumps(evidence_to_dict(both_fail)))
    (evidence_dir / "gates.json").write_text(json.dumps(evidence_to_dict(both_fail)))
    view = morning_view(store.complete_from_artifacts(job.run_id), tmp_path)
    assert view["funnel"]["n_evaluated"] == 3
    assert view["funnel"]["n_complete"] == 3
    assert view["funnel"]["n_passed"] == 0
    assert view["funnel"]["n_failed"] == 3
    assert view["funnel"]["n_incomplete"] == 0
    assert view["funnel"]["failure_counts"]["dsr"] == 3
    assert view["funnel"]["dominant_failures"][0] == "dsr"
    assert view["funnel"]["dominant_failure_labels"][0] == "dsr — Deflated Sharpe Ratio"
    assert view["qualifying_candidates"] == []


def test_morning_view_report_markdown_is_sealed_file_or_empty(tmp_path):
    from alphaloop.contracts.artifacts import RunLayout
    from alphaloop.runtime.artifacts_io import write_report

    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(_spec())
    view = morning_view(job, tmp_path)
    assert view["report_markdown"] == ""
    layout = RunLayout(tmp_path / job.run_id)
    write_report(
        layout,
        research_outcome="NO_EVIDENCE",
        stop_reason="hard_gate_failed",
        spec=job.spec,
        n_trials=0,
    )
    view = morning_view(job, tmp_path)
    assert view["report_markdown"] == layout.report.read_text(encoding="utf-8")
    assert "This report does not claim alpha or future profitability." in view["report_markdown"]
    assert view["research_outcome"] == job.research_outcome.value


def test_qualifying_candidates_only_all_passed_trial_files(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(_spec())
    run_dir = tmp_path / job.run_id
    (run_dir / "trial-ledger.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "trial_id": "c_pass",
                        "kind": "momentum_12_1",
                        "parameters": {"lookback": 126},
                    }
                ),
                json.dumps(
                    {
                        "trial_id": "c_fail",
                        "kind": "momentum_12_1",
                        "parameters": {},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    required = tuple(HardGateName(name) for name in job.spec.success_criteria.hard_gates)
    passed = _gates_for(job.spec)
    failed = _gates_for(job.spec, fail_first=True)
    evidence_dir = run_dir / "evidence"
    trials = evidence_dir / "trials"
    trials.mkdir(parents=True)
    (trials / "c_fail.json").write_text(json.dumps(evidence_to_dict(failed)))
    (trials / "c_pass.json").write_text(json.dumps(evidence_to_dict(passed)))
    (evidence_dir / "gates.json").write_text(json.dumps(evidence_to_dict(failed)))
    view = morning_view(store.complete_from_artifacts(job.run_id), tmp_path)
    assert view["research_outcome"] == ResearchOutcome.NO_EVIDENCE.value
    assert view["qualifying_candidates"] == [
        {
            "trial_id": "c_pass",
            "kind": "momentum_12_1",
            "kind_label": "momentum_12_1 — 12-1 momentum",
            "parameters": {"lookback": 126},
        }
    ]


def test_morning_view_evidence_lines_include_walk_forward_detail(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(_spec())
    required = (HardGateName.WALK_FORWARD,)
    evidence = evaluate_hard_gates(
        required,
        (
            GateResult(
                name=HardGateName.WALK_FORWARD,
                passed=False,
                detail={
                    "regime_stable": False,
                    "returns_scope": "oos_walk_forward",
                    "oos_sharpe_median": -0.2,
                },
            ),
        ),
    )
    evidence_dir = tmp_path / job.run_id / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "gates.json").write_text(json.dumps(evidence_to_dict(evidence)))
    view = morning_view(store.complete_from_artifacts(job.run_id), tmp_path)
    assert view["evidence_lines"]
    line = view["evidence_lines"][0]
    assert line.startswith("walk_forward — walk-forward OOS: fail")
    assert "regime_stable=false" in line
    assert "returns_scope=oos_walk_forward" in line
    assert "oos_sharpe_median=-0.2" in line


def test_morning_view_missing_evidence_has_empty_lines(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(_spec())
    view = morning_view(store.complete_from_artifacts(job.run_id), tmp_path)
    assert view["evidence_lines"] == []


NO_ALPHA = "This status does not claim alpha or future profitability."


def test_format_export_handoff_cluster():
    text = format_export_handoff(candidate_id="c_abc", exported_path="/tmp/out.asb")
    lines = text.splitlines()
    assert lines[0] == "FOUND"
    assert lines[1] == "Qualifying: c_abc"
    assert lines[2] == "Exported: /tmp/out.asb"
    assert lines[3] == EXPORT_NO_ALPHA
    assert lines[3] == "This export does not claim alpha or future profitability."
    assert text.endswith("\n")
    assert "target found" not in text.lower()
    with pytest.raises(json.JSONDecodeError):
        json.loads(text)


def test_format_status_verdict_found_cluster():
    text = format_status_verdict(
        {
            "research_outcome": "FOUND",
            "primary_evidence": "all required hard gates passed",
            "stop_reason": "all_gates_passed",
            "status": "completed",
            "queued_hypotheses": [],
            "qualifying_candidates": [
                {
                    "trial_id": "c_abc",
                    "kind": "momentum_12_1",
                    "kind_label": "momentum_12_1 — 12-1 momentum",
                    "parameters": {"lookback": 12},
                }
            ],
        }
    )
    lines = text.splitlines()
    assert lines[0] == "FOUND"
    assert lines[1] == (
        "FOUND means every required hard gate is present and passed. "
        "It is not a promise of alpha."
    )
    assert lines[2] == "Primary evidence: all required hard gates passed"
    assert lines[3] == "Stop reason: all_gates_passed"
    assert lines[4] == (
        "Qualifying: c_abc · momentum_12_1 — 12-1 momentum · lookback=12"
    )
    fallback = format_status_verdict(
        {
            "research_outcome": "FOUND",
            "primary_evidence": "all required hard gates passed",
            "stop_reason": "all_gates_passed",
            "status": "completed",
            "queued_hypotheses": [],
            "qualifying_candidates": [
                {
                    "trial_id": "c_abc",
                    "kind": "momentum_12_1",
                    "parameters": {"lookback": 12},
                }
            ],
        }
    )
    assert "Qualifying: c_abc · momentum_12_1 · lookback=12" in fallback
    assert lines[5] == "Job status: completed"
    assert lines[6] == NO_ALPHA
    assert text.endswith("\n")
    assert "target found" not in text.lower()
    assert "report_markdown" not in text


def test_format_status_verdict_none_omits_optional_lines():
    text = format_status_verdict(
        {
            "research_outcome": "NONE",
            "primary_evidence": None,
            "stop_reason": None,
            "status": "running",
            "queued_hypotheses": [],
            "qualifying_candidates": [{"trial_id": "c_skip"}],
        }
    )
    lines = text.splitlines()
    assert lines[0] == "NONE"
    assert lines[1] == (
        "Job status (queued, running, completed, failed, cancelled) "
        "is not the research conclusion."
    )
    assert lines[2] == "Primary evidence: (running or not yet terminal)"
    assert lines[3] == "Stop reason: (running or not yet terminal)"
    assert lines[4] == "Job status: running"
    assert "Next run:" not in text
    assert "Qualifying:" not in text


def test_format_status_verdict_queued_next_run():
    text = format_status_verdict(
        {
            "research_outcome": "NO_EVIDENCE",
            "primary_evidence": "dsr — Deflated Sharpe Ratio failed",
            "stop_reason": "hard_gate_failed",
            "status": "completed",
            "queued_hypotheses": [
                {"statement": "Try rsi. Not a claim of alpha."}
            ],
        }
    )
    assert "Next run: Try rsi. Not a claim of alpha." in text.splitlines()
    assert text.splitlines()[1].startswith("NO_EVIDENCE means")


def test_format_status_verdict_inconclusive_gloss():
    text = format_status_verdict(
        {
            "research_outcome": "INCONCLUSIVE",
            "primary_evidence": "no sealed gates.json",
            "stop_reason": "incomplete_evidence",
            "status": "completed",
        }
    )
    assert "incomplete" in text.splitlines()[1]
    assert "cannot produce FOUND" in text


def test_replay_view_uses_artifact_outcome_not_store_token(tmp_path):
    from alphaloop.contracts.artifacts import RunLayout

    layout = RunLayout(tmp_path / "j_replay")
    view = replay_view(layout, research_outcome="FOUND", status="completed")
    assert view["research_outcome"] == "FOUND"
    assert view["status"] == "completed"
    assert view["stop_reason"] == STOP_REASON_ALL_GATES_PASSED
    assert view["primary_evidence"] == "all required hard gates passed"
    assert view["queued_hypotheses"] == []
    assert isinstance(view["qualifying_candidates"], list)
