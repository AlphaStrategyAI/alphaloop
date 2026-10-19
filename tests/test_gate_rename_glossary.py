"""P0-7a: display-name rename, legacy aliases, glossary single source."""

from __future__ import annotations

import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from engine.dialogue.intent import _parse_methods
from engine.dialogue.prompts import QUESTIONS, SlotName
from engine.export import build_research_record_pack, build_strategy_pack
from engine.main import ResearchCommandService
from engine.research.display_names import method_label
from engine.research.glossary import glossary_entries, glossary_markdown
from engine.research.method_body_display import format_method_body_display, method_purpose
from engine.research.models import MethodDefinition, MethodSource, ResearchStatus
from engine.research.runtime import EnginePaths
from engine.research.store import SQLiteStore
from engine.strategy import MarketPanel
from engine.verifiers import VERIFIER_REVISIONS
from tests.test_export_pack import completed_research, reference_strategy

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_gate_display_names_renamed_ids_unchanged() -> None:
    assert method_label("overfit.walk") == "分段稳健性检验"
    assert method_label("crowding.load") == "集中度"
    assert method_label("stability.oos") == "样本外稳定"
    assert VERIFIER_REVISIONS["overfit.walk"]["revision"] == "walk-v1"
    assert VERIFIER_REVISIONS["crowding.load"]["revision"] == "crowding-v1"
    assert VERIFIER_REVISIONS["overfit.walk"]["oos_to_is_min"] == 0.6
    assert VERIFIER_REVISIONS["stability.oos"]["same_sign_ratio_min"] == 2 / 3
    assert VERIFIER_REVISIONS["crowding.load"]["sharpe_impact_min"] == 0.0


def test_legacy_and_new_method_words_resolve_to_same_refs() -> None:
    old = _parse_methods("走样检验 样本外稳定 拥挤度 换手成本")
    new = _parse_methods("分段稳健性检验 样本外稳定 集中度 换手成本")
    assert [item.method_id for item in old] == [
        "overfit.walk",
        "stability.oos",
        "crowding.load",
        "cost.turnover",
    ]
    assert old == new


def test_alias_plus_new_name_does_not_duplicate_method() -> None:
    refs = _parse_methods("分段稳健性检验，走样检验，集中度，拥挤度")
    assert [item.method_id for item in refs] == ["overfit.walk", "crowding.load"]


def test_round1_prompt_uses_new_names() -> None:
    text = QUESTIONS[SlotName.ROUND1_METHODS]
    assert "分段稳健性检验" in text
    assert "集中度" in text
    assert "走样检验" not in text
    assert "拥挤度" not in text


def test_purposes_distinguish_segment_consistency_and_weight_concentration() -> None:
    walk = method_purpose("overfit.walk")
    assert "时间分段" in walk
    assert "walk-forward" in walk
    assert "走样" not in walk
    crowding = method_purpose("crowding.load")
    assert "权重集中度" in crowding
    assert "非市场拥挤度" in crowding


def test_method_body_display_drops_old_gate_names() -> None:
    walk_body = json.dumps(dict(VERIFIER_REVISIONS["overfit.walk"]))
    walk_text = format_method_body_display("overfit.walk", walk_body)
    assert "走样" not in walk_text
    assert "walk-v1" not in walk_text
    assert "分段" in walk_text
    crowd_body = json.dumps(dict(VERIFIER_REVISIONS["crowding.load"]))
    crowd_text = format_method_body_display("crowding.load", crowd_body)
    assert "权重集中度" in crowd_text
    assert "crowding-v1" not in crowd_text


def test_legacy_library_rows_display_new_names_without_rewriting_stored_name(
    tmp_path: Path,
) -> None:
    store = SQLiteStore(tmp_path / "legacy.db")
    store.insert_method_definition(
        MethodDefinition(
            method_id="overfit.walk",
            revision_hash="walk-v1",
            name="走样检验",
            description="legacy",
            body=json.dumps(dict(VERIFIER_REVISIONS["overfit.walk"]), sort_keys=True),
            source=MethodSource.PRESET,
            deposited_from_research_id=None,
            created_at=NOW,
            supersedes=None,
        )
    )
    store.insert_method_definition(
        MethodDefinition(
            method_id="crowding.load",
            revision_hash="crowding-v1",
            name="拥挤度",
            description="legacy",
            body=json.dumps(dict(VERIFIER_REVISIONS["crowding.load"]), sort_keys=True),
            source=MethodSource.PRESET,
            deposited_from_research_id=None,
            created_at=NOW,
            supersedes=None,
        )
    )
    service = ResearchCommandService(store, EnginePaths.for_colocated_root(tmp_path))
    view = service.view_for("#/methods")
    by_id = {item["id"]: item for item in view["methods"]}
    assert by_id["overfit.walk"]["name"] == "分段稳健性检验"
    assert by_id["crowding.load"]["name"] == "集中度"
    assert store.latest_method_definition("overfit.walk").name == "走样检验"
    assert store.latest_method_definition("crowding.load").name == "拥挤度"
    assert "走样" not in by_id["overfit.walk"]["description"]
    assert "走样" not in by_id["overfit.walk"]["definitionDisplay"]
    assert "走样" not in by_id["overfit.walk"]["revisionLabel"]
    for dim in by_id["overfit.walk"]["dimensions"]:
        assert "走样" not in str(dim.get("failureDisplay", ""))
    assert by_id["crowding.load"]["category"] == "集中度"
    kind_labels = [
        dim["kindLabel"]
        for item in view["methods"]
        for dim in item["dimensions"]
        if dim.get("kind") == "crowding"
    ]
    assert kind_labels == [] or set(kind_labels) == {"集中度"}


def test_glossary_is_single_source_for_doc_and_required_terms() -> None:
    terms = {entry.term: entry.body for entry in glossary_entries()}
    assert method_label("pit.consistency") in terms
    assert "试验次数（X/N）与累计 M" in terms
    assert method_label("overfit.walk") in terms
    assert method_label("crowding.load") in terms
    assert "冻结验证方法" in terms
    assert "基准口径" in terms
    assert "成本（bp）" in terms
    assert method_label("stability.oos") in terms
    walk = terms[method_label("overfit.walk")]
    assert "时间分段" in walk
    assert "walk-forward" in walk
    assert "走样检验" in walk
    crowd = terms[method_label("crowding.load")]
    assert "权重集中度" in crowd
    assert "拥挤度" in crowd
    assert "样本外稳定" in terms[method_label("stability.oos")] or "同号" in terms[
        method_label("stability.oos")
    ]
    doc = Path("docs/GLOSSARY.md").read_text(encoding="utf-8")
    assert doc == glossary_markdown()
    assert "走样检验" in doc
    assert "分段稳健性检验" in doc


def test_glossary_view_uses_same_entries(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "g.db")
    service = ResearchCommandService(store, EnginePaths.for_colocated_root(tmp_path))
    view = service.view_for("#/glossary")
    assert view["kind"] == "glossary"
    assert [item["term"] for item in view["entries"]] == [
        entry.term for entry in glossary_entries()
    ]
    assert view["entries"][0]["body"] == glossary_entries()[0].body


def test_strategy_and_research_packs_embed_glossary(tmp_path: Path) -> None:
    from dataclasses import replace

    research = completed_research()
    prices = pd.DataFrame(
        {"AAA": [10.0, 11.0, 9.5], "BBB": [8.0, 7.5, 8.5]},
        index=pd.DatetimeIndex(["2020-01-02", "2020-01-03", "2020-01-06"], name="date"),
    )
    panel = MarketPanel(prices, prices.mean(axis=1).rename("SPX"))
    pack = build_strategy_pack(research, reference_strategy(), panel, tmp_path / "pack.zip")
    record = build_research_record_pack(
        replace(research, status=ResearchStatus.ENDED, export_eligible=False),
        tmp_path / "record.zip",
    )
    expected = glossary_markdown()
    with zipfile.ZipFile(pack) as archive:
        assert archive.read("docs/GLOSSARY.md").decode("utf-8") == expected
        manifest = json.loads(archive.read("manifest.json"))
        assert "docs/GLOSSARY.md" in manifest["files"]
    with zipfile.ZipFile(record) as archive:
        assert archive.read("docs/GLOSSARY.md").decode("utf-8") == expected
