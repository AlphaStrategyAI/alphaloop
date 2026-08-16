"""Unit tests for the v0.8 calibration dataset (R-Dataset).

Covers PRD § 3.1 acceptance criteria A-1.1 through A-1.8:

- A-1.1: dataset.jsonl exists and contains exactly 100 valid JSONL rows.
- A-1.2: every row has 3 ground-truth dims.
- A-1.3: meta shows ≥ 5 strategies, ≥ 3 asset classes, ≥ 3 periods,
         ≥ 2 languages.
- A-1.4: ≥ 20 "clearly bad" cases.
- A-1.5: inter_rater_alpha ≥ 0.70.
- A-1.6: SHA-256 round-trips.
- A-1.7: deterministic (same seed → byte-identical).
- A-1.8: no LLM API call in dataset build pipeline.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from alphaloop.calibration.dataset import (
    build_dataset,
    build_in_memory,
    dataset_sha256,
    load_dataset,
    save_dataset,
)
from alphaloop.calibration.schema import (
    DEFAULT_REVIEWER_IDS,
    DIMENSIONS,
    CalibrationCase,
    DatasetMeta,
    DimensionGroundTruth,
    ReviewerScore,
    case_id_for_index,
)


# ---------------------------------------------------------------------------
# A-1.1: 100 cases
# ---------------------------------------------------------------------------


def test_build_dataset_has_exactly_100_cases():
    """A-1.1: dataset.jsonl exists and contains exactly 100 valid rows."""
    cases, scores, meta = build_in_memory()
    assert len(cases) == 100
    assert len(scores) == 100 * 3 * 3  # 900 ratings
    assert meta.n_cases == 100


def test_save_load_roundtrip(tmp_path: Path):
    """A-1.1 + A-1.6: save + load + SHA round-trip."""
    jsonl = save_dataset(tmp_path)
    assert jsonl.is_file()
    # Load + verify SHA pinned.
    cases, meta = load_dataset(tmp_path)
    assert len(cases) == 100
    assert meta.n_cases == 100
    assert meta.dataset_sha256 == dataset_sha256(tmp_path)


def test_case_ids_canonical():
    """All case_ids follow calib_NNN pattern, no gaps."""
    cases, _, _ = build_in_memory()
    expected = {case_id_for_index(i) for i in range(100)}
    assert {c.case_id for c in cases} == expected


# ---------------------------------------------------------------------------
# A-1.2: every row has 3 dims, no nulls
# ---------------------------------------------------------------------------


def test_every_case_has_three_dimensions():
    """A-1.2: every row has 3 ground-truth dims (no null)."""
    cases, _, _ = build_in_memory()
    for c in cases:
        assert set(c.ground_truth.keys()) == set(DIMENSIONS)
        for dim in DIMENSIONS:
            gt = c.ground_truth[dim]
            assert isinstance(gt, DimensionGroundTruth)
            assert 1 <= gt.score <= 10
            assert gt.reviewer_ids  # non-empty
            assert gt.reviewer_scores  # non-empty


def test_every_dimension_in_jsonl_row(tmp_path: Path):
    """A-1.2: the on-disk JSONL row also has 3 dims per case."""
    save_dataset(tmp_path)
    raw = (tmp_path / "dataset.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(raw) == 100
    for line in raw:
        d = json.loads(line)
        assert set(d["ground_truth"].keys()) == set(DIMENSIONS)


# ---------------------------------------------------------------------------
# A-1.3: diversity matrix
# ---------------------------------------------------------------------------


def test_diversity_strategies_at_least_5():
    """A-1.3: ≥ 5 distinct strategies in meta."""
    _, _, meta = build_in_memory()
    assert len(meta.strategies) >= 5


def test_diversity_asset_classes_at_least_3():
    """A-1.3: ≥ 3 distinct asset classes."""
    _, _, meta = build_in_memory()
    assert len(meta.asset_classes) >= 3


def test_diversity_time_periods_at_least_3():
    """A-1.3: ≥ 3 distinct time periods."""
    _, _, meta = build_in_memory()
    assert len(meta.time_periods) >= 3


def test_diversity_languages_at_least_2():
    """A-1.3: ≥ 2 distinct languages (en + zh)."""
    _, _, meta = build_in_memory()
    assert "en" in meta.languages
    assert "zh" in meta.languages
    assert meta.languages["zh"] >= 10


# ---------------------------------------------------------------------------
# A-1.4: ≥ 20 "clearly bad" cases
# ---------------------------------------------------------------------------


def test_at_least_20_clearly_bad_cases():
    """A-1.4: ≥ 20 cases in the "clearly bad" stratum."""
    _, _, meta = build_in_memory()
    assert len(meta.degraded_cases) >= 20


# ---------------------------------------------------------------------------
# A-1.5: inter_rater_alpha ≥ 0.70
# ---------------------------------------------------------------------------


def test_inter_rater_alpha_at_least_0_70():
    """A-1.5: meta.inter_rater_alpha ≥ 0.70."""
    _, _, meta = build_in_memory()
    assert meta.inter_rater_alpha >= 0.70


# ---------------------------------------------------------------------------
# A-1.6: SHA-256 round-trip
# ---------------------------------------------------------------------------


def test_sha256_pinning_matches_bytes(tmp_path: Path):
    """A-1.6: dataset_sha256 matches SHA-256 of dataset.jsonl bytes."""
    save_dataset(tmp_path)
    meta = json.loads((tmp_path / "dataset.meta.json").read_text(encoding="utf-8"))
    raw_bytes = (tmp_path / "dataset.jsonl").read_bytes()
    import hashlib

    expected = hashlib.sha256(raw_bytes).hexdigest()
    assert meta["dataset_sha256"] == expected


def test_sha_pin_rejects_modified_dataset(tmp_path: Path):
    """Modifying dataset.jsonl after the meta is written must fail load."""
    save_dataset(tmp_path)
    p = tmp_path / "dataset.jsonl"
    p.write_bytes(p.read_bytes() + b"\n")
    try:
        load_dataset(tmp_path)
    except ValueError as e:
        assert "SHA mismatch" in str(e)
        return
    raise AssertionError("expected SHA mismatch to raise")


# ---------------------------------------------------------------------------
# A-1.7: determinism
# ---------------------------------------------------------------------------


def test_build_is_deterministic_with_same_seed():
    """A-1.7: same seed → byte-identical JSONL."""
    a, _, _ = build_in_memory(seed=42)
    b, _, _ = build_in_memory(seed=42)
    assert len(a) == len(b)
    for ca, cb in zip(a, b):
        assert ca.case_id == cb.case_id
        assert ca.report_markdown == cb.report_markdown
        for dim in DIMENSIONS:
            assert ca.ground_truth[dim].score == cb.ground_truth[dim].score


def test_different_seeds_change_output():
    """Different seeds produce different report bodies (sanity)."""
    a, _, _ = build_in_memory(seed=42)
    b, _, _ = build_in_memory(seed=99)
    # At least one case should differ.
    diffs = sum(
        1
        for ca, cb in zip(a, b)
        if ca.report_markdown != cb.report_markdown
    )
    assert diffs > 0


# ---------------------------------------------------------------------------
# A-1.8: no LLM API call in dataset build
# ---------------------------------------------------------------------------


def test_dataset_build_does_not_import_llm_clients():
    """A-1.8: dataset.py must NOT import LLM client modules."""
    src = Path(__file__).resolve().parents[2] / "src" / "alphaloop" / "calibration" / "dataset.py"
    text = src.read_text(encoding="utf-8")
    # Match import lines that would pull in an LLM client.
    forbidden = re.compile(r"^\s*(from|import)\s+.*(openai|anthropic|llm_judge|LLMJudgeClient)", re.MULTILINE)
    assert not forbidden.search(text), (
        f"dataset.py must not import LLM clients:\n{text[:400]}"
    )


def test_dataset_build_does_not_make_http_calls():
    """A-1.8: dataset.py must NOT use urllib."""
    src = Path(__file__).resolve().parents[2] / "src" / "alphaloop" / "calibration" / "dataset.py"
    text = src.read_text(encoding="utf-8")
    assert "urllib" not in text, "dataset.py must not use urllib"
    assert "requests" not in text, "dataset.py must not use requests"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def test_reviewer_count_is_three():
    """Default reviewer_ids is exactly 3 (PRD Story 1: 3 reviewers)."""
    assert len(DEFAULT_REVIEWER_IDS) == 3


def test_dataset_meta_round_trip():
    """DatasetMeta dataclass round-trips through dict."""
    meta = DatasetMeta(n_cases=10, strategies={"a": 10}, inter_rater_alpha=0.8)
    d = meta.to_dict()
    restored = DatasetMeta.from_dict(d)
    assert restored.n_cases == 10
    assert restored.strategies == {"a": 10}
    assert abs(restored.inter_rater_alpha - 0.8) < 1e-9