"""
全球多资产再平衡策略 - Global Multi-Asset Rebalancing Strategy

支持股票区域分布（美股、欧股、亚太、新兴市场）和债券类型
（美债、国际债券、通胀保值债券）的资产配置策略
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    from typing import Literal
except ImportError:
    pass

import numpy as np
import pandas as pd

from ..core.portfolio import Portfolio
from .base import BaseStrategy, Signal

logger = logging.getLogger(__name__)


class RebalanceTrigger(Enum):
    """再平衡触发方式"""

    THRESHOLD = "threshold"  # 阈值触发
    CALENDAR = "calendar"  # 日历触发
    BOTH = "both"  # 两者结合


class TacticalMethod(Enum):
    """战术资产配置方法"""

    NONE = "none"  # 无战术调整
    VOLATILITY = "volatility"  # 基于波动率
    MOMENTUM = "momentum"  # 基于动量
    RISK_PARITY = "risk_parity"  # 风险平价


@dataclass
class RegionalAllocation:
    """区域资产配置权重 - 全球股票区域配置"""

    # 股票区域 (用户指定的新分类)
    us_equity: float = 0.35  # 美国
    china_equity: float = 0.20  # 中国
    europe_equity: float = 0.15  # 欧洲
    japan_korea_taiwan_equity: float = 0.15  # 日韩台
    southeast_asia_equity: float = 0.05  # 东南亚
    india_equity: float = 0.05  # 印度
    latin_america_equity: float = 0.05  # 拉美

    def __post_init__(self):
        """验证权重总和为1"""
        total = sum(
            [
                self.us_equity,
                self.china_equity,
                self.europe_equity,
                self.japan_korea_taiwan_equity,
                self.southeast_asia_equity,
                self.india_equity,
                self.latin_america_equity,
            ]
        )
        if not 0.99 <= total <= 1.01:
            logger.warning(f"RegionalAllocation weights sum to {total:.2%}, normalizing")
            # 归一化
            factor = 1.0 / total
            self.us_equity *= factor
            self.china_equity *= factor
            self.europe_equity *= factor
            self.japan_korea_taiwan_equity *= factor
            self.southeast_asia_equity *= factor
            self.india_equity *= factor
            self.latin_america_equity *= factor

    def to_dict(self) -> Dict[str, float]:
        """转换为字典"""
        return {
            "us_equity": self.us_equity,
            "china_equity": self.china_equity,
            "europe_equity": self.europe_equity,
            "japan_korea_taiwan_equity": self.japan_korea_taiwan_equity,
            "southeast_asia_equity": self.southeast_asia_equity,
            "india_equity": self.india_equity,
            "latin_america_equity": self.latin_america_equity,
        }


@dataclass
class AssetMapping:
    """资产配置映射（ETF代码）- 新区域配置"""

    # 美国 - Vanguard Total Stock Market
    us_equity: str = "VTI"
    # 中国 - iShares MSCI China ETF
    china_equity: str = "MCHI"
    # 欧洲 - Vanguard FTSE Europe ETF
    europe_equity: str = "VGK"
    # 日韩台 - 使用iShares MSCI All Country Asia ex Japan ETF作为代表
    # 注意：实际应用中可考虑拆分为EWJ(日本)+EWY(韩国)+EWT(台湾)
    japan_korea_taiwan_equity: str = "EPP"  # iShares MSCI Pacific ex Japan (含韩国澳洲等)
    # 东南亚 - Global X FTSE Southeast Asia ETF
    southeast_asia_equity: str = "ASEA"
    # 印度 - iShares MSCI India ETF
    india_equity: str = "INDA"
    # 拉美 - iShares Latin America 40 ETF
    latin_america_equity: str = "ILF"


class GlobalMultiAssetStrategy(BaseStrategy):
    """
    全球多资产再平衡策略

    支持:
    - 股票区域分布: 美股、欧股、亚太、新兴市场
    - 债券类型: 美债、国际债券、通胀保值债券
    - 再平衡方式: 阈值触发、日历触发
    - 战术资产配置: 基于波动率或动量的动态权重调整

    Examples:
        >>> strategy = GlobalMultiAssetStrategy(
        ...     equity_ratio=0.6,
        ...     bond_ratio=0.4,
        ...     rebalance_trigger=RebalanceTrigger.THRESHOLD,
        ...     rebalance_threshold=0.05,
        ...     tactical_method=TacticalMethod.MOMENTUM,
        ... )

    Attributes:
        equity_ratio: 股票整体比例
        bond_ratio: 债券整体比例
        regional_allocation: 区域资产配置
        rebalance_trigger: 再平衡触发方式
        rebalance_threshold: 偏离阈值（阈值触发用）
        rebalance_frequency: 再平衡频率天数（日历触发用）
        tactical_method: 战术资产配置方法
        lookback_days: 回看天数（用于计算波动率/动量）
        volatility_target: 目标波动率（波动率调整用）
    """

    # 资产映射
    ASSET_MAPPING = AssetMapping()

    # 区域分类 - 新分类：美国、中国、欧洲、日韩台、东南亚、印度、拉美
    EQUITY_REGIONS = [
        "us_equity",
        "china_equity",
        "europe_equity",
        "japan_korea_taiwan_equity",
        "southeast_asia_equity",
        "india_equity",
        "latin_america_equity",
    ]
    ALL_ASSETS = EQUITY_REGIONS

    def __init__(
        self,
        # 区域权重（直接配置各区域比例）
        us_weight: float = 0.35,  # 美国
        china_weight: float = 0.20,  # 中国
        europe_weight: float = 0.15,  # 欧洲
        japan_korea_taiwan_weight: float = 0.15,  # 日韩台
        southeast_asia_weight: float = 0.05,  # 东南亚
        india_weight: float = 0.05,  # 印度
        latin_america_weight: float = 0.05,  # 拉美
        # 再平衡设置
        rebalance_trigger: RebalanceTrigger = RebalanceTrigger.THRESHOLD,
        rebalance_threshold: float = 0.05,  # 5%偏离阈值
        rebalance_frequency: int = 30,  # 月度再平衡
        # 战术配置
        tactical_method: TacticalMethod = TacticalMethod.NONE,
        lookback_days: int = 60,  # 回看60天
        volatility_target: float = 0.10,  # 10%目标波动率
        # 其他
        tolerance: float = 0.001,
        name: str = "global_multi_asset",
    ):
        """
        初始化全球股票区域配置策略

        Args:
            us_weight: 美国权重
            china_weight: 中国权重
            europe_weight: 欧洲权重
            japan_korea_taiwan_weight: 日韩台权重
            southeast_asia_weight: 东南亚权重
            india_weight: 印度权重
            latin_america_weight: 拉美权重
            rebalance_trigger: 再平衡触发方式
            rebalance_threshold: 偏离阈值
            rebalance_frequency: 再平衡频率（天）
            tactical_method: 战术资产配置方法
            lookback_days: 回看天数
            volatility_target: 目标波动率
            tolerance: 最小交易阈值
            name: 策略名称
        """
        super().__init__(name=name)

        # 计算最终权重（所有区域权重总和应为1）
        self.regional_allocation = self._calculate_allocation(
            us_weight,
            china_weight,
            europe_weight,
            japan_korea_taiwan_weight,
            southeast_asia_weight,
            india_weight,
            latin_america_weight,
        )

        self.rebalance_trigger = rebalance_trigger
        self.rebalance_threshold = rebalance_threshold
        self.rebalance_frequency = rebalance_frequency
        self.tactical_method = tactical_method
        self.lookback_days = lookback_days
        self.volatility_target = volatility_target
        self.tolerance = tolerance

        # 内部状态
        self._last_rebalance: Optional[datetime] = None
        self._initial_allocation_done = False
        self._target_weights: Dict[str, float] = {}
        self._tactical_multipliers: Dict[str, float] = {}

        # 构建符号映射
        self._build_symbol_mapping()

    def _calculate_allocation(
        self,
        us_weight: float,
        china_weight: float,
        europe_weight: float,
        japan_korea_taiwan_weight: float,
        southeast_asia_weight: float,
        india_weight: float,
        latin_america_weight: float,
    ) -> RegionalAllocation:
        """计算各区域最终权重（归一化到100%）"""
        # 归一化所有区域权重
        total = (
            us_weight
            + china_weight
            + europe_weight
            + japan_korea_taiwan_weight
            + southeast_asia_weight
            + india_weight
            + latin_america_weight
        )

        if total <= 0:
            raise ValueError(f"Total weight must be positive, got {total}")

        return RegionalAllocation(
            us_equity=us_weight / total,
            china_equity=china_weight / total,
            europe_equity=europe_weight / total,
            japan_korea_taiwan_equity=japan_korea_taiwan_weight / total,
            southeast_asia_equity=southeast_asia_weight / total,
            india_equity=india_weight / total,
            latin_america_equity=latin_america_weight / total,
        )

    def _build_symbol_mapping(self) -> None:
        """构建区域到ETF符号的映射"""
        mapping = self.ASSET_MAPPING
        self._region_to_symbol = {
            "us_equity": mapping.us_equity,
            "china_equity": mapping.china_equity,
            "europe_equity": mapping.europe_equity,
            "japan_korea_taiwan_equity": mapping.japan_korea_taiwan_equity,
            "southeast_asia_equity": mapping.southeast_asia_equity,
            "india_equity": mapping.india_equity,
            "latin_america_equity": mapping.latin_america_equity,
        }
        self._symbol_to_region = {v: k for k, v in self._region_to_symbol.items()}
        self.symbols = list(self._region_to_symbol.values())

    def get_symbols(self) -> List[str]:
        """获取策略使用的ETF代码列表"""
        return self.symbols

    def get_target_weights(self) -> Dict[str, float]:
        """获取当前目标权重（考虑战术调整）"""
        base_weights = self.regional_allocation.to_dict()

        # 应用战术调整
        if self.tactical_method != TacticalMethod.NONE and self._tactical_multipliers:
            adjusted_weights = {}
            for region, weight in base_weights.items():
                multiplier = self._tactical_multipliers.get(region, 1.0)
                adjusted_weights[region] = weight * multiplier

            # 归一化
            total = sum(adjusted_weights.values())
            if total > 0:
                adjusted_weights = {k: v / total for k, v in adjusted_weights.items()}
            return adjusted_weights

        return base_weights

    def initialize(self, **kwargs) -> None:
        """初始化策略"""
        super().initialize(**kwargs)
        self._last_rebalance = None
        self._initial_allocation_done = False
        self._target_weights = self.get_target_weights()
        self._tactical_multipliers = {}

    def generate_signals(
        self,
        data: pd.DataFrame,
        portfolio: Portfolio,
        current_date: Optional[datetime] = None,
    ) -> List[Signal]:
        """
        生成交易信号

        Args:
            data: 历史价格数据
            portfolio: 当前投资组合
            current_date: 当前日期

        Returns:
            交易信号列表
        """
        if data.empty or current_date is None:
            return []

        # 更新战术调整
        if self.tactical_method != TacticalMethod.NONE and len(data) >= self.lookback_days:
            self._update_tactical_adjustment(data)

        current_prices = data.iloc[-1].to_dict()
        target_weights = self.get_target_weights()

        # 1. 初始配置
        if not self._initial_allocation_done:
            signals = self._generate_initial_signals(target_weights, current_prices, current_date)
            self._initial_allocation_done = True
            self._last_rebalance = current_date
            return signals

        # 2. 检查是否需要再平衡
        if not self._should_rebalance(portfolio, current_prices, current_date):
            return []

        # 3. 生成再平衡信号
        signals = self._generate_rebalance_signals(
            portfolio, target_weights, current_prices, current_date
        )

        if signals:
            self._last_rebalance = current_date
            logger.info(f"[{self.name}] Rebalanced on {current_date.date()}: {len(signals)} trades")

        return signals

    def _update_tactical_adjustment(self, data: pd.DataFrame) -> None:
        """更新战术资产配置调整"""
        if self.tactical_method == TacticalMethod.VOLATILITY:
            self._tactical_multipliers = self._calculate_volatility_adjustment(data)
        elif self.tactical_method == TacticalMethod.MOMENTUM:
            self._tactical_multipliers = self._calculate_momentum_adjustment(data)
        elif self.tactical_method == TacticalMethod.RISK_PARITY:
            self._tactical_multipliers = self._calculate_risk_parity_adjustment(data)

    def _calculate_volatility_adjustment(self, data: pd.DataFrame) -> Dict[str, float]:
        """基于波动率的战术调整 - 降低高波动资产权重"""
        lookback_data = data.tail(self.lookback_days)
        multipliers = {}

        for symbol in self.symbols:
            if symbol not in lookback_data.columns:
                multipliers[self._symbol_to_region[symbol]] = 1.0
                continue

            prices = lookback_data[symbol].dropna()
            if len(prices) < 20:
                multipliers[self._symbol_to_region[symbol]] = 1.0
                continue

            # 计算波动率
            returns = prices.pct_change().dropna()
            volatility = returns.std() * np.sqrt(252)

            # 根据波动率调整: 高波动降低权重，低波动增加权重
            if volatility > 0:
                multiplier = self.volatility_target / volatility
                # 限制调整幅度
                multiplier = np.clip(multiplier, 0.5, 1.5)
            else:
                multiplier = 1.0

            multipliers[self._symbol_to_region[symbol]] = multiplier

        return multipliers

    def _calculate_momentum_adjustment(self, data: pd.DataFrame) -> Dict[str, float]:
        """基于动量的战术调整 - 增加动量强的资产权重"""
        lookback_data = data.tail(self.lookback_days)
        multipliers = {}
        momentums = {}

        # 计算各资产的动量
        for symbol in self.symbols:
            if symbol not in lookback_data.columns:
                momentums[self._symbol_to_region[symbol]] = 0.0
                continue

            prices = lookback_data[symbol].dropna()
            if len(prices) < 20:
                momentums[self._symbol_to_region[symbol]] = 0.0
                continue

            # 计算动量 (20日收益 vs 60日收益)
            momentum_20 = prices.iloc[-1] / prices.iloc[-20] - 1 if len(prices) >= 20 else 0
            momentum_60 = prices.iloc[-1] / prices.iloc[-60] - 1 if len(prices) >= 60 else 0
            momentum = 0.6 * momentum_20 + 0.4 * momentum_60
            momentums[self._symbol_to_region[symbol]] = momentum

        # 排序并计算调整
        if momentums:
            sorted_momentum = sorted(momentums.items(), key=lambda x: x[1], reverse=True)
            n = len(sorted_momentum)

            # 动量越高，乘数越大 (0.8 - 1.2 范围)
            for i, (region, _) in enumerate(sorted_momentum):
                multiplier = 1.2 - (i / n) * 0.4  # 第一名1.2，最后一名0.8
                multipliers[region] = multiplier

        return multipliers

    def _calculate_risk_parity_adjustment(self, data: pd.DataFrame) -> Dict[str, float]:
        """基于风险平价的战术调整 - 使各资产对组合风险贡献相等"""
        lookback_data = data.tail(self.lookback_days)

        # 计算各资产的波动率
        volatilities = {}
        for symbol in self.symbols:
            if symbol not in lookback_data.columns:
                continue
            prices = lookback_data[symbol].dropna()
            if len(prices) >= 20:
                returns = prices.pct_change().dropna()
                volatilities[self._symbol_to_region[symbol]] = returns.std() * np.sqrt(252)

        if not volatilities:
            return {region: 1.0 for region in self.ALL_ASSETS}

        # 风险平价权重与波动率成反比
        inverse_vols = {r: 1.0 / v if v > 0 else 0 for r, v in volatilities.items()}
        total = sum(inverse_vols.values())

        if total > 0:
            risk_parity_weights = {r: v / total for r, v in inverse_vols.items()}
        else:
            risk_parity_weights = {r: 1.0 / len(self.ALL_ASSETS) for r in self.ALL_ASSETS}

        # 计算相对于基础权重的调整系数
        base_weights = self.regional_allocation.to_dict()
        multipliers = {}
        for region in self.ALL_ASSETS:
            base = base_weights.get(region, 0)
            target = risk_parity_weights.get(region, base)
            if base > 0:
                multiplier = target / base
                multipliers[region] = np.clip(multiplier, 0.5, 1.5)
            else:
                multipliers[region] = 1.0

        return multipliers

    def _should_rebalance(
        self,
        portfolio: Portfolio,
        prices: Dict[str, float],
        current_date: datetime,
    ) -> bool:
        """判断是否需要再平衡"""
        target_weights = self.get_target_weights()

        # 日历触发
        if self.rebalance_trigger in (RebalanceTrigger.CALENDAR, RebalanceTrigger.BOTH):
            if self._last_rebalance is None:
                return True
            days_since = (current_date - self._last_rebalance).days
            if days_since >= self.rebalance_frequency:
                return True

        # 阈值触发
        if self.rebalance_trigger in (RebalanceTrigger.THRESHOLD, RebalanceTrigger.BOTH):
            max_dev = self._calculate_max_deviation(portfolio, target_weights, prices)
            if max_dev >= self.rebalance_threshold:
                return True

        return False

    def _calculate_max_deviation(
        self,
        portfolio: Portfolio,
        target_weights: Dict[str, float],
        prices: Dict[str, float],
    ) -> float:
        """计算最大偏离度"""
        total_value = portfolio.total_value(prices)
        if total_value <= 0:
            return 0.0

        max_dev = 0.0
        for region, target_weight in target_weights.items():
            symbol = self._region_to_symbol.get(region)
            if not symbol or symbol not in prices:
                continue

            position = portfolio.get_position(symbol)
            current_qty = position.quantity if position else 0.0
            current_value = current_qty * prices[symbol]
            current_weight = current_value / total_value

            deviation = abs(current_weight - target_weight)
            max_dev = max(max_dev, deviation)

        return max_dev

    def _generate_initial_signals(
        self,
        target_weights: Dict[str, float],
        prices: Dict[str, float],
        current_date: datetime,
    ) -> List[Signal]:
        """生成初始配置信号"""
        signals = []
        initial_investment = self.params.get("initial_investment", 100000.0)

        for region, weight in target_weights.items():
            symbol = self._region_to_symbol.get(region)
            if not symbol or symbol not in prices:
                continue

            price = prices[symbol]
            if price <= 0:
                continue

            target_value = initial_investment * weight
            quantity = target_value / price

            signals.append(
                Signal(
                    symbol=symbol,
                    action="buy",
                    quantity=quantity,
                    weight=weight,
                    price=price,
                    timestamp=current_date,
                    metadata={
                        "reason": "initial_allocation",
                        "region": region,
                    },
                )
            )

        return signals

    def _generate_rebalance_signals(
        self,
        portfolio: Portfolio,
        target_weights: Dict[str, float],
        prices: Dict[str, float],
        current_date: datetime,
    ) -> List[Signal]:
        """生成再平衡信号"""
        signals = []
        total_value = portfolio.total_value(prices)

        if total_value <= 0:
            return signals

        for region, target_weight in target_weights.items():
            symbol = self._region_to_symbol.get(region)
            if not symbol or symbol not in prices:
                continue

            price = prices[symbol]
            if price <= 0:
                continue

            # 当前持仓
            current_pos = portfolio.get_position(symbol)
            current_qty = current_pos.quantity if current_pos else 0.0
            current_value = current_qty * price
            current_weight = current_value / total_value

            # 目标持仓
            target_value = total_value * target_weight
            target_qty = target_value / price

            # 需要调整的数量
            delta_qty = target_qty - current_qty
            delta_value = abs(delta_qty) * price

            # 检查最小交易阈值
            if delta_value < self.tolerance * total_value:
                continue

            # 生成信号
            action = "buy" if delta_qty > 0 else "sell"
            signals.append(
                Signal(
                    symbol=symbol,
                    action=action,
                    quantity=abs(delta_qty),
                    weight=target_weight,
                    price=price,
                    timestamp=current_date,
                    metadata={
                        "reason": "rebalance",
                        "region": region,
                        "current_weight": current_weight,
                        "target_weight": target_weight,
                        "deviation": current_weight - target_weight,
                    },
                )
            )

        return signals

    def get_summary(self) -> Dict[str, Any]:
        """获取策略摘要"""
        return {
            "name": self.name,
            "type": "全球股票区域配置",
            "target_allocation": {
                k: f"{v:.1%}" for k, v in self.regional_allocation.to_dict().items()
            },
            "rebalance_trigger": self.rebalance_trigger.value,
            "rebalance_threshold": f"{self.rebalance_threshold:.1%}",
            "tactical_method": self.tactical_method.value,
            "symbols": self.symbols,
        }
