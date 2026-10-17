"""Data root contract (`docs/requirements/paths-contract.md`)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.research.data_paths import APP_DATA_DIR_NAME, resolve_data_root

FIXTURE_PATH = Path("tests/fixtures/data_root_cases.json")


def load_cases() -> list[dict]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", load_cases(), ids=lambda c: c["id"])
def test_resolve_data_root_fixture(case: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALPHALOOP_DATA_ROOT", raising=False)
    for key, value in case.get("env", {}).items():
        monkeypatch.setenv(key, value)
    root = resolve_data_root()
    if "expected_data_root" in case:
        assert root == Path(case["expected_data_root"])
    else:
        assert case["expected_suffix"] in str(root)
        assert APP_DATA_DIR_NAME in str(root)


def test_paths_contract_doc_exists() -> None:
    doc = Path("docs/requirements/paths-contract.md").read_text(encoding="utf-8")
    assert "ALPHALOOP_DATA_ROOT" in doc
    assert "research.db" in doc
    assert "owner.json" in doc
