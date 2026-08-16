"""
Pydantic schemas for the v0.7.1 WebUI JSON API.

Mirrors v0.7's persisted TopPick / RunManifest dataclasses (in
loop.persistence) but as Pydantic models so FastAPI auto-generates
OpenAPI / JSON Schema.

All schemas round-trip through model_validate(model_dump()) — see
tests/test_webapi.py.
"""
from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator


class TopPick(BaseModel):
    """One row of top5.json — drives the TopFiveCard component."""

    rank: int = Field(..., ge=1, le=5)
    task_id: str
    strategy: str
    factor: str = ""
    params: dict[str, Any] = Field(default_factory=dict)
    dsr: float = Field(..., ge=0.0, le=1.0)
    sharpe: float
    cagr: float
    max_dd: float
    passes_all: bool
    one_line_thesis: str = ""


class RunSummary(BaseModel):
    """Header summary for a run."""

    rid: str
    started_at: str
    finished_at: Optional[str] = None
    elapsed_s: float = 0.0
    termination_reason: Optional[str] = None
    goal: str = ""


class RunListItem(BaseModel):
    """One entry in /api/runs list."""

    rid: str
    started_at: str
    elapsed_s: float = 0.0
    goal: str = ""


class RunManifest(BaseModel):
    """Full manifest.yaml contents."""

    run_id: str
    goal: str = ""
    seed: int = 0
    git_commit: str = ""
    llm_model: str = ""
    target_dsr: float = 0.0
    budget_usd: float = 0.0
    timeout_s: int = 0
    started_at: str = ""
    finished_at: Optional[str] = None
    termination_reason: Optional[str] = None
    estimated_cost_usd: float = 0.0
    task_count: int = 0


class TopFiveResponse(BaseModel):
    """Response of /api/runs/{rid}/top5."""

    rid: str
    top5: list[TopPick]
    goals: list[dict[str, str]] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)


class DiagnosticItem(BaseModel):
    """One Q1–Q7 diagnostic."""

    label: str
    value: float
    pass_: bool = Field(alias="pass")
    detail: str = ""

    class Config:
        populate_by_name = True


class StrategyDetailResponse(BaseModel):
    """Response of /api/runs/{rid}/strategies/{sid}."""

    rid: str
    sid: str
    pick: TopPick
    diagnostics: dict[str, DiagnosticItem]
    equity: list[float] = Field(default_factory=list)
    judge_summary: str = ""


class RadarPoint(BaseModel):
    axis: str
    value: float = Field(..., ge=0.0, le=1.0)
    category: str  # "math" | "stats" | "ai"


class BarPoint(BaseModel):
    label: str
    pass_rate: float = Field(..., ge=0.0, le=1.0)
    pass_count: int = 0
    total: int = 0
    category: str = "math"


class DiagnosticsResponse(BaseModel):
    """Response of /api/runs/{rid}/diagnostics."""

    rid: str
    manifest: RunManifest
    radar: list[RadarPoint]
    bar: list[BarPoint]
    compare_with: Optional[list[RadarPoint]] = None


class DagNode(BaseModel):
    id: str
    label: str
    description: str = ""
    status: str = "pending"  # "pending" | "running" | "done" | "failed"
    elapsed_s: Optional[float] = None


class DagEdge(BaseModel):
    from_: str = Field(alias="from")
    to: str

    class Config:
        populate_by_name = True


class ReplayResponse(BaseModel):
    """Response of /api/runs/{rid}/replay."""

    rid: str
    dag: dict[str, Any]  # {nodes: [DagNode], edges: [DagEdge]}
    timing: dict[str, float] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: str = "ok"
    runs_dir: str
    n_runs: int


class ErrorResponse(BaseModel):
    error: str
