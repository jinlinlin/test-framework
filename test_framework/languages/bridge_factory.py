"""
桥接工厂模块 — 根据语言名称创建对应的桥接器实例（工厂模式）。

设计模式：工厂模式
职责：集中管理语言 → 桥接器的映射，
      支持动态注册新语言，按名称创建实例。
"""
from __future__ import annotations

import logging
from typing import Dict, List, Type

from .bridge import LanguageBridge

logger = logging.getLogger(__name__)


class BridgeFactory:
    """
    桥接器工厂（工厂模式）。

    维护 language_name → BridgeClass 的注册表，
    支持动态注册和按名称创建桥接器实例。

    Attributes:
        _registry: 语言名称 → 桥接器类的映射表。
    """

    _registry: Dict[str, Type[LanguageBridge]] = {}

    @classmethod
    def register(cls, language: str, bridge_cls: Type[LanguageBridge]) -> None:
        """
        注册语言桥接器。

        Args:
            language: 语言标识（如 'python'、'nodejs'、'shell'）。
            bridge_cls: 桥接器类（必须继承 LanguageBridge）。
        """
        cls._registry[language.lower()] = bridge_cls
        logger.debug(f"注册语言桥接器: {language!r} → {bridge_cls.__name__}")

    @classmethod
    def create(cls, language: str, **kwargs) -> LanguageBridge:
        """
        根据语言名称创建桥接器实例。

        Args:
            language: 语言标识。
            **kwargs: 传递给桥接器构造函数的参数。

        Returns:
            创建的桥接器实例。

        Raises:
            ValueError: 不支持的语言。
        """
        lang = language.lower()
        bridge_cls = cls._registry.get(lang)
        if bridge_cls is None:
            raise ValueError(
                f"不支持的语言: {language!r}，"
                f"已注册: {list(cls._registry.keys())}"
            )
        return bridge_cls(**kwargs)

    @classmethod
    def available_languages(cls) -> List[str]:
        """返回已注册的所有语言名称列表。"""
        return list(cls._registry.keys())

    @classmethod
    async def create_all_available(cls) -> Dict[str, LanguageBridge]:
        """
        创建所有已注册且运行环境可用的桥接器。

        Returns:
            语言名称 → 桥接器实例的字典（仅包含环境可用的语言）。
        """
        available = {}
        for lang, bridge_cls in cls._registry.items():
            try:
                bridge = bridge_cls()
                if await bridge.is_available():
                    available[lang] = bridge
                    logger.debug(f"语言 {lang!r} 环境可用，已创建桥接器")
                else:
                    logger.warning(f"语言 {lang!r} 环境不可用，跳过")
            except Exception as e:
                logger.warning(f"语言 {lang!r} 初始化失败: {e}")
        return available


# ===== 模块导入时自动注册内置语言 =====
def _auto_register() -> None:
    """自动注册框架内置的三种语言桥接器。"""
    try:
        from .python.executor import PythonExecutor
        BridgeFactory.register("python", PythonExecutor)
    except ImportError:
        logger.debug("Python 桥接器未就绪")

    try:
        from .nodejs.executor import NodeExecutor
        BridgeFactory.register("nodejs", NodeExecutor)
    except ImportError:
        logger.debug("Node.js 桥接器未就绪")

    try:
        from .shell.executor import ShellExecutor
        BridgeFactory.register("shell", ShellExecutor)
    except ImportError:
        logger.debug("Shell 桥接器未就绪")


# 首次导入时自动注册
_auto_register()
