"""P0-6a: README, cut-line, and screen notes match the 40-name pools."""

from __future__ import annotations

import json
from pathlib import Path

from engine.research.symbol_pool import list_pool_files, pool_by_version

ROOT = Path(__file__).resolve().parents[1]


def test_checked_in_pools_are_forty_names_and_not_a_parquet_universe() -> None:
    us = pool_by_version("us_equity_large_cap_v1")
    cn = pool_by_version("cn_equity_large_cap_v1")
    assert us is not None and cn is not None
    assert len(us.symbols) == 40
    assert len(cn.symbols) == 40
    assert len(us.symbols) == len(set(us.symbols))
    assert len(cn.symbols) == len(set(cn.symbols))
    names = [path.name for path in list_pool_files()]
    assert names == [
        "cn_equity_large_cap_v1.json",
        "cn_equity_large_cap_v2.json",
        "us_equity_large_cap_v1.json",
        "us_equity_large_cap_v2.json",
    ]
    us_v2 = pool_by_version("us_equity_large_cap_v2")
    cn_v2 = pool_by_version("cn_equity_large_cap_v2")
    assert us_v2 is not None and cn_v2 is not None
    assert len(us_v2.symbols) >= 100
    assert len(cn_v2.symbols) >= 100
    for path in list_pool_files():
        raw = json.loads(path.read_text(encoding="utf-8"))
        assert "parquet" not in json.dumps(raw).lower()
        assert "US-EQ-LIQUID" not in json.dumps(raw)


def test_readme_describes_the_shipped_product() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "empty skeleton" not in text
    assert "40" in text
    assert "均值回归" in text
    assert "不下单" in text
    assert "P1" in text
    assert "parquet" in text
    assert "pytest" in text
    assert "#129" in text
    assert "#132" in text
    assert "#133" in text


def test_cut_line_locks_forty_names_and_three_part_acceptance() -> None:
    text = (ROOT / "docs/requirements/v1-cut-line.md").read_text(encoding="utf-8")
    assert "40 只" in text
    assert "Yahoo" in text
    assert "parquet" in text
    assert "P1" in text
    assert "均值回归" in text
    assert "三段式" in text
    assert "不作为门槛" in text
    assert "#132" in text
    assert "US-EQ-LIQUID" in text


def test_ui_design_annotates_screens_and_specifies_glossary_nav() -> None:
    text = (ROOT / "docs/requirements/ui-design-v0_0_1.md").read_text(encoding="utf-8")
    assert "128 只" in text
    assert "本机 parquet" in text or "parquet" in text
    assert "P1" in text
    assert "仅测试" in text or "手动路径" in text
    assert "设计稿所示的全绿路径在 PIT 修复后可达" in text
    assert "回撤下限" in text
    assert "#132" in text
    assert "#129" in text
    assert "术语" in text
    assert "#/glossary" in text
    assert "不重画" in text
