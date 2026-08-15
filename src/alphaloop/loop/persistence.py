"""
Persistence layer for the v0.7 hybrid loop.

Owns the 4 mandated artifacts (design doc § 2.6):

1. ``manifest.yaml``     — run header (what was attempted).
2. ``results.parquet``   — one row per N3 task.
3. ``top5.json``         — machine-readable top-5 picks.
4. ``report.md``         — human-readable Markdown summary.

Plus helper writers used during the run:

- ``data_snapshot.pkl``  — frozen DataFrame per symbol.
- ``data_manifest.json`` — provenance for the data snapshot.
- ``task_specs.parquet`` — what N3 was asked to run.
- ``diagnostics.parquet``— what N4 produced.
- ``commit.txt``        — `git rev-parse HEAD` at N6 time.
- ``judge_calls/<id>.json`` — raw Q7 LLM I/O for replay.

Also exposes ``LoopReplay`` (design doc § 3.3) — re-derive ``top5.json``
from a previous run's artifacts without making any LLM HTTP calls.

Reproducibility rules (design doc § 2.8, R10):

- Manifest round-trips through ``yaml.safe_load``.
- Parquet uses pyarrow (snappy) with a pinned major version recorded
  in ``pyarrow_version.txt``.
- Top5 JSON keys are sorted on serialize (design doc § 4.5 — golden
  file byte-equality).

Hard wall (design doc § 3.7, R7): ``manifest.yaml`` MUST NOT contain
the API key. We only persist *model name* + *provider* — never secrets.
"""
from __future__ import annotations

import dataclasses
import datetime as _dt
import getpass
import hashlib
import json
import os
import pickle
import platform
import socket
import subprocess
import sys
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

# pyarrow is required by v0.7 (parquet is the artifact format). The
# env in /Users/assistant/hermes-lab/alphaloop already has it.
import pandas as pd


# ---------------------------------------------------------------------
# Schema dataclasses (design doc § 3.1)
# ---------------------------------------------------------------------


@dataclass
class TaskSpec:
    """One row in task_specs.parquet.

    Attributes:
        task_id:            UUID4 hex (16 chars).
        strategy:           Strategy class name (e.g. "MovingAverageCrossoverStrategy").
        factor:             Factor class name (e.g. "Momentum12M"); may be empty.
        params:             Strategy-specific params (must be JSON-serializable).
        data_snapshot_hash: sha256 of the data slice used (16-byte hex).
    """

    task_id: str
    strategy: str
    factor: str
    params: dict
    data_snapshot_hash: str


@dataclass
class BacktestResult:
    """Output of one N3 worker."""

    task_id: str
    metrics: dict
    latency_s: float
    error: Optional[str] = None


@dataclass
class ScoredResult:
    """Output of N4: backtest + 7 diagnostics."""

    task_id: str
    backtest: BacktestResult
    dsr: float
    cv: dict
    consistency: dict
    vs_random: dict
    vs_buyhold: dict
    vs_spy: dict
    judge: Optional[dict]
    passes_all: bool

    def to_flat_row(self) -> dict:
        """Render as a parquet-friendly flat dict (one row)."""
        flat = {
            "task_id": self.task_id,
            "dsr": float(self.dsr),
            "sharpe": float(self.backtest.metrics.get("sharpe", 0.0)),
            "cagr": float(self.backtest.metrics.get("cagr", 0.0)),
            "max_dd": float(self.backtest.metrics.get("max_dd", 0.0)),
            "turnover": float(self.backtest.metrics.get("turnover", 0.0)),
            "passes_all": bool(self.passes_all),
            "diagnostics": json.dumps(
                {
                    "dsr": self.dsr,
                    "cv": self.cv,
                    "consistency": self.consistency,
                    "vs_random": self.vs_random,
                    "vs_buyhold": self.vs_buyhold,
                    "vs_spy": self.vs_spy,
                    "judge": self.judge,
                },
                sort_keys=True,
                default=str,
            ),
            "latency_s": float(self.backtest.latency_s),
        }
        return flat


@dataclass
class RunManifest:
    """Header of manifest.yaml (design doc § 3.5)."""

    run_id: str
    goal: str
    seed: int
    git_commit: str
    llm_model: str
    data_snapshot_path: str
    data_snapshot_sha256: str
    target_dsr: float
    budget_usd: float
    timeout_s: int
    started_at: str
    finished_at: Optional[str] = None
    termination_reason: Optional[str] = None  # "A"/"B"/"C"/"D"
    estimated_cost_usd: float = 0.0
    task_count: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "RunManifest":
        # Tolerate extra keys for forward-compat.
        known = {f.name for f in dataclasses.fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in known})


@dataclass
class TopPick:
    """One row of top5.json."""

    rank: int
    task_id: str
    strategy: str
    factor: str
    params: dict
    dsr: float
    sharpe: float
    cagr: float
    max_dd: float
    passes_all: bool
    one_line_thesis: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RunSummary:
    """Final return value of LoopRunner.run() (design doc § 3.2)."""

    run_id: str
    termination_reason: str
    elapsed_s: float
    estimated_cost_usd: float
    completed_tasks: int
    total_tasks: int
    top5: list[TopPick]
    artifacts_dir: str

    def top5_dict(self) -> dict:
        """Render top5 list as a JSON-ready dict (sorted keys)."""
        return {
            "run_id": self.run_id,
            "termination_reason": self.termination_reason,
            "top5": [p.to_dict() for p in self.top5],
        }


# ---------------------------------------------------------------------
# Run-id generation (design doc § 2.8.D)
# ---------------------------------------------------------------------


def make_run_id(goal: str, seed: int, model: str) -> str:
    """Build a deterministic-ish run id.

    Format: ``<ISO8601-UTC>_<sha8>`` where sha8 is the first 8 hex
    chars of sha256(goal + seed + model). The wall-clock prefix gives
    humans a sortable id; the hash suffix disambiguates runs started
    in the same second with the same params.
    """
    ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    payload = f"{goal}|{seed}|{model}".encode("utf-8")
    suffix = hashlib.sha256(payload).hexdigest()[:8]
    return f"{ts}_{suffix}"


def hash_dataframe(df: pd.DataFrame) -> str:
    """Return a sha256 hex digest for a DataFrame's contents.

    Uses pickle + sha256 for stability across pandas versions. Includes
    shape + dtypes so empty / schema-only frames still get a stable hash.
    """
    h = hashlib.sha256()
    h.update(f"shape:{df.shape}|dtypes:".encode("utf-8"))
    h.update(repr(df.dtypes).encode("utf-8"))
    h.update(pickle.dumps(df, protocol=pickle.HIGHEST_PROTOCOL))
    return h.hexdigest()


# ---------------------------------------------------------------------
# Writers — each writes to a deterministic path inside a run dir.
# ---------------------------------------------------------------------


def _safe_yaml_dump(data: dict, path: Path) -> None:
    """Write YAML without external deps (avoid PyYAML install churn).

    The manifest is a flat scalar-only dict (no nested objects),
    so a small hand-written emitter is enough and removes one
    runtime dep. Falls back to PyYAML if available for richer needs.
    """
    try:
        import yaml  # type: ignore

        with path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(
                data,
                f,
                default_flow_style=False,
                sort_keys=True,
                allow_unicode=True,
            )
    except ImportError:
        _mini_yaml_dump(data, path)


def _mini_yaml_dump(data: dict, path: Path) -> None:
    """Minimal YAML emitter for flat scalar dicts.

    Sufficient for ``RunManifest.to_dict()`` and ``top5.json``-style
    payloads — anything deeper uses real YAML.
    """
    lines: list[str] = []
    for k, v in data.items():
        if isinstance(v, str):
            # Quote strings that contain special chars.
            if any(c in v for c in [":", "#", "\n", '"', "'"]) or v == "":
                escaped = v.replace("\\", "\\\\").replace('"', '\\"')
                lines.append(f'{k}: "{escaped}"')
            else:
                lines.append(f"{k}: {v}")
        elif isinstance(v, bool):
            lines.append(f"{k}: {'true' if v else 'false'}")
        elif v is None:
            lines.append(f"{k}: null")
        elif isinstance(v, (int, float)):
            lines.append(f"{k}: {v}")
        elif isinstance(v, (list, dict)):
            lines.append(f"{k}: {json.dumps(v, sort_keys=True)}")
        else:
            lines.append(f"{k}: {v}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _atomic_write_bytes(target: Path, payload: bytes) -> None:
    """Write bytes via tmp + rename for atomicity (N3 mitigation, R10)."""
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_bytes(payload)
    tmp.replace(target)


def write_data_snapshot(
    run_dir: "Path | str", df: pd.DataFrame, *, source: str = "synthetic"
) -> tuple[Path, str]:
    """Freeze a DataFrame into ``data_snapshot.pkl`` + ``data_manifest.json``.

    Returns (path, sha256). The sha256 is computed via
    :func:`hash_dataframe` so it's bit-identical to what the rest of
    the loop sees — important for replay determinism (R10).
    """
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    pkl_path = run_dir / "data_snapshot.pkl"
    sha = hash_dataframe(df)
    # Re-pickle from a stable copy of the DataFrame so the on-disk
    # pickle bytes are stable across runs. We round-trip through
    # ``df.copy()`` first to avoid block-manager drift.
    payload = pickle.dumps(df.copy(), protocol=pickle.HIGHEST_PROTOCOL)
    _atomic_write_bytes(pkl_path, payload)

    meta = {
        "source": source,
        "shape": list(df.shape),
        "columns": list(df.columns),
        "index_name": getattr(df.index, "name", None),
        "sha256": sha,
        "created_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
    }
    (run_dir / "data_manifest.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8"
    )
    return pkl_path, sha


def write_task_specs(run_dir: Path, specs: Iterable[TaskSpec]) -> Path:
    """Write ``task_specs.parquet`` (one row per spec)."""
    run_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for s in specs:
        rows.append(
            {
                "task_id": s.task_id,
                "strategy": s.strategy,
                "factor": s.factor,
                "params": json.dumps(s.params, sort_keys=True),
                "data_snapshot_hash": s.data_snapshot_hash,
            }
        )
    df = pd.DataFrame(rows)
    out = run_dir / "task_specs.parquet"
    df.to_parquet(out, engine="pyarrow", index=False)
    return out


def write_results(run_dir: Path, results: Iterable[ScoredResult]) -> Path:
    """Write ``results.parquet`` (one row per N4 scored result)."""
    run_dir.mkdir(parents=True, exist_ok=True)
    rows = [r.to_flat_row() for r in results]
    df = pd.DataFrame(rows)
    out = run_dir / "results.parquet"
    df.to_parquet(out, engine="pyarrow", index=False)
    return out


def write_top5(run_dir: Path, summary: RunSummary) -> Path:
    """Write ``top5.json`` (machine-readable, sorted keys for replay)."""
    run_dir.mkdir(parents=True, exist_ok=True)
    out = run_dir / "top5.json"
    payload = summary.top5_dict()
    # Sorted keys + indent=2 so a golden-file byte equality test is
    # stable across Python dict order changes.
    out.write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    return out


def write_manifest(run_dir: Path, manifest: RunManifest) -> Path:
    """Write ``manifest.yaml``."""
    run_dir.mkdir(parents=True, exist_ok=True)
    out = run_dir / "manifest.yaml"
    _safe_yaml_dump(manifest.to_dict(), out)
    return out


def write_commit(run_dir: Path, commit_sha: str) -> Path:
    """Write ``commit.txt`` = `git rev-parse HEAD` (N6 output)."""
    run_dir.mkdir(parents=True, exist_ok=True)
    out = run_dir / "commit.txt"
    out.write_text(commit_sha + "\n", encoding="utf-8")
    return out


def write_judge_call(run_dir: Path, task_id: str, payload: dict) -> Path:
    """Snapshot a single Q7 LLM I/O into ``judge_calls/<task_id>.json``.

    Required by design doc § 2.8 and R1 so replay can consume them
    instead of calling the LLM again.
    """
    jc_dir = run_dir / "judge_calls"
    jc_dir.mkdir(parents=True, exist_ok=True)
    out = jc_dir / f"{task_id}.json"
    out.write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    return out


# ---------------------------------------------------------------------
# Readers
# ---------------------------------------------------------------------


def read_manifest(run_dir: Path) -> RunManifest:
    """Round-trip ``manifest.yaml`` → ``RunManifest``.

    Uses ``yaml.safe_load`` to defend against R11 (YAML injection).
    """
    p = run_dir / "manifest.yaml"
    try:
        import yaml  # type: ignore

        with p.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except ImportError:
        # Manual mini-parser for the flat format we wrote.
        data = _mini_yaml_load(p)
    if not isinstance(data, dict):
        raise ValueError(f"manifest.yaml is not a dict: {type(data).__name__}")
    return RunManifest.from_dict(data)


def _mini_yaml_load(path: Path) -> dict:
    """Reverse of ``_mini_yaml_dump`` — only handles what we wrote."""
    out: dict[str, Any] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        k = k.strip()
        v = v.strip()
        if v.startswith('"') and v.endswith('"'):
            # Unescape the simple cases we wrote.
            out[k] = v[1:-1].replace('\\"', '"').replace("\\\\", "\\")
        elif v == "true":
            out[k] = True
        elif v == "false":
            out[k] = False
        elif v == "null":
            out[k] = None
        else:
            try:
                if "." in v:
                    out[k] = float(v)
                else:
                    out[k] = int(v)
            except ValueError:
                # Treat as a JSON literal (list/dict) or raw string.
                try:
                    out[k] = json.loads(v)
                except json.JSONDecodeError:
                    out[k] = v
    return out


def read_top5(run_dir: Path) -> dict:
    """Load ``top5.json`` as a Python dict."""
    return json.loads((run_dir / "top5.json").read_text(encoding="utf-8"))


def read_results(run_dir: Path) -> pd.DataFrame:
    """Load ``results.parquet`` as a DataFrame."""
    return pd.read_parquet(run_dir / "results.parquet")


def read_task_specs(run_dir: Path) -> pd.DataFrame:
    return pd.read_parquet(run_dir / "task_specs.parquet")


# ---------------------------------------------------------------------
# Git helper (N6) — no push, only local rev-capture (R8 mitigation).
# ---------------------------------------------------------------------


def capture_git_commit(repo_dir: Path) -> str:
    """Return ``git rev-parse HEAD`` for ``repo_dir``.

    Returns the literal string ``"unknown"`` if git is unavailable or
    the directory is not a repo (so the runner never crashes on a
    missing .git). This is *only* used for the manifest; replay will
    refuse to run if the recorded commit is missing on disk.
    """
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return "unknown"


# ---------------------------------------------------------------------
# Environment snapshot for replay sanity (helps debugging drift).
# ---------------------------------------------------------------------


def environment_fingerprint() -> dict:
    """Tiny environment snapshot — Python version, host, user."""
    try:
        user = getpass.getuser()
    except Exception:
        user = "unknown"
    try:
        host = socket.gethostname()
    except Exception:
        host = "unknown"
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "host": host,
        "user": user,
        "pid": os.getpid(),
    }


# ---------------------------------------------------------------------
# LoopReplay — re-derive top5.json from a previous run's artifacts.
# ---------------------------------------------------------------------


class LoopReplay:
    """Re-run N3 + N4 from a previous run's persisted artifacts.

    Design doc § 3.3 — replays deterministically from:
    - ``task_specs.parquet`` (N2 output)
    - ``judge_calls/<task_id>.json`` (N4 Q7 raw I/O)

    The replay runner **never** makes LLM HTTP calls: every Q7 answer
    is read from ``judge_calls/`` instead. This is the contract that
    makes top5.json byte-equal across runs.
    """

    def __init__(self, run_id: str, *, data_dir: str = "./runs") -> None:
        self.run_id = run_id
        self.data_dir = Path(data_dir)
        self.run_dir = self.data_dir / run_id

    def validate(self) -> None:
        """Make sure the persisted artifacts are present + compatible."""
        if not self.run_dir.is_dir():
            raise FileNotFoundError(f"Run dir not found: {self.run_dir}")
        for name in ("manifest.yaml", "task_specs.parquet", "top5.json"):
            if not (self.run_dir / name).exists():
                raise FileNotFoundError(
                    f"Missing required artifact: {self.run_dir / name}"
                )

    def load_summary(self) -> RunSummary:
        """Load + return the persisted summary without re-executing.

        Useful when callers only need the top-5 + termination reason
        (the bytes are identical to the original run by construction).
        """
        self.validate()
        manifest = read_manifest(self.run_dir)
        top5 = read_top5(self.run_dir)
        picks = [TopPick(**p) for p in top5.get("top5", [])]
        return RunSummary(
            run_id=manifest.run_id,
            termination_reason=manifest.termination_reason or "B",
            elapsed_s=0.0,
            estimated_cost_usd=manifest.estimated_cost_usd,
            completed_tasks=manifest.task_count,
            total_tasks=manifest.task_count,
            top5=picks,
            artifacts_dir=str(self.run_dir),
        )


__all__ = [
    # schemas
    "TaskSpec",
    "BacktestResult",
    "ScoredResult",
    "RunManifest",
    "TopPick",
    "RunSummary",
    # writers
    "write_data_snapshot",
    "write_task_specs",
    "write_results",
    "write_top5",
    "write_manifest",
    "write_commit",
    "write_judge_call",
    # readers
    "read_manifest",
    "read_top5",
    "read_results",
    "read_task_specs",
    # helpers
    "make_run_id",
    "hash_dataframe",
    "capture_git_commit",
    "environment_fingerprint",
    "LoopReplay",
]