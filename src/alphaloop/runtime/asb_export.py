from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from alphaloop.bundle.archive import ASB_SCHEMA_VERSION, write_asb
from alphaloop.bundle.fixtures import (
    CONFORMANCE_AS_OF,
    conformance_members,
    conformance_prices,
    expected_weights,
)
from alphaloop.contracts.artifacts import RunLayout
from alphaloop.contracts.bundle import assert_exportable, bundle_from_payload
from alphaloop.protocol.dsl import DSL_SCHEMA_VERSION
from alphaloop.runtime.store import JobStore


def _universe(market_scope: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in market_scope.split(",") if part.strip())


def _reject_unsafe_candidate_id(candidate_id: str) -> None:
    if not candidate_id or any(part in candidate_id for part in ("/", "\\", "..")):
        raise ValueError("invalid candidate_id")


def _ledger(layout: RunLayout) -> tuple[tuple[str, ...], dict[str, dict[str, Any]]]:
    ids: list[str] = []
    params: dict[str, dict[str, Any]] = {}
    if not layout.trial_ledger.is_file():
        return (), {}
    for line in layout.trial_ledger.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        trial_id = row.get("trial_id")
        if not trial_id:
            continue
        ids.append(str(trial_id))
        parameters = row.get("parameters") or {}
        params[str(trial_id)] = dict(parameters) if isinstance(parameters, dict) else {}
    return tuple(ids), params


def export_found_asb(
    *,
    store: JobStore,
    data_dir: Path,
    run_id: str,
    candidate_id: str,
    output: Path,
) -> Path:
    _reject_unsafe_candidate_id(candidate_id)
    job = store.get(run_id)
    layout = RunLayout(Path(data_dir) / job.run_id)
    sealed_ids, params_by_id = _ledger(layout)
    assert_exportable(job.research_outcome, sealed_ids, candidate_id)
    spec = job.spec
    universe = _universe(spec.hypothesis.market_scope)
    parameters = params_by_id.get(candidate_id, {})
    kind = spec.hypothesis.signal_mechanism
    profile = spec.hypothesis.market_profile
    weights = expected_weights(
        kind,
        parameters,
        universe,
        profile,
        conformance_prices(),
        CONFORMANCE_AS_OF,
    )
    payload = {
        "schema_version": ASB_SCHEMA_VERSION,
        "strategy_dsl": {
            "schema_version": DSL_SCHEMA_VERSION,
            "kind": kind,
            "parameters": parameters,
            "universe": list(universe),
            "market_profile": profile,
        },
        "market_profile": profile,
        "parameters": parameters,
        "risk_envelope": {"max_weight": 1.0},
        "lineage": {
            "run_id": job.run_id,
            "candidate_id": candidate_id,
            "spec_id": spec.spec_id,
        },
        "conformance": {
            "inputs": {
                "as_of": CONFORMANCE_AS_OF.isoformat(),
                "universe": list(universe),
            },
            "expected_weights": weights,
        },
        "registry_uri": None,
    }
    bundle = bundle_from_payload(payload)
    evidence: dict[str, bytes] = {}
    gates = layout.evidence / "gates.json"
    if gates.is_file():
        evidence["gates.json"] = gates.read_bytes()
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_asb(
        output,
        bundle,
        evidence=evidence,
        conformance=conformance_members(kind, parameters, universe, profile),
    )
    return output
