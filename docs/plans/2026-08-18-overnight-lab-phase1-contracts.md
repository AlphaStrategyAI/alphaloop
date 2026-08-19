# Overnight Lab Phase 1 — Core Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add versioned overnight-lab contracts and fix package identity so later runtime/protocol work has a single source of truth for job status, research outcome, frozen specs, hard gates, artifacts, and bundle export.

**Architecture:** Keep `diagnostic`, `engineer`, `data`, `backtest`, and `strategies` in place. Add `src/alphaloop/contracts/` as a side-effect-light schema layer. Wrap existing diagnostics behind `HardGateName` without calling them yet. Stop exporting `live` from the package root. Do not start a daemon in this plan.

**Tech Stack:** Python 3.9+, pytest, PyYAML, stdlib `enum`/`dataclasses`/`hashlib`/`json`, existing `alphaloop.cli` argparse.

## Global Constraints

- Local-first; this phase adds no network server and no broker calls.
- `FOUND` can only be derived from complete hard-gate evidence.
- `llm_judge` is not a hard gate.
- `JobStatus` and `ResearchOutcome` are separate types; never store a termination letter as a research outcome.
- `alphaloop.contracts` must not import `alphaloop.live`.
- Bundle `registry_uri` is optional and may be `None`.
- Do not rewrite `loop/aggregator.py` diagnostic math in this plan.
- Source of truth: `docs/requirements/product-positioning-requirements.md` and `docs/plans/overnight-research-lab-refactor.md`.

---

### Task 1: Package identity and CLI entry

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/alphaloop/__init__.py`
- Modify: `src/alphaloop/__version__.py`
- Modify: `src/alphaloop/cli/main.py`
- Test: `tests/test_package_identity.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Consumes: existing `alphaloop.cli.main:main`
- Produces: installable console script `alphaloop`; `__version__ == pyproject version`; root `__all__` without live-trading names

- [ ] **Step 1: Write the failing identity tests**

Create `tests/test_package_identity.py`:

```python
from __future__ import annotations

from pathlib import Path

import alphaloop
from alphaloop.cli.main import create_parser, main


ROOT = Path(__file__).resolve().parents[1]


def _pyproject_text() -> str:
    return (ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_pyproject_script_points_at_alphaloop_cli():
    text = _pyproject_text()
    assert 'alphaloop = "alphaloop.cli.main:main"' in text
    assert "openstrategy.cli:main" not in text


def test_hatch_wheel_does_not_point_at_missing_openstrategy():
    assert "src/openstrategy" not in _pyproject_text()


def test_dunder_version_matches_pyproject():
    text = _pyproject_text()
    assert f'version = "{alphaloop.__version__}"' in text


def test_package_docstring_says_alphaloop():
    assert "OpenStrategy" not in (alphaloop.__doc__ or "")
    assert "alphaloop" in (alphaloop.__doc__ or "").lower()


def test_live_names_are_not_in_root_all():
    forbidden = {
        "AlpacaAdapter",
        "Broker",
        "BrokerConfig",
        "CONFIRM_LIVE_FLAG",
        "LiveTradingRefused",
    }
    assert forbidden.isdisjoint(set(alphaloop.__all__))


def test_cli_help_uses_alphaloop_not_openstrategy(capsys):
    rc = main([])
    assert rc == 1
    out = capsys.readouterr().out
    assert "alphaloop" in out.lower()
    assert "OpenStrategy" not in out


def test_cli_parser_prog_is_alphaloop():
    parser = create_parser()
    assert parser.prog == "alphaloop"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_package_identity.py -v`

Expected: FAIL on script name `openstrategy`, hatch `src/openstrategy`, version mismatch (`1.0.0` vs `0.5.0`), docstring, `__all__`, and CLI help text.

- [ ] **Step 3: Align packaging, version, and public exports**

Set `src/alphaloop/__version__.py` to:

```python
"""版本信息"""

__version__ = "0.5.0"
__version_info__ = (0, 5, 0)
```

Replace the `[project.scripts]` table with:

```toml
[project.scripts]
alphaloop = "alphaloop.cli.main:main"
```

Delete the hatch override that points at a missing tree:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/openstrategy"]
```

Hatchling then discovers `src/alphaloop` via the default src layout. Leave `[project] version = "0.5.0"` unchanged so it matches `__version__`.

In `src/alphaloop/__init__.py`:

- Change the module docstring to:

```python
"""
alphaloop — local-first overnight research lab.

Honest, verifiable, agent-assisted quantitative research.
It does not promise alpha.
"""
```

- Set `__version__` from `.__version__`:

```python
from .__version__ import __version__
```

- Remove the `from .live import ...` block.
- Remove live names from `__all__`.
- Keep diagnostic, strategy, backtest, and lazy loop exports.

In `src/alphaloop/cli/main.py` `create_parser()`, set:

```python
parser = argparse.ArgumentParser(
    prog="alphaloop",
    description="alphaloop — local-first overnight research lab",
)
```

- [ ] **Step 4: Update the existing CLI help assertion**

In `tests/test_cli.py::test_cli_help_exits_cleanly`, replace
`assert "OpenStrategy" in out` with:

```python
assert "alphaloop" in out.lower()
assert "backtest" in out
assert "fetch" in out
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_package_identity.py tests/test_cli.py tests/live -v`

Expected: PASS. Live tests still import `alphaloop.live` directly.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/alphaloop/__init__.py src/alphaloop/__version__.py \
  src/alphaloop/cli/main.py tests/test_package_identity.py tests/test_cli.py
git commit -m "fix: point packaging and public API at alphaloop"
```

---

### Task 2: JobStatus, ResearchOutcome, and derivation table

**Files:**
- Create: `src/alphaloop/contracts/__init__.py`
- Create: `src/alphaloop/contracts/status.py`
- Test: `tests/contracts/test_status.py`

**Interfaces:**
- Consumes: nothing from Task 1 besides the package import path
- Produces: `JobStatus`, `ResearchOutcome`, `derive_research_outcome(job_status, evidence_complete, all_gates_passed, sealed=None)`

- [ ] **Step 1: Write failing derivation tests**

Create `tests/contracts/test_status.py`:

```python
from __future__ import annotations

import pytest

from alphaloop.contracts.status import (
    JobStatus,
    ResearchOutcome,
    derive_research_outcome,
)


def test_running_has_no_research_outcome():
    assert (
        derive_research_outcome(
            JobStatus.RUNNING,
            evidence_complete=False,
            all_gates_passed=False,
        )
        is ResearchOutcome.NONE
    )


def test_completed_all_pass_is_found():
    assert (
        derive_research_outcome(
            JobStatus.COMPLETED,
            evidence_complete=True,
            all_gates_passed=True,
        )
        is ResearchOutcome.FOUND
    )


def test_completed_any_fail_is_no_evidence():
    assert (
        derive_research_outcome(
            JobStatus.COMPLETED,
            evidence_complete=True,
            all_gates_passed=False,
        )
        is ResearchOutcome.NO_EVIDENCE
    )


def test_completed_incomplete_evidence_is_inconclusive():
    assert (
        derive_research_outcome(
            JobStatus.COMPLETED,
            evidence_complete=False,
            all_gates_passed=True,
        )
        is ResearchOutcome.INCONCLUSIVE
    )


@pytest.mark.parametrize("status", [JobStatus.FAILED, JobStatus.CANCELLED])
def test_failed_or_cancelled_cannot_claim_found(status):
    assert (
        derive_research_outcome(
            status,
            evidence_complete=True,
            all_gates_passed=True,
        )
        is ResearchOutcome.INCONCLUSIVE
    )


def test_sealed_found_survives_cancel():
    assert (
        derive_research_outcome(
            JobStatus.CANCELLED,
            evidence_complete=True,
            all_gates_passed=True,
            sealed=ResearchOutcome.FOUND,
        )
        is ResearchOutcome.FOUND
    )


def test_incomplete_evidence_cannot_use_all_gates_passed_shortcut():
    outcome = derive_research_outcome(
        JobStatus.COMPLETED,
        evidence_complete=False,
        all_gates_passed=True,
    )
    assert outcome is not ResearchOutcome.FOUND
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/contracts/test_status.py -v`

Expected: FAIL with `ModuleNotFoundError: alphaloop.contracts`.

- [ ] **Step 3: Implement status types**

Create `src/alphaloop/contracts/status.py`:

```python
from __future__ import annotations

from enum import Enum
from typing import Optional


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ResearchOutcome(str, Enum):
    FOUND = "FOUND"
    NO_EVIDENCE = "NO_EVIDENCE"
    INCONCLUSIVE = "INCONCLUSIVE"
    NONE = "NONE"


def derive_research_outcome(
    job_status: JobStatus,
    evidence_complete: bool,
    all_gates_passed: bool,
    sealed: Optional[ResearchOutcome] = None,
) -> ResearchOutcome:
    if sealed is ResearchOutcome.FOUND:
        return ResearchOutcome.FOUND
    if job_status in (JobStatus.QUEUED, JobStatus.RUNNING):
        return ResearchOutcome.NONE
    if job_status in (JobStatus.FAILED, JobStatus.CANCELLED):
        return ResearchOutcome.INCONCLUSIVE
    if job_status is JobStatus.COMPLETED:
        if not evidence_complete:
            return ResearchOutcome.INCONCLUSIVE
        if all_gates_passed:
            return ResearchOutcome.FOUND
        return ResearchOutcome.NO_EVIDENCE
    raise ValueError(f"unknown job status: {job_status}")
```

Create `src/alphaloop/contracts/__init__.py`:

```python
from .status import JobStatus, ResearchOutcome, derive_research_outcome

__all__ = [
    "JobStatus",
    "ResearchOutcome",
    "derive_research_outcome",
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/contracts/test_status.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/contracts/__init__.py src/alphaloop/contracts/status.py \
  tests/contracts/test_status.py
git commit -m "feat: add job status and research outcome contracts"
```

---

### Task 3: Frozen ResearchSpec

**Files:**
- Create: `src/alphaloop/contracts/research_spec.py`
- Modify: `src/alphaloop/contracts/__init__.py`
- Test: `tests/contracts/test_research_spec.py`

**Interfaces:**
- Consumes: none
- Produces: frozen `Hypothesis`, `SuccessCriteria`, `ResearchSpec`; `ResearchSpec.replace_hypothesis` does not exist; mutation attempts fail

- [ ] **Step 1: Write failing spec tests**

Create `tests/contracts/test_research_spec.py`:

```python
from __future__ import annotations

import dataclasses

import pytest

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


def test_new_spec_ids_are_stable_for_same_payload_and_seed():
    a = _spec()
    b = _spec()
    assert a.spec_id == b.spec_id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/contracts/test_research_spec.py -v`

Expected: FAIL with import error for `research_spec`.

- [ ] **Step 3: Implement ResearchSpec**

Create `src/alphaloop/contracts/research_spec.py`:

```python
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence


ALLOWED_PROFILES = ("us-equity-daily", "crypto-daily")


@dataclass(frozen=True)
class Hypothesis:
    statement: str
    economic_logic: str
    signal_mechanism: str
    market_scope: str
    market_profile: str
    benchmark: str

    def __post_init__(self) -> None:
        if self.market_profile not in ALLOWED_PROFILES:
            raise ValueError(f"unsupported market_profile: {self.market_profile}")


@dataclass(frozen=True)
class SuccessCriteria:
    hard_gates: tuple[str, ...]


@dataclass(frozen=True)
class ResearchSpec:
    spec_id: str
    hypothesis: Hypothesis
    success_criteria: SuccessCriteria
    seed: int
    time_budget_s: int
    cost_budget_usd: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ResearchSpec":
        hyp = payload["hypothesis"]
        crit = payload["success_criteria"]
        return cls(
            spec_id=str(payload["spec_id"]),
            hypothesis=Hypothesis(
                statement=str(hyp["statement"]),
                economic_logic=str(hyp["economic_logic"]),
                signal_mechanism=str(hyp["signal_mechanism"]),
                market_scope=str(hyp["market_scope"]),
                market_profile=str(hyp["market_profile"]),
                benchmark=str(hyp["benchmark"]),
            ),
            success_criteria=SuccessCriteria(
                hard_gates=tuple(crit["hard_gates"]),
            ),
            seed=int(payload["seed"]),
            time_budget_s=int(payload["time_budget_s"]),
            cost_budget_usd=float(payload["cost_budget_usd"]),
        )


def new_research_spec(
    *,
    statement: str,
    economic_logic: str,
    signal_mechanism: str,
    market_scope: str,
    market_profile: str,
    benchmark: str,
    hard_gates: Sequence[str],
    seed: int,
    time_budget_s: int,
    cost_budget_usd: float,
) -> ResearchSpec:
    hypothesis = Hypothesis(
        statement=statement,
        economic_logic=economic_logic,
        signal_mechanism=signal_mechanism,
        market_scope=market_scope,
        market_profile=market_profile,
        benchmark=benchmark,
    )
    criteria = SuccessCriteria(hard_gates=tuple(hard_gates))
    payload = {
        "hypothesis": asdict(hypothesis),
        "success_criteria": asdict(criteria),
        "seed": seed,
        "time_budget_s": time_budget_s,
        "cost_budget_usd": cost_budget_usd,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return ResearchSpec(
        spec_id="rs_" + digest[:32],
        hypothesis=hypothesis,
        success_criteria=criteria,
        seed=seed,
        time_budget_s=time_budget_s,
        cost_budget_usd=cost_budget_usd,
    )
```

Export the new names from `src/alphaloop/contracts/__init__.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/contracts/test_research_spec.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/contracts/research_spec.py src/alphaloop/contracts/__init__.py \
  tests/contracts/test_research_spec.py
git commit -m "feat: add frozen research spec contract"
```

---

### Task 4: Hard-gate evidence contract

**Files:**
- Create: `src/alphaloop/contracts/gates.py`
- Modify: `src/alphaloop/contracts/__init__.py`
- Test: `tests/contracts/test_gates.py`

**Interfaces:**
- Consumes: `derive_research_outcome`, `JobStatus`
- Produces: `HardGateName`, `GateResult`, `GateEvidence`, `IncompleteEvidenceError`, `evaluate_hard_gates(required, results)`, `outcome_from_evidence(job_status, evidence)`

- [ ] **Step 1: Write failing gate tests**

Create `tests/contracts/test_gates.py`:

```python
from __future__ import annotations

import pytest

from alphaloop.contracts.gates import (
    GateResult,
    HardGateName,
    IncompleteEvidenceError,
    evaluate_hard_gates,
    outcome_from_evidence,
)
from alphaloop.contracts.status import JobStatus, ResearchOutcome


REQUIRED = (
    HardGateName.DSR,
    HardGateName.WALK_FORWARD,
    HardGateName.VS_RANDOM,
    HardGateName.VS_BUY_HOLD,
    HardGateName.VS_BENCHMARK,
    HardGateName.DATA_CONSISTENCY,
)


def _all_pass() -> tuple[GateResult, ...]:
    return tuple(GateResult(name=name, passed=True, detail={}) for name in REQUIRED)


def test_llm_judge_is_not_a_hard_gate():
    names = {item.value for item in HardGateName}
    assert "llm_judge" not in names
    assert "judge" not in names


def test_missing_required_gate_raises():
    partial = _all_pass()[:-1]
    with pytest.raises(IncompleteEvidenceError):
        evaluate_hard_gates(REQUIRED, partial)


def test_complete_pass_is_found_when_job_completed():
    evidence = evaluate_hard_gates(REQUIRED, _all_pass())
    assert (
        outcome_from_evidence(JobStatus.COMPLETED, evidence)
        is ResearchOutcome.FOUND
    )


def test_one_failure_is_no_evidence():
    rows = list(_all_pass())
    rows[-1] = GateResult(name=HardGateName.VS_BENCHMARK, passed=False, detail={})
    evidence = evaluate_hard_gates(REQUIRED, tuple(rows))
    assert (
        outcome_from_evidence(JobStatus.COMPLETED, evidence)
        is ResearchOutcome.NO_EVIDENCE
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/contracts/test_gates.py -v`

Expected: FAIL with import error.

- [ ] **Step 3: Implement gates**

Create `src/alphaloop/contracts/gates.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Sequence

from .status import JobStatus, ResearchOutcome, derive_research_outcome


class IncompleteEvidenceError(ValueError):
    """Raised when a required hard gate is missing from the evidence set."""


class HardGateName(str, Enum):
    DSR = "dsr"
    WALK_FORWARD = "walk_forward"
    VS_RANDOM = "vs_random"
    VS_BUY_HOLD = "vs_buy_hold"
    VS_BENCHMARK = "vs_benchmark"
    DATA_CONSISTENCY = "data_consistency"


@dataclass(frozen=True)
class GateResult:
    name: HardGateName
    passed: bool
    detail: dict


@dataclass(frozen=True)
class GateEvidence:
    results: tuple[GateResult, ...]
    required: tuple[HardGateName, ...]

    @property
    def complete(self) -> bool:
        present = {row.name for row in self.results}
        return all(name in present for name in self.required)

    @property
    def all_passed(self) -> bool:
        if not self.complete:
            return False
        by_name = {row.name: row.passed for row in self.results}
        return all(by_name[name] for name in self.required)


def evaluate_hard_gates(
    required: Sequence[HardGateName],
    results: Iterable[GateResult],
) -> GateEvidence:
    rows = tuple(results)
    present = {row.name for row in rows}
    missing = [name for name in required if name not in present]
    if missing:
        raise IncompleteEvidenceError(
            "missing hard gates: " + ", ".join(name.value for name in missing)
        )
    return GateEvidence(results=rows, required=tuple(required))


def outcome_from_evidence(job_status: JobStatus, evidence: GateEvidence) -> ResearchOutcome:
    return derive_research_outcome(
        job_status,
        evidence_complete=evidence.complete,
        all_gates_passed=evidence.all_passed,
    )
```

Export `HardGateName`, `GateResult`, `GateEvidence`, `IncompleteEvidenceError`, `evaluate_hard_gates`, `outcome_from_evidence`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/contracts/test_gates.py tests/contracts/test_status.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/contracts/gates.py src/alphaloop/contracts/__init__.py \
  tests/contracts/test_gates.py
git commit -m "feat: add hard-gate evidence contract"
```

---

### Task 5: Run artifact layout and dataset hash

**Files:**
- Create: `src/alphaloop/contracts/artifacts.py`
- Modify: `src/alphaloop/contracts/__init__.py`
- Test: `tests/contracts/test_artifacts.py`

**Interfaces:**
- Consumes: none
- Produces: `RunLayout`, `DatasetRef`, `hash_bytes(data: bytes) -> str`, `require_dataset(ref, blob) -> None` (raises `DatasetMismatchError`)

- [ ] **Step 1: Write failing artifact tests**

Create `tests/contracts/test_artifacts.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from alphaloop.contracts.artifacts import (
    DatasetMismatchError,
    DatasetRef,
    RunLayout,
    hash_bytes,
    require_dataset,
)


def test_run_layout_paths(tmp_path: Path):
    layout = RunLayout(tmp_path / "runs" / "rid")
    assert layout.research_spec.name == "research-spec.yaml"
    assert layout.manifest.name == "manifest.yaml"
    assert layout.trial_ledger.name == "trial-ledger.jsonl"
    assert layout.checkpoints.name == "checkpoints"
    assert layout.candidates.name == "candidates.parquet"
    assert layout.evidence.name == "evidence"
    assert layout.recommendations.name == "recommendations.json"
    assert layout.report.name == "report.md"


def test_require_dataset_accepts_matching_hash():
    blob = b"ohlcv-v1"
    ref = DatasetRef(dataset_id="ds_test", sha256=hash_bytes(blob))
    require_dataset(ref, blob)


def test_require_dataset_fails_closed_on_mismatch():
    ref = DatasetRef(dataset_id="ds_test", sha256=hash_bytes(b"a"))
    with pytest.raises(DatasetMismatchError):
        require_dataset(ref, b"b")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/contracts/test_artifacts.py -v`

Expected: FAIL with import error.

- [ ] **Step 3: Implement artifact layout**

Create `src/alphaloop/contracts/artifacts.py`:

```python
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


class DatasetMismatchError(ValueError):
    """Raised when snapshot bytes do not match the recorded hash."""


@dataclass(frozen=True)
class DatasetRef:
    dataset_id: str
    sha256: str


@dataclass(frozen=True)
class RunLayout:
    run_dir: Path

    @property
    def research_spec(self) -> Path:
        return self.run_dir / "research-spec.yaml"

    @property
    def manifest(self) -> Path:
        return self.run_dir / "manifest.yaml"

    @property
    def trial_ledger(self) -> Path:
        return self.run_dir / "trial-ledger.jsonl"

    @property
    def checkpoints(self) -> Path:
        return self.run_dir / "checkpoints"

    @property
    def candidates(self) -> Path:
        return self.run_dir / "candidates.parquet"

    @property
    def evidence(self) -> Path:
        return self.run_dir / "evidence"

    @property
    def recommendations(self) -> Path:
        return self.run_dir / "recommendations.json"

    @property
    def report(self) -> Path:
        return self.run_dir / "report.md"


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require_dataset(ref: DatasetRef, blob: bytes) -> None:
    digest = hash_bytes(blob)
    if digest != ref.sha256:
        raise DatasetMismatchError(
            f"dataset {ref.dataset_id} hash mismatch: expected {ref.sha256}, got {digest}"
        )
```

Export the new names.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/contracts/test_artifacts.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/contracts/artifacts.py src/alphaloop/contracts/__init__.py \
  tests/contracts/test_artifacts.py
git commit -m "feat: add run artifact layout and dataset hash contract"
```

---

### Task 6: Bundle schema, canonical hash, and export guard

**Files:**
- Create: `src/alphaloop/contracts/bundle.py`
- Modify: `src/alphaloop/contracts/__init__.py`
- Create: `src/alphaloop/cli/export.py`
- Modify: `src/alphaloop/cli/main.py`
- Test: `tests/contracts/test_bundle.py`
- Test: `tests/cli/test_export.py`

**Interfaces:**
- Consumes: `ResearchOutcome`, `StrategyCandidateBundle`
- Produces: `canonical_hash(payload: dict) -> str`, `bundle_from_payload(payload) -> StrategyCandidateBundle`, `assert_exportable(outcome, candidate_ids, candidate_id)`, `cli export`

- [ ] **Step 1: Write failing bundle and CLI tests**

Create `tests/contracts/test_bundle.py`:

```python
from __future__ import annotations

import pytest

from alphaloop.contracts.bundle import (
    ExportNotAllowed,
    assert_exportable,
    bundle_from_payload,
    canonical_hash,
)
from alphaloop.contracts.status import ResearchOutcome


def _payload() -> dict:
    return {
        "schema_version": "1",
        "strategy_dsl": {"kind": "momentum_12_1", "lookback": 252},
        "market_profile": "us-equity-daily",
        "parameters": {"lookback": 252},
        "risk_envelope": {"max_weight": 0.05},
        "lineage": {"run_id": "r1", "candidate_id": "c1"},
        "conformance": {
            "inputs": {"as_of": "2024-01-02"},
            "expected_weights": {"AAPL": 0.01, "MSFT": 0.02},
        },
        "registry_uri": None,
    }


def test_hash_is_order_independent():
    a = canonical_hash(_payload())
    flipped = dict(reversed(list(_payload().items())))
    assert canonical_hash(flipped) == a


def test_bundle_id_is_derived_from_hash():
    bundle = bundle_from_payload(_payload())
    digest = canonical_hash(_payload())
    assert bundle.content_hash == digest
    assert bundle.bundle_id == "b_" + digest[:32]
    assert bundle.registry_uri is None


def test_export_requires_found_and_known_candidate():
    assert_exportable(ResearchOutcome.FOUND, ("c1",), "c1")
    with pytest.raises(ExportNotAllowed):
        assert_exportable(ResearchOutcome.NO_EVIDENCE, ("c1",), "c1")
    with pytest.raises(ExportNotAllowed):
        assert_exportable(ResearchOutcome.FOUND, ("c1",), "c2")
```

Create `tests/cli/test_export.py`:

```python
from __future__ import annotations

from alphaloop.cli.main import main


def test_export_without_found_returns_nonzero(tmp_path, capsys):
    rc = main(
        [
            "export",
            "c1",
            "--outcome",
            "NO_EVIDENCE",
            "--candidate-ids",
            "c1",
            "--output",
            str(tmp_path / "strategy.asb"),
        ]
    )
    assert rc == 2
    err = capsys.readouterr().err
    assert "FOUND" in err
```

Phase 1 `export` takes explicit `--outcome` and `--candidate-ids` so it can enforce the guard before sealed runs exist. Later phases will read those fields from artifacts and drop the flags.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/contracts/test_bundle.py tests/cli/test_export.py -v`

Expected: FAIL with import / invalid choice errors.

- [ ] **Step 3: Implement bundle + CLI guard**

Create `src/alphaloop/contracts/bundle.py`:

```python
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

from .status import ResearchOutcome


class ExportNotAllowed(ValueError):
    """Raised when a candidate cannot be exported as a bundle."""


@dataclass(frozen=True)
class StrategyCandidateBundle:
    schema_version: str
    bundle_id: str
    content_hash: str
    strategy_dsl: dict
    market_profile: str
    parameters: dict
    risk_envelope: dict
    lineage: dict
    conformance: dict
    registry_uri: Optional[str]


def canonical_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def bundle_from_payload(payload: Mapping[str, Any]) -> StrategyCandidateBundle:
    digest = canonical_hash(payload)
    registry = payload.get("registry_uri")
    return StrategyCandidateBundle(
        schema_version=str(payload["schema_version"]),
        bundle_id="b_" + digest[:32],
        content_hash=digest,
        strategy_dsl=dict(payload["strategy_dsl"]),
        market_profile=str(payload["market_profile"]),
        parameters=dict(payload["parameters"]),
        risk_envelope=dict(payload["risk_envelope"]),
        lineage=dict(payload["lineage"]),
        conformance=dict(payload["conformance"]),
        registry_uri=None if registry in (None, "") else str(registry),
    )


def assert_exportable(
    outcome: ResearchOutcome,
    candidate_ids: Sequence[str],
    candidate_id: str,
) -> None:
    if outcome is not ResearchOutcome.FOUND:
        raise ExportNotAllowed("export requires research outcome FOUND")
    if candidate_id not in set(candidate_ids):
        raise ExportNotAllowed(f"candidate not in sealed evidence: {candidate_id}")
```

Create `src/alphaloop/cli/export.py`:

```python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from alphaloop.contracts.bundle import ExportNotAllowed, assert_exportable
from alphaloop.contracts.status import ResearchOutcome


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "export",
        help="export a FOUND candidate as an immutable .asb bundle",
    )
    parser.add_argument("candidate_id")
    parser.add_argument("--outcome", required=True, help="sealed research outcome")
    parser.add_argument(
        "--candidate-ids",
        required=True,
        help="comma-separated sealed candidate ids",
    )
    parser.add_argument("--output", "-o", required=True)
    parser.set_defaults(func=run_export)


def run_export(args: argparse.Namespace) -> int:
    try:
        outcome = ResearchOutcome(args.outcome)
    except ValueError:
        print(f"error: unknown outcome {args.outcome}", file=sys.stderr)
        return 2
    sealed_ids = tuple(item for item in args.candidate_ids.split(",") if item)
    try:
        assert_exportable(outcome, sealed_ids, args.candidate_id)
    except ExportNotAllowed as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    destination = Path(args.output)
    destination.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "candidate_id": args.candidate_id,
                "outcome": outcome.value,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    print(destination)
    return 0
```

In `src/alphaloop/cli/main.py`, import `register as register_export` from `.export`, call `register_export(subparsers)` next to the other subcommands, and dispatch:

```python
elif parsed.command == "export":
    return parsed.func(parsed)
```

Export bundle names from `contracts/__init__.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/contracts/test_bundle.py tests/cli/test_export.py tests/test_cli.py tests/test_package_identity.py -v`

Expected: PASS. `export` appears in CLI help.

- [ ] **Step 5: Add an import-graph guard**

Append to `tests/test_package_identity.py` (do not re-import `Path`; it is already imported):

```python
def test_contracts_do_not_import_live():
    root = ROOT / "src" / "alphaloop" / "contracts"
    for path in root.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "alphaloop.live" not in text
        assert "from ..live" not in text
```

Run: `python3 -m pytest tests/test_package_identity.py::test_contracts_do_not_import_live -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/alphaloop/contracts/bundle.py src/alphaloop/contracts/__init__.py \
  src/alphaloop/cli/export.py src/alphaloop/cli/main.py \
  tests/contracts/test_bundle.py tests/cli/test_export.py tests/test_package_identity.py
git commit -m "feat: add strategy bundle contract and export guard"
```

---

### Task 7: Regression sweep and docs pointers

**Files:**
- Modify: `docs/requirements/product-positioning-requirements.md` (section 13 link)
- Modify: `mkdocs.yml`

**Interfaces:**
- Consumes: all prior tasks
- Produces: green unit suite excluding integration tests; docs nav entry for the refactor design

- [ ] **Step 1: Run the unit suite**

Run: `python3 -m pytest tests/ -m "not integration" -q`

Expected: PASS, including new `tests/contracts/` and identity tests. Do not fail on previously skipped integration tests.

- [ ] **Step 2: Link the design from requirements and mkdocs**

In `docs/requirements/product-positioning-requirements.md` section 13, after the six-item list, add:

```markdown
Refactor mapping and file boundaries:
[`docs/plans/overnight-research-lab-refactor.md`](overnight-research-lab-refactor.md).

Phase 1 implementation plan:
[`docs/plans/2026-08-18-overnight-lab-phase1-contracts.md`](2026-08-18-overnight-lab-phase1-contracts.md).
```

In `mkdocs.yml` under `Design docs`, add:

```yaml
    - Overnight lab refactor: plans/overnight-research-lab-refactor.md
```

- [ ] **Step 3: Rebuild docs**

Run: `python3 -m mkdocs build --strict`

Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add docs/requirements/product-positioning-requirements.md mkdocs.yml
git commit -m "docs: link overnight-lab refactor design to requirements"
```
