"""P0-6a: cut-line and screen notes match the 40-name pools.

The README is the bilingual product page. English is the default file.
Chinese lives in README.zh-CN.md. Both describe the lists that ship
(503 and 300 names), not the legacy 40-name pools.
"""

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
    english = (ROOT / "README.md").read_text(encoding="utf-8")
    chinese = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")

    assert "empty skeleton" not in english
    assert "empty skeleton" not in chinese
    assert english.startswith("English | [简体中文](README.zh-CN.md)")
    assert "[English](README.md)" in chinese
    assert "均值回归" not in english
    assert "不下单" not in english
    assert "mean reversion" in english.lower()
    assert "does not send orders" in english
    assert "503" in english
    assert "300" in english
    assert "AlphaStrategyAI" in english

    assert "均值回归" in chinese
    assert "不下单" in chinese
    assert "503" in chinese
    assert "300" in chinese
    assert "AlphaStrategyAI" in chinese

    assert "Copyright (c) 2026 AlphaStrategyAI" in license_text


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
