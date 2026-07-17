"""
引擎工厂 — 根据 TestType 创建对应引擎实例（工厂模式）。

设计模式：工厂模式
职责：集中管理 TestType → 引擎类 的映射，
      支持动态注册和按类型创建引擎实例。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Type

from ..core.models.enums import TestType
from .base import BaseEngine

logger = logging.getLogger(__name__)


class EngineFactory:
    """
    引擎工厂（工厂模式）。

    维护 TestType → EngineClass 的注册表，
    按测试类型创建对应的引擎实例。

    Attributes:
        _registry: 测试类型 → 引擎类的映射表。
    """

    _registry: Dict[TestType, Type[BaseEngine]] = {}

    @classmethod
    def register(cls, test_type: TestType, engine_cls: Type[BaseEngine]) -> None:
        """
        注册引擎类。

        Args:
            test_type: 测试类型枚举。
            engine_cls: 引擎类（必须继承 BaseEngine）。
        """
        cls._registry[test_type] = engine_cls
        logger.debug(f"注册引擎: {test_type.value} → {engine_cls.__name__}")

    @classmethod
    def create(
        cls,
        test_type: TestType,
        config: Dict[str, Any],
        container: Any,
    ) -> BaseEngine:
        """
        根据测试类型创建引擎实例。

        Args:
            test_type: 测试类型枚举。
            config: 引擎配置字典。
            container: IoC 容器。

        Returns:
            创建的引擎实例。

        Raises:
            ValueError: 不支持的测试类型。
        """
        engine_cls = cls._registry.get(test_type)
        if engine_cls is None:
            raise ValueError(
                f"不支持的测试类型: {test_type.value}，"
                f"已注册: {[t.value for t in cls._registry]}"
            )
        return engine_cls(config=config, container=container)

    @classmethod
    def available_engines(cls) -> List[TestType]:
        """返回已注册的所有测试类型列表。"""
        return list(cls._registry.keys())


# ===== 自动注册内置引擎 =====
def _auto_register() -> None:
    """模块导入时自动注册内置引擎。"""
    try:
        from .web_performance.engine import WebPerformanceEngine
        EngineFactory.register(TestType.WEB_PERFORMANCE, WebPerformanceEngine)
    except ImportError:
        pass

    try:
        from .backend_performance.engine import BackendPerformanceEngine
        EngineFactory.register(TestType.BACKEND_PERFORMANCE, BackendPerformanceEngine)
    except ImportError:
        pass

    try:
        from .rest_api.engine import RestAPIEngine
        EngineFactory.register(TestType.REST_API, RestAPIEngine)
    except ImportError:
        pass

    try:
        from .database.engine import DatabaseEngine
        EngineFactory.register(TestType.DATABASE, DatabaseEngine)
    except ImportError:
        pass

    try:
        from .knowledge_qa.engine import KnowledgeQAEngine
        EngineFactory.register(TestType.KNOWLEDGE_QA, KnowledgeQAEngine)
    except ImportError:
        pass

    try:
        from .penetration.engine import PenetrationEngine
        EngineFactory.register(TestType.PENETRATION, PenetrationEngine)
    except ImportError:
        pass

    try:
        from .auth_bypass.engine import AuthBypassEngine
        EngineFactory.register(TestType.AUTH_BYPASS, AuthBypassEngine)
    except ImportError:
        pass

    try:
        from .ui_automation.engine import UIAutomationEngine
        EngineFactory.register(TestType.UI_AUTOMATION, UIAutomationEngine)
    except ImportError:
        pass


_auto_register()
