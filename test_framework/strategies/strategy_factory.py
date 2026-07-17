"""
策略工厂 — 根据类型和名称创建策略实例（工厂模式）。

设计模式：工厂模式（Factory Pattern）
职责：维护 strategy_type → name → StrategyClass 的注册表，
      按需创建策略实例，支持从配置字典自动创建。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Type

from .base import BaseStrategy

logger = logging.getLogger(__name__)


class StrategyFactory:
    """
    策略工厂。

    注册表结构::

        {
            "load": {
                "constant": ConstantLoadStrategy,
                "ramp_up": RampUpLoadStrategy,
                ...
            },
            "validation": { ... },
            "retry": { ... },
        }
    """

    _registry: Dict[str, Dict[str, Type[BaseStrategy]]] = {}

    @classmethod
    def register(
        cls,
        strategy_type: str,
        name: str,
        strategy_cls: Type[BaseStrategy],
    ) -> None:
        """
        注册策略类。

        Args:
            strategy_type: 策略类型（load / validation / retry）。
            name: 策略名称。
            strategy_cls: 策略类。
        """
        if strategy_type not in cls._registry:
            cls._registry[strategy_type] = {}
        cls._registry[strategy_type][name] = strategy_cls
        logger.debug(f"注册策略: {strategy_type}/{name} → {strategy_cls.__name__}")

    @classmethod
    def create(
        cls,
        strategy_type: str,
        name: str,
        **kwargs: Any,
    ) -> BaseStrategy:
        """
        创建策略实例。

        Args:
            strategy_type: 策略类型。
            name: 策略名称。
            **kwargs: 传递给策略构造函数的参数。

        Returns:
            策略实例。

        Raises:
            ValueError: 未注册的策略类型或名称。
        """
        strategies = cls._registry.get(strategy_type)
        if not strategies:
            raise ValueError(f"未注册的策略类型: {strategy_type}")

        strategy_cls = strategies.get(name)
        if not strategy_cls:
            raise ValueError(
                f"未注册的策略: {strategy_type}/{name}，"
                f"可用: {list(strategies.keys())}"
            )

        return strategy_cls(**kwargs)

    @classmethod
    def create_from_config(cls, config: Dict[str, Any]) -> BaseStrategy:
        """
        根据配置字典自动创建策略。

        配置格式::

            {
                "strategy_type": "load",
                "name": "constant",
                "params": { "concurrency": 100, "duration": 60 }
            }

        Args:
            config: 包含 strategy_type / name / params 的配置字典。

        Returns:
            策略实例。
        """
        strategy_type = config.get("strategy_type", "")
        name = config.get("name", "")
        params = config.get("params", {})
        return cls.create(strategy_type, name, **params)

    @classmethod
    def available(cls, strategy_type: str) -> List[str]:
        """获取指定类型的所有可用策略名称。"""
        return list(cls._registry.get(strategy_type, {}).keys())

    @classmethod
    def available_types(cls) -> List[str]:
        """获取所有已注册的策略类型。"""
        return list(cls._registry.keys())


# ===== 自动注册内置策略 =====
def _auto_register() -> None:
    """导入时自动注册内置策略。"""
    # 负载策略
    try:
        from .load.constant import ConstantLoadStrategy
        StrategyFactory.register("load", "constant", ConstantLoadStrategy)
    except ImportError:
        pass
    try:
        from .load.ramp_up import RampUpLoadStrategy
        StrategyFactory.register("load", "ramp_up", RampUpLoadStrategy)
    except ImportError:
        pass
    try:
        from .load.spike import SpikeLoadStrategy
        StrategyFactory.register("load", "spike", SpikeLoadStrategy)
    except ImportError:
        pass
    try:
        from .load.soak import SoakLoadStrategy
        StrategyFactory.register("load", "soak", SoakLoadStrategy)
    except ImportError:
        pass
    try:
        from .load.step import StepLoadStrategy
        StrategyFactory.register("load", "step", StepLoadStrategy)
    except ImportError:
        pass
    try:
        from .load.wave import WaveLoadStrategy
        StrategyFactory.register("load", "wave", WaveLoadStrategy)
    except ImportError:
        pass

    # 验证策略
    try:
        from .validation.threshold import ThresholdValidationStrategy
        StrategyFactory.register("validation", "threshold", ThresholdValidationStrategy)
    except ImportError:
        pass
    try:
        from .validation.percentile import PercentileValidationStrategy
        StrategyFactory.register("validation", "percentile", PercentileValidationStrategy)
    except ImportError:
        pass
    try:
        from .validation.trend import TrendValidationStrategy
        StrategyFactory.register("validation", "trend", TrendValidationStrategy)
    except ImportError:
        pass
    try:
        from .validation.custom import CustomValidationStrategy
        StrategyFactory.register("validation", "custom", CustomValidationStrategy)
    except ImportError:
        pass

    # 重试策略
    try:
        from .retry.fixed import FixedRetryStrategy
        StrategyFactory.register("retry", "fixed", FixedRetryStrategy)
    except ImportError:
        pass
    try:
        from .retry.exponential import ExponentialRetryStrategy
        StrategyFactory.register("retry", "exponential", ExponentialRetryStrategy)
    except ImportError:
        pass
    try:
        from .retry.custom import CustomRetryStrategy
        StrategyFactory.register("retry", "custom", CustomRetryStrategy)
    except ImportError:
        pass


_auto_register()
