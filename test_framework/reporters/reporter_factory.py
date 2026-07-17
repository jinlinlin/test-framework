"""
报告器工厂 — 根据类型创建报告器实例（工厂模式）。

设计模式：工厂模式（Factory Pattern）
职责：维护 reporter_type → ReporterClass 的注册表，
      按需创建报告器实例，支持从配置列表批量创建。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Type

from .base import BaseReporter

logger = logging.getLogger(__name__)


class ReporterFactory:
    """
    报告器工厂。

    注册表结构::

        {
            "html": HTMLReporter,
            "json": JSONReporter,
            "console": ConsoleReporter,
            "allure": AllureReporter,
        }
    """

    _registry: Dict[str, Type[BaseReporter]] = {}

    @classmethod
    def register(cls, reporter_type: str, reporter_cls: Type[BaseReporter]) -> None:
        """
        注册报告器类。

        Args:
            reporter_type: 报告器类型名。
            reporter_cls: 报告器类。
        """
        cls._registry[reporter_type] = reporter_cls
        logger.debug(f"注册报告器: {reporter_type} → {reporter_cls.__name__}")

    @classmethod
    def create(cls, reporter_type: str, **kwargs: Any) -> BaseReporter:
        """
        创建报告器实例。

        Args:
            reporter_type: 报告器类型。
            **kwargs: 传递给报告器构造函数的参数。

        Returns:
            报告器实例。

        Raises:
            ValueError: 未注册的报告器类型。
        """
        reporter_cls = cls._registry.get(reporter_type)
        if not reporter_cls:
            raise ValueError(
                f"未注册的报告器类型: {reporter_type}，"
                f"可用: {list(cls._registry.keys())}"
            )
        return reporter_cls(**kwargs)

    @classmethod
    def create_from_config(cls, config: Dict[str, Any]) -> List[BaseReporter]:
        """
        根据配置批量创建报告器。

        配置格式::

            {
                "reporters": [
                    {"type": "html", "params": {"output_dir": "./reports"}},
                    {"type": "json", "params": {"output_dir": "./reports"}},
                    {"type": "console", "params": {}},
                ]
            }

        Args:
            config: 报告器配置。

        Returns:
            报告器实例列表。
        """
        reporters: List[BaseReporter] = []
        for reporter_config in config.get("reporters", []):
            r_type = reporter_config.get("type", "")
            r_params = reporter_config.get("params", {})
            try:
                reporter = cls.create(r_type, **r_params)
                reporters.append(reporter)
            except ValueError as e:
                logger.warning(f"创建报告器失败: {e}")
        return reporters

    @classmethod
    def available(cls) -> List[str]:
        """获取所有已注册的报告器类型。"""
        return list(cls._registry.keys())


# ===== 自动注册内置报告器 =====
def _auto_register() -> None:
    """导入时自动注册内置报告器。"""
    try:
        from .html.reporter import HTMLReporter
        ReporterFactory.register("html", HTMLReporter)
    except ImportError:
        pass
    try:
        from .json.reporter import JSONReporter
        ReporterFactory.register("json", JSONReporter)
    except ImportError:
        pass
    try:
        from .console.reporter import ConsoleReporter
        ReporterFactory.register("console", ConsoleReporter)
    except ImportError:
        pass
    try:
        from .allure.reporter import AllureReporter
        ReporterFactory.register("allure", AllureReporter)
    except ImportError:
        pass


_auto_register()
