"""
策略模式基类 — 所有策略的统一抽象接口。

设计模式：策略模式（Strategy Pattern）
职责：定义所有策略（负载 / 验证 / 重试）的统一抽象，
      具体策略通过工厂创建并注入引擎执行流程。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseStrategy(ABC):
    """
    策略抽象基类。

    所有策略（负载策略、验证策略、重试策略）必须继承此类，
    并实现 strategy_type 和 name 属性。

    策略生命周期::

        1. 工厂创建策略实例
        2. 引擎调用策略的方法（get_load_profile / validate / execute_with_retry）
        3. 策略返回结果
    """

    @property
    @abstractmethod
    def strategy_type(self) -> str:
        """
        策略类型。

        Returns:
            "load" / "validation" / "retry"
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """
        策略名称（唯一标识）。

        Returns:
            如 "constant" / "ramp_up" / "threshold" / "fixed" 等。
        """
        ...

    def get_config(self) -> Dict[str, Any]:
        """
        获取策略配置参数（用于序列化/日志）。

        Returns:
            策略参数字典。
        """
        return {}

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(type={self.strategy_type}, name={self.name})>"
