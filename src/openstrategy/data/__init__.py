"""
Data Layer - 数据获取与管理

支持多数据源：Yahoo Finance、AKShare、CCXT、OpenBB
"""

from .akshare import AKShareSource
from .base import DataSource, DataSourceError
from .cache import DataCache
from .yahoo import YahooFinanceSource

__all__ = [
    "DataSource",
    "DataSourceError",
    "YahooFinanceSource",
    "AKShareSource",
    "DataCache",
]

# Optional data sources
try:
    from .ccxt import CCXTSource

    __all__.append("CCXTSource")
except ImportError:
    pass  # CCXT is optional

try:
    from .openbb_source import OpenBBDataSource

    __all__.append("OpenBBDataSource")
except ImportError:
    pass  # OpenBB is optional
