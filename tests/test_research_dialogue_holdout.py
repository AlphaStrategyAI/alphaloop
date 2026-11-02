"""Sealed dialogue holdout harness.

The development corpora stay in dialogue_slot_corpus.json and
symbol_regression_corpus.json. This file replays a separate sealed subset.
It does not claim a 114/120 model score.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.research.holdout_runner import (
    DANGER_CLASSES,
    GROUPS,
    TARGET_PER_GROUP,
    TARGET_SESSIONS,
    THRESHOLD_TOTAL,
    harness_report,
    load_corpus,
    run_case,
)
from engine.research.holdout_seal import corpus_sha256

ROOT = Path(__file__).resolve().parent
CORPUS_PATH = ROOT / "data" / "dialogue_holdout_corpus.json"
SEAL_PATH = ROOT / "data" / "dialogue_holdout_seal.json"
DEV_SLOT = ROOT / "data" / "dialogue_slot_corpus.json"
DEV_SYMBOL = ROOT / "data" / "symbol_regression_corpus.json"


def _corpus() -> dict:
    return load_corpus(CORPUS_PATH)


def _cases() -> list[dict]:
    return list(_corpus()["cases"])


def test_holdout_is_separate_from_the_development_corpora() -> None:
    assert CORPUS_PATH != DEV_SLOT
    assert CORPUS_PATH != DEV_SYMBOL
    sealed = CORPUS_PATH.read_bytes()
    assert sealed != DEV_SLOT.read_bytes()
    assert sealed != DEV_SYMBOL.read_bytes()
    assert b"dialogue_slot_corpus" not in sealed


def test_seal_matches_the_corpus_bytes_and_is_not_a_model_score() -> None:
    seal = json.loads(SEAL_PATH.read_text(encoding="utf-8"))
    corpus = _corpus()
    assert seal["algorithm"] == "sha256"
    assert seal["corpus_sha256"] == corpus_sha256(CORPUS_PATH)
    assert seal["label"] == corpus["label"]
    assert seal["scored_against_model"] is False
    assert corpus["release_gate"]["scored_against_model"] is False
    assert seal["target_sessions"] == TARGET_SESSIONS
    assert seal["threshold_total"] == THRESHOLD_TOTAL
    assert "114/120" not in seal["claim"]
    assert seal["claim"] == "not scored"


def test_grouping_covers_every_planned_bucket_without_pretending_to_be_120() -> None:
    corpus = _corpus()
    cases = _cases()
    ids = [case["id"] for case in cases]
    assert len(ids) == len(set(ids))
    assert len(cases) < TARGET_SESSIONS
    assert [group["id"] for group in corpus["groups"]] == list(GROUPS)
    languages = {group: set() for group in GROUPS}
    templates: dict[str, set[str]] = {}
    authors: dict[str, set[str]] = {}
    for case in cases:
        assert case["group"] in GROUPS
        assert case["language"] in {"zh", "en"}
        languages[case["group"]].add(case["language"])
        templates.setdefault(case["intent_template"], set()).add(case["group"])
        authors.setdefault(case["intent_template"], set()).add(case["author_bucket"])
        turn = case["turns"][0]
        assert turn["utterance"]
        expect = turn["expect"]
        assert "allowed_tools" in expect
        assert "forbidden_actions" in expect
    for group, seen in languages.items():
        assert seen == {"zh", "en"}, group
    for template, groups in templates.items():
        assert len(groups) == 1, template
        assert len(authors[template]) == 1, template
    report = harness_report(corpus)
    assert report["model_scored"] is False
    assert report["claim"] == "not scored"
    assert report["sessions_target"] == TARGET_SESSIONS
    assert report["per_group_target"] == TARGET_PER_GROUP
    assert all(count < TARGET_PER_GROUP for count in report["per_group_sealed"].values())


def test_every_danger_class_has_both_languages() -> None:
    found: dict[str, set[str]] = {name: set() for name in DANGER_CLASSES}
    for case in _cases():
        danger = case.get("danger_class")
        if not danger:
            continue
        assert danger in found
        found[danger].add(case["language"])
    for name, languages in found.items():
        assert languages == {"zh", "en"}, name


@pytest.mark.parametrize("case", _cases(), ids=lambda case: case["id"])
def test_holdout_case(case: dict, tmp_path: Path) -> None:
    run_case(case, tmp_path)


def test_danger_interception_on_the_sealed_subset_is_complete(tmp_path: Path) -> None:
    danger = [case for case in _cases() if case.get("danger_class")]
    assert danger
    blocked = 0
    for case in danger:
        run_case(case, tmp_path)
        blocked += 1
    assert blocked == len(danger)
    assert blocked / len(danger) == 1.0
