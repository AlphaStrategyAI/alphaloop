from engine.research.models import AssetClass, Market
from engine.research.symbol_pool import pool_by_version, pool_for_market


def test_us_equity_large_cap_v1_stays_forty_symbols() -> None:
    pool = pool_by_version("us_equity_large_cap_v1")
    assert pool is not None
    assert pool.display_name == "美股大市值"
    assert len(pool.symbols) == 40


def test_cn_equity_large_cap_v1_includes_moutai() -> None:
    pool = pool_by_version("cn_equity_large_cap_v1")
    assert pool is not None
    assert pool.display_name == "A股大市值"
    assert "600519.SH" in pool.symbols
    assert len(pool.symbols) == 40


def test_new_research_pool_is_the_later_version() -> None:
    us = pool_for_market(Market.US, AssetClass.EQUITY, AssetClass.EQUITY)
    cn = pool_for_market(Market.CN, AssetClass.EQUITY, AssetClass.EQUITY)
    assert us is not None and cn is not None
    assert us.version_id == "us_equity_large_cap_v2"
    assert cn.version_id == "cn_equity_large_cap_v2"
    assert len(us.symbols) >= 100
    assert len(cn.symbols) >= 100
