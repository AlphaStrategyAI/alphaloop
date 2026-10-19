"""Verifier dispatch and preset seeding are keyed by (method id, revision)."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from engine.research.methods import _insert_preset_if_missing, seed_preset_methods
from engine.research.models import MethodDefinition, MethodRef
from engine.research.store import SQLiteStore
from engine.verifiers import UNKNOWN_METHOD_RULE, run_verifiers
from tests.test_verifiers import passing_report, spec

NOW = datetime(2026, 6, 1, tzinfo=UTC)


def test_v1_definitions_still_dispatch_as_v1() -> None:
    result = run_verifiers(passing_report(), spec())
    by_id = {item.verifier_id: item for item in result.results}
    assert by_id["scorecard.market"].revision == "scorecard-v1"
    assert by_id["scorecard.market"].rule == (
        "sharpe_oos > 0 and excess_ann > 0 and max_drawdown >= max_drawdown_floor"
    )
    assert by_id["scorecard.market"].values["sharpe_oos"] == pytest.approx(0.7)
    assert by_id["scorecard.market"].values["excess_ann"] == pytest.approx(0.04)
    assert by_id["scorecard.market"].values["max_drawdown"] == pytest.approx(-0.20)
    assert by_id["overfit.walk"].revision == "walk-v1"
    assert by_id["overfit.walk"].rule == "sharpe_oos > 0 and sharpe_oos / sharpe_is >= 0.6"
    assert by_id["overfit.walk"].values["oos_to_is"] == pytest.approx(0.7)
    assert by_id["stability.oos"].revision == "stability-v1"
    assert by_id["stability.oos"].rule == (
        "at least 3 OOS segments and same-sign ratio >= 2/3"
    )
    assert by_id["stability.oos"].values["same_sign_ratio"] == pytest.approx(2 / 3)
    assert by_id["crowding.load"].revision == "crowding-v1"
    assert by_id["crowding.load"].rule == "top 20% crowding bucket sharpe impact >= 0"
    assert by_id["cost.turnover"].revision == "cost-v1"
    assert by_id["cost.turnover"].rule == (
        "excess_ann - annual_turnover * market_cost_bp / 10000 > 0"
    )
    assert by_id["cost.turnover"].values["cost_drag"] == pytest.approx(0.001)
    assert by_id["cost.turnover"].values["net_excess_ann"] == pytest.approx(0.039)
    assert by_id["pit.consistency"].revision == "pit-v1"
    assert by_id["pit.consistency"].passed is True
    assert by_id["pit.consistency"].rule == "all evidence as_of <= backtest cutoff"
    assert by_id["pit.consistency"].values["violations_count"] == pytest.approx(0.0)
    assert result.passed


def test_unknown_revision_refuses_to_fall_back() -> None:
    baseline = spec()
    report = passing_report()
    v1_cost = next(
        item
        for item in run_verifiers(report, baseline).results
        if item.verifier_id == "cost.turnover"
    )
    assert v1_cost.passed is True
    assert v1_cost.values["net_excess_ann"] == pytest.approx(0.039)

    swapped = replace(
        baseline,
        method_set=tuple(
            MethodRef(
                item.method_id,
                "cost-v2" if item.method_id == "cost.turnover" else item.revision_hash,
            )
            for item in baseline.method_set
        ),
    )
    result = run_verifiers(report, swapped)
    cost = next(item for item in result.results if item.verifier_id == "cost.turnover")
    assert cost.passed is False
    assert cost.revision == "cost-v2"
    assert cost.values == {}
    assert "cost-v2" in cost.rule
    assert "fall back" in cost.rule
    walk = next(item for item in result.results if item.verifier_id == "overfit.walk")
    assert walk.revision == "walk-v1"
    assert walk.passed is True
    assert walk.values["oos_to_is"] == pytest.approx(0.7)


def test_unknown_method_id_keeps_the_existing_rule() -> None:
    baseline = spec()
    extra = replace(
        baseline,
        method_set=baseline.method_set + (MethodRef("custom.gap", "gap-v1"),),
    )
    result = run_verifiers(passing_report(), extra)
    custom = next(item for item in result.results if item.verifier_id == "custom.gap")
    assert custom.passed is False
    assert custom.revision == "gap-v1"
    assert custom.rule == UNKNOWN_METHOD_RULE


def test_unknown_pit_revision_refuses_to_fall_back() -> None:
    result = run_verifiers(passing_report(), spec(), pit_revision="pit-v9")
    pit = next(item for item in result.results if item.verifier_id == "pit.consistency")
    assert pit.passed is False
    assert pit.revision == "pit-v9"
    assert pit.values == {}
    assert "pit-v9" in pit.rule
    assert "fall back" in pit.rule


def _rows(store: SQLiteStore, method_id: str) -> dict[str, MethodDefinition]:
    return {
        row.revision_hash: row
        for row in store._all_method_revision_rows()
        if row.method_id == method_id
    }


def test_new_revision_seeds_into_existing_db_without_overwriting_frozen_definition(
    tmp_path,
) -> None:
    store = SQLiteStore(tmp_path / "methods.db")
    seed_preset_methods(store)
    with store.connection:
        store.connection.execute(
            """
            UPDATE method_revisions
               SET body=?, description=?
             WHERE method_id=? AND revision_hash=?
            """,
            ("FROZEN-V1", "FROZEN-V1", "cost.turnover", "cost-v1"),
        )
    _insert_preset_if_missing(
        store,
        "cost.turnover",
        {
            "revision": "cost-v2",
            "us_cost_bp": 10,
            "cn_cost_bp": 20,
            "net_excess_min_exclusive": 0.0,
            "supersedes": "cost-v1",
        },
        NOW,
    )
    seeded = _rows(store, "cost.turnover")
    assert seeded["cost-v1"].body == "FROZEN-V1"
    assert seeded["cost-v1"].description == "FROZEN-V1"
    assert "cost-v2" in seeded
    assert seeded["cost-v2"].supersedes == "cost-v1"
    frozen_v2_body = seeded["cost-v2"].body
    _insert_preset_if_missing(
        store,
        "cost.turnover",
        {
            "revision": "cost-v2",
            "us_cost_bp": 99,
            "cn_cost_bp": 99,
            "net_excess_min_exclusive": 0.0,
            "supersedes": "cost-v1",
        },
        datetime(2026, 7, 1, tzinfo=UTC),
    )
    again = _rows(store, "cost.turnover")
    assert again["cost-v1"].body == "FROZEN-V1"
    assert again["cost-v2"].body == frozen_v2_body
    assert "99" not in again["cost-v2"].body


def test_seed_preset_methods_inserts_catalog_revision_into_populated_database(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from engine.research import methods

    store = SQLiteStore(tmp_path / "methods.db")
    seed_preset_methods(store)
    with store.connection:
        store.connection.execute(
            """
            UPDATE method_revisions
               SET body=?, description=?
             WHERE method_id=? AND revision_hash=?
            """,
            ("FROZEN-PIT", "FROZEN-PIT", "pit.consistency", "pit-v1"),
        )

    def catalog() -> tuple[tuple[str, dict[str, object]], ...]:
        return methods._builtin_preset_catalog() + (
            (
                "pit.consistency",
                {
                    "revision": "pit-v2",
                    "category": "时点/前视一致性",
                    "supersedes": "pit-v1",
                },
            ),
        )

    monkeypatch.setattr(methods, "iter_preset_definitions", catalog)
    seed_preset_methods(store)
    rows = _rows(store, "pit.consistency")
    assert rows["pit-v1"].body == "FROZEN-PIT"
    assert "pit-v2" in rows
    assert rows["pit-v2"].supersedes == "pit-v1"
    seed_preset_methods(store)
    assert _rows(store, "pit.consistency")["pit-v2"].body == rows["pit-v2"].body
