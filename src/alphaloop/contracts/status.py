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
