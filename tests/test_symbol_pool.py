from engine.research.models import AssetClass, Market
from engine.research.symbol_pool import pool_for_market


def test_us_equity_large_cap_pool_is_versioned_and_has_forty_symbols() -> None:
    pool = pool_for_market(Market.US, AssetClass.EQUITY, AssetClass.EQUITY)
    assert pool is not None
    assert pool.version_id == "us_equity_large_cap_v1"
    assert pool.display_name == "美股大市值"
    assert len(pool.symbols) == 40


def test_cn_equity_large_cap_pool_includes_moutai() -> None:
    pool = pool_for_market(Market.CN, AssetClass.EQUITY, AssetClass.EQUITY)
    assert pool is not None
    assert pool.version_id == "cn_equity_large_cap_v1"
    assert pool.display_name == "A股大市值"
    assert "600519.SH" in pool.symbols
    assert len(pool.symbols) == 40
