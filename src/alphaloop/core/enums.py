"""
核心枚举定义
"""

from enum import Enum, auto


class RebalanceMethod(Enum):
    """再平衡方法"""

    THRESHOLD = "threshold"  # 阈值触发 - 当偏离超过阈值时触发
    CALENDAR = "calendar"  # 定期再平衡 - 按固定时间周期
    CALENDAR_AND_THRESHOLD = "calendar_and_threshold"  # 日历+阈值结合
    BUY_HOLD = "buy_hold"  # 买入持有 - 不再平衡，作为对比基准

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"


class AssetClass(Enum):
    """资产类别"""

    STOCK = auto()  # 股票
    BOND = auto()  # 债券
    COMMODITY = auto()  # 大宗商品
    CASH = auto()  # 现金
    ALTERNATIVE = auto()  # 另类投资

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"


class OrderType(Enum):
    """订单类型"""

    MARKET = auto()  # 市价单
    LIMIT = auto()  # 限价单
    STOP = auto()  # 止损单

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"


class Frequency(Enum):
    """时间频率"""

    DAILY = "D"
    WEEKLY = "W"
    MONTHLY = "M"
    QUARTERLY = "Q"
    YEARLY = "Y"

    def to_pandas_freq(self) -> str:
        """转换为 pandas 频率字符串"""
        return self.value

    def days(self) -> int:
        """估算的天数"""
        mapping = {
            Frequency.DAILY: 1,
            Frequency.WEEKLY: 7,
            Frequency.MONTHLY: 30,
            Frequency.QUARTERLY: 90,
            Frequency.YEARLY: 365,
        }
        return mapping[self]

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"
