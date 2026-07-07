"""
策略工厂 - 动态创建策略实例
"""

import logging
from typing import Any, Dict, List, Optional, Type

from .base import BaseStrategy

logger = logging.getLogger(__name__)


class StrategyFactory:
    """
    策略工厂类

    用于动态注册和创建策略实例

    Examples:
        >>> factory = StrategyFactory()
        >>> factory.register("buy_hold", BuyHoldStrategy)
        >>> strategy = factory.create("buy_hold", symbols=["VTI", "BND"], weights=[0.6, 0.4])
    """

    _strategies: Dict[str, Type[BaseStrategy]] = {}

    @classmethod
    def register(cls, name: str, strategy_class: Type[BaseStrategy]) -> None:
        """
        注册策略类

        Args:
            name: 策略标识名
            strategy_class: 策略类
        """
        cls._strategies[name] = strategy_class
        logger.debug(f"Registered strategy: {name}")

    @classmethod
    def create(cls, name: str, **kwargs) -> BaseStrategy:
        """
        创建策略实例

        Args:
            name: 策略标识名
            **kwargs: 传递给策略构造函数的参数

        Returns:
            策略实例

        Raises:
            ValueError: 策略未注册
        """
        if name not in cls._strategies:
            available = list(cls._strategies.keys())
            raise ValueError(f"Unknown strategy: {name}. Available: {available}")

        strategy_class = cls._strategies[name]
        return strategy_class(**kwargs)

    @classmethod
    def list_strategies(cls) -> List[str]:
        """
        获取所有已注册策略

        Returns:
            策略名称列表
        """
        return list(cls._strategies.keys())

    @classmethod
    def get_strategy_info(cls, name: str) -> Optional[Dict[str, Any]]:
        """
        获取策略信息

        Args:
            name: 策略名称

        Returns:
            策略信息字典
        """
        if name not in cls._strategies:
            return None

        strategy_class = cls._strategies[name]
        return {
            "name": name,
            "class": strategy_class.__name__,
            "doc": strategy_class.__doc__,
        }
