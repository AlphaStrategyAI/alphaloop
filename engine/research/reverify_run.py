"""Re-run one frozen round without opening a version or counting another trial."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import date
from typing import Any

import pandas as pd

from engine.export import mark_exports_overturned
from engine.research.gather import pit_evidence_annotations, pit_evidence_from_payloads
from engine.research.methods import execute_method_revision
from engine.research.models import Research, ResearchEvent, Reverification
from engine.research.simulate import simulate_daily
from engine.research.state_machine import transition
from engine.strategy import MeanReversionStrategy
from engine.verifiers import VERIFIER_REVISIONS, recorded_pit_revision, run_verifiers

_BUILTIN_METHODS = frozenset(VERIFIER_REVISIONS) | {"pit.consistency"}


def _locate(research: Research, round_id: str):
    found = [
        (version, round_)
        for version in research.versions
        for round_ in version.rounds
        if round_.round_id == round_id
    ]
    if len(found) != 1:
        raise ValueError("reverify requires one frozen round_id")
    return found[0]


def _current_round_id(research: Research) -> str | None:
    if research.versions and research.versions[-1].rounds:
        return research.versions[-1].rounds[-1].round_id
    return None


def _commit(research: Research, record: Reverification, now) -> Research:
    with_rerun = replace(
        research,
        reverifications=research.reverifications + (record,),
        reverification_audit=research.reverification_audit + (record,),
        updated_at=now,
    )
    if not record.passed:
        with_rerun = mark_exports_overturned(with_rerun, record)
    current = _current_round_id(research)
    if record.passed:
        event = ResearchEvent.REVERIFY_PASS
    elif record.round_id == current:
        event = ResearchEvent.REVERIFY_FAIL
    else:
        return with_rerun
    return transition(with_rerun, event, now)


def _library_reverify(research: Research, request: dict[str, Any], now, store) -> Research:
    version, round_ = _locate(research, str(request["round_id"]))
    accepted = round_.accepted_attempt
    refs = tuple(getattr(accepted.spec, "method_set", ()) or ())
    matches = [item for item in refs if item.method_id == request["method_id"]]
    if len(matches) != 1:
        raise ValueError("reverify requires one frozen round_id/method_id/revision")
    frozen_revision = matches[0].revision_hash
    requested = request.get("revision")
    if isinstance(requested, str) and requested and requested != frozen_revision:
        raise ValueError("unregistered method revision")
    if store is None:
        raise ValueError("unregistered method revision")
    observed = float(accepted.simulation.sharpe)
    passed = execute_method_revision(store, str(request["method_id"]), frozen_revision, observed)
    digest = hashlib.sha256(f"{frozen_revision}:{observed}".encode()).hexdigest()
    record = Reverification(
        round_id=str(request["round_id"]),
        method_id=str(request["method_id"]),
        report={"revision": frozen_revision, "observed": observed, "passed": passed},
        passed=passed,
        created_at=now,
        version_number=version.number,
        revision=frozen_revision,
        input_hash=digest,
    )
    return _commit(research, record, now)


def reverify_round(research: Research, request: dict[str, Any], now, store=None) -> Research:
    """Reuse the frozen snapshot, materials, and method revision. Does not add a round."""
    method_id = str(request["method_id"])
    if method_id not in _BUILTIN_METHODS:
        return _library_reverify(research, request, now, store)
    version, round_ = _locate(research, str(request["round_id"]))
    accepted = round_.accepted_attempt
    if accepted.data_snapshot_path is None:
        raise ValueError("reverify requires the selected round's frozen data")
    snapshot_path = accepted.data_snapshot_path
    frozen = pd.read_csv(snapshot_path, index_col="date", parse_dates=True)

    class FrozenDataPort:
        def load_daily(self, symbols: tuple[str, ...], start: date, end: date) -> pd.DataFrame:
            del start, end
            if symbols == (accepted.simulation.benchmark_id,):
                return frozen[["__benchmark__"]].rename(
                    columns={"__benchmark__": accepted.simulation.benchmark_id}
                )
            return frozen[list(symbols)]

    rerun_simulation = simulate_daily(
        MeanReversionStrategy(accepted.spec),
        FrozenDataPort(),
        frozen.index.min().date(),
        frozen.index.max().date(),
    )
    pit_revision = recorded_pit_revision(accepted.verification)
    evidence_payloads = tuple(
        json.loads(path.read_text(encoding="utf-8")) for path in accepted.evidence_paths
    )
    evidence_as_of, missing_as_of, undated_excluded = pit_evidence_from_payloads(
        evidence_payloads,
        revision=pit_revision,
    )
    rerun = run_verifiers(
        rerun_simulation,
        accepted.spec,
        evidence_as_of=evidence_as_of,
        missing_as_of_material_ids=missing_as_of,
        undated_excluded=undated_excluded,
        evidence_annotations=pit_evidence_annotations(evidence_payloads),
        pit_revision=pit_revision,
    )
    matching_method = [result for result in rerun.results if result.verifier_id == method_id]
    if len(matching_method) != 1:
        raise ValueError("method_id is not frozen on the selected round")
    revision = str(matching_method[0].revision)
    requested = request.get("revision")
    if isinstance(requested, str) and requested and requested != revision:
        raise ValueError("unregistered method revision")
    record = Reverification(
        round_id=str(request["round_id"]),
        method_id=method_id,
        report=rerun,
        passed=bool(matching_method[0].passed),
        created_at=now,
        version_number=version.number,
        revision=revision,
        input_hash=hashlib.sha256(snapshot_path.read_bytes()).hexdigest(),
    )
    return _commit(research, record, now)
