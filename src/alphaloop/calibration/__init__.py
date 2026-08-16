"""alphaloop.calibration — v0.8 calibration infrastructure.

This package implements the 4 features from
`docs/requirements/v08-requirements.md`:

- **R-Dataset** (submodule `dataset`, `reviewers`, `schema`):
  build and load the 100-case ground-truth dataset.
- **R-Accuracy** (submodule `accuracy`, `cli`):
  compute per-dimension accuracy metrics + the release gate.
- **R-Drift** (submodule `drift`):
  regression test that catches 10%+ drift vs the v0.8 golden file.
- **R-Prompt** (submodule `prompt_registry`, plus modifications to
  `judge.prompts`): track and compare prompt versions.

Public surface (importable from `alphaloop.calibration`):

    from alphaloop.calibration import (
        # schema
        BacktestReport, ReviewerScore, CalibrationCase, DatasetMeta,
        # dataset
        load_dataset, dataset_sha256,
        # accuracy
        compute_pearson, compute_spearman, compute_mae,
        compute_agreement, compute_confusion_matrix,
        gate_v1_release, CalibrationReport,
        # drift
        DriftReport, compare_to_golden, compute_drift,
        should_block_release,
        # prompt registry
        PromptRegistry, get_prompt, list_versions, register_version,
    )

The package is intentionally self-contained: it imports `judge`,
`diagnostic.judge`, and stdlib only. No new third-party runtime deps.
"""
from .accuracy import (
    CalibrationReport,
    compute_agreement,
    compute_confusion_matrix,
    compute_mae,
    compute_pearson,
    compute_spearman,
    gate_v1_release,
)
from .dataset import dataset_sha256, load_dataset
from .drift import (
    DriftReport,
    compare_to_golden,
    compute_drift,
    should_block_release,
)
from .prompt_registry import (
    PromptRegistry,
    get_prompt,
    list_versions,
    register_version,
)
from .reviewers import (
    median_score,
    resolve_conflicts,
    reviewer_scores_to_ground_truth,
)
from .schema import (
    BacktestReport,
    CalibrationCase,
    DatasetMeta,
    DimensionGroundTruth,
    ReviewerScore,
)

__all__ = [
    # schema
    "BacktestReport",
    "CalibrationCase",
    "DatasetMeta",
    "DimensionGroundTruth",
    "ReviewerScore",
    # dataset
    "load_dataset",
    "dataset_sha256",
    # reviewers
    "median_score",
    "resolve_conflicts",
    "reviewer_scores_to_ground_truth",
    # accuracy
    "compute_pearson",
    "compute_spearman",
    "compute_mae",
    "compute_agreement",
    "compute_confusion_matrix",
    "gate_v1_release",
    "CalibrationReport",
    # drift
    "compute_drift",
    "should_block_release",
    "compare_to_golden",
    "DriftReport",
    # prompt registry
    "PromptRegistry",
    "get_prompt",
    "list_versions",
    "register_version",
]