from __future__ import annotations

import argparse
import json
import sys
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
from alphaloop.contracts.bundle import (
    ExportNotAllowed,
    assert_exportable,
    bundle_from_payload,
)
from alphaloop.protocol.dsl import DSL_SCHEMA_VERSION
from alphaloop.runtime.store import JobStore

DEFAULT_DATA_DIR = "./runs"


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "export",
        help="export a FOUND candidate as an immutable .asb bundle",
    )
    parser.add_argument("candidate_id")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR, type=Path)
    parser.add_argument("--output", "-o", required=True, type=Path)
    parser.set_defaults(func=run_export)


def _universe(market_scope: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in market_scope.split(",") if part.strip())


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


def run_export(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    store = JobStore(data_dir / ".alphaloop" / "state.db", data_dir)
    try:
        job = store.get(args.run_id)
    except KeyError:
        print(f"error: job not found: {args.run_id}", file=sys.stderr)
        return 2

    layout = RunLayout(data_dir / job.run_id)
    sealed_ids, params_by_id = _ledger(layout)
    try:
        assert_exportable(job.research_outcome, sealed_ids, args.candidate_id)
    except ExportNotAllowed as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    spec = job.spec
    universe = _universe(spec.hypothesis.market_scope)
    parameters = params_by_id.get(args.candidate_id, {})
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
            "candidate_id": args.candidate_id,
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
    write_asb(
        args.output,
        bundle,
        evidence=evidence,
        conformance=conformance_members(kind, parameters, universe, profile),
    )
    print(args.output)
    return 0
