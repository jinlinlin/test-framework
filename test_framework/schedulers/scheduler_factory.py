"""
调度器工厂 — 根据配置自动创建合适的调度器实例。

职责：工厂模式创建 SequentialScheduler / ParallelScheduler /
      DistributedScheduler / CronScheduler。
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Coroutine, Dict, Optional

from .base import BaseScheduler
from .cron import CronScheduler
from .distributed import DistributedScheduler
from .parallel import ParallelScheduler
from .sequential import SequentialScheduler

logger = logging.getLogger(__name__)


class SchedulerFactory:
    """
    调度器工厂。

    根据调度类型字符串创建对应的调度器实例。

    使用示例::

        factory = SchedulerFactory()
        scheduler = factory.create("parallel", max_concurrency=5)
    """

    # 注册表：调度类型 -> 调度器类
    _registry: Dict[str, type] = {
        "sequential": SequentialScheduler,
        "parallel": ParallelScheduler,
        "distributed": DistributedScheduler,
        "cron": CronScheduler,
    }

    @classmethod
    def register(cls, scheduler_type: str, scheduler_class: type) -> None:
        """
        注册自定义调度器类型。

        Args:
            scheduler_type: 调度类型名称。
            scheduler_class: 调度器类（必须是 BaseScheduler 子类）。
        """
        cls._registry[scheduler_type] = scheduler_class
        logger.info(f"已注册调度器类型: {scheduler_type}")

    @classmethod
    def create(
        cls,
        scheduler_type: str = "sequential",
        executor: Optional[Callable[..., Coroutine]] = None,
        **kwargs: Any,
    ) -> BaseScheduler:
        """
        创建调度器实例。

        Args:
            scheduler_type: 调度类型（sequential / parallel / distributed / cron）。
            executor: 可选的执行回调函数。
            **kwargs: 传递给调度器构造函数的额外参数。

        Returns:
            调度器实例。

        Raises:
            ValueError: 不支持的调度类型。
        """
        scheduler_class = cls._registry.get(scheduler_type)
        if not scheduler_class:
            available = ", ".join(cls._registry.keys())
            raise ValueError(
                f"不支持的调度类型: {scheduler_type}，可用类型: {available}"
            )

        # 构造参数
        init_kwargs: Dict[str, Any] = {}
        if executor is not None:
            init_kwargs["executor"] = executor
        init_kwargs.update(kwargs)

        try:
            instance = scheduler_class(**init_kwargs)
            logger.info(f"已创建调度器: {scheduler_type}")
            return instance
        except TypeError as e:
            # 某些调度器可能不支持 executor 参数，回退无参构造
            logger.debug(f"调度器构造回退: {e}")
            return scheduler_class()

    @classmethod
    def create_from_config(cls, config: Dict[str, Any]) -> BaseScheduler:
        """
        从配置字典创建调度器。

        配置格式::

            {
                "type": "parallel",
                "max_concurrency": 10,
                "executor": null
            }

        Args:
            config: 配置字典。

        Returns:
            调度器实例。
        """
        scheduler_type = config.pop("type", "sequential")
        return cls.create(scheduler_type, **config)

    @classmethod
    def list_types(cls) -> list:
        """列出所有已注册的调度器类型。"""
        return list(cls._registry.keys())
